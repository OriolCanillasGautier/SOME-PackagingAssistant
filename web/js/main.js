/**
 * PackAssist Web - Main Application
 * Connects UI with packing calculator, 3D visualization, and physics simulation
 */

import * as THREE from 'three';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import { calcularEmpaquetatge, createSummary, getDistribution, getPieceDimensions } from './packing/calculator.js?v=force_update_42';
import { loadMesh, loadSTL, extractDimensions, computeMeshVolume, computeSurfaceArea, analyzeMeshIntegrity, centerToOrigin, isSupported, SUPPORTED_EXTENSIONS, guessPermForDims, applyPermutation, getSupportStability, alignToStableBase } from './mesh/mesh-utils.js?v=force_update_42';
import { SceneManager } from './visualization/scene.js?v=force_update_42';
import { BulkSimulation, PhysicsWorld, initRapier } from './physics/physics-world.js?v=force_update_42';
import { ReportGenerator } from './report/report-generator.js?v=force_update_42';
import { getSimplificationModal } from './mesh/simplification-modal.js?v=force_update_42';
import { StorageManager } from './storage/storage-manager.js?v=force_update_42';
import { loadLocale, t as localeText, getStoredLanguage, setStoredLanguage } from './i18n.js?v=force_update_42';

// Helper for dynamic limits
function updateMaxPiecesLimit() {
    const maxWeight = parseFloat(elements.maxWeight.value) || 0;
    const objWeight = parseFloat(elements.objWeight.value) || 0;
    
    if (maxWeight > 0 && objWeight > 0) {
        const theoreticalMax = Math.floor(maxWeight / objWeight);
        // Set a reasonable absolute max (5000) but allow what's calculated
        const newMax = Math.min(5000, Math.max(1, theoreticalMax));
        elements.maxPieces.max = newMax;
        
        // If current value too high, adjust
        if (parseInt(elements.maxPieces.value) > newMax) {
            elements.maxPieces.value = newMax;
            elements.maxPiecesValue.textContent = newMax;
        }
    }
}


// Application state
const state = {
    mode: 'optimized', // 'optimized' or 'bulk'
    language: getStoredLanguage(), // 'ca' or 'en'
    locale: null,
    stlGeometry: null,
    stlAlignedGeometry: null, // transient in-memory geometry aligned to stable gravity orientation
    stlSettledQuat: null, // cached quaternion from gravity drop on current loaded geometry
    stlStableOrientations: [], // [{ quat, geometry, stability }] precomputed gravity bases
    orientationPrepMs: 0,
    stlIntegrity: null,
    stlDimensions: null,
    stlFileName: null,
    stlFileData: null, // Store the raw file data for saving
    stlFileId: null,   // IndexedDB id for the currently active STL entry
    sceneManager: null,
    bulkSimulation: null,
    isSimulating: false,
    gravitySimulation: null,
    physicsWorld: null,
    orientationEval: null,
    reportGenerator: null,
    lastResults: null, // Store last results for report generation
    displayCount: 0, // Single source of truth for piece count (UI/render/gravity/PDF)
    storage: null, // StorageManager instance
    calcAbortController: null
};

const stlExporter = new STLExporter();

function mainText(path, variables = {}, fallback = path) {
    return state.locale ? localeText(state.locale, `main.${path}`, variables, fallback) : fallback;
}

function commonText(path, variables = {}, fallback = path) {
    return state.locale ? localeText(state.locale, `common.${path}`, variables, fallback) : fallback;
}

function mainRaw(path, fallback = null) {
    return state.locale ? localeText(state.locale, `main.${path}`, {}, fallback ?? path) : (fallback ?? path);
}

function getCalculatorLabels() {
    return mainRaw('results', {});
}

function buildSimplifiedFileName(originalName, percentKeep) {
    if (!originalName) return originalName;
    const dot = originalName.lastIndexOf('.');
    const base = dot >= 0 ? originalName.slice(0, dot) : originalName;
    const ext = dot >= 0 ? originalName.slice(dot) : '.stl';
    const pct = Number(percentKeep);
    const pctLabel = Number.isFinite(pct) ? (pct < 1 ? pct.toFixed(1) : String(Math.round(pct))) : 'simp';
    const cleanedBase = base.replace(/_simp\d+(?:\.\d+)?pct$/i, '');
    return `${cleanedBase}_simp${pctLabel}pct${ext}`;
}

function ensureSTLFileName(fileName) {
    if (!fileName) return 'packassist_mesh.stl';
    const dot = fileName.lastIndexOf('.');
    const base = dot >= 0 ? fileName.slice(0, dot) : fileName;
    return `${base}.stl`;
}

function downloadArrayBuffer(buffer, fileName, mimeType = 'model/stl') {
    const blob = new Blob([buffer], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportGeometryToBinarySTL(geometry) {
    const mesh = new THREE.Mesh(geometry.clone(), new THREE.MeshBasicMaterial());
    const exported = stlExporter.parse(mesh, { binary: true });
    if (exported instanceof ArrayBuffer) return exported;
    if (exported?.buffer instanceof ArrayBuffer) return exported.buffer;
    throw new Error('Binary STL export failed');
}

function downloadCurrentSTL(fileNameOverride = null, geometryOverride = null) {
    const geometry = geometryOverride || state.stlGeometry;
    if (!geometry) return;

    const sourceName = fileNameOverride || state.stlFileName || 'packassist_mesh.stl';
    const fileName = ensureSTLFileName(sourceName);
    const canUseCachedData = !geometryOverride && state.stlFileData instanceof ArrayBuffer && /\.stl$/i.test(sourceName);
    const data = canUseCachedData ? state.stlFileData : exportGeometryToBinarySTL(geometry);
    downloadArrayBuffer(data, fileName, 'model/stl');
}

function bindSTLStatusActions(geometryForSimplify = null) {
    document.getElementById('download-stl-btn')?.addEventListener('click', () => {
        try {
            downloadCurrentSTL();
        } catch (error) {
            console.error('Error downloading STL:', error);
            elements.stlStatus.className = 'stl-status error';
            elements.stlStatus.textContent = mainText('downloadStlError', {}, 'Could not download STL');
        }
    });

    document.getElementById('simplify-mesh-btn')?.addEventListener('click', () => {
        const sourceGeometry = geometryForSimplify || state.stlGeometry;
        if (!sourceGeometry) return;

        const modal = getSimplificationModal();
        modal.open(sourceGeometry, async (simplifiedGeometry, simplifiedSTLData, meta = {}) => {
            let geometry = simplifiedGeometry;
            centerToOrigin(geometry);

            state.stlGeometry = geometry;
            elements.stlStatus.className = 'stl-status';
            elements.stlStatus.textContent = 'Preparant orientació estable...';
            elements.stlStatus.style.display = 'block';
            await updateStableOrientationCache();
            updateMeshIntegrityCache(state.stlGeometry);

            if (simplifiedSTLData instanceof ArrayBuffer) {
                state.stlFileData = simplifiedSTLData;
                state.stlFileName = buildSimplifiedFileName(state.stlFileName, meta.percentKeep);
                await saveSTLToHistory();
            }

            elements.objLength.value = state.stlDimensions.length.toFixed(2);
            elements.objWidth.value = state.stlDimensions.width.toFixed(2);
            elements.objHeight.value = state.stlDimensions.height.toFixed(2);

            const newPositions = geometry.getAttribute('position');
            elements.stlStatus.className = 'stl-status success';
            elements.stlStatus.innerHTML = `${mainText('statusSimplified', {
                vertices: newPositions.count.toLocaleString(),
                length: state.stlDimensions.length.toFixed(2),
                width: state.stlDimensions.width.toFixed(2),
                height: state.stlDimensions.height.toFixed(2)
            }, 'Simplified')} <button id="download-stl-btn" class="btn-small" style="margin-left:8px;">${mainText('downloadStl', {}, 'Download STL')}</button><br>${buildOrientationAndIntegrityLine()}`;
            bindSTLStatusActions();
        }, state.stlFileData, state.stlFileName || 'packassist_mesh.stl');
    });
}

// UI translations
const uiTranslations = {
    ca: {
        headerTitle: 'Calculadora de Capacitat de Peces',
        headerSubtitle: 'Càlcul optimitzat + Mode a Granel amb Física Real',
        historyLink: 'Historial de Càlculs',
        modeOptimized: 'Mode Optimitzat',
        modeOptimizedDesc: 'Càlcul matemàtic precís',
        modeBulk: 'Mode a Granel',
        modeBulkDesc: 'Simulació amb gravetat',
        objectTitle: "Dimensions de l'Objecte",
        objLength: 'Llargada (mm)',
        objWidth: 'Amplada (mm)',
        objHeight: 'Alçada (mm)',
        objWeight: 'Pes (kg)',
        allowRotation: "Permet girar l'objecte (6 orientacions)",
        heightmapNesting: "Mapa d'altures (experimental)",
        colorCount: 'Nombre de colors:',
        boxTitle: 'Dimensions de la Caixa',
        boxLength: 'Llargada (mm)',
        boxWidth: 'Amplada (mm)',
        boxHeight: 'Alçada (mm)',
        maxWeight: 'Pes màxim (kg)',
        packingGap: 'Espaiat entre peces:',
        bulkTitle: 'Opcions Mode a Granel',
        dropHeight: 'Alçada de caiguda:',
        autoCapacity: 'Mode automàtic (detecta capacitat i pes)',
        maxPieces: 'Peces màximes:',
        dropInterval: 'Interval (ms):',
        vibFreq: 'Freq. vibració:',
        vibAmp: 'Amplitud vibració:',
        vibNoise: 'Soroll vibració:',
        randomRotation: 'Rotació aleatòria en caiguda',
        calculateBtn: 'CALCULAR CAPACITAT',
        gravityBtn: 'APLICAR GRAVETAT',
        simulateBtn: 'INICIAR SIMULACIÓ',
        stopBtn: 'ATURAR',
        resetBtn: 'REINICIAR',
        previewReport: 'Previsualitzar Informe',
        placeholder: 'Introdueix les dades i fes clic a Calcular',
        reportTitle: "Configuració de l'Informe",
        reportLang: 'Idioma',
        reportColors: 'Nombre de colors',
        reportColorsHint: 'Les peces tindran fins a aquest nombre de colors diferents',
        reportCancel: 'Cancel·lar',
        reportDownload: 'Descarregar PDF',
        cancelBtn: 'Cancel·lar',
    },
    en: {
        headerTitle: 'Piece Capacity Calculator',
        headerSubtitle: 'Optimized calculation + Bulk Mode with Real Physics',
        historyLink: 'Calculation History',
        modeOptimized: 'Optimized Mode',
        modeOptimizedDesc: 'Precise math calculation',
        modeBulk: 'Bulk Mode',
        modeBulkDesc: 'Gravity simulation',
        objectTitle: 'Object Dimensions',
        objLength: 'Length (mm)',
        objWidth: 'Width (mm)',
        objHeight: 'Height (mm)',
        objWeight: 'Weight (kg)',
        allowRotation: 'Allow rotation (6 orientations)',
        heightmapNesting: 'Heightmap nesting (experimental)',
        colorCount: 'Number of colors:',
        boxTitle: 'Box Dimensions',
        boxLength: 'Length (mm)',
        boxWidth: 'Width (mm)',
        boxHeight: 'Height (mm)',
        maxWeight: 'Max weight (kg)',
        packingGap: 'Pack spacing:',
        bulkTitle: 'Bulk Mode Options',
        dropHeight: 'Drop height:',
        autoCapacity: 'Auto mode (detects capacity & weight)',
        maxPieces: 'Max pieces:',
        dropInterval: 'Interval (ms):',
        vibFreq: 'Vibration freq:',
        vibAmp: 'Vibration amplitude:',
        vibNoise: 'Vibration noise:',
        randomRotation: 'Random rotation on drop',
        calculateBtn: 'CALCULATE CAPACITY',
        gravityBtn: 'APPLY GRAVITY',
        simulateBtn: 'START SIMULATION',
        stopBtn: 'STOP',
        resetBtn: 'RESET',
        previewReport: 'Preview Report',
        placeholder: 'Enter data and click Calculate',
        reportTitle: 'Report Settings',
        reportLang: 'Language',
        reportColors: 'Number of colors',
        reportColorsHint: 'Pieces will have up to this many different colors',
        reportCancel: 'Cancel',
        reportDownload: 'Download PDF',
        cancelBtn: 'Cancel',
    }
};

/**
 * Apply a yaw rotation (around Y) to a geometry that is already stable-base-aligned.
 * Recenters XZ and resets min-Y to 0 afterwards.
 */
function applyYawToGeometry(geometry, angleDeg) {
    if (angleDeg === 0) return;
    const rad = (angleDeg * Math.PI) / 180;
    const mat = new THREE.Matrix4().makeRotationY(rad);
    geometry.applyMatrix4(mat);

    // Recenter
    recenterGeometry(geometry);
}

/**
 * Recenter a geometry so min-Y = 0 and XZ is centered at origin.
 */
function recenterGeometry(geometry) {
    geometry.computeBoundingBox();
    const bb = geometry.boundingBox;
    const cx = (bb.min.x + bb.max.x) / 2;
    const cz = (bb.min.z + bb.max.z) / 2;
    const dy = -bb.min.y;
    geometry.translate(-cx, dy, -cz);
    geometry.computeBoundingBox();
}

function buildOrientationAndIntegrityLine() {
    const baseCount = state.stlStableOrientations?.length || 1;
    const integrityText = state.stlIntegrity
        ? (state.stlIntegrity.skipped
            ? ` | ${mainText('meshLabel', {}, 'Mesh')}: ${mainText('integrityUnavailable', {}, 'check unavailable')}`
            : ` | ${mainText('meshLabel', {}, 'Mesh')}: ${state.stlIntegrity.watertight ? mainText('integrityClosed', {}, 'closed') : mainText('integrityLeaking', {}, 'leaking')}`)
        : '';
    return `${mainText('orientationLabel', {}, 'Orientation')}: ${state.orientationPrepMs.toFixed(0)} ms (${baseCount} ${mainText('basesLabel', {}, 'bases')})${integrityText}`;
}

function updateMeshIntegrityCache(geometry) {
    if (!geometry) {
        state.stlIntegrity = null;
        return;
    }

    try {
        const pos = geometry.getAttribute('position');
        const triCount = pos ? Math.floor(pos.count / 3) : 0;
        const MAX_INTEGRITY_TRIANGLES = 250000;

        if (triCount > MAX_INTEGRITY_TRIANGLES) {
            state.stlIntegrity = {
                skipped: true,
                watertight: false,
                triangleCount: triCount,
                boundaryEdgeCount: 0,
                nonManifoldEdgeCount: 0
            };
            return;
        }

        state.stlIntegrity = analyzeMeshIntegrity(geometry);
    } catch (error) {
        console.warn('[Integrity] Failed:', error?.message || error);
        state.stlIntegrity = null;
    }
}

/**
 * Drop a single piece with Rapier gravity to find its naturally stable resting orientation.
 * Returns a THREE.Quaternion representing how the piece settles on a flat floor.
 * This replaces geometric stable-base detection with actual physics simulation,
 * so pieces exported at arbitrary angles still land correctly.
 * @param {THREE.BufferGeometry} geometry - the STL geometry (will NOT be modified)
 * @returns {Promise<THREE.Quaternion>} The settled rotation quaternion
 */
async function findStableOrientationByGravity(geometry, initialQuat = null) {
    await initRapier();
    const RAPIER = await import('@dimforge/rapier3d-compat');
    if (RAPIER.init) await RAPIER.init();

    const geo = geometry.clone();
    geo.computeBoundingBox();
    const size = new THREE.Vector3();
    geo.boundingBox.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);

    // Physics world with floor
    const world = new RAPIER.World({ x: 0.0, y: -9810.0, z: 0.0 });
    world.numSolverIterations = 16;

    const floorBody = world.createRigidBody(
        RAPIER.RigidBodyDesc.fixed().setTranslation(0, -50, 0)
    );
    world.createCollider(
        RAPIER.ColliderDesc.cuboid(maxDim * 5, 50, maxDim * 5)
            .setFriction(0.8).setRestitution(0.0),
        floorBody
    );

    // Center geometry at origin for physics
    const centered = geo.clone();
    centered.computeBoundingBox();
    const center = new THREE.Vector3();
    centered.boundingBox.getCenter(center);
    centered.translate(-center.x, -center.y, -center.z);

    const positions = centered.getAttribute('position');
    const vertices = new Float32Array(positions.array);

    // Drop piece from above
    const dropHeight = maxDim * 2;
    const bodyDesc = RAPIER.RigidBodyDesc.dynamic()
        .setTranslation(0, dropHeight, 0)
        .setLinearDamping(0.5)
        .setAngularDamping(0.8);
    const body = world.createRigidBody(bodyDesc);
    if (initialQuat && typeof body.setRotation === 'function') {
        body.setRotation({ x: initialQuat.x, y: initialQuat.y, z: initialQuat.z, w: initialQuat.w }, true);
    }

    let colliderDesc = null;
    try { colliderDesc = RAPIER.ColliderDesc.convexHull(vertices); } catch (e) { /* fallback */ }
    if (!colliderDesc) {
        colliderDesc = RAPIER.ColliderDesc.cuboid(size.x / 2, size.y / 2, size.z / 2);
    }
    colliderDesc.setDensity(2.0).setFriction(0.8).setRestitution(0.05);
    world.createCollider(colliderDesc, body);

    // Run until settled or 5s timeout
    const dt = 1 / 240;
    const maxSteps = 240 * 5;
    let settledFrames = 0;
    for (let step = 0; step < maxSteps; step++) {
        world.timestep = dt;
        world.step();
        const lv = body.linvel(), av = body.angvel();
        const speed = Math.sqrt(lv.x ** 2 + lv.y ** 2 + lv.z ** 2);
        const angSpeed = Math.sqrt(av.x ** 2 + av.y ** 2 + av.z ** 2);
        if (speed < 3.0 && angSpeed < 0.3) {
            if (++settledFrames >= 60) break;    // ~0.25s of stability
        } else {
            settledFrames = 0;
        }
    }

    const rot = body.rotation();
    const settledQuat = new THREE.Quaternion(rot.x, rot.y, rot.z, rot.w);
    world.free();

    console.log(`[Gravity] Settled quat=(${rot.x.toFixed(3)}, ${rot.y.toFixed(3)}, ${rot.z.toFixed(3)}, ${rot.w.toFixed(3)})`);
    return settledQuat;
}

function getDeterministicOrientationSeeds() {
    const eulers = [
        [0, 0, 0],
        [Math.PI / 2, 0, 0],
        [-Math.PI / 2, 0, 0],
        [0, Math.PI / 2, 0],
        [0, -Math.PI / 2, 0],
        [0, 0, Math.PI / 2],
        [0, 0, -Math.PI / 2],
        [Math.PI, 0, 0]
    ];

    return eulers.map(([x, y, z]) => new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z, 'XYZ')));
}

function quatAngularDistanceDeg(a, b) {
    const dot = Math.min(1, Math.abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w));
    return (2 * Math.acos(dot) * 180) / Math.PI;
}

async function findStableOrientationCandidatesByGravity(geometry, sampleCount = 4) {
    const uniqueQuats = [];
    const seeds = [null, ...getDeterministicOrientationSeeds().slice(0, Math.max(0, sampleCount - 1))];

    for (const seed of seeds) {
        let quat = null;
        try {
            quat = await findStableOrientationByGravity(geometry, seed);
        } catch (error) {
            console.warn('[Gravity] Candidate drop failed:', error?.message || error);
            continue;
        }
        if (!quat) continue;
        const isDuplicate = uniqueQuats.some(q => quatAngularDistanceDeg(q, quat) < 10);
        if (!isDuplicate) uniqueQuats.push(quat);
    }

    return uniqueQuats;
}

/**
 * Apply a quaternion to geometry, then recenter (min-Y = 0, XZ centered).
 */
function applyQuatToGeometry(geometry, quat) {
    geometry.applyMatrix4(new THREE.Matrix4().makeRotationFromQuaternion(quat));
    recenterGeometry(geometry);
}

/**
 * Precompute stable gravity orientation once for the currently loaded STL geometry.
 * Does NOT modify state.stlFileData, so saved STL bytes remain unchanged.
 */
async function updateStableOrientationCache() {
    if (!state.stlGeometry) {
        state.stlAlignedGeometry = null;
        state.stlSettledQuat = null;
        state.stlStableOrientations = [];
        state.orientationPrepMs = 0;
        return null;
    }

    const t0 = performance.now();
    const pos = state.stlGeometry.getAttribute('position');
    const vertexCount = pos ? pos.count : 0;
    const sampleCount = vertexCount > 60000 ? 4 : (vertexCount > 20000 ? 6 : 8);
    let quats = [];
    try {
        quats = await findStableOrientationCandidatesByGravity(state.stlGeometry, sampleCount);
    } catch (error) {
        console.warn('[Orientation] Gravity precompute failed:', error?.message || error);
        quats = [];
    }

    if (!quats.length) {
        const fallbackGeometry = state.stlGeometry.clone();
        try {
            alignToStableBase(fallbackGeometry);
            recenterGeometry(fallbackGeometry);
        } catch (_) {
            recenterGeometry(fallbackGeometry);
        }

        state.stlStableOrientations = [{ quat: null, geometry: fallbackGeometry, stability: getSupportStability(fallbackGeometry) }];
        state.stlSettledQuat = null;
        state.stlAlignedGeometry = fallbackGeometry;
        state.stlDimensions = extractDimensions(fallbackGeometry);
        state.orientationPrepMs = performance.now() - t0;
        return fallbackGeometry;
    }

    const stableBases = [];

    for (const quat of quats) {
        const alignedGeometry = state.stlGeometry.clone();
        applyQuatToGeometry(alignedGeometry, quat);
        const stability = getSupportStability(alignedGeometry);
        stableBases.push({ quat, geometry: alignedGeometry, stability });
    }

    try {
        const fallbackGeometry = state.stlGeometry.clone();
        alignToStableBase(fallbackGeometry);
        recenterGeometry(fallbackGeometry);
        const fallbackStability = getSupportStability(fallbackGeometry);
        const fallbackDims = extractDimensions(fallbackGeometry);
        const alreadyPresent = stableBases.some(base => {
            const dims = extractDimensions(base.geometry);
            return Math.abs(dims.length - fallbackDims.length) < 0.5 &&
                Math.abs(dims.width - fallbackDims.width) < 0.5 &&
                Math.abs(dims.height - fallbackDims.height) < 0.5;
        });
        if (!alreadyPresent) {
            stableBases.push({ quat: null, geometry: fallbackGeometry, stability: fallbackStability });
        }
    } catch (error) {
        console.warn('[Orientation] Stable-base fallback candidate failed:', error?.message || error);
    }

    stableBases.sort((a, b) => {
        const aStable = a.stability?.stable ? 1 : 0;
        const bStable = b.stability?.stable ? 1 : 0;
        if (bStable !== aStable) return bStable - aStable;
        const aArea = a.stability?.supportArea || 0;
        const bArea = b.stability?.supportArea || 0;
        if (Math.abs(bArea - aArea) > 1e-6) return bArea - aArea;
        const ad = extractDimensions(a.geometry);
        const bd = extractDimensions(b.geometry);
        return ad.height - bd.height;
    });

    const primary = stableBases[0];
    state.stlStableOrientations = stableBases;
    state.stlSettledQuat = primary?.quat || null;
    state.stlAlignedGeometry = primary?.geometry || null;
    state.stlDimensions = primary ? extractDimensions(primary.geometry) : extractDimensions(state.stlGeometry);
    state.orientationPrepMs = performance.now() - t0;

    return primary?.geometry || null;
}

/**
 * Build an oriented geometry: gravity base quaternion + yaw rotation.
 * @param {THREE.BufferGeometry} originalGeometry
 * @param {{ quat: THREE.Quaternion }} tilt
 * @param {number} yawDeg
 * @returns {THREE.BufferGeometry}
 */
function buildOrientedGeometry(originalGeometry, tilt, yawDeg) {
    const geo = originalGeometry.clone();
    if (tilt?.quat) {
        applyQuatToGeometry(geo, tilt.quat);
    }
    applyYawToGeometry(geo, yawDeg);
    return geo;
}

/**
 * Build a pool of orientations to try during packing.
 * Uses the best base geometry + 4 cardinal yaw rotations.
 * @param {THREE.BufferGeometry} baseGeometry - already in best stable base
 * @param {number} boxL @param {number} boxW @param {number} boxH
 * @returns {Array<{geometry: THREE.BufferGeometry, yaw: number, name: string}>}
 */
function buildOrientationPool(baseGeometry, boxL, boxW, boxH) {
    const pool = [];
    // Try all 4 cardinal yaw rotations to maximize interlocking potential
    const yaws = [0, 90, 180, 270];

    for (const yaw of yaws) {
        const geom = baseGeometry.clone();
        applyYawToGeometry(geom, yaw);
        recenterGeometry(geom);

        geom.computeBoundingBox();
        const bb = geom.boundingBox;
        const sx = bb.max.x - bb.min.x;
        const sy = bb.max.y - bb.min.y;
        const sz = bb.max.z - bb.min.z;

        if (sx > boxL + 0.01 || sz > boxW + 0.01 || sy > boxH + 0.01) {
            console.log(`[OrientPool] Skip ${yaw}° — doesn't fit (${sx.toFixed(1)}×${sy.toFixed(1)}×${sz.toFixed(1)})`);
            continue;
        }

        pool.push({ geometry: geom, yaw, name: `${yaw}°` });
    }

    console.log(`[OrientPool] Built ${pool.length} orientations: ${pool.map(o => o.name).join(', ')}`);
    return pool;
}

function buildOrientationPoolFromCandidates(candidatePool, boxL, boxW, boxH) {
    const pool = [];
    const seen = new Set();

    for (const candidate of candidatePool) {
        if (!candidate?.oriented) continue;
        const geom = candidate.oriented.clone();
        recenterGeometry(geom);
        geom.computeBoundingBox();
        const bb = geom.boundingBox;
        const sx = bb.max.x - bb.min.x;
        const sy = bb.max.y - bb.min.y;
        const sz = bb.max.z - bb.min.z;
        if (sx > boxL + 0.01 || sz > boxW + 0.01 || sy > boxH + 0.01) continue;

        const key = [candidate.name || '', candidate.tiltName || '', candidate.yawDeg || 0, sx.toFixed(2), sy.toFixed(2), sz.toFixed(2)].join('_');
        if (seen.has(key)) continue;
        seen.add(key);
        pool.push({ geometry: geom, yaw: candidate.yawDeg || 0, name: candidate.name || `${candidate.yawDeg || 0}°` });
    }

    console.log(`[OrientPool] Built ${pool.length} candidate orientations: ${pool.map(o => o.name).join(', ')}`);
    return pool;
}

function compactGridSpacingCollides(geometry, dx, dz) {
    if (!geometry) return false;
    if (!geometry.boundsTree && typeof geometry.computeBoundsTree === 'function') {
        geometry.computeBoundsTree();
    }
    if (!geometry.boundsTree) return false;
    const matrix = new THREE.Matrix4().makeTranslation(dx, 0, dz);
    return geometry.boundsTree.intersectsGeometry(geometry, matrix);
}

function computeWallAlignedGridCapacity(geometry, boxL, boxW, packingGap = 0) {
    geometry.computeBoundingBox();
    const bb = geometry.boundingBox;
    const sizeX = bb.max.x - bb.min.x;
    const sizeZ = bb.max.z - bb.min.z;
    const factors = [1.0, 0.98, 0.96, 0.94, 0.92, 0.9, 0.88];
    let best = null;

    for (const fx of factors) {
        for (const fz of factors) {
            const stepX = Math.max(sizeX + packingGap * 0.35, (sizeX + packingGap) * fx);
            const stepZ = Math.max(sizeZ + packingGap * 0.35, (sizeZ + packingGap) * fz);

            if (compactGridSpacingCollides(geometry, stepX, 0)) continue;
            if (compactGridSpacingCollides(geometry, 0, stepZ)) continue;
            if (compactGridSpacingCollides(geometry, stepX, stepZ)) continue;

            const gridNX = Math.max(1, Math.floor((boxL - sizeX + 0.01) / stepX) + 1);
            const gridNZ = Math.max(1, Math.floor((boxW - sizeZ + 0.01) / stepZ) + 1);
            const count = gridNX * gridNZ;
            const usedL = sizeX + Math.max(0, gridNX - 1) * stepX;
            const usedW = sizeZ + Math.max(0, gridNZ - 1) * stepZ;
            const leftoverL = Math.max(0, boxL - usedL);
            const leftoverW = Math.max(0, boxW - usedW);
            const leftoverArea = leftoverL * boxW + leftoverW * boxL - leftoverL * leftoverW;

            if (!best || count > best.count || (count === best.count && leftoverArea < best.leftoverArea)) {
                best = {
                    sizeX,
                    sizeZ,
                    stepX,
                    stepZ,
                    gridNX,
                    gridNZ,
                    count,
                    leftoverL,
                    leftoverW,
                    leftoverArea
                };
            }
        }
    }

    if (best) return best;

    const stepX = sizeX + packingGap;
    const stepZ = sizeZ + packingGap;
    const gridNX = Math.max(1, Math.floor((boxL - sizeX + 0.01) / stepX) + 1);
    const gridNZ = Math.max(1, Math.floor((boxW - sizeZ + 0.01) / stepZ) + 1);
    const count = gridNX * gridNZ;
    const usedL = sizeX + Math.max(0, gridNX - 1) * stepX;
    const usedW = sizeZ + Math.max(0, gridNZ - 1) * stepZ;
    const leftoverL = Math.max(0, boxL - usedL);
    const leftoverW = Math.max(0, boxW - usedW);

    return {
        sizeX,
        sizeZ,
        stepX,
        stepZ,
        gridNX,
        gridNZ,
        count,
        leftoverL,
        leftoverW,
        leftoverArea: leftoverL * boxW + leftoverW * boxL - leftoverL * leftoverW
    };
}

/**
 * Generate yaw candidates from gravity-settled base.
 * Piece is locked to its resting orientation; only Y-axis rotation changes.
 * @param {THREE.BufferGeometry} alignedGeometry - already aligned to stable gravity pose
 * @param {number} boxL  @param {number} boxW  @param {number} boxH
 * @param {boolean} allowRotation
 * @returns {Array}
 */
function generateYawCandidates(originalGeometry, stableBases, boxL, boxW, boxH, allowRotation, placementStrategy = 'stable-contact') {
    const candidates = [];
    const seen = new Set();
    const stableOnlyBases = stableBases.filter(base => base.stability?.stable);
    const sourceBases = stableOnlyBases.length > 0 ? stableOnlyBases : stableBases;
    const isSquareBox = Math.abs(boxL - boxW) < 1;
    const yaws = allowRotation
        ? (isSquareBox ? [0, 90] : [0, 90, 180, 270])
        : [0];

    const pushCandidate = (candidate) => {
        candidate.oriented.computeBoundingBox();
        const bb = candidate.oriented.boundingBox;
        const sX = bb.max.x - bb.min.x;
        const sY = bb.max.y - bb.min.y;
        const sZ = bb.max.z - bb.min.z;
        if (sX > boxL + 0.01 || sZ > boxW + 0.01 || sY > boxH + 0.01) return;

        const key = [sX, sY, sZ, candidate.yawDeg]
            .map(v => Number(v).toFixed(2))
            .join('_');
        if (seen.has(key)) return;
        seen.add(key);
        candidates.push(candidate);
    };

    for (let baseIndex = 0; baseIndex < sourceBases.length; baseIndex++) {
        const base = sourceBases[baseIndex];
        for (const yawDeg of yaws) {
            const oriented = base.geometry.clone();
            applyYawToGeometry(oriented, yawDeg);

            pushCandidate({
                tilt: { quat: base.quat, baseIndex },
                tiltName: `Base ${baseIndex + 1}`,
                yawDeg,
                name: `B${baseIndex + 1} · Y ${yawDeg}°`,
                oriented,
            });
        }
    }

    const includeAxisPermutations = placementStrategy !== 'stable-contact';

    if (allowRotation && originalGeometry && includeAxisPermutations) {
        const permutations = [
            [0, 1, 2], [0, 2, 1], [1, 0, 2],
            [1, 2, 0], [2, 0, 1], [2, 1, 0]
        ];
        permutations.forEach((perm, permIndex) => {
            const oriented = originalGeometry.clone();
            applyPermutation(oriented, perm);
            recenterGeometry(oriented);
            pushCandidate({
                tilt: { quat: null, baseIndex: permIndex },
                tiltName: `Axis ${permIndex + 1}`,
                yawDeg: 0,
                name: `A${permIndex + 1} · P${perm.join('')}`,
                oriented,
            });
        });
    }

    console.log(`[Orientation] Multi-base yaw search: ${candidates.length} candidates (${sourceBases.length} stable bases × ${yaws.length} yaw)`);
    return candidates;
}

function computeFootprintArea(geometry) {
    const positions = geometry.getAttribute('position');
    if (!positions || positions.count === 0) return 0;
    geometry.computeBoundingBox();
    const bbox = geometry.boundingBox;
    const sizeY = bbox ? (bbox.max.y - bbox.min.y) : 0;

    let minY = Infinity;
    for (let i = 0; i < positions.count; i++) {
        const y = positions.getY(i);
        if (y < minY) minY = y;
    }

    const eps = Math.max(0.5, sizeY * 0.02);
    const maxY = minY + eps;
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    let count = 0;
    for (let i = 0; i < positions.count; i++) {
        const y = positions.getY(i);
        if (y <= maxY) {
            const x = positions.getX(i);
            const z = positions.getZ(i);
            minX = Math.min(minX, x);
            maxX = Math.max(maxX, x);
            minZ = Math.min(minZ, z);
            maxZ = Math.max(maxZ, z);
            count++;
        }
    }
    if (count < 3) return 0;
    return Math.max(0, (maxX - minX)) * Math.max(0, (maxZ - minZ));
}

function renderOrientationAlternativesUI(evalResult) {
    if (!evalResult || !Array.isArray(evalResult.results) || evalResult.results.length === 0) return;
    const rows = evalResult.results
        .map((r, idx) => {
            const disabled = r.count <= 0 ? 'disabled' : '';
            return `
                <tr>
                    <td>${r.name}</td>
                    <td>${r.count}</td>
                    <td><button class="btn-small" data-action="view-ori" data-idx="${idx}" ${disabled}>${mainText('orientationView')}</button></td>
                </tr>
            `;
        })
        .join('');

    const html = `
        <div style="margin-top: 10px;">
            <button class="btn-small" data-action="toggle-ori">${mainText('orientationAlternatives')}</button>
            <div data-role="ori-panel" style="display:none; margin-top: 8px;" class="results-content">
                <table>
                    <thead>
                        <tr>
                            <th>${mainText('orientationLabel')}</th>
                            <th>${mainRaw('results.unitsColumn', 'Units')}</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
                <p class="info-text" style="margin-top:6px;">${mainText('orientationCompareHint')}</p>
            </div>
        </div>
    `;

    elements.results.insertAdjacentHTML('beforeend', html);
}

// DOM Elements
const elements = {
    // Mode buttons
    modeButtons: document.querySelectorAll('.mode-btn'),
    
    // Object inputs
    objLength: document.getElementById('obj-length'),
    objWidth: document.getElementById('obj-width'),
    objHeight: document.getElementById('obj-height'),
    objWeight: document.getElementById('obj-weight'),
    allowRotation: document.getElementById('allow-rotation'),
    placementStrategy: document.getElementById('placement-strategy'),
    placementStability: document.getElementById('placement-stability'),
    placementSearchEffort: document.getElementById('placement-search-effort'),
    placementSideStacking: document.getElementById('placement-side-stacking'),
    placementSettleCheck: document.getElementById('placement-settle-check'),
    placementLayerSeparator: document.getElementById('placement-layer-separator'),
    stlUpload: document.getElementById('stl-upload'),
    stlStatus: document.getElementById('stl-status'),
    optPieceColors: document.getElementById('opt-piece-colors'),
    optPieceColorsValue: document.getElementById('opt-piece-colors-value'),
    
    // Box inputs
    boxLength: document.getElementById('box-length'),
    boxWidth: document.getElementById('box-width'),
    boxHeight: document.getElementById('box-height'),
    maxWeight: document.getElementById('max-weight'),
    materialDensity: document.getElementById('material-density'),
    customDensityGroup: document.getElementById('custom-density-group'),
    customDensity: document.getElementById('custom-density'),
    solidPiece: document.getElementById('solid-piece'),
    wallThicknessGroup: document.getElementById('wall-thickness-group'),
    wallThickness: document.getElementById('wall-thickness'),
    packingGap: document.getElementById('packing-gap'),
    packingGapValue: document.getElementById('packing-gap-value'),
    
    // Bulk mode options
    bulkOptions: document.getElementById('bulk-options'),
    dropHeight: document.getElementById('drop-height'),
    dropHeightValue: document.getElementById('drop-height-value'),
    maxPieces: document.getElementById('max-pieces'),
    maxPiecesValue: document.getElementById('max-pieces-value'),
    maxPiecesGroup: document.getElementById('max-pieces-group'),
    dropInterval: document.getElementById('drop-interval'),
    dropIntervalValue: document.getElementById('drop-interval-value'),
    vibrationFrequency: document.getElementById('vibration-frequency'),
    vibrationFrequencyValue: document.getElementById('vibration-frequency-value'),
    vibrationAmplitude: document.getElementById('vibration-amplitude'),
    vibrationAmplitudeValue: document.getElementById('vibration-amplitude-value'),
    vibrationNoise: document.getElementById('vibration-noise'),
    vibrationNoiseValue: document.getElementById('vibration-noise-value'),
    pieceColors: document.getElementById('piece-colors'),
    pieceColorsValue: document.getElementById('piece-colors-value'),
    randomRotation: document.getElementById('random-rotation'),
    autoCapacity: document.getElementById('auto-capacity'),
    autoModeHint: document.getElementById('auto-mode-hint'),
    
    // Buttons
    calculateBtn: document.getElementById('calculate-btn'),
    startSimBtn: document.getElementById('start-simulation-btn'),
    stopSimBtn: document.getElementById('stop-simulation-btn'),
    resetSimBtn: document.getElementById('reset-simulation-btn'),
    applyGravityBtn: document.getElementById('apply-gravity-btn'),
    
    // Report buttons
    reportButtons: document.getElementById('report-buttons'),
    reportPreviewBtn: document.getElementById('report-preview-btn'),
    
    // Language toggle
    langToggle: document.getElementById('lang-toggle'),

    // Progress bar (below viewer)
    calcProgress: document.getElementById('calc-progress'),
    calcProgressBar: document.getElementById('calc-progress-bar'),
    calcProgressLabel: document.getElementById('calc-progress-label'),
    calcCancelBtn: document.getElementById('calc-cancel-btn'),
    
    // Report Modal
    reportModal: document.getElementById('report-modal'),
    modalClose: document.getElementById('modal-close'),
    modalCancel: document.getElementById('modal-cancel'),
    modalDownload: document.getElementById('modal-download'),
    reportPreviewFrame: document.getElementById('report-preview-frame'),
    colorCount: document.getElementById('color-count'),
    colorCountValue: document.getElementById('color-count-value'),
    
    // STL History
    stlHistoryInline: document.getElementById('stl-history-inline'),
    stlHistoryList: document.getElementById('stl-history-list'),
    
    // View buttons
    viewButtons: document.querySelectorAll('.view-btn'),
    
    // Output
    threeCanvas: document.getElementById('three-canvas'),
    simulationStatus: document.getElementById('simulation-status'),
    results: document.getElementById('results')
};

function setCalcProgress(visible, percent = 0, label = '', startTime = null) {
    if (!elements.calcProgress || !elements.calcProgressBar) return;
    elements.calcProgress.style.display = visible ? 'flex' : 'none';
    if (elements.calcCancelBtn) {
        elements.calcCancelBtn.disabled = !visible;
    }
    if (elements.calcProgressLabel) {
        let displayLabel = label;
        if (startTime && visible && percent < 100) {
            const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
            displayLabel = `${label}  [${elapsed}s]`;
        }
        elements.calcProgressLabel.textContent = displayLabel;
    }
    if (visible) {
        const clamped = Math.max(0, Math.min(100, percent));
        elements.calcProgressBar.style.width = `${clamped}%`;
    }
}

function nextFrame() {
    return new Promise(resolve => requestAnimationFrame(() => resolve()));
}

/**
 * Initialize the application
 */
async function init() {
    state.locale = await loadLocale(state.language);
    state.sceneManager = new SceneManager(elements.threeCanvas);
    state.reportGenerator = new ReportGenerator(state.sceneManager);
    state.storage = new StorageManager();
    await state.storage.init();
    setupEventListeners();
    await applyLanguage();
    await loadSTLHistory();
    switchMode(state.mode);
    initRapier().then(() => {
        console.log('Physics engine ready');
    }).catch(() => {});

    // Auto-start mesh_server.py via PHP (works under XAMPP/Apache)
    ensureMeshServer();
}

/**
 * Probe mesh_server.py and auto-start it via PHP if not running.
 * Non-blocking — fires and forgets.
 */
function ensureMeshServer() {
    const healthUrl = 'http://127.0.0.1:8787/api/health';
    fetch(healthUrl, { signal: AbortSignal.timeout(2000) })
        .then(r => r.json())
        .then(data => {
            if (data?.status === 'ok') {
                console.log('[mesh_server] Already running', data.pymeshlab ? '(PyMeshLab ✓)' : '(no PyMeshLab)');
            }
        })
        .catch(() => {
            // Not running — try to start via PHP
            console.log('[mesh_server] Not running, trying auto-start via PHP...');
            fetch('api/start-server.php', { signal: AbortSignal.timeout(10000) })
                .then(r => r.json())
                .then(data => {
                    console.log('[mesh_server]', data.status, data.message);
                })
                .catch(err => {
                    console.log('[mesh_server] Auto-start not available (no PHP?):', err.message);
                });
        });
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    elements.langToggle?.addEventListener('click', () => {
        toggleLanguage().catch(err => console.error('Language toggle error:', err));
    });

    elements.modeButtons.forEach(btn => {
        btn.addEventListener('click', () => switchMode(btn.dataset.mode));
    });

    elements.packingGap.addEventListener('input', (e) => {
        const val = e.target.value;
        elements.packingGapValue.textContent = `${val}`;
    });

    // Material density selector
    elements.materialDensity?.addEventListener('change', (e) => {
        const isCustom = e.target.value === 'custom';
        if (elements.customDensityGroup) {
            elements.customDensityGroup.style.display = isCustom ? '' : 'none';
        }
        updateWeightFromMaterial();
    });

    // Custom density input
    elements.customDensity?.addEventListener('input', () => updateWeightFromMaterial());

    // Solid/hollow toggle — show wall thickness when hollow
    elements.solidPiece?.addEventListener('change', () => {
        const isSolid = elements.solidPiece.checked;
        if (elements.wallThicknessGroup) {
            elements.wallThicknessGroup.style.display = isSolid ? 'none' : '';
        }
        updateWeightFromMaterial();
    });

    // Wall thickness change
    elements.wallThickness?.addEventListener('input', () => updateWeightFromMaterial());

    elements.calcCancelBtn?.addEventListener('click', () => {
        if (state.calcAbortController) {
            state.calcAbortController.abort();
        }
    });

    elements.optPieceColors?.addEventListener('input', (e) => {
        elements.optPieceColorsValue.textContent = e.target.value;
    });

    elements.placementStrategy?.addEventListener('change', () => {
        const isLegacy = elements.placementStrategy.value === 'legacy';
        if (elements.placementSettleCheck) {
            elements.placementSettleCheck.disabled = isLegacy;
        }
    });

    elements.dropHeight.addEventListener('input', (e) => {
        elements.dropHeightValue.textContent = e.target.value;
    });

    elements.maxPieces.addEventListener('input', (e) => {
        elements.maxPiecesValue.textContent = e.target.value;
    });

    elements.dropInterval.addEventListener('input', (e) => {
        elements.dropIntervalValue.textContent = e.target.value;
    });

    elements.vibrationFrequency?.addEventListener('input', (e) => {
        if (elements.vibrationFrequencyValue) {
            elements.vibrationFrequencyValue.textContent = parseFloat(e.target.value).toFixed(1);
        }
    });

    elements.vibrationAmplitude?.addEventListener('input', (e) => {
        if (elements.vibrationAmplitudeValue) {
            elements.vibrationAmplitudeValue.textContent = parseFloat(e.target.value).toFixed(2);
        }
    });

    elements.vibrationNoise?.addEventListener('input', (e) => {
        if (elements.vibrationNoiseValue) {
            elements.vibrationNoiseValue.textContent = parseFloat(e.target.value).toFixed(2);
        }
    });

    elements.pieceColors.addEventListener('input', (e) => {
        elements.pieceColorsValue.textContent = e.target.value;
    });

    elements.autoCapacity.addEventListener('change', (e) => {
        const autoMode = e.target.checked;
        if (elements.maxPiecesGroup) {
            elements.maxPiecesGroup.style.display = autoMode ? 'none' : 'block';
        }
        if (elements.autoModeHint) {
            elements.autoModeHint.style.display = autoMode ? 'block' : 'none';
        }
    });

    elements.objWeight.addEventListener('input', updateMaxPiecesLimit);
    elements.maxWeight.addEventListener('input', updateMaxPiecesLimit);

    elements.stlUpload.addEventListener('change', handleSTLUpload);

    elements.calculateBtn.addEventListener('click', handleCalculate);
    elements.startSimBtn.addEventListener('click', startSimulation);
    elements.stopSimBtn.addEventListener('click', stopSimulation);
    elements.resetSimBtn.addEventListener('click', resetSimulation);
    elements.applyGravityBtn?.addEventListener('click', applyGravityTest);

    elements.reportPreviewBtn?.addEventListener('click', openReportModal);
    elements.modalClose?.addEventListener('click', closeReportModal);
    elements.modalCancel?.addEventListener('click', closeReportModal);
    elements.modalDownload?.addEventListener('click', downloadReportFromModal);
    
    elements.colorCount?.addEventListener('input', (e) => {
        elements.colorCountValue.textContent = e.target.value;
    });

    document.querySelectorAll('input[name="report-lang"]').forEach(radio => {
        radio.addEventListener('change', updateReportPreview);
    });

    elements.reportModal?.addEventListener('click', (e) => {
        if (e.target === elements.reportModal) {
            closeReportModal();
        }
    });

    elements.viewButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.dataset.view === 'fullscreen') {
                state.sceneManager.toggleFullscreen();
            } else {
                state.sceneManager.setView(btn.dataset.view);
            }
        });
    });

    // Event delegation for orientation alternatives in results
    elements.results?.addEventListener('click', (e) => {
        const target = e.target;
        if (!(target instanceof HTMLElement)) return;
        const action = target.dataset?.action;
        if (!action) return;

        if (action === 'toggle-ori') {
            const panel = elements.results.querySelector('[data-role="ori-panel"]');
            if (panel) {
                panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
            }
            return;
        }

        if (action === 'view-ori') {
            const idx = parseInt(target.dataset.idx, 10);
            if (!Number.isFinite(idx)) return;
            const evalState = state.orientationEval;
            if (!evalState || !evalState.originalGeometry || !evalState.results[idx]) return;

            const candidate = evalState.results[idx];
            const values = evalState.values;
            state.sceneManager.clearPieces();
            state.sceneManager.createBox(values.boxL, values.boxW, values.boxH);
            const oriented = buildOrientedGeometry(evalState.originalGeometry, candidate.tilt, candidate.yawDeg);
            const drawn = state.sceneManager.addPackedSTLHeightMap({
                stlGeometry: oriented,
                maxDraw: evalState.maxDraw,
                maxTry: evalState.maxTry || null,
                packingGap: values.packingGap,
                colorCount: values.colorCount,
                boxL: values.boxL,
                boxW: values.boxW,
                boxH: values.boxH,
                dryRun: false
            });

            const count = typeof drawn === 'number' ? drawn : drawn.count;
            console.log(`Rendered orientation "${candidate.name}" count=${count}`);
        }
    });
}

/**
 * Switch between optimized and bulk modes
 * @param {string} mode
 */
function switchMode(mode) {
    state.mode = mode;
    
    // Update button states
    elements.modeButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    
    // Show/hide mode-specific elements
    const isOptimized = mode === 'optimized';
    
    elements.bulkOptions.style.display = isOptimized ? 'none' : 'block';
    elements.calculateBtn.style.display = isOptimized ? 'block' : 'none';
    elements.startSimBtn.style.display = isOptimized ? 'none' : 'block';
    if (elements.applyGravityBtn) {
        elements.applyGravityBtn.style.display = 'none';
    }
    
    // Reset button is now redundant as Start handles reset, but we can keep it hidden
    elements.stopSimBtn.style.display = 'none';
    elements.resetSimBtn.style.display = 'none'; // User requested to remove it
    
    // Reset results
    if (!isOptimized) {
        elements.results.innerHTML = `<p class="placeholder-text">${mainText('bulkPlaceholder')}</p>`;
        state.sceneManager.clearPieces();
    }
}

/**
 * Handle 3D file upload (STL, OBJ)
 * @param {Event} event
 */
async function handleSTLUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    

    // Check if format is supported
    if (!isSupported(file.name)) {
        elements.stlStatus.className = 'stl-status error';
        elements.stlStatus.textContent = mainText('unsupportedFormat', {
            formats: SUPPORTED_EXTENSIONS.join(', ')
        });
        elements.stlStatus.style.display = 'block';
        return;
    }
    
    const ext = file.name.substring(file.name.lastIndexOf('.')).toUpperCase();
    elements.stlStatus.className = 'stl-status';
    elements.stlStatus.textContent = `Carregant ${ext}...`;
    elements.stlStatus.style.display = 'block';
    
    // Store the raw file data for saving to history
    const fileData = await file.arrayBuffer();
    state.stlFileName = file.name;
    state.stlFileData = fileData;
    state.stlFileId = null;

    try {
        let geometry = await loadMesh(file);
        centerToOrigin(geometry);
        
        // Comprovar si la malla té molts vèrtexs i oferir simplificació
        const positions = geometry.getAttribute('position');
        const vertexCount = positions.count;
        const VERTEX_THRESHOLD = 50000; // Llindar per oferir simplificació
        
        if (vertexCount > VERTEX_THRESHOLD) {
            const triangleCount = Math.floor(vertexCount / 3);
            // Mostrar opció de simplificació
            elements.stlStatus.className = 'stl-status warning';
            elements.stlStatus.innerHTML = `⚠️ Malla complexa (${triangleCount.toLocaleString()} triangles / ${vertexCount.toLocaleString()} vèrtexs). El rendiment pot ser lent. <button id="simplify-mesh-btn" class="btn-small">Simplificar</button>`;
        }
        
        state.stlGeometry = geometry;
        elements.stlStatus.className = 'stl-status';
        elements.stlStatus.textContent = 'Preparant orientació estable...';
        elements.stlStatus.style.display = 'block';
        await updateStableOrientationCache();
        updateMeshIntegrityCache(state.stlGeometry);
        
        // Update dimension inputs
        elements.objLength.value = state.stlDimensions.length.toFixed(2);
        elements.objWidth.value = state.stlDimensions.width.toFixed(2);
        elements.objHeight.value = state.stlDimensions.height.toFixed(2);

        // Recalculate weight from material if a material is selected
        updateWeightFromMaterial();
        
        if (vertexCount <= VERTEX_THRESHOLD) {
            elements.stlStatus.className = 'stl-status success';
            elements.stlStatus.innerHTML = `${mainText('statusDimensions', {
                length: state.stlDimensions.length.toFixed(2),
                width: state.stlDimensions.width.toFixed(2),
                height: state.stlDimensions.height.toFixed(2)
            })} <button id="download-stl-btn" class="btn-small" style="margin-left:8px;">${mainText('downloadStl')}</button><br>${buildOrientationAndIntegrityLine()}`;
            bindSTLStatusActions();
        } else {
            const triangleCount = Math.floor(vertexCount / 3);
            const baseCount = state.stlStableOrientations?.length || 1;
            elements.stlStatus.className = 'stl-status warning';
            elements.stlStatus.innerHTML = `⚠️ ${mainText('complexMeshWarning', {
                triangles: triangleCount.toLocaleString(),
                vertices: vertexCount.toLocaleString()
            })} <button id="simplify-mesh-btn" class="btn-small">${commonText('buttons.simplify')}</button> <button id="download-stl-btn" class="btn-small" style="margin-left:8px;">${mainText('downloadStl')}</button> <span style="margin-left:8px; opacity:.85;">${mainText('orientationLabel')}: ${state.orientationPrepMs.toFixed(0)} ms (${baseCount} ${mainText('basesLabel')})</span>`;
            bindSTLStatusActions(geometry);
        }
        
        // Save to history
        await saveSTLToHistory();
        
        // Update dynamic limits
        const maxWeight = parseFloat(elements.maxWeight.value) || 0;
        const objWeight = parseFloat(elements.objWeight.value) || 0;
        if (maxWeight > 0 && objWeight > 0) {
            const maxByWeight = Math.floor(maxWeight / objWeight);
            const newMax = Math.min(5000, Math.max(50, maxByWeight));
            elements.maxPieces.max = newMax;
        }


    } catch (error) {
        elements.stlStatus.className = 'stl-status error';
        elements.stlStatus.textContent = `Error: ${error.message}`;
        state.stlGeometry = null;
        state.stlAlignedGeometry = null;
        state.stlSettledQuat = null;
        state.stlStableOrientations = [];
        state.orientationPrepMs = 0;
        state.stlIntegrity = null;
        state.stlDimensions = null;
        state.stlFileName = null;
        state.stlFileData = null;
        state.stlFileId = null;
    }
}

/**
 * Save the current STL file to history
 */
async function saveSTLToHistory() {
    if (!state.stlFileData || !state.stlDimensions || !state.stlFileName) return;
    
    try {
        const weight = parseFloat(elements.objWeight.value) || 0;
        if (state.stlFileId) {
            await state.storage.updateFile(state.stlFileId, {
                name: state.stlFileName,
                data: state.stlFileData,
                dimensions: state.stlDimensions,
                weight,
                lastUsed: Date.now()
            });
        } else {
            state.stlFileId = await state.storage.saveFile(
                state.stlFileName,
                state.stlFileData,
                state.stlDimensions,
                weight
            );
        }
        
        // Refresh the history list
        await loadSTLHistory();
        console.log('STL saved to history:', state.stlFileName);
    } catch (error) {
        console.error('Error saving STL to history:', error);
    }
}

/**
 * Load STL history from storage
 */
async function loadSTLHistory() {
    if (!elements.stlHistoryList) return;
    
    try {
        const files = await state.storage.getRecentFiles(5); // Max 5 items
        
        if (files.length === 0) {
            elements.stlHistoryList.innerHTML = '';
            elements.stlHistoryInline.style.display = 'none';
            return;
        }
        
        elements.stlHistoryInline.style.display = 'block';
        
        elements.stlHistoryList.innerHTML = files.map(file => {
            const isActive = state.stlFileName === file.name;
            const dims = `${file.dimensions.length.toFixed(1)}×${file.dimensions.width.toFixed(1)}×${file.dimensions.height.toFixed(1)}`;
            
            return `
            <div class="stl-history-item ${isActive ? 'active' : ''}" data-id="${file.id}">
                <span class="stl-icon"></span>
                <div class="stl-info">
                    <input type="text" class="stl-name-input" value="${escapeHtml(file.name)}" 
                           data-id="${file.id}" data-field="name" 
                           title="${mainText('editNameTitle')}">
                    <div class="stl-meta">
                        <span class="stl-dims">${dims} mm</span>
                        <input type="number" class="stl-weight-input" value="${file.weight || 0}" 
                               step="0.001" min="0" data-id="${file.id}" data-field="weight"
                               title="${mainText('unitWeightTitle')}">
                        <span class="stl-weight-unit">kg</span>
                    </div>
                </div>
                <div class="stl-actions">
                    <button class="stl-btn download" data-id="${file.id}" title="${commonText('buttons.download')}">${commonText('buttons.download')}</button>
                    <button class="stl-btn delete" data-id="${file.id}" title="${commonText('buttons.delete')}">${commonText('buttons.delete')}</button>
                </div>
            </div>
            `;
        }).join('');
        
        // Add event listeners
        setupSTLHistoryListeners();
        
    } catch (error) {
        console.error('Error loading STL history:', error);
        elements.stlHistoryList.innerHTML = '';
    }
}

/**
 * Setup event listeners for STL history items
 */
function setupSTLHistoryListeners() {
    // Name input - save on blur or enter
    elements.stlHistoryList.querySelectorAll('.stl-name-input').forEach(input => {
        input.addEventListener('blur', async (e) => {
            const id = parseInt(e.target.dataset.id);
            const newName = e.target.value.trim();
            if (newName) {
                await updateSTLField(id, 'name', newName);
            }
        });
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.target.blur();
            }
        });
        // Prevent item click when editing
        input.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    });
    
    // Weight input - save on blur or enter
    elements.stlHistoryList.querySelectorAll('.stl-weight-input').forEach(input => {
        input.addEventListener('blur', async (e) => {
            const id = parseInt(e.target.dataset.id);
            const newWeight = parseFloat(e.target.value) || 0;
            await updateSTLField(id, 'weight', newWeight);
        });
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.target.blur();
            }
        });
        // Prevent item click when editing
        input.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    });
    
    // Download button
    elements.stlHistoryList.querySelectorAll('.stl-btn.download').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = parseInt(e.target.dataset.id);
            await downloadSTLFromHistory(id);
        });
    });
    
    // Delete button
    elements.stlHistoryList.querySelectorAll('.stl-btn.delete').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = parseInt(e.target.dataset.id);
            await deleteSTLFromHistory(id);
        });
    });
    
    // Item click (on the row, not inputs/buttons)
    elements.stlHistoryList.querySelectorAll('.stl-history-item').forEach(item => {
        item.addEventListener('click', async (e) => {
            // Only load if clicking on the item itself, not inputs or buttons
            if (e.target.classList.contains('stl-history-item') || 
                e.target.classList.contains('stl-icon') ||
                e.target.classList.contains('stl-info') ||
                e.target.classList.contains('stl-dims')) {
                const id = parseInt(item.dataset.id);
                await loadSTLFromHistory(id);
            }
        });
    });
}

/**
 * Update a field in an STL history entry
 */
async function updateSTLField(id, field, value) {
    try {
        const file = await state.storage.getFile(id);
        if (!file) return;
        
        // Update the field
        file[field] = value;
        
        // Save back using a new method
        await state.storage.updateFile(id, file);
        
        console.log(`Updated STL ${id} ${field} to:`, value);
    } catch (error) {
        console.error('Error updating STL field:', error);
    }
}

async function downloadSTLFromHistory(id) {
    try {
        const file = await state.storage.getFile(id);
        if (!file?.data || !file?.name) return;
        downloadArrayBuffer(file.data, ensureSTLFileName(file.name), 'model/stl');
    } catch (error) {
        console.error('Error downloading STL from history:', error);
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Load an STL file from history
 */
async function loadSTLFromHistory(id) {
    try {
        const file = await state.storage.getFile(id);
        if (!file) return;
        
        // Update lastUsed
        await state.storage.updateLastUsed(id);
        
        elements.stlStatus.className = 'stl-status';
        elements.stlStatus.textContent = 'Carregant des de l\'historial...';
        elements.stlStatus.style.display = 'block';
        
        // Create a File-like object from the stored data
        const blob = new Blob([file.data], { type: 'application/octet-stream' });
        const fileObj = new File([blob], file.name);
        
        const geometry = await loadMesh(fileObj);
        centerToOrigin(geometry);
        
        state.stlGeometry = geometry;
        await updateStableOrientationCache();
        updateMeshIntegrityCache(state.stlGeometry);
        state.stlFileName = file.name;
        state.stlFileData = file.data;
        state.stlFileId = id;
        
        // Update dimension inputs
        elements.objLength.value = state.stlDimensions.length.toFixed(2);
        elements.objWidth.value = state.stlDimensions.width.toFixed(2);
        elements.objHeight.value = state.stlDimensions.height.toFixed(2);
        
        // Restore stored weight, then override with material if selected
        if (file.weight !== undefined && file.weight !== null) {
            elements.objWeight.value = file.weight;
        }
        updateWeightFromMaterial();
        
        elements.stlStatus.className = 'stl-status success';
        elements.stlStatus.innerHTML = `${file.name}: ${state.stlDimensions.length.toFixed(2)} × ${state.stlDimensions.width.toFixed(2)} × ${state.stlDimensions.height.toFixed(2)} mm<br>${buildOrientationAndIntegrityLine()}`;
        
        // Refresh history to show updated order and active state
        await loadSTLHistory();
        
    } catch (error) {
        console.error('Error loading STL from history:', error);
        elements.stlStatus.className = 'stl-status error';
        elements.stlStatus.textContent = mainText('loadError', { message: error.message });
        elements.stlStatus.style.display = 'block';
    }
}

/**
 * Delete an STL file from history
 */
async function deleteSTLFromHistory(id) {
    try {
        await state.storage.deleteFile(id);
        await loadSTLHistory();
    } catch (error) {
        console.error('Error deleting STL from history:', error);
    }
}

/**
 * Recompute piece weight from material density and update the weight input field.
 * Called live when material/density/solid-hollow/wall settings change.
 */
function updateWeightFromMaterial() {
    const val = elements.materialDensity?.value;
    if (!val || val === '0') return; // "No estimar pes" — keep manual weight
    const density = val === 'custom'
        ? (parseFloat(elements.customDensity?.value) || 0)
        : (parseFloat(val) || 0);
    if (density <= 0) return;

    const isSolid = elements.solidPiece?.checked ?? true;
    const wallT = parseFloat(elements.wallThickness?.value) || 2;

    // Volume / surface area — prefer real mesh data, fall back to dimension inputs
    const meshVol = state.stlGeometry ? computeMeshVolume(state.stlGeometry) : 0;
    const meshSA = state.stlGeometry ? computeSurfaceArea(state.stlGeometry) : 0;
    const objL = parseFloat(elements.objLength.value) || 0;
    const objW = parseFloat(elements.objWidth.value) || 0;
    const objH = parseFloat(elements.objHeight.value) || 0;

    let weight;
    if (isSolid) {
        const vol = meshVol > 0 ? meshVol : (objL * objW * objH);
        weight = (vol / 1e9) * density; // mm³ → m³ × kg/m³
    } else {
        const sa = meshSA > 0 ? meshSA : 2 * (objL * objW + objL * objH + objW * objH);
        weight = (sa * wallT / 1e9) * density;
    }

    if (weight > 0) {
        elements.objWeight.value = weight.toFixed(3);
    }
}

/**
 * Get current input values
 * @returns {Object}
 */
function getInputValues() {
    // Use mode-specific color count slider
    const colorCount = state.mode === 'optimized' 
        ? parseInt(elements.optPieceColors?.value) || 10
        : parseInt(elements.pieceColors?.value) || 10;
    
    return {
        objL: parseFloat(elements.objLength.value) || 0,
        objW: parseFloat(elements.objWidth.value) || 0,
        objH: parseFloat(elements.objHeight.value) || 0,
        objWeight: parseFloat(elements.objWeight.value) || 0,
        boxL: parseFloat(elements.boxLength.value) || 0,
        boxW: parseFloat(elements.boxWidth.value) || 0,
        boxH: parseFloat(elements.boxHeight.value) || 0,
        maxWeight: parseFloat(elements.maxWeight.value) || 0,
        allowRotation: elements.allowRotation.checked,
        heightMapNesting: !!state.stlGeometry,
        placementStrategy: elements.placementStrategy?.value || 'auto',
        placementStability: 'medium',
        placementSearchEffort: elements.placementSearchEffort?.value || 'balanced',
        placementSideStacking: elements.placementSideStacking?.checked ?? true,
        placementSettleCheck: true,
        placementLayerSeparator: Math.max(0, parseFloat(elements.placementLayerSeparator?.value) || 0),
        materialDensity: (() => {
            const val = elements.materialDensity?.value;
            if (!val || val === '0') return 0;
            if (val === 'custom') return parseFloat(elements.customDensity?.value) || 0;
            return parseFloat(val) || 0;
        })(),
        packingGap: Math.max(0, parseFloat(elements.packingGap.value) || 0),
        solidPiece: elements.solidPiece?.checked ?? true,
        wallThickness: parseFloat(elements.wallThickness?.value) || 2,
        // Bulk mode
        dropHeight: parseInt(elements.dropHeight.value),
        maxPieces: parseInt(elements.maxPieces.value),
        dropIntervalMs: parseInt(elements.dropInterval.value),
        vibrationFrequency: parseFloat(elements.vibrationFrequency?.value) || 8.0,
        vibrationAmplitude: parseFloat(elements.vibrationAmplitude?.value) || 0.5,
        vibrationNoise: parseFloat(elements.vibrationNoise?.value) || 0.15,
        colorCount: colorCount,
        randomRotation: elements.randomRotation.checked,
        autoCapacity: elements.autoCapacity.checked
    };
}

function buildOrientationOverrides(geometry, allowRotation) {
    // Use the same 6 axis-aligned permutations as cuboid mode.
    // This is fast, predictable, and gives correct grid results.
    // For STL heightmap mode, the actual placement tries yaw rotations
    // on the aligned geometry separately, so random sampling isn't needed here.
    geometry.computeBoundingBox();
    const bbox = geometry.boundingBox;
    const L = bbox.max.x - bbox.min.x;
    const W = bbox.max.z - bbox.min.z;
    const H = bbox.max.y - bbox.min.y;

    const perms = allowRotation
        ? [
            { dims: [L, W, H], name: 'Original (L×W×H)' },
            { dims: [L, H, W], name: 'Rotació Y (L×H×W)' },
            { dims: [W, L, H], name: 'Rotació Z (W×L×H)' },
            { dims: [W, H, L], name: 'Rotació XY (W×H×L)' },
            { dims: [H, L, W], name: 'Rotació XZ (H×L×W)' },
            { dims: [H, W, L], name: 'Rotació YZ (H×W×L)' },
        ]
        : [
            { dims: [L, W, H], name: 'Sense rotació' }
        ];

    // Deduplicate near-equal bounding boxes
    const seen = new Set();
    const overrides = [];
    for (const p of perms) {
        const key = p.dims.map(d => d.toFixed(1)).sort().join('_');
        if (seen.has(key)) continue;
        seen.add(key);
        overrides.push({
            dims: p.dims,
            name: p.name,
            permIndex: 0,
            rotation: null,
            stable: true
        });
    }

    return overrides;
}

/**
 * Handle calculate button click (optimized mode)
 */
async function handleCalculate() {
    if (state.calcAbortController) {
        state.calcAbortController.abort();
    }
    state.calcAbortController = new AbortController();
    const abortSignal = state.calcAbortController.signal;

    const calcStartTime = performance.now();
    console.time('[PackAssist] Càlcul total');
    setCalcProgress(true, 1, 'Iniciant càlcul...', calcStartTime);
    await nextFrame();

    try {
        elements.results.innerHTML = `<p class="loading-text">${mainText('calculating')}</p>`;

        // Allow UI update
        await new Promise(resolve => setTimeout(resolve, 10));

        // Get input values
        setCalcProgress(true, 2, 'Preparant dades...', calcStartTime);
        await nextFrame();
        const values = getInputValues();

        // Resolve 'auto' strategy to 'stable-contact' with post-packing gravity
        const isAutoStrategy = values.placementStrategy === 'auto';
        if (isAutoStrategy) {
            values.placementStrategy = 'stable-contact';
        }

        let orientationOverrides = null;

        // Normal STL mode overrides
        if (state.stlGeometry) {
            if (!state.stlDimensions) {
                state.stlDimensions = extractDimensions(state.stlGeometry);
            }
            if (state.stlDimensions) {
                // Only update if not in nesting mode
                values.objL = state.stlDimensions.length;
                values.objW = state.stlDimensions.width;
                values.objH = state.stlDimensions.height;

                elements.objLength.value = state.stlDimensions.length.toFixed(2);
                elements.objWidth.value = state.stlDimensions.width.toFixed(2);
                elements.objHeight.value = state.stlDimensions.height.toFixed(2);
            }
            orientationOverrides = buildOrientationOverrides(state.stlGeometry, values.allowRotation);
        }

        // Compute real mesh volume and surface area if STL is loaded
        const meshVolume = state.stlGeometry ? computeMeshVolume(state.stlGeometry) : 0;
        const meshSurfaceArea = state.stlGeometry ? computeSurfaceArea(state.stlGeometry) : 0;

        // --- Compute material weight and override objWeight for the limiter ---
        const matDensity = values.materialDensity || 0;
        let estPieceWeight = 0;
        if (matDensity > 0) {
            if (values.solidPiece) {
                // Solid: weight = volume × density
                const volForWeight = meshVolume > 0 ? meshVolume : (values.objL * values.objW * values.objH);
                estPieceWeight = (volForWeight / 1e9) * matDensity; // mm³ → m³ × kg/m³
            } else {
                // Hollow: weight = surfaceArea × wallThickness × density
                const wallT = values.wallThickness || 2; // mm
                const saForWeight = meshSurfaceArea > 0 ? meshSurfaceArea : 2 * (values.objL * values.objW + values.objL * values.objH + values.objW * values.objH);
                estPieceWeight = (saForWeight * wallT / 1e9) * matDensity; // mm² × mm = mm³ → m³ × kg/m³
            }
            // Use material-derived weight for the weight limiter
            values.objWeight = estPieceWeight;
            elements.objWeight.value = estPieceWeight.toFixed(3);
            console.log(`[PackAssist] Pes per material (${matDensity} kg/m³): ${(estPieceWeight * 1000).toFixed(1)} g/peça`);
        }

        // Run packing calculation
        setCalcProgress(true, 3, 'Calculant empaquetatge...', calcStartTime);
        await nextFrame();
        const result = calcularEmpaquetatge({
            ...values,
            orientationOverrides,
            meshVolume,
            labels: getCalculatorLabels()
        });

        // Don't show results yet — wait until placement finishes for accurate count
        const isHeightmap = state.stlGeometry && values.heightMapNesting;
        if (!isHeightmap) {
            // For cuboid/non-heightmap: grid result is correct, show now
            setCalcProgress(true, 4, 'Mostrant resultats...', calcStartTime);
            elements.results.innerHTML = result.summary;
            elements.results.classList.add('fade-in');
        } else {
            // For heightmap: show placeholder, real results will be shown after placement
            elements.results.innerHTML = `<p class="loading-text">${mainText('placingPieces')}</p>`;
        }

        // Update 3D visualization
        setCalcProgress(true, 5, 'Preparant geometria 3D...', calcStartTime);
        await nextFrame();
        state.sceneManager.clearPieces();

        // Always create box even if no data fits
        state.sceneManager.createBox(values.boxL, values.boxW, values.boxH);

        if (result.data) {
            const [pieceL, pieceW, pieceH] = getPieceDimensions(result.data);
            const [nx, ny, nz] = getDistribution(result.data);

            if (nx > 0 && ny > 0 && nz > 0) {
                let drawn;
                let realDistributionText = null;

                // Decide what geometry to draw
                setCalcProgress(true, 6, 'Provant orientacions...', calcStartTime);
                await nextFrame();
                if (state.stlGeometry) {
                    if (values.heightMapNesting) {
                        const rawMaxDraw = 500;
                    const stableBases = state.stlStableOrientations?.length
                        ? state.stlStableOrientations
                        : [{ quat: null, geometry: (state.stlAlignedGeometry || state.stlGeometry), stability: null }];
                    const orientedSourceGeometry = stableBases[0].geometry;

                    // Compute adaptive placement limit from volume ratio
                    const stlBBox = orientedSourceGeometry.boundingBox || (() => { orientedSourceGeometry.computeBoundingBox(); return orientedSourceGeometry.boundingBox; })();
                    const stlSize = new THREE.Vector3();
                    stlBBox.getSize(stlSize);
                    const pieceBBoxVol = stlSize.x * stlSize.y * stlSize.z;
                    const boxVol = values.boxL * values.boxW * values.boxH;
                    const maxByWeight = (values.maxWeight > 0 && values.objWeight > 0)
                        ? Math.max(0, Math.floor(values.maxWeight / values.objWeight))
                        : Infinity;
                    const maxDraw = Number.isFinite(maxByWeight)
                        ? Math.min(rawMaxDraw, maxByWeight)
                        : rawMaxDraw;
                    const maxTry = pieceBBoxVol > 0
                        ? Math.min(2000, Math.max(maxDraw, Math.ceil(boxVol / pieceBBoxVol * 1.2)))
                        : maxDraw;
                    const searchEffortMultiplier = values.placementSearchEffort === 'dense'
                        ? 1.45
                        : values.placementSearchEffort === 'fast'
                        ? 0.75
                        : 1.0;
                    const effectiveMaxTry = Math.max(maxDraw, Math.min(3000, Math.ceil(maxTry * searchEffortMultiplier)));
                    console.log(`[Packing] boxVol=${boxVol.toFixed(0)}, pieceBBoxVol=${pieceBBoxVol.toFixed(1)}, maxTry=${maxTry}, maxDraw=${maxDraw}, weightCap=${Number.isFinite(maxByWeight) ? maxByWeight : 'none'}`);

                    // --- Step 1: Use precomputed stable orientation (from load/simplify) + generate yaw candidates ---
                    setCalcProgress(true, 8, `Cercant millor orientació Y (${stableBases.length} bases)...`, calcStartTime);
                    await nextFrame();
                    if (abortSignal.aborted) throw new DOMException('Aborted', 'AbortError');

                    // --- Step 1b: Generate yaw candidates on oriented source ---
                    const candidates = generateYawCandidates(
                        state.stlGeometry,
                        stableBases,
                        values.boxL,
                        values.boxW,
                        values.boxH,
                        values.allowRotation,
                        values.placementStrategy
                    );

                    if (candidates.length === 0) {
                        console.warn('Piece does not fit in any yaw orientation.');
                        drawn = { count: 0 };
                    } else {

                    // --- Step 2: Evaluate each yaw candidate via dry-run ---
                    const evalResults = [];
                    const evalStart = 15;
                    const evalEnd = 70;
                    const perCandidate = (evalEnd - evalStart) / Math.max(1, candidates.length);

                    for (let ci = 0; ci < candidates.length; ci++) {
                        const c = candidates[ci];
                        if (abortSignal.aborted) throw new DOMException('Aborted', 'AbortError');

                        const footprintArea = computeFootprintArea(c.oriented);
                        const stability = getSupportStability(c.oriented);
                        c.oriented.computeBoundingBox();
                        const candidateBox = c.oriented.boundingBox;
                        const candidateHeight = candidateBox ? (candidateBox.max.y - candidateBox.min.y) : Infinity;
                        const gridFit = computeWallAlignedGridCapacity(
                            c.oriented,
                            values.boxL,
                            values.boxW,
                            values.packingGap
                        );
                        const dryRunMaxTry = values.placementSearchEffort === 'dense'
                            ? Math.min(120, effectiveMaxTry)
                            : values.placementSearchEffort === 'fast'
                            ? Math.min(30, effectiveMaxTry)
                            : Math.min(60, effectiveMaxTry);
                        const trial = await state.sceneManager.addPackedSTLHeightMapAsync({
                            stlGeometry: c.oriented,
                            maxDraw,
                            maxTry: dryRunMaxTry,
                            packingGap: values.packingGap,
                            colorCount: values.colorCount,
                            boxL: values.boxL,
                            boxW: values.boxW,
                            boxH: values.boxH,
                            placementStrategy: values.placementStrategy,
                            stabilityMode: values.placementStability,
                            allowSideStacking: values.placementSideStacking,
                            useSettleCheck: values.placementSettleCheck,
                            searchEffort: values.placementSearchEffort,
                            layerSeparator: values.placementLayerSeparator,
                            dryRun: true,
                            abortSignal,
                            onProgress: ({ placed, maxTry: mt }) => {
                                const t = mt > 0 ? (placed / mt) : 0;
                                const base = evalStart + perCandidate * ci;
                                setCalcProgress(true, base + perCandidate * Math.max(0, Math.min(1, t)), `Avaluant orientació ${ci + 1}/${candidates.length}...`, calcStartTime);
                            }
                        });
                        const count = typeof trial === 'number' ? trial : trial.count;
                        evalResults.push({
                            candidateIndex: ci,
                            tilt: c.tilt,
                            tiltName: c.tiltName,
                            yawDeg: c.yawDeg,
                            name: c.name,
                            count: count || 0,
                            gridCount: gridFit.count,
                            gridNX: gridFit.gridNX,
                            gridNZ: gridFit.gridNZ,
                            leftoverArea: gridFit.leftoverArea,
                            stable: !!stability?.stable,
                            baseArea: footprintArea || 0,
                            height: candidateHeight
                        });
                    }

                    const sortDenseBand = (list, { stableFirst = false, prioritizeDenseBase = true } = {}) => {
                        list.sort((a, b) => {
                            if (prioritizeDenseBase && (b.gridCount || 0) !== (a.gridCount || 0)) {
                                return (b.gridCount || 0) - (a.gridCount || 0);
                            }
                            if (stableFirst && b.stable !== a.stable) return b.stable ? 1 : -1;
                            if (b.count !== a.count) return b.count - a.count;
                            if ((a.height || Infinity) !== (b.height || Infinity)) {
                                return (a.height || Infinity) - (b.height || Infinity);
                            }
                            if (!stableFirst && b.stable !== a.stable) return b.stable ? 1 : -1;
                            if ((a.leftoverArea || 0) !== (b.leftoverArea || 0)) return (a.leftoverArea || 0) - (b.leftoverArea || 0);
                            return (b.baseArea || 0) - (a.baseArea || 0);
                        });
                        return list;
                    };

                    let rankedEvalResults = [...evalResults];

                    // --- Step 3: Pick the orientation.
                    // Stable-contact must stay within the densest first-layer band, then choose
                    // the most stable candidate inside that band. Other modes keep looser ranking.
                    if (values.placementStrategy === 'stable-contact' && rankedEvalResults.length > 0) {
                        const bestGridCount = Math.max(...rankedEvalResults.map(result => result.gridCount || 0));
                        const denseBand = rankedEvalResults.filter(result => (result.gridCount || 0) >= Math.max(1, bestGridCount - 1));
                        rankedEvalResults = sortDenseBand(denseBand, { stableFirst: true, prioritizeDenseBase: true });
                    } else {
                        const prioritizeDenseBase = values.placementStrategy !== 'legacy';
                        rankedEvalResults = sortDenseBand(rankedEvalResults, {
                            stableFirst: false,
                            prioritizeDenseBase
                        });
                    }

                    let best = rankedEvalResults[0] || { tilt: { quat: state.stlSettledQuat }, yawDeg: 0, name: 'Y 0°', count: 0 };

                    state.orientationEval = {
                        values: { ...values },
                        maxDraw,
                        maxTry,
                        originalGeometry: state.stlGeometry.clone(),
                        results: rankedEvalResults
                    };

                    if (rankedEvalResults[0]) {
                        console.log(
                            `[Orientation] Selected ${rankedEvalResults[0].name} ` +
                            `grid=${rankedEvalResults[0].gridNX}x${rankedEvalResults[0].gridNZ} (${rankedEvalResults[0].gridCount}), ` +
                            `dryRun=${rankedEvalResults[0].count}, leftoverArea=${(rankedEvalResults[0].leftoverArea || 0).toFixed(1)}`
                        );
                    }

                    const bestGeom = buildOrientedGeometry(state.stlGeometry, best.tilt, best.yawDeg);

                    // Auto strategy resolves to stable-contact + gravity refinement
                    let resolvedStrategy = values.placementStrategy;
                    if (isAutoStrategy) {
                        resolvedStrategy = 'stable-contact';
                        values.placementStrategy = resolvedStrategy;
                        console.log(`[Auto] resolved to ${resolvedStrategy}`);
                    }

                    // Build orientation pool for mixed-orientation packing
                    const orientPool = values.placementStrategy === 'stable-contact'
                        ? buildOrientationPoolFromCandidates(
                            sortDenseBand([...evalResults], {
                                stableFirst: false,
                                prioritizeDenseBase: true
                            })
                                .slice(0, 6)
                                .map(result => candidates[result.candidateIndex])
                                .filter(Boolean),
                            values.boxL,
                            values.boxW,
                            values.boxH
                        )
                        : buildOrientationPool(
                            bestGeom,
                            values.boxL, values.boxW, values.boxH
                        );

                    drawn = await state.sceneManager.addPackedSTLHeightMapAsync({
                        stlGeometry: bestGeom,
                        orientationPool: orientPool,
                        useMixedOrientations: orientPool.length > 1 && (values.placementSideStacking || values.placementStrategy === 'stable-contact'),
                        lockPrimaryFirstLayer: values.placementStrategy === 'stable-contact',
                        maxDraw,
                        maxTry: effectiveMaxTry,
                        packingGap: values.packingGap,
                        colorCount: values.colorCount,
                        boxL: values.boxL,
                        boxW: values.boxW,
                        boxH: values.boxH,
                        placementStrategy: values.placementStrategy,
                        stabilityMode: values.placementStability,
                        allowSideStacking: values.placementSideStacking,
                        useSettleCheck: values.placementSettleCheck,
                        searchEffort: values.placementSearchEffort,
                        layerSeparator: values.placementLayerSeparator,
                        dryRun: false,
                        abortSignal,
                        onProgress: ({ placed, maxTry }) => {
                            const start = 70;
                            const end = 95;
                            const t = maxTry > 0 ? (placed / maxTry) : 0;
                            setCalcProgress(true, start + (end - start) * t, mainText('placingPiecesProgress', { placed: Math.floor(placed), maxTry }), calcStartTime);
                        }
                    });

                    // Add a small UI block so you can inspect other orientations
                    renderOrientationAlternativesUI(state.orientationEval);
                    } // end else (candidates.length > 0)
                } else {
                    // Non-heightmap path: also align to stable base first
                    const orientedGeometry = state.stlGeometry.clone();
                    alignToStableBase(orientedGeometry);
                    const best = result.data.bestOrientation || {};
                    if (best.rotation && Array.isArray(best.rotation)) {
                        const quat = new THREE.Quaternion(...best.rotation);
                        const matrix = new THREE.Matrix4().makeRotationFromQuaternion(quat);
                        orientedGeometry.applyMatrix4(matrix);
                    }

                    drawn = state.sceneManager.addPackedSTLPieces({
                        stlGeometry: orientedGeometry,
                        pieceL, pieceW, pieceH,
                        nx, ny, nz,
                        maxDraw: 500,
                        packingGap: values.packingGap,
                        colorCount: values.colorCount,
                        boxL: values.boxL,
                        boxW: values.boxW,
                        boxH: values.boxH,
                        strictGeometryCheck: true
                    });
                }
            } else {
                // Fallback to Box Drawing OR Nested Box drawing
                // For now, if nesting is active, we just draw cuboids representing the pairs
                // TODO: Ideally we would draw the two meshes for each pair
                drawn = state.sceneManager.addPackedPieces({
                    pieceL, pieceW, pieceH,
                    nx, ny, nz,
                    maxDraw: 500,
                    packingGap: values.packingGap,
                    colorCount: values.colorCount,
                    boxL: values.boxL,
                    boxW: values.boxW,
                    boxH: values.boxH
                });
            }
            
            // ... Result handling ...
            const drawnCount = typeof drawn === 'number' ? drawn : drawn.count;
            if (typeof drawn === 'object' && drawn?.distributionText) {
                realDistributionText = drawn.distributionText;
            }
            
            const maxByWeight = (values.maxWeight > 0 && values.objWeight > 0)
                ? Math.max(0, Math.floor(values.maxWeight / values.objWeight))
                : Infinity;
            const displayCount = Number.isFinite(maxByWeight)
                ? Math.min(drawnCount, maxByWeight)
                : drawnCount;
            state.displayCount = displayCount;

            console.log(`Rendered ${drawnCount} items (${displayCount} pieces)`);

            stopGravitySimulation();
            const autoGravity = isAutoStrategy || values.placementStrategy === 'physics-assisted';
            if (values.mode === 'optimized' && autoGravity && displayCount > 0) {
                if (elements.simulationStatus) {
                    elements.simulationStatus.textContent = 'Compactant amb gravetat...';
                    elements.simulationStatus.style.display = 'block';
                }
                setTimeout(() => {
                    // Auto: moderate damping (allows small rotations, prevents full tipping)
                    // Physics-assisted: low damping (allows natural rotation)
                    applyGravityTest({
                        lockRotations: false,
                        settleAngularDamping: isAutoStrategy ? 12.0 : 3.0
                    }).catch(error => {
                        console.error('[GravityRefine] Automatic settle failed:', error);
                    });
                }, 0);
            }

            // Estimated total weight (estPieceWeight computed above, before calcularEmpaquetatge)
            const estTotalWeight = estPieceWeight * displayCount;

            // Material name for display
            const materialNames = {
                '2700': mainText('materialAluminium').split(' (')[0],
                '7850': mainText('materialSteel').split(' (')[0],
                '1200': mainText('materialPlastic').split(' (')[0],
                '8940': mainText('materialCopper').split(' (')[0]
            };
            const matName = materialNames[String(matDensity)] || (matDensity > 0 ? `${matDensity} kg/m³` : null);

            // Build final summary with ACTUAL count (not grid estimate)
            const finalConfig = { ...result.data.bestOrientation };
            if (isHeightmap) {
                // Override with real placement data
                finalConfig.distribution = realDistributionText || `${displayCount} (${mainText('heightmapSuffix')})`;
                finalConfig.weight = displayCount * values.objWeight;
                const volObj = meshVolume > 0 ? meshVolume : (values.objL * values.objW * values.objH);
                const volBox = values.boxL * values.boxW * values.boxH;
                finalConfig.volEfficiency = volBox > 0 ? (displayCount * volObj / volBox * 100) : 0;
                finalConfig.weightEfficiency = values.maxWeight > 0 ? (finalConfig.weight / values.maxWeight * 100) : 0;
            }

            const finalSummary = createSummary(displayCount, finalConfig, result.data.allOrientations, {
                volumeTheoreticalMax: result.data.volumeTheoreticalMax,
                meshVolumeMM3: meshVolume > 0 ? meshVolume : null,
                estimatedPieceWeight: estPieceWeight,
                estimatedTotalWeight: estTotalWeight,
                materialName: matName,
                labels: getCalculatorLabels(),
            });
            elements.results.innerHTML = finalSummary;
            elements.results.classList.add('fade-in');

             state.lastResults = {
                pieceDims: { l: values.objL, w: values.objW, h: values.objH },
                boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
                pieceCount: displayCount,
                pieceWeight: values.objWeight,
                maxWeight: values.maxWeight,
                mode: 'optimized',
                stlFileName: state.stlFileName || null,
                meshVolume: meshVolume || 0,
                materialDensity: matDensity,
                estimatedPieceWeight: estPieceWeight,
                estimatedTotalWeight: estTotalWeight
            };
            
                setCalcProgress(true, 96, 'Desant resultats...', calcStartTime);
                await saveCalculationToHistory(state.lastResults);

                // Show report buttons
                elements.reportButtons.style.display = 'block';
                if (elements.applyGravityBtn) {
                    elements.applyGravityBtn.style.display = 'block';
                }
            }
        }

        const elapsed = ((performance.now() - calcStartTime) / 1000).toFixed(1);
        console.timeEnd('[PackAssist] Càlcul total');
        console.log(`[PackAssist] Temps total: ${elapsed}s`);
        setCalcProgress(true, 100, `Completat! (${elapsed}s)`);
        setTimeout(() => setCalcProgress(false, 0), 1200);
    } catch (err) {
        if (err?.name === 'AbortError') {
            elements.results.innerHTML = `<p class="placeholder-text">${mainText('calcCancelled')}</p>`;
            // Clean up scene on cancellation
            state.sceneManager?.clearPieces();
            if (elements.reportButtons) elements.reportButtons.style.display = 'none';
            if (elements.applyGravityBtn) elements.applyGravityBtn.style.display = 'none';
        } else {
            console.error(err);
        }
        setCalcProgress(false, 0);
        if (err?.name !== 'AbortError') {
            throw err;
        }
    } finally {
        state.calcAbortController = null;
    }
}


function stopGravitySimulation() {
    if (!state.gravitySimulation) return;
    const sim = state.gravitySimulation;
    sim.running = false;
    if (sim.animationId) {
        cancelAnimationFrame(sim.animationId);
    }
    if (sim.physics) {
        sim.physics.pause();
    }
    state.gravitySimulation = null;
}

async function initGravitySimulation() {
    if (!state.sceneManager?.lastPlacement) return null;

    const placement = state.sceneManager.lastPlacement;
    if (!placement.boxDims) return null;

    const physics = new PhysicsWorld();
    await physics.init({
        length: placement.boxDims.l,
        width: placement.boxDims.w,
        height: placement.boxDims.h
    });

    physics.addCeiling({
        length: placement.boxDims.l,
        width: placement.boxDims.w,
        height: placement.boxDims.h
    });

    state.sceneManager.clearPieces();

    const pieceColors = state.sceneManager.pieceColors || [];
    const colorCount = Math.min(pieceColors.length || 1, (state.mode === 'optimized'
        ? parseInt(elements.optPieceColors?.value) || 10
        : parseInt(elements.pieceColors?.value) || 10));

    // Slight convex-hull shrink to reduce explosive separation
    const hullScale = 0.995;

    const placementItems = placement.items?.length
        ? placement.items
        : (placement.positions || []).map((position, index) => ({ position, orientIdx: 0, index }));

    placementItems.forEach((item, idx) => {
        const pos = item.position;
        const orientation = placement.orientations?.[item.orientIdx] || null;
        const color = pieceColors.length > 0 ? pieceColors[idx % colorCount] : 0x3b82f6;
        let mesh;

        if (placement.type === 'stl' && (orientation?.geometry || placement.geometry)) {
            const geometry = (orientation?.geometry || placement.geometry).clone();
            geometry.computeBoundingBox();
            const bbox = geometry.boundingBox;
            const center = new THREE.Vector3();
            bbox.getCenter(center);

            const material = new THREE.MeshPhongMaterial({
                color,
                flatShading: true,
                transparent: true,
                opacity: 0.92
            });
            mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            state.sceneManager.scene.add(mesh);
            state.sceneManager.pieces.push(mesh);

            const hullVertices = orientation?.vertices || placement.vertices;
            if (hullVertices) {
                const verts = hullVertices;
                const centered = new Float32Array(verts.length);
                for (let i = 0; i < verts.length; i += 3) {
                    centered[i] = verts[i] - center.x;
                    centered[i + 1] = verts[i + 1] - center.y;
                    centered[i + 2] = verts[i + 2] - center.z;
                }

                // Place at exact grid position — no lifting
                const bodyPos = new THREE.Vector3(pos.x + center.x, pos.y + center.y, pos.z + center.z);
                physics.addConvexHull(centered, bodyPos, null, mesh, center, { hullScale });
            } else {
                const bodyPos = new THREE.Vector3(pos.x + center.x, pos.y + center.y, pos.z + center.z);
                physics.addCuboid({
                    l: orientation?.dims?.l || placement.dims.l,
                    w: orientation?.dims?.w || placement.dims.w,
                    h: orientation?.dims?.h || placement.dims.h
                }, bodyPos, null, mesh, center);
            }
        } else {
            const geometry = new THREE.BoxGeometry(placement.dims.l, placement.dims.h, placement.dims.w);
            const material = new THREE.MeshPhongMaterial({
                color,
                flatShading: true,
                transparent: true,
                opacity: 0.92
            });
            mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            mesh.position.copy(pos);
            state.sceneManager.scene.add(mesh);
            state.sceneManager.pieces.push(mesh);

            // Place at exact grid position — no lifting
            const bodyPos = new THREE.Vector3(pos.x, pos.y, pos.z);
            physics.addCuboid({
                l: placement.dims.l,
                w: placement.dims.w,
                h: placement.dims.h
            }, bodyPos, null, mesh);
        }
    });

    // Lock rotations initially — keeps pieces aligned during settling
    physics.lockAllRotations(true);

    // Set high damping to prevent bouncing / explosions
    for (const { body } of physics.meshBodies) {
        if (!body || !body.isValid?.()) continue;
        body.setLinearDamping(2.0);
        body.setAngularDamping(5.0);
    }

    physics.start();

    return {
        physics,
        running: true,
        animationId: null,
        phase: 'initial', // initial → vibrating → settling → done
        frameCount: 0,
    };
}


async function applyGravityTest(options = {}) {
    const { lockRotations = false, settleAngularDamping = 3.0 } = options;
    if (!state.sceneManager?.lastPlacement) return;

    if (!state.gravitySimulation) {
        const sim = await initGravitySimulation();
        if (!sim) return;
        state.gravitySimulation = sim;
    }

    const sim = state.gravitySimulation;
    sim.running = true;
    sim.phase = 'initial';
    sim.frameCount = 0;
    sim.physics.setGravity(-9810);
    // Rotations stay locked during initial gravity settling
    sim.physics.lockAllRotations(true);

    if (elements.simulationStatus) {
        elements.simulationStatus.textContent = 'Aplicant gravetat (estabilitzant...)';
        elements.simulationStatus.style.display = 'block';
    }

    // Settled callback
    sim.physics.onSettled = (count) => {
        if (sim.phase === 'initial') {
            // Initial settle complete — start vibration phase  
            sim.phase = 'vibrating';
            sim.physics.settledCount = 0;
            sim.physics.startVibration(4000);
            if (elements.simulationStatus) {
                elements.simulationStatus.textContent = 'Vibrant per compactar...';
            }
        } else if (sim.phase === 'vibrating') {
            // Vibration settle — unlock rotations for natural settling (unless locked)
            sim.phase = 'settling';
            sim.physics.settledCount = 0;
            if (!lockRotations) sim.physics.lockAllRotations(false);
            // Adjust damping for final settling
            for (const { body } of sim.physics.meshBodies) {
                if (!body || !body.isValid?.()) continue;
                body.setLinearDamping(1.0);
                body.setAngularDamping(settleAngularDamping);
            }
            if (elements.simulationStatus) {
                elements.simulationStatus.textContent = 'Assentament final...';
            }
        } else if (sim.phase === 'settling') {
            // Done!
            sim.phase = 'done';
            sim.running = false;
            if (sim.animationId) cancelAnimationFrame(sim.animationId);
            const insideCount = sim.physics.countPiecesInBox();
            // Update single source of truth
            state.displayCount = insideCount;
            if (state.lastResults) {
                state.lastResults.pieceCount = insideCount;
            }
            if (elements.simulationStatus) {
                elements.simulationStatus.textContent = mainText('gravitySettled', { count: insideCount });
            }
        }
    };

    const animate = () => {
        if (!sim.running) return;
        sim.frameCount++;
        sim.physics.step();

        // Safety timeout: stop after 30 seconds (~1800 frames at 60fps)
        if (sim.frameCount > 1800) {
            sim.running = false;
            const insideCount = sim.physics.countPiecesInBox();
            // Update single source of truth
            state.displayCount = insideCount;
            if (state.lastResults) {
                state.lastResults.pieceCount = insideCount;
            }
            if (elements.simulationStatus) {
                elements.simulationStatus.textContent = mainText('gravityTimeout', { count: insideCount });
            }
            return;
        }

        // If vibration finished and we're still in vibrating phase, move to settling
        if (sim.phase === 'vibrating' && !sim.physics.isVibrating) {
            sim.phase = 'settling';
            sim.physics.settledCount = 0;
            if (!lockRotations) sim.physics.lockAllRotations(false);
            if (elements.simulationStatus) {
                elements.simulationStatus.textContent = 'Assentament final...';
            }
        }

        sim.animationId = requestAnimationFrame(animate);
    };

    animate();
}

/**
 * Save calculation to history
 */
async function saveCalculationToHistory(results) {
    try {
        await state.storage.saveCalculation({
            ...results,
            timestamp: Date.now()
        });
        console.log('Calculation saved to history');
    } catch (error) {
        console.error('Error saving calculation to history:', error);
    }
}
/**
 * Start bulk simulation
 */
async function startSimulation() {
    // If already simulating or has results, reset first
    if (state.bulkSimulation && (state.bulkSimulation.isRunning || state.bulkSimulation.droppedCount > 0)) {
        await resetSimulation();
        // Small delay to ensure clean state
        await new Promise(r => setTimeout(r, 100));
    }

    const values = getInputValues();
    
    // Validate inputs
    if ([values.objL, values.objW, values.objH, values.boxL, values.boxW, values.boxH].some(v => v <= 0)) {
        elements.results.innerHTML = `<p>${mainText('invalidDimensions')}</p>`;
        return;
    }
    
    // Initialize bulk simulation
    state.bulkSimulation = new BulkSimulation(state.sceneManager);
    
    try {
        await state.bulkSimulation.init({
            boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
            pieceDims: { l: values.objL, w: values.objW, h: values.objH },
            stlGeometry: state.stlGeometry,
            maxPieces: values.maxPieces,
            dropHeight: values.dropHeight,
            dropIntervalMs: values.dropIntervalMs,
            vibrationFrequency: values.vibrationFrequency,
            vibrationAmplitude: values.vibrationAmplitude,
            vibrationNoise: values.vibrationNoise,
            randomRotation: values.randomRotation,
            autoMode: values.autoCapacity,
            settlingTimeoutMs: 30000,
            colorCount: values.colorCount,
            pieceWeight: values.objWeight,
            maxWeight: values.maxWeight
        });
        
        // Setup status callback
        state.bulkSimulation.onStatusUpdate = (status) => {
            updateSimulationStatus(status);
        };
        
        // Start
        state.bulkSimulation.start();
        state.isSimulating = true;
        
        // Update UI
        elements.startSimBtn.style.display = 'none';
        elements.stopSimBtn.style.display = 'block';
        elements.resetSimBtn.style.display = 'block';
        
    } catch (error) {
        elements.results.innerHTML = `<p>${mainText('simulationInitError', { message: error.message })}</p>`;
    }
}

/**
 * Stop bulk simulation
 */
function stopSimulation() {
    if (state.bulkSimulation) {
        state.bulkSimulation.stop();
        state.isSimulating = false;
        
        elements.startSimBtn.style.display = 'block';
        elements.stopSimBtn.style.display = 'none';
        
        updateSimulationStatus({
            status: 'paused',
            message: '⏸️ Simulació pausada'
        });
    }
}

/**
 * Reset bulk simulation
 */
function resetSimulation() {
    if (state.bulkSimulation) {
        state.bulkSimulation.reset();
        state.isSimulating = false;
    }
    
    state.sceneManager.clearPieces();
    state.lastResults = null;
    
    elements.startSimBtn.style.display = 'block';
    elements.stopSimBtn.style.display = 'none';
    elements.reportButtons.style.display = 'none';
    
    elements.simulationStatus.className = 'simulation-status';
    elements.simulationStatus.textContent = '';
    
    elements.results.innerHTML = `<p class="placeholder-text">${mainText('bulkPlaceholder')}</p>`;
}

/**
 * Update simulation status display
 * @param {Object} status
 */
async function updateSimulationStatus(status) {
    elements.simulationStatus.className = 'simulation-status active';
    elements.simulationStatus.textContent = status.message;
    
    if (status.status === 'settled' || status.status === 'timeout' || status.status === 'saturated') {
        const values = getInputValues();
        const localizedRemovedText = status.removed > 0 ? `<li><strong>${mainText('bulkRemoved')}</strong> ${status.removed}</li>` : '';
        
        elements.results.innerHTML = `
            <h1>${mainText('bulkResultTitle')}</h1>
            <ul>
                <li><strong>${mainText('bulkDropped')}</strong> ${status.dropped}</li>
                <li><strong>${mainText('bulkInside')}</strong> ${status.inside}</li>
                ${localizedRemovedText}
                <li><strong>${mainText('bulkEfficiency')}</strong> ${((status.inside / status.dropped) * 100).toFixed(1)}%</li>
            </ul>
            <p>${mainText('bulkExplanation')}</p>
        `;
        
        // Store results for report
        const bulkMeshVolume = state.stlGeometry ? computeMeshVolume(state.stlGeometry) : 0;
        const bulkSurfaceArea = state.stlGeometry ? computeSurfaceArea(state.stlGeometry) : 0;
        const matDensity = values.materialDensity || 0;
        let estPieceWeight = 0;
        if (matDensity > 0) {
            if (values.solidPiece) {
                const volForWeight = bulkMeshVolume > 0 ? bulkMeshVolume : (values.objL * values.objW * values.objH);
                estPieceWeight = (volForWeight / 1e9) * matDensity;
            } else {
                const wallT = values.wallThickness || 2;
                const saForWeight = bulkSurfaceArea > 0 ? bulkSurfaceArea : 2 * (values.objL * values.objW + values.objL * values.objH + values.objW * values.objH);
                estPieceWeight = (saForWeight * wallT / 1e9) * matDensity;
            }
            // Use material-derived weight for consistency
            values.objWeight = estPieceWeight;
            elements.objWeight.value = estPieceWeight.toFixed(3);
        }
        const estTotalWeight = estPieceWeight * status.inside;

        state.lastResults = {
            pieceDims: { l: values.objL, w: values.objW, h: values.objH },
            boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
            pieceCount: status.inside,
            pieceWeight: values.objWeight,
            maxWeight: values.maxWeight,
            mode: 'bulk',
            stlFileName: state.stlFileName || null,
            meshVolume: bulkMeshVolume,
            materialDensity: matDensity,
            estimatedPieceWeight: estPieceWeight,
            estimatedTotalWeight: estTotalWeight
        };
        state.displayCount = status.inside;
        
        // Save to calculation history
        await saveCalculationToHistory(state.lastResults);
        
        // Show report buttons
        elements.reportButtons.style.display = 'block';

        elements.startSimBtn.style.display = 'block';
        elements.stopSimBtn.style.display = 'none';
    }
}

/**
 * Open report preview modal
 */
/**
 * Toggle UI language between CA and EN
 */
async function toggleLanguage() {
    state.language = state.language === 'ca' ? 'en' : 'ca';
    setStoredLanguage(state.language);
    await applyLanguage();
}

/**
 * Apply current language to all UI elements
 */
async function applyLanguage() {
    state.locale = await loadLocale(state.language);
    const t = state.locale.main;
    const btn = elements.langToggle;
    if (btn) {
        const active = btn.querySelector('.lang-active');
        const inactive = btn.querySelector('.lang-inactive');
        if (state.language === 'ca') {
            active.textContent = 'CA';
            inactive.textContent = 'EN';
        } else {
            active.textContent = 'EN';
            inactive.textContent = 'CA';
        }
    }

    document.title = t.pageTitle;
    
    // Header
    const headerH1 = document.querySelector('.header h1');
    const headerP = document.querySelector('.header p');
    const navLink = document.querySelector('.nav-link');
    if (headerH1) headerH1.textContent = t.headerTitle;
    if (headerP) headerP.textContent = t.headerSubtitle;
    if (navLink) navLink.textContent = t.historyLink;
    
    // Mode buttons
    const modeBtns = document.querySelectorAll('.mode-btn');
    modeBtns.forEach(btn => {
        const mode = btn.dataset.mode;
        const desc = btn.querySelector('.mode-desc');
        if (mode === 'optimized') {
            btn.childNodes[0].textContent = t.modeOptimized + '\n';
            if (desc) desc.textContent = t.modeOptimizedDesc;
        } else if (mode === 'bulk') {
            btn.childNodes[0].textContent = t.modeBulk + '\n';
            if (desc) desc.textContent = t.modeBulkDesc;
        }
    });
    
    // Section titles
    const objSection = document.querySelector('.object-section .section-header h2');
    const boxSection = document.querySelector('.box-section > h2');
    const bulkSection = document.querySelector('.bulk-section > h2');
    if (objSection) objSection.textContent = t.objectTitle;
    if (boxSection) boxSection.textContent = t.boxTitle;
    if (bulkSection) bulkSection.textContent = t.bulkTitle;
    
    // Input labels (by associated input id)
    const labelMap = {
        'obj-length': t.objLength,
        'obj-width': t.objWidth,
        'obj-height': t.objHeight,
        'obj-weight': t.objWeight,
        'box-length': t.boxLength,
        'box-width': t.boxWidth,
        'box-height': t.boxHeight,
        'max-weight': t.maxWeight,
    };
    for (const [id, text] of Object.entries(labelMap)) {
        const label = document.querySelector(`label[for="${id}"]`);
        if (label) label.textContent = text;
    }
    
    // Checkbox labels
    const rotLabel = document.querySelector('label[for="allow-rotation"]');
    const randRotLabel = document.querySelector('label[for="random-rotation"]');
    const autoCapLabel = document.querySelector('label[for="auto-capacity"]');
    const solidLabel = document.querySelector('label[for="solid-piece"]');
    const customDensityLabel = document.querySelector('label[for="custom-density"]');
    const wallThicknessLabel = document.querySelector('label[for="wall-thickness"]');
    const materialDensityLabel = document.querySelector('label[for="material-density"]');
    if (rotLabel) rotLabel.textContent = t.allowRotation;
    if (randRotLabel) randRotLabel.textContent = t.randomRotation;
    if (autoCapLabel) autoCapLabel.textContent = t.autoCapacity;
    if (solidLabel) solidLabel.textContent = t.solidPiece;
    if (customDensityLabel) customDensityLabel.textContent = t.customDensity;
    if (wallThicknessLabel) wallThicknessLabel.textContent = t.wallThickness;
    if (materialDensityLabel) materialDensityLabel.textContent = t.materialDensity;

    const placementOptionsTitle = document.getElementById('placement-options-title');
    const placementStrategyLabel = document.querySelector('label[for="placement-strategy"]');
    const placementSearchLabel = document.querySelector('label[for="placement-search-effort"]');
    const placementSideLabel = document.querySelector('label[for="placement-side-stacking"]');
    const placementLayerSepLabel = document.querySelector('label[for="placement-layer-separator"]');
    const placementHint = document.getElementById('placement-hint');
    if (placementOptionsTitle) placementOptionsTitle.textContent = t.placementOptionsTitle;
    if (placementStrategyLabel) placementStrategyLabel.textContent = t.placementStrategyLabel;
    if (placementSearchLabel) placementSearchLabel.textContent = t.placementSearchEffortLabel;
    if (placementSideLabel) placementSideLabel.textContent = t.placementSideStacking;
    if (placementLayerSepLabel) placementLayerSepLabel.textContent = t.placementLayerSeparator;
    if (placementHint) placementHint.textContent = t.placementHint;

    if (elements.placementStrategy) {
        const optionTexts = [
            t.placementStrategyAuto,
            t.placementStrategyStable,
            t.placementStrategyPhysics,
            t.placementStrategyLegacy
        ];
        Array.from(elements.placementStrategy.options).forEach((option, index) => {
            if (optionTexts[index]) option.textContent = optionTexts[index];
        });
    }
    if (elements.placementSearchEffort) {
        const optionTexts = [
            t.placementSearchFast,
            t.placementSearchBalanced,
            t.placementSearchDense
        ];
        Array.from(elements.placementSearchEffort.options).forEach((option, index) => {
            if (optionTexts[index]) option.textContent = optionTexts[index];
        });
    }

    if (elements.materialDensity) {
        const optionTexts = [
            t.materialNone,
            t.materialAluminium,
            t.materialSteel,
            t.materialPlastic,
            t.materialCopper,
            t.materialCustom
        ];
        Array.from(elements.materialDensity.options).forEach((option, index) => {
            if (optionTexts[index]) option.textContent = optionTexts[index];
        });
    }

    const optColorsLabel = document.querySelector('label[for="opt-piece-colors"]');
    if (optColorsLabel) {
        optColorsLabel.innerHTML = `${t.colorCount} <span id="opt-piece-colors-value">${elements.optPieceColorsValue.textContent}</span>`;
    }
    const packingGapLabel = document.querySelector('label[for="packing-gap"]');
    if (packingGapLabel) {
        packingGapLabel.innerHTML = `${t.packingGap} <span id="packing-gap-value">${elements.packingGapValue.textContent}</span> mm`;
    }
    const dropHeightLabel = document.querySelector('label[for="drop-height"]');
    if (dropHeightLabel) {
        dropHeightLabel.innerHTML = `${t.dropHeight} <span id="drop-height-value">${elements.dropHeightValue.textContent}</span>mm`;
    }
    const maxPiecesLabel = document.querySelector('label[for="max-pieces"]');
    if (maxPiecesLabel) {
        maxPiecesLabel.innerHTML = `${t.maxPieces} <span id="max-pieces-value">${elements.maxPiecesValue.textContent}</span>`;
    }
    const dropIntervalLabel = document.querySelector('label[for="drop-interval"]');
    if (dropIntervalLabel) {
        dropIntervalLabel.innerHTML = `${t.dropInterval} <span id="drop-interval-value">${elements.dropIntervalValue.textContent}</span>`;
    }
    const vibrationFrequencyLabel = document.querySelector('label[for="vibration-frequency"]');
    if (vibrationFrequencyLabel) {
        vibrationFrequencyLabel.innerHTML = `${t.vibFreq} <span id="vibration-frequency-value">${elements.vibrationFrequencyValue.textContent}</span> Hz`;
    }
    const vibrationAmplitudeLabel = document.querySelector('label[for="vibration-amplitude"]');
    if (vibrationAmplitudeLabel) {
        vibrationAmplitudeLabel.innerHTML = `${t.vibAmp} <span id="vibration-amplitude-value">${elements.vibrationAmplitudeValue.textContent}</span> mm`;
    }
    const vibrationNoiseLabel = document.querySelector('label[for="vibration-noise"]');
    if (vibrationNoiseLabel) {
        vibrationNoiseLabel.innerHTML = `${t.vibNoise} <span id="vibration-noise-value">${elements.vibrationNoiseValue.textContent}</span> mm`;
    }
    const pieceColorsLabel = document.querySelector('label[for="piece-colors"]');
    if (pieceColorsLabel) {
        pieceColorsLabel.innerHTML = `${t.colorCount} <span id="piece-colors-value">${elements.pieceColorsValue.textContent}</span>`;
    }
    
    // Buttons
    elements.calculateBtn.textContent = t.calculateBtn;
    if (elements.applyGravityBtn) elements.applyGravityBtn.textContent = t.gravityBtn;
    if (elements.startSimBtn) elements.startSimBtn.textContent = t.simulateBtn;
    if (elements.stopSimBtn) elements.stopSimBtn.textContent = t.stopBtn;
    if (elements.resetSimBtn) elements.resetSimBtn.textContent = t.resetBtn;
    if (elements.reportPreviewBtn) elements.reportPreviewBtn.textContent = t.previewReport;
    
    // Report modal
    const modalTitle = document.querySelector('.modal-header h2');
    const modalDownload = document.getElementById('modal-download');
    const modalCancel = document.getElementById('modal-cancel');
    if (modalTitle) modalTitle.textContent = t.reportTitle;
    if (modalDownload) modalDownload.textContent = t.reportDownload;
    if (modalCancel) modalCancel.textContent = t.reportCancel;
    
    // Cancel button for calc
    const calcCancelBtn = document.getElementById('calc-cancel-btn');
    if (calcCancelBtn) calcCancelBtn.textContent = t.cancelBtn;
    
    // Placeholder
    const placeholder = document.querySelector('.placeholder-text');
    if (placeholder) placeholder.textContent = state.mode === 'optimized' ? t.placeholder : t.bulkPlaceholder;
    
    // Also sync the report language radio
    const radioToCheck = document.querySelector(`input[name="report-lang"][value="${state.language}"]`);
    if (radioToCheck) radioToCheck.checked = true;

    // Set html lang attribute
    document.documentElement.lang = state.language === 'ca' ? 'ca' : 'en';
}

/**
 * Open report preview modal
 */
async function openReportModal() {
    if (!state.lastResults) {
        alert('No hi ha resultats per generar l\'informe. Executa una simulació primer.');
        return;
    }
    
    elements.reportModal.style.display = 'flex';
    elements.reportPreviewFrame.innerHTML = '<p class="loading-text">Carregant previsualització...</p>';
    
    // Generate preview
    await updateReportPreview();
}

/**
 * Close report preview modal
 */
function closeReportModal() {
    elements.reportModal.style.display = 'none';
}

/**
 * Update report preview in modal
 */
async function updateReportPreview() {
    if (!state.lastResults || !state.reportGenerator) return;
    
    const language = document.querySelector('input[name="report-lang"]:checked')?.value || 'ca';
    
    try {
        const html = await state.reportGenerator.generatePreview(state.lastResults, language);
        
        // Create iframe with content
        const iframe = document.createElement('iframe');
        iframe.style.width = '100%';
        iframe.style.height = '450px';
        iframe.style.border = 'none';
        
        elements.reportPreviewFrame.innerHTML = '';
        elements.reportPreviewFrame.appendChild(iframe);
        
        // Write content to iframe
        const doc = iframe.contentWindow.document;
        doc.open();
        doc.write(html);
        doc.close();
        
    } catch (error) {
        console.error('Error updating preview:', error);
        elements.reportPreviewFrame.innerHTML = `<p class="loading-text" style="color: red;">${mainText('reportPreviewError')}</p>`;
    }
}

/**
 * Download report from modal
 */
async function downloadReportFromModal() {
    if (!state.lastResults) return;
    
    const language = document.querySelector('input[name="report-lang"]:checked')?.value || 'ca';
    
    try {
        await state.reportGenerator.downloadReport(state.lastResults, language);
        closeReportModal();
    } catch (error) {
        console.error('Error generating report:', error);
        alert(mainText('reportGenerateError'));
    }
}

/**
 * Generate and download report
 * @param {string} language - 'ca' or 'en'
 */
async function generateReport(language) {
    if (!state.lastResults) {
        alert(mainText('reportNoResults'));
        return;
    }
    
    try {
        await state.reportGenerator.downloadReport(state.lastResults, language);
    } catch (error) {
        console.error('Error generating report:', error);
        alert(mainText('reportGenerateError'));
    }
}

// Initialize app on DOM ready
document.addEventListener('DOMContentLoaded', init);

// Export for debugging
window.PackAssist = { state, elements };
