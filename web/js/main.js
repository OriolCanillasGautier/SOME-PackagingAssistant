/**
 * PackAssist Web - Main Application
 * Connects UI with packing calculator, 3D visualization, and physics simulation
 */

import * as THREE from 'three';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { calcularEmpaquetatge, createSummary, getDistribution, getPieceDimensions } from './packing/calculator.js?v=force_update_42';
import { loadMesh, loadSTL, extractDimensions, computeMeshVolume, computeSurfaceArea, analyzeMeshIntegrity, centerToOrigin, isSupported, SUPPORTED_EXTENSIONS, guessPermForDims, applyPermutation, getSupportStability, alignToStableBase } from './mesh/mesh-utils.js?v=force_update_42';
import { SceneManager } from './visualization/scene.js?v=ui_fix_v2';
import { BulkSimulation, PhysicsWorld, initRapier } from './physics/physics-world.js?v=force_update_42';
import { ReportGenerator } from './report/report-generator.js?v=force_update_42';
import { getSimplificationModal } from './mesh/simplification-modal.js?v=force_update_42';
import { StorageManager } from './storage/storage-manager.js?v=force_update_42';
import { loadLocale, t as localeText, getStoredLanguage, setStoredLanguage } from './i18n.js?v=force_update_42';
import { initBoxOptions } from './box-options.js?v=box_compare_v1';

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
        }
    }
}


// Application state
const state = {
    mode: 'fast', // 'fast' (Planar), 'bulk' (Gravetat), or 'gpu' (Optimitzat)
    bulkVariant: 'gravity', // 'gravity' | 'optimized' — sub-option of Bulk
    planarVariant: 'grid', // 'grid' | 'stacking' | 'compartment' — sub-option of Planar
    bulkConfigSet: false, // User confirmed pieces/auto via popup or advanced
    language: getStoredLanguage(), // 'ca' or 'en'
    locale: null,
    stlGeometry: null,
    stlAlignedGeometry: null, // transient in-memory geometry aligned to stable gravity orientation
    stlSettledQuat: null, // cached quaternion from gravity drop on current loaded geometry
    stlStableOrientations: [], // [{ quat, geometry, stability }] precomputed gravity bases
    selectedOrientations: null, // Set of selected orientation indices
    orientationConfirmed: false, // User confirmed a pose via the modal
    orientationExplicit: false, // User actively clicked a pose (vs default)
    activeOrientationIndex: 0, // Index of the orientation shown in the large viewer
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
        modeOptimizedDesc: 'Nidificació amb heightmap BVH',
        modeFast: 'Optimitzador Ràpid',
        modeFastDesc: 'Graella regular amb densitat màxima',
        modeBulk: 'Mode a Granel',
        modeBulkDesc: 'Simulació amb gravetat',
        modeGPU: 'GPU Voxel',
        modeGPUDesc: 'Servidor CUDA — màxima precisió',
        modeGPURequiresSTL: 'El mode GPU requereix un fitxer STL',
        modeGPUSubmitting: 'Enviant al servidor GPU...',
        modeGPUPacking: 'Processant al servidor...',
        modeGPUError: 'Error del servidor',
        modeGPUPlacements: 'col·locacions individuals',
        modeGPUStlUrl: 'Descarregar STL',
        reoptimize: 'Re-optimitzar',
        gpuComparison: 'Comparació de resultats',
        fillPct: 'd\'ocupació',
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
        modeOptimizedDesc: 'Heightmap BVH nesting',
        modeFast: 'Fast Optimizer',
        modeFastDesc: 'Regular grid with max density',
        modeBulk: 'Bulk Mode',
        modeBulkDesc: 'Gravity simulation',
        modeGPU: 'GPU Voxel',
        modeGPUDesc: 'CUDA server — maximum precision',
        modeGPURequiresSTL: 'GPU mode requires an STL file',
        modeGPUSubmitting: 'Sending to GPU server...',
        modeGPUPacking: 'Processing on server...',
        modeGPUError: 'Server error',
        modeGPUPlacements: 'individual placements',
        modeGPUStlUrl: 'Download STL',
        reoptimize: 'Re-optimize',
        gpuComparison: 'Results comparison',
        fillPct: 'fill',
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
        maybeShowOrientationModal();
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

    state.selectedOrientations = new Set([0]);
    state.activeOrientationIndex = 0;
    maybeShowOrientationModal();
    return primary?.geometry || null;
}

/**
 * The orientation selection is only relevant for modes that place pieces in
 * a chosen pose (Planar). Bulk gravity and the GPU optimizer explore
 * orientations themselves.
 */
function modeNeedsOrientation() {
    return state.mode === 'fast';
}

/**
 * Show the orientation modal only when the active mode needs a pose and the
 * user has not confirmed one yet.
 */
function maybeShowOrientationModal() {
    if (!state.orientationConfirmed && modeNeedsOrientation()) {
        renderOrientationSelector();
    }
}

const MAX_ORIENTATION_CARDS = 4;

const orientationViewerState = {
    initialized: false,
    renderer: null,
    scene: null,
    camera: null,
    controls: null,
    grid: null,
    mesh: null,
    animId: null,
    resizeObserver: null
};

/**
 * Create (once) the shared WebGL renderer, scene, camera, floor grid and
 * OrbitControls used by the large orientation viewer. Kept alive across
 * orientation switches so the user's orbit/zoom is preserved.
 */
function initOrientationViewer() {
    const canvas = document.getElementById('orientation-viewer-canvas');
    const container = document.getElementById('orientation-viewer');
    if (!canvas || !container) return;

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: false, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const width = Math.max(220, container.clientWidth || 350);
    const height = Math.max(220, container.clientHeight || 350);
    renderer.setSize(width, height);
    renderer.setClearColor(0x1e1e1f, 1);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x1e1e1f, 60, 140);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(3, 2.2, 3);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = true;
    controls.target.set(0, 0, 0);

    const ambient = new THREE.AmbientLight(0xffffff, 0.55);
    scene.add(ambient);
    const dir = new THREE.DirectionalLight(0xffffff, 0.9);
    dir.position.set(3, 6, 2);
    scene.add(dir);
    const dir2 = new THREE.DirectionalLight(0x8888ff, 0.35);
    dir2.position.set(-3, 2, -3);
    scene.add(dir2);

    const grid = new THREE.GridHelper(10, 20, 0x9aa7bd, 0x5b6b83);
    grid.material.transparent = true;
    grid.material.opacity = 0.55;
    grid.position.y = 0;
    scene.add(grid);

    orientationViewerState.renderer = renderer;
    orientationViewerState.scene = scene;
    orientationViewerState.camera = camera;
    orientationViewerState.controls = controls;
    orientationViewerState.grid = grid;
    orientationViewerState.initialized = true;

    // Keep the canvas size in sync with its container. Fires when the modal
    // becomes visible (size jumps from 0 to its laid-out dimensions) and on
    // any window/panel resize, so a stale 0-size frame never gets rendered.
    if (typeof ResizeObserver !== 'undefined') {
        const resizeObserver = new ResizeObserver(() => {
            const w = container.clientWidth;
            const h = container.clientHeight;
            if (w <= 0 || h <= 0) return;
            renderer.setSize(w, h);
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            if (orientationViewerState.scene && orientationViewerState.camera) {
                renderer.render(orientationViewerState.scene, orientationViewerState.camera);
            }
        });
        resizeObserver.observe(container);
        orientationViewerState.resizeObserver = resizeObserver;
    }

    // Self-schedule FIRST so the animation loop can never be killed by the
    // modal-visibility early return below.
    const loop = () => {
        orientationViewerState.animId = requestAnimationFrame(loop);
        const modal = document.getElementById('orientation-modal');
        if (!modal || modal.style.display === 'none') return;
        if (orientationViewerState.controls) orientationViewerState.controls.update();
        if (orientationViewerState.renderer && orientationViewerState.scene && orientationViewerState.camera) {
            orientationViewerState.renderer.render(orientationViewerState.scene, orientationViewerState.camera);
        }
    };
    orientationViewerState.animId = requestAnimationFrame(loop);
}

/**
 * Swap the mesh shown in the large viewer and reframe the camera/grid so the
 * floor plane sits under the piece. Disposes the previous mesh geometry.
 */
function setActiveOrientationMesh(geometry) {
    const vs = orientationViewerState;
    if (!vs.initialized) initOrientationViewer();
    if (!vs.scene || !vs.camera || !vs.controls) return;

    if (vs.mesh) {
        vs.scene.remove(vs.mesh);
        if (vs.mesh.geometry) vs.mesh.geometry.dispose();
        if (vs.mesh.material) vs.mesh.material.dispose();
        vs.mesh = null;
    }

    if (geometry) {
        const geom = geometry.clone();
        geom.computeVertexNormals();
        geom.center();
        const mat = new THREE.MeshPhongMaterial({ color: 0x3b82f6, flatShading: false, shininess: 40 });
        const mesh = new THREE.Mesh(geom, mat);
        vs.scene.add(mesh);
        vs.mesh = mesh;

        const box = new THREE.Box3().setFromObject(mesh);
        const size = new THREE.Vector3();
        box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        const center = new THREE.Vector3();
        box.getCenter(center);

        // Grid floor sits directly under the piece's lowest point (the
        // geometry is centered, so box.min.y is the bottom of the mesh).
        vs.grid.scale.set(maxDim * 4, 1, maxDim * 4);
        vs.grid.position.y = box.min.y;

        // Fixed diagonal camera direction (same angle as before).
        const dirVec = new THREE.Vector3(0.75, 0.55, 0.75).normalize();

        // Frame the camera so the piece's projected bounding box fills ~60%
        // of the smaller viewport dimension. Place a provisional camera at a
        // nominal distance to derive the view basis (right/up), then project
        // the box corners onto it to pick a distance that guarantees the
        // whole piece stays in frame regardless of its shape.
        vs.camera.position.copy(center).addScaledVector(dirVec, maxDim);
        vs.camera.lookAt(center);
        vs.camera.updateMatrixWorld();
        const viewDir = new THREE.Vector3();
        vs.camera.getWorldDirection(viewDir);
        const rightVec = new THREE.Vector3().crossVectors(viewDir, vs.camera.up).normalize();
        const upVec = new THREE.Vector3().crossVectors(rightVec, viewDir).normalize();

        const corners = [
            new THREE.Vector3(box.min.x, box.min.y, box.min.z),
            new THREE.Vector3(box.max.x, box.min.y, box.min.z),
            new THREE.Vector3(box.min.x, box.max.y, box.min.z),
            new THREE.Vector3(box.min.x, box.min.y, box.max.z),
            new THREE.Vector3(box.max.x, box.max.y, box.min.z),
            new THREE.Vector3(box.max.x, box.min.y, box.max.z),
            new THREE.Vector3(box.min.x, box.max.y, box.max.z),
            new THREE.Vector3(box.max.x, box.max.y, box.max.z)
        ];
        let minR = Infinity, maxR = -Infinity, minU = Infinity, maxU = -Infinity;
        for (const c of corners) {
            const r = c.dot(rightVec);
            const u = c.dot(upVec);
            if (r < minR) minR = r;
            if (r > maxR) maxR = r;
            if (u < minU) minU = u;
            if (u > maxU) maxU = u;
        }
        const projW = maxR - minR;
        const projH = maxU - minU;

        const canvasEl = vs.renderer ? vs.renderer.domElement : null;
        const vw = canvasEl ? canvasEl.clientWidth : 0;
        const vh = canvasEl ? canvasEl.clientHeight : 0;
        const aspect = vw > 0 && vh > 0 ? vw / vh : 1;
        const halfTan = Math.tan(THREE.MathUtils.degToRad(vs.camera.fov / 2));
        const targetFraction = 0.7;
        const distFromTarget = Math.max(
            projW / (targetFraction * 2 * halfTan * aspect),
            projH / (targetFraction * 2 * halfTan)
        );
        const dist = distFromTarget / dirVec.length();

        // Keep the depth fog scaled to the piece. The camera sits ~distFromTarget
        // away, so a fixed 60–140 fog range washes the whole scene out to the
        // clear color whenever the piece is larger than ~50mm.
        if (vs.scene && vs.scene.fog) {
            vs.scene.fog.near = distFromTarget * 1.6;
            vs.scene.fog.far = Math.max(distFromTarget * 4, vs.scene.fog.near + 1);
        }

        vs.camera.near = Math.max(0.001, maxDim / 100);
        vs.camera.far = maxDim * 100;
        vs.camera.position.copy(center).addScaledVector(dirVec, dist);
        vs.camera.lookAt(center);
        vs.camera.updateProjectionMatrix();
        vs.controls.target.copy(center);
        vs.controls.minDistance = maxDim * 0.4;
        vs.controls.maxDistance = maxDim * 20;
        vs.controls.update();
    }

    if (vs.renderer) vs.renderer.render(vs.scene, vs.camera);
}

function renderOrientationSelector() {
    const modal = document.getElementById('orientation-modal');
    const optionsDiv = document.getElementById('orientation-options');
    if (!modal || !optionsDiv) return;

    const orientations = state.stlStableOrientations || [];
    if (orientations.length <= 1) {
        modal.style.display = 'none';
        state.selectedOrientations = new Set([0]);
        return;
    }

    if (!state.selectedOrientations) state.selectedOrientations = new Set([0]);
    if (typeof state.activeOrientationIndex !== 'number') state.activeOrientationIndex = 0;

    const shown = orientations.slice(0, MAX_ORIENTATION_CARDS);
    if (state.activeOrientationIndex >= shown.length) state.activeOrientationIndex = 0;

    optionsDiv.innerHTML = shown.map((o, i) => {
        const dims = extractDimensions(o.geometry);
        const isSelected = state.selectedOrientations.has(i);
        const isActive = state.activeOrientationIndex === i;
        const canvasId = `orient-canvas-${i}`;
        const stabilityText = o.stability?.stable
            ? `${mainText('orientationStable', {}, 'Estable')} · ${(o.stability.supportArea || 0).toFixed(0)} mm²`
            : mainText('orientationStable', {}, 'Estable');
        return `<div class="orient-card ${isSelected ? 'selected' : ''} ${isActive ? 'active' : ''}" data-index="${i}"
                tabindex="0" role="button" aria-pressed="${isSelected}"
                onclick="selectOrientation(${i})">
            <canvas id="${canvasId}" class="orient-preview" width="140" height="140"></canvas>
            <div class="orient-info">
                <span class="orient-dims">${dims.length.toFixed(0)}×${dims.width.toFixed(0)}×${dims.height.toFixed(0)}mm</span>
                <span class="orient-stability">${stabilityText}</span>
            </div>
            <span class="orient-check" aria-hidden="true"></span>
        </div>`;
    }).join('');

    modal.style.display = 'flex';
    document.getElementById('orientation-confirm').onclick = confirmOrientationSelection;
    const confirmBtn = document.getElementById('orientation-confirm');
    if (confirmBtn) confirmBtn.focus();

    // Render thumbnail previews and the large viewer after DOM update
    requestAnimationFrame(() => {
        shown.forEach((o, i) => {
            renderOrientationPreview(`orient-canvas-${i}`, o.geometry);
        });
        setActiveOrientationMesh(shown[state.activeOrientationIndex]?.geometry);
    });
}

function confirmOrientationSelection() {
    const modal = document.getElementById('orientation-modal');
    if (modal) modal.style.display = 'none';
    state.orientationConfirmed = true;
}

/**
 * Keyboard support: Esc closes the modal, Enter on a card activates that
 * orientation (Confirm button handles Enter-to-confirm natively), arrow keys
 * move the active orientation.
 */
function setupOrientationModalKeyboard() {
    const modal = document.getElementById('orientation-modal');
    if (!modal) return;

    document.addEventListener('keydown', (e) => {
        if (!modal || modal.style.display === 'none') return;
        if (e.key === 'Escape') {
            e.preventDefault();
            modal.style.display = 'none';
        } else if (e.key === 'Enter' && e.target && e.target.classList && e.target.classList.contains('orient-card')) {
            e.preventDefault();
            selectOrientation(parseInt(e.target.dataset.index, 10));
        } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            moveActiveOrientation(1);
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault();
            moveActiveOrientation(-1);
        }
    });
}

function moveActiveOrientation(delta) {
    const orientations = state.stlStableOrientations || [];
    const count = Math.min(MAX_ORIENTATION_CARDS, orientations.length);
    if (count === 0) return;
    const next = (state.activeOrientationIndex + delta + count) % count;
    setActiveOrientationIndex(next);
}

/**
 * Single selection: clicking a card makes it THE selected orientation.
 * Clicking the already-selected card keeps it (can't deselect to zero).
 */
function toggleOrientationSelection(index) {
    state.selectedOrientations = new Set([index]);
    state.orientationExplicit = true; // user actively picked this pose
}

/**
 * Sync every card's classes/aria with the current selection + active state
 * without rebuilding the thumbnail canvases or the viewer.
 */
function updateOrientationCardUI() {
    document.querySelectorAll('#orientation-options .orient-card').forEach(card => {
        const idx = parseInt(card.dataset.index, 10);
        const isSelected = state.selectedOrientations.has(idx);
        const isActive = state.activeOrientationIndex === idx;
        card.classList.toggle('selected', isSelected);
        card.classList.toggle('active', isActive);
        card.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
    });
}

/**
 * Show an orientation in the large viewer without touching the selection.
 */
function setActiveOrientationIndex(index) {
    state.activeOrientationIndex = index;
    updateOrientationCardUI();

    const orientations = state.stlStableOrientations || [];
    const shown = orientations.slice(0, MAX_ORIENTATION_CARDS);
    const o = shown[index];
    if (o) setActiveOrientationMesh(o.geometry);
}

/**
 * Card interaction: toggle this orientation for packing AND show it in the
 * large viewer (the last clicked card is always the one inspected).
 */
function selectOrientation(index) {
    const orientations = state.stlStableOrientations || [];
    if (index < 0 || index >= Math.min(MAX_ORIENTATION_CARDS, orientations.length)) return;
    toggleOrientationSelection(index);
    setActiveOrientationIndex(index);
}

// Expose for inline onclick handlers (module scope)
window.toggleOrientation = toggleOrientation;
window.selectOrientation = selectOrientation;
window.setBoxPreset = setBoxPreset;

const orientationRenderers = new Map();

function renderOrientationPreview(canvasId, geometry) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const oldRenderer = orientationRenderers.get(canvasId);
    if (oldRenderer) {
        oldRenderer.dispose();
        orientationRenderers.delete(canvasId);
    }

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    orientationRenderers.set(canvasId, renderer);
    renderer.setSize(140, 140);
    renderer.setClearColor(0x000000, 0);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 1000);
    camera.position.set(2, 1.5, 2);
    camera.lookAt(0, 0, 0);

    const ambient = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambient);
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(1, 2, 1);
    scene.add(dir);

    const meshGeom = geometry.clone();
    meshGeom.computeVertexNormals();
    meshGeom.center();
    const mat = new THREE.MeshPhongMaterial({ color: 0x3b82f6, flatShading: false, shininess: 40 });
    const mesh = new THREE.Mesh(meshGeom, mat);
    scene.add(mesh);

    const box = new THREE.Box3().setFromObject(mesh);
    const size = Math.max(box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z);
    camera.position.set(size * 1.5, size * 1.2, size * 1.5);
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
}

function toggleOrientation(index) {
    toggleOrientationSelection(index);
    updateOrientationCardUI();
}

function setBoxPreset(l, w, h, btn) {
    document.getElementById('box-length').value = l;
    document.getElementById('box-width').value = w;
    document.getElementById('box-height').value = h;
    document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
}

// ── Saved (user-defined) box presets — localStorage ──
const BOXES_STORAGE_KEY = 'packassist.boxes';

function loadSavedBoxes() {
    try {
        const raw = JSON.parse(localStorage.getItem(BOXES_STORAGE_KEY) || '[]');
        return Array.isArray(raw) ? raw : [];
    } catch (e) {
        return [];
    }
}

function saveBoxesList(boxes) {
    try {
        localStorage.setItem(BOXES_STORAGE_KEY, JSON.stringify(boxes));
    } catch (e) { /* storage unavailable — non fatal */ }
}

function renderSavedBoxes() {
    const wrap = document.getElementById('saved-boxes');
    if (!wrap) return;
    const boxes = loadSavedBoxes();
    wrap.style.display = boxes.length ? 'flex' : 'none';
    wrap.innerHTML = boxes.map((b, i) => `
        <button class="preset-btn" onclick="setBoxPreset(${b.l},${b.w},${b.h},this)" title="${b.l}×${b.w}×${b.h} mm">
            ${b.l}×${b.w}×${b.h}
            <span class="preset-remove" onclick="event.stopPropagation();removeSavedBox(${i})">×</span>
        </button>
    `).join('');
}

window.removeSavedBox = (i) => {
    const boxes = loadSavedBoxes();
    if (i >= 0 && i < boxes.length) {
        boxes.splice(i, 1);
        saveBoxesList(boxes);
        renderSavedBoxes();
    }
};

function saveCurrentBox() {
    const l = parseFloat(document.getElementById('box-length')?.value);
    const w = parseFloat(document.getElementById('box-width')?.value);
    const h = parseFloat(document.getElementById('box-height')?.value);
    if (!(l > 0) || !(w > 0) || !(h > 0)) {
        alert(mainText('invalidDimensions'));
        return;
    }
    const boxes = loadSavedBoxes();
    const exists = boxes.some(b => Math.abs(b.l - l) < 0.1 && Math.abs(b.w - w) < 0.1 && Math.abs(b.h - h) < 0.1);
    if (!exists) {
        boxes.push({ l, w, h });
        saveBoxesList(boxes);
    }
    renderSavedBoxes();
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
    stackingQuality: document.getElementById('stacking-quality'),
    stlUpload: document.getElementById('stl-upload'),
    stlStatus: document.getElementById('stl-status'),
    optPieceColors: document.getElementById('opt-piece-colors'),
    
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
    cardboardMm: document.getElementById('cardboard-mm'),
    cardboardMmGroup: document.getElementById('cardboard-mm-group'),
    multitrayTotalGroup: document.getElementById('multitray-total-group'),
    multitrayTotal: document.getElementById('multitray-total'),
    
    // Bulk mode options
    bulkOptions: document.getElementById('bulk-options'),
    gpuOptions: document.getElementById('gpu-options'),
    dropHeight: document.getElementById('drop-height'),
    maxPieces: document.getElementById('max-pieces'),
    maxPiecesGroup: document.getElementById('max-pieces-group'),
    dropInterval: document.getElementById('drop-interval'),
    vibrationFrequency: document.getElementById('vibration-frequency'),
    vibrationAmplitude: document.getElementById('vibration-amplitude'),
    vibrationNoise: document.getElementById('vibration-noise'),
    pieceColors: document.getElementById('piece-colors'),
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
    window.__sceneManager = state.sceneManager; // dev/test hook
    state.reportGenerator = new ReportGenerator(state.sceneManager);
    state.storage = new StorageManager();
    await state.storage.init();
    setupEventListeners();
    setupOrientationModalKeyboard();
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
    const healthUrl = '/api/health';
    fetch(healthUrl, { signal: AbortSignal.timeout(2000) })
        .then(r => r.json())
        .then(data => {
            if (data?.status === 'ok') {
                const extras = [];
                if (data.pymeshlab) extras.push('PyMeshLab ✓');
                if (data.cuda) extras.push('CUDA ✓');
                console.log('[server.py] Running on :8787', extras.length ? `(${extras.join(', ')})` : '');
            }
        })
        .catch(() => {
            console.warn('[server.py] Not running. GPU Voxel + Simplify need it.');
            console.info('[server.py] Start manually:   python3 server.py --port 8787');
            // Try PHP auto-start as fallback (XAMPP only)
            fetch('api/start-server.php', { signal: AbortSignal.timeout(4000) })
                .then(r => r.ok ? r.json() : Promise.reject('PHP not running'))
                .then(data => console.log('[server.py] Auto-start:', data.status))
                .catch(() => {});
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

    // Bulk variant sub-selector (Gravetat / Optimitzat)
    document.querySelectorAll('#bulk-variant-selector .variant-btn').forEach(btn => {
        btn.addEventListener('click', () => switchBulkVariant(btn.dataset.variant));
    });

    // Planar variant sub-selector (Graella / Apilat / Compartiment)
    document.querySelectorAll('#planar-variant-selector .variant-btn').forEach(btn => {
        btn.addEventListener('click', () => switchPlanarVariant(btn.dataset.variant));
    });

    // Auto mode popup
    const autoModeConfirm = document.getElementById('auto-mode-confirm');
    if (autoModeConfirm) {
        autoModeConfirm.addEventListener('click', () => {
            const popup = document.getElementById('auto-mode-popup');
            if (popup) popup.style.display = 'none';
        });
    }

    // Bulk start popup — radio toggles the fixed-pieces input
    document.querySelectorAll('input[name="bulk-mode"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            const fixedGroup = document.getElementById('bulk-fixed-pieces-group');
            if (fixedGroup) fixedGroup.style.display = e.target.value === 'fixed' ? 'block' : 'none';
        });
    });
    const bulkStartConfirm = document.getElementById('bulk-start-confirm');
    if (bulkStartConfirm) {
        bulkStartConfirm.addEventListener('click', confirmBulkStartPopup);
    }

    // Changing the advanced bulk settings counts as a manual configuration
    elements.autoCapacity?.addEventListener('change', () => { state.bulkConfigSet = true; });
    elements.maxPieces?.addEventListener('input', () => { state.bulkConfigSet = true; });

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

    elements.placementStrategy?.addEventListener('change', () => {
        const isLegacy = elements.placementStrategy.value === 'legacy';
        if (elements.placementSettleCheck) {
            elements.placementSettleCheck.disabled = isLegacy;
        }
    });

    // Bulk numeric inputs — values are read directly at simulation start

    elements.autoCapacity.addEventListener('change', (e) => {
        const autoMode = e.target.checked;
        if (elements.maxPiecesGroup) {
            elements.maxPiecesGroup.style.display = autoMode ? 'none' : 'block';
        }
        if (elements.autoModeHint) {
            elements.autoModeHint.style.display = autoMode ? 'block' : 'none';
        }
        // Explain auto mode when the user enables it manually
        if (autoMode && !state._programmaticBulkChange) {
            showAutoModePopup();
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
        if (elements.optPieceColors) elements.optPieceColors.value = e.target.value;
        if (elements.reportModal && elements.reportModal.style.display === 'flex') {
            recolorScene(parseInt(e.target.value, 10) || 1);
            updateReportPreview();
        }
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
        // Orientation alternatives UI removed — unified grid-based evaluation.
    });
}

/**
 * Monotonic counter used to invalidate in-flight calculations when the user
 * switches mode/variant. Any async calc (client pack or server GPU poll) that
 * finishes after a mode change must NOT render stale results.
 */
let calcGeneration = 0;

/**
 * Clear every trace of the previous calculation from the UI + 3D scene:
 * results table/stats, re-optimize buttons, report buttons, comparison panel,
 * the 3D scene (pieces + box + partitions + protective overlays), the
 * progress bar and the simulation status. Call on every mode/variant switch.
 * @param {{placeholder?: string|null}} [opts]
 */
function clearResults({ placeholder = null } = {}) {
    calcGeneration++;

    // Abort any in-flight client-side calculation
    if (state.calcAbortController) {
        state.calcAbortController.abort();
        state.calcAbortController = null;
    }

    setCalcProgress(false, 0, '', 0);
    stopGravitySimulation();

    state.sceneManager?.clearPieces();
    state.sceneManager?.clearBox();

    // Reset the Pack Studio overlay checkboxes (meshes are gone with the scene)
    ['protective-partitions', 'protective-foam', 'protective-tray'].forEach(id => {
        const cb = document.getElementById(id);
        if (cb) cb.checked = false;
    });

    if (elements.simulationStatus) {
        elements.simulationStatus.className = 'simulation-status';
        elements.simulationStatus.textContent = '';
    }
    if (elements.reportButtons) elements.reportButtons.style.display = 'none';
    if (elements.applyGravityBtn) elements.applyGravityBtn.style.display = 'none';

    // Clear the "Comparar caixes" results panel below the results section
    const boxOpts = document.getElementById('box-options-container');
    if (boxOpts) boxOpts.innerHTML = '';

    state.lastResults = null;
    state.displayCount = 0;

    if (placeholder !== null && elements.results) {
        elements.results.innerHTML = placeholder;
        elements.results.classList.remove('fade-in');
    }
}

/**
 * Switch between optimized and bulk modes
 * @param {string} mode
 */
function switchMode(mode) {
    state.mode = mode;

    const isBulkGroup = mode === 'bulk' || mode === 'gpu';
    const isBulk = mode === 'bulk';
    const isGPU = mode === 'gpu';
    if (isBulkGroup) state.bulkVariant = isBulk ? 'gravity' : 'optimized';

    // Main mode buttons: Bulk stays active for both variants
    elements.modeButtons.forEach(btn => {
        if (btn.dataset.mode === 'bulk') {
            btn.classList.toggle('active', isBulkGroup);
        } else {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        }
    });

    // Planar variant sub-selector (Graella / Apilat / Compartiment) — shown
    // only in Planar mode. state.planarVariant is preserved across switches.
    const planarSelector = document.getElementById('planar-variant-selector');
    if (planarSelector) planarSelector.style.display = mode === 'fast' ? 'flex' : 'none';
    document.querySelectorAll('#planar-variant-selector .variant-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.variant === state.planarVariant);
    });

    // Bulk variant sub-selector (Gravetat / Optimitzat)
    const variantSelector = document.getElementById('bulk-variant-selector');
    if (variantSelector) variantSelector.style.display = isBulkGroup ? 'flex' : 'none';
    document.querySelectorAll('#bulk-variant-selector .variant-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.variant === state.bulkVariant);
    });

    elements.bulkOptions.style.display = isBulk ? 'block' : 'none';
    elements.gpuOptions.style.display = isGPU ? 'block' : 'none';
    elements.calculateBtn.style.display = isBulk ? 'none' : 'block';
    elements.startSimBtn.style.display = isBulk ? 'block' : 'none';

    elements.stopSimBtn.style.display = 'none';
    elements.resetSimBtn.style.display = 'none';

    if (elements.applyGravityBtn) {
        elements.applyGravityBtn.style.display = 'none';
    }

    // Any previous calculation is invalid once the mode changes: clear the
    // results, stats, 3D scene, re-optimize buttons and progress UI.
    const placeholder = isBulk
        ? `<p class="placeholder-text">${mainText('bulkPlaceholder')}</p>`
        : (isGPU
            ? `<p class="placeholder-text">${mainText('gpuPlaceholder')}</p>`
            : `<p class="placeholder-text">${mainText('placeholder')}</p>`);
    clearResults({ placeholder });

    // Ask for an orientation if entering Planar without a confirmed pose
    if (modeNeedsOrientation() && !state.orientationConfirmed && state.stlGeometry) {
        maybeShowOrientationModal();
    }
}

/**
 * Switch between Bulk variants (Gravetat / Optimitzat).
 */
function switchBulkVariant(variant) {
    if (variant === 'optimized') {
        switchMode('gpu');
    } else {
        switchMode('bulk');
    }
}

/**
 * Switch between Planar variants (Graella / Apilat / Compartiment).
 * Planar keeps state.mode = 'fast' — only the sub-variant changes.
 */
function switchPlanarVariant(variant) {
    state.planarVariant = variant;
    document.querySelectorAll('#planar-variant-selector .variant-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.variant === variant);
    });

    // Compartment mode: show the cardboard thickness input (the dividers are
    // sized from it and the grid gap equals it).
    if (elements.cardboardMmGroup) {
        elements.cardboardMmGroup.style.display = variant === 'compartment' ? 'block' : 'none';
    }
    // Multi-tray mode: show the total piece count input.
    if (elements.multitrayTotalGroup) {
        elements.multitrayTotalGroup.style.display = variant === 'multitray' ? 'block' : 'none';
    }

    // Refresh the Planar mode button subtitle to match the active variant.
    const descMap = {
        grid: mainText('planarGridDesc'),
        stacking: mainText('planarStackingDesc'),
        multitray: mainText('planarMultitrayDesc'),
        compartment: mainText('planarCompartmentDesc'),
    };
    const planarBtn = document.querySelector('.mode-btn[data-mode="fast"]');
    const descEl = planarBtn?.querySelector('.mode-desc');
    if (descEl) descEl.textContent = descMap[variant] || mainText('modePlanarDesc');

    // Switching variant invalidates the previous calculation: clear results,
    // 3D scene, re-optimize buttons, report buttons and progress UI.
    clearResults({ placeholder: `<p class="placeholder-text">${mainText('placeholder')}</p>` });

    // All Planar variants still place pieces in a chosen pose, so keep the
    // orientation requirement (re-offer the modal if not yet confirmed).
    if (state.mode === 'fast' && !state.orientationConfirmed && state.stlGeometry) {
        maybeShowOrientationModal();
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
            elements.stlStatus.innerHTML = `Malla complexa (${triangleCount.toLocaleString()} triangles / ${vertexCount.toLocaleString()} vèrtexs). El rendiment pot ser lent. <button id="simplify-mesh-btn" class="btn-small">Simplificar</button>`;
        }
        
        state.stlGeometry = geometry;
        state.orientationConfirmed = false;
        state.orientationExplicit = false;
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
            elements.stlStatus.innerHTML = `${mainText('complexMeshWarning', {
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
    const colorCount = state.mode !== 'bulk' 
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
        placementStability: elements.placementStability?.value || 'medium',
        placementSearchEffort: elements.placementSearchEffort?.value || 'balanced',
        placementSideStacking: elements.placementSideStacking?.checked ?? true,
        placementSettleCheck: elements.placementSettleCheck?.checked ?? true,
        placementLayerSeparator: Math.max(0, parseFloat(elements.placementLayerSeparator?.value) || 0),
        stackingQuality: parseInt(elements.stackingQuality?.value) || 2,
        materialDensity: (() => {
            const val = elements.materialDensity?.value;
            if (!val || val === '0') return 0;
            if (val === 'custom') return parseFloat(elements.customDensity?.value) || 0;
            return parseFloat(val) || 0;
        })(),
        packingGap: Math.max(0, parseFloat(elements.packingGap.value) || 0),
        cardboardMm: Math.max(0, parseFloat(elements.cardboardMm?.value) || 0),
        solidPiece: elements.solidPiece?.checked ?? true,
        wallThickness: parseFloat(elements.wallThickness?.value) || 2,
        // Bulk mode
        dropHeight: (() => {
            const manual = parseInt(elements.dropHeight.value);
            if (manual > 0) return manual;
            // Auto: drop from well above the box based on box height + item bbox
            const boxH = parseFloat(elements.boxHeight.value) || 0;
            const itemMax = Math.max(
                parseFloat(elements.objLength.value) || 0,
                parseFloat(elements.objWidth.value) || 0,
                parseFloat(elements.objHeight.value) || 0
            );
            return Math.max(100, boxH + itemMax * 2);
        })(),
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
    geometry.computeBoundingBox();
    const bbox = geometry.boundingBox;
    const L = bbox.max.x - bbox.min.x;
    const W = bbox.max.z - bbox.min.z;
    const H = bbox.max.y - bbox.min.y;

    // Each entry specifies (dims for calculator) + (appliedXYZ perm for geometry transform)
    const perms = allowRotation
        ? [
            { dims: [L, W, H], perm: [0, 1, 2], name: 'Original (LxWxH)' },
            { dims: [L, H, W], perm: [0, 2, 1], name: 'Rotacio Y (LxHxW)' },
            { dims: [W, L, H], perm: [1, 0, 2], name: 'Rotacio Z (WxLxH)' },
            { dims: [W, H, L], perm: [1, 2, 0], name: 'Rotacio XY (WxHxL)' },
            { dims: [H, L, W], perm: [2, 0, 1], name: 'Rotacio XZ (HxLxW)' },
            { dims: [H, W, L], perm: [2, 1, 0], name: 'Rotacio YZ (HxWxL)' },
        ]
        : [
            { dims: [L, W, H], perm: [0, 1, 2], name: 'Sense rotacio' }
        ];

    const seen = new Set();
    const overrides = [];
    for (const p of perms) {
        const key = p.dims.map(d => d.toFixed(1)).join('_');
        if (seen.has(key)) continue;
        seen.add(key);
        overrides.push({
            dims: p.dims,
            name: p.name,
            perm: p.perm,
            rotation: null,
            stable: true
        });
    }

    return overrides;
}

/**
 * GPU Voxel Packer — submits STL to the backend server,
 * polls with live progress, stores results for comparison.
 */
let gpuHistory = [];
const MAX_GPU_HISTORY = 10;

async function handleGPUCalculate(calcStartTime, options = null) {
    const calcGen = ++calcGeneration;
    const isCurrent = () => calcGeneration === calcGen;

    if (!state.stlGeometry) {
        elements.results.innerHTML = `<p class="error-text">${mainText('modeGPURequiresSTL')}</p>`;
        return;
    }

    const values = getInputValues();
    let cellSize = document.getElementById('gpu-cell-size')?.value || '0.5';
    let gpuMethod = document.getElementById('gpu-method')?.value || 'voxel';
    let extraSeed = 0;

    if (options) {
        // Method override (Planar stacking/compartment variants reuse this handler).
        if (options.method) {
            gpuMethod = options.method;
        } else if (state.mode === 'fast' && (state.planarVariant === 'stacking' || state.planarVariant === 'compartment')) {
            // Re-optimize (horizontal angle / accuracy / reseed) reuses the
            // active Planar variant's packer.
            gpuMethod = state.planarVariant;
        }
        if (options.accuracy === 'accurate') {
            gpuMethod = 'voxel';
            cellSize = '0.5';
        } else if (options.accuracy === 'fast') {
            gpuMethod = 'sparrow';
            cellSize = '2.0';
        } else if (options.accuracy === 'reseed') {
            extraSeed = Math.floor(Math.random() * 2 ** 31);
        }
    }

    setCalcProgress(true, 5, mainText('modeGPUSubmitting'), calcStartTime);
    await nextFrame();

    try {
        // Stacking/Compartment ALWAYS honor the user's chosen orientation
        // (the modal selection): export the selected pose's geometry and tell
        // the server to use only that rotation. Other methods explore all
        // orientations themselves.
        let stlBlob = null;
        let fixedOrientation = 0;
        const isPoseMethod = gpuMethod === 'stacking' || gpuMethod === 'compartment';
        const selectedSet = state.selectedOrientations;
        if (isPoseMethod && selectedSet && selectedSet.size === 1 && state.stlStableOrientations?.length) {
            const selIdx = [...selectedSet][0];
            const selOrientation = state.stlStableOrientations[selIdx];
            if (selOrientation?.geometry) {
                stlBlob = new Blob([exportGeometryToBinarySTL(selOrientation.geometry)],
                                   { type: 'application/octet-stream' });
                fixedOrientation = 1;
            }
        }
        if (!stlBlob) {
            stlBlob = new Blob([state.stlFileData], { type: 'application/octet-stream' });
        }

        const formData = new FormData();
        formData.append('stl', stlBlob, state.stlFileName || 'piece.stl');
        formData.append('box_l', values.boxL);
        formData.append('box_w', values.boxW);
        formData.append('box_h', values.boxH);
        formData.append('cell', cellSize);
        formData.append('method', gpuMethod);
        if (options?.totalPieces) formData.append('total_pieces', String(options.totalPieces));
        if (extraSeed) formData.append('seed', String(extraSeed));
        if (fixedOrientation) formData.append('fixed_orientation', String(fixedOrientation));
        if (fixedOrientation && options?.horizontalAngle != null) {
            formData.append('horizontal_angle', String(options.horizontalAngle));
        }

        const resp = await fetch('/api/pack', {
            method: 'POST',
            body: formData,
            signal: AbortSignal.timeout(10000)
        });
        if (!resp.ok) throw new Error(`Servidor: ${resp.status}`);
        const submitData = await resp.json();
        const job_id = submitData.job_id;

        // Poll with live progress
        let job, pollCount = 0;
        const staticEta = submitData.estimated_time;
        const gpuColorCount = parseInt(elements.optPieceColors?.value) || 10;
        // Live-preview bookkeeping: the server's placements_partial grows in
        // pack order, so we only ever append the NEW entries to the scene.
        let liveGeo = null;
        let liveRendered = 0;
        do {
            const r = await fetch(`/api/pack/${job_id}`);
            job = await r.json();
            pollCount++;

            // User switched mode while the server was packing → abandon silently.
            if (!isCurrent()) return;

            // Live packing preview (sparrow): render placements as they arrive
            // so the user watches the box fill while the server is still packing.
            if (job.status === 'running' && Array.isArray(job.placements_partial)) {
                const partialLen = job.placements_partial.length;
                // A later worker attempt restarts from zero → drop the stale
                // preview and re-render the new attempt from the start so the
                // visible state always matches a single consistent packing run.
                if (partialLen < liveRendered) {
                    state.sceneManager.clearPieces();
                    liveRendered = 0;
                }
                if (partialLen > liveRendered) {
                    if (!liveGeo) {
                        liveGeo = await loadSTL(state.stlFileData);
                    }
                    if (liveGeo) {
                        state.sceneManager.createBox(values.boxL, values.boxW, values.boxH);
                        state.sceneManager.addPackedPlacementsPartial({
                            placements: job.placements_partial,
                            baseGeometry: liveGeo,
                            boxL: values.boxL,
                            boxW: values.boxW,
                            boxH: values.boxH,
                            colorCount: gpuColorCount,
                        });
                        liveRendered = partialLen;
                    }
                }
            }

            if (job.status === 'running' || job.status === 'queued') {
                let etaText = '';
                if (job.pieces > 2 && job.time_s > 0) {
                    // Live ETA from actual measured progress
                    const perPiece = job.time_s / job.pieces;
                    const boxVol = (submitData.box?.[0] || 1) * (submitData.box?.[1] || 1) * (submitData.box?.[2] || 1);
                    const estTotal = Math.min(500, (boxVol / 100000) * 3);
                    const remainS = Math.max(0, estTotal - job.pieces) * perPiece;
                    etaText = remainS > 60
                        ? ` (≈${Math.round(remainS / 60)} min restants)`
                        : ` (≈${Math.round(remainS)}s restants)`;
                } else if (staticEta && job.pieces === 0) {
                    etaText = ` (≈${staticEta.label})`;
                }
                const progressText = job.pieces > 0
                    ? `${mainText('modeGPUPacking')} — ${job.pieces} ${mainText('pieces')}${etaText}`
                    : mainText('modeGPUPacking') + etaText;
                setCalcProgress(true, 10 + Math.min(pollCount * 5, 60), progressText, calcStartTime);
            }
            if (job.status !== 'done') {
                await new Promise(r => setTimeout(r, 2000));
            }
        } while (job.status === 'queued' || job.status === 'running');

        if (job.status === 'error') {
            throw new Error(job.error || mainText('modeGPUError'));
        }

        if (!isCurrent()) return;

        setCalcProgress(true, 80, 'Carregant resultats...', calcStartTime);
        await nextFrame();

        // Render individual pieces from the server's placement data.
        // baseGeometry must match the exact STL bytes that were sent to the
        // server (raw file bytes, or the exported selected pose) — NOT
        // state.stlGeometry, which may have been aligned/transformed client-side.
        let baseGeometry;
        if (fixedOrientation && state.selectedOrientations && state.stlStableOrientations?.length) {
            const selIdx = [...state.selectedOrientations][0];
            baseGeometry = state.stlStableOrientations[selIdx]?.geometry?.clone() || null;
        } else if (state.stlFileData instanceof ArrayBuffer) {
            baseGeometry = liveGeo || await loadSTL(state.stlFileData);
        }
        if (!baseGeometry) throw new Error('No s\'ha pogut carregar el STL');

        state.sceneManager.createBox(values.boxL, values.boxW, values.boxH);

        // Multi-tray: render the FIRST box; tray buttons re-render the scene.
        // Non-tray jobs keep the server's flat placements list.
        const isTrays = Array.isArray(job.trays) && job.trays.length > 0;
        state._trayJob = isTrays ? job : null;
        state._trayBaseGeo = isTrays ? baseGeometry : null;
        const placements = isTrays ? (job.trays[0].placements || []) : (job.placements || []);
        const trayInterlocked = isTrays
            ? (job.trays[0].interlocked ? job.trays[0].interlocked.indices : null)
            : (job.interlocked ? job.interlocked.indices : null);
        state.sceneManager.addPackedPlacements({
            placements,
            baseGeometry,
            boxL: values.boxL,
            boxW: values.boxW,
            boxH: values.boxH,
            colorCount: gpuColorCount,
            fillPct: job.fill_pct || 0,
            interlocked: trayInterlocked,
            onProgress: (p) => {
                const el = document.getElementById('gpu-piece-count');
                if (el) el.textContent = String(p.revealed);
            }
        });
        state._renderCtx = {
            placements,
            baseGeometry,
            boxL: values.boxL,
            boxW: values.boxW,
            boxH: values.boxH,
            fillPct: job.fill_pct || 0,
            interlocked: trayInterlocked,
        };

        // Compartment packing: render the cardboard partition grid between
        // the cells (Pack Studio "Partitions" — the carton that separates
        // each piece). The server reports the cell pitch + layer pitch so
        // the walls and shelves sit exactly where pieces are placed.
        if (job.compartment && job.compartment.cellL && job.compartment.cellW) {
            state.sceneManager.addPartitions({
                boxL: values.boxL,
                boxW: values.boxW,
                boxH: values.boxH,
                cellL: job.compartment.cellL,
                cellW: job.compartment.cellW,
                nLayers: job.compartment.nLayers || 1,
                layerPitch: job.compartment.layerPitch || null,
            });
        }

        // Store in history for comparison
        const run = {
            id: Date.now(),
            cellSize: parseFloat(cellSize),
            pieces: job.pieces,
            fillPct: job.fill_pct,
            timeS: job.time_s,
            boxL: values.boxL,
            boxW: values.boxW,
            boxH: values.boxH,
            stlUrl: `/api/pack/${job_id}/stl`,
            timestamp: new Date().toLocaleTimeString(),
        };
        gpuHistory.unshift(run);
        if (gpuHistory.length > MAX_GPU_HISTORY) gpuHistory.pop();

        // Render results + comparison table
        const stlUrl = `/api/pack/${job_id}/stl`;
        let comparisonHtml = '';
        if (gpuHistory.length > 1) {
            const rows = gpuHistory.map(r => {
                const isCurrent = r.id === run.id;
                const best = gpuHistory.reduce((a, b) => b.pieces > a.pieces ? b : a, gpuHistory[0]);
                const isBest = r.pieces === best.pieces && r.id === best.id;
                const cls = [isCurrent ? 'current-run' : '', isBest ? 'best-run' : ''].filter(Boolean).join(' ');
                return `<tr${cls ? ` class="${cls}"` : ''}>
                    <td>${r.timestamp}</td>
                    <td>${r.cellSize}mm</td>
                    <td><strong>${r.pieces}</strong></td>
                    <td>${r.fillPct}%</td>
                    <td>${r.timeS}s</td>
                    <td>${r.boxL}×${r.boxW}×${r.boxH}</td>
                </tr>`;
            }).join('');
            comparisonHtml = `
                <details open class="gpu-comparison">
                    <summary>${mainText('gpuComparison') || 'Comparació de resultats'}</summary>
                    <table class="comparison-table">
                        <tr><th>Hora</th><th>Cel·la</th><th>Peces</th><th>Fill</th><th>Temps</th><th>Caixa</th></tr>
                        ${rows}
                    </table>
                </details>`;
        }

        const clampedFill = Math.max(0, Math.min(100, job.fill_pct || 0));
        const isStacking = gpuMethod === 'stacking';

        // Guard: a mode/variant switch may have happened during the poll loop.
        if (!isCurrent()) return;

        elements.results.innerHTML = `
            <div class="results-hero">
                <div class="hero-number" id="gpu-piece-count" data-total="${job.pieces}">0</div>
                <div class="hero-label">${mainText('pieces')}</div>
            </div>
            ${job.interlocked && job.interlocked.count > 0 ? `
                <div class="results-warning" id="interlock-warning">
                    ${job.interlocked.count} peces no es poden extreure verticalment (entrellaçades)
                </div>
            ` : ''}
            ${Array.isArray(job.trays) && job.trays.length > 0 ? `
                <div class="results-warning" id="tray-summary">
                    ${job.trays.length} ${job.trays.length === 1 ? 'caixa' : 'caixes'} de
                    ${values.boxL}×${values.boxW}×${values.boxH}mm:
                    ${job.trays.map(t => t.pieces).join(' + ')}
                    = ${job.pieces} ${mainText('pieces')}
                </div>
                <div class="tray-selector" id="tray-selector">
                    ${job.trays.map((t, idx) => `
                        <button class="reopt-option tray-opt ${idx === 0 ? 'active' : ''}"
                                data-tray="${idx}"
                                onclick="window.selectTray(${idx})">Caixa ${idx + 1}: ${t.pieces}</button>
                    `).join('')}
                </div>
            ` : ''}
            <div class="results-cards">
                <div class="result-card">
                    <div class="card-body">
                        <div class="card-value">${job.fill_pct}%</div>
                        <div class="card-label">${mainText('fillPct')}</div>
                        <div class="fill-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${job.fill_pct}">
                            <div class="fill-bar-fill" style="width: ${clampedFill}%"></div>
                        </div>
                    </div>
                </div>
                <div class="result-card">
                    <div class="card-body">
                        <div class="card-value">${job.time_s}s</div>
                        <div class="card-label">${mainText('timeResult')}</div>
                        <div class="card-sub">${cellSize}mm · ${gpuMethod}</div>
                    </div>
                </div>
            </div>
            <div class="results-actions">
                <a class="report-link" href="${stlUrl}" target="_blank">${mainText('modeGPUStlUrl')}</a>
                <button class="replay-btn" id="replay-animation-btn" onclick="window.replayGPUAnimation()">${mainText('gpuReplayAnimation')}</button>
                <button class="reoptimize-btn" onclick="window.askReoptimize()">${mainText('reoptimize')}</button>
            </div>
            ${isStacking ? `
                <div class="reopt-horizontal" id="reopt-horizontal-group">
                    <span class="reopt-horizontal-label">Rotació horitzontal:</span>
                    <button class="reopt-option" onclick="window.reoptimizeGPU('horizontal', 0)">0°</button>
                    <button class="reopt-option" onclick="window.reoptimizeGPU('horizontal', 45)">45°</button>
                    <button class="reopt-option" onclick="window.reoptimizeGPU('horizontal', 90)">90°</button>
                    <button class="reopt-option" onclick="window.reoptimizeGPU('horizontal', 135)">135°</button>
                    <button class="reopt-option" onclick="window.reoptimizeGPU('horizontal', null)">Auto</button>
                </div>
            ` : ''}
            <div id="reoptimize-chooser" class="reoptimize-chooser" style="display: none;">
                <button class="reopt-option" onclick="window.reoptimizeGPU('accurate')">${mainText('reoptAccurate')}</button>
                <button class="reopt-option" onclick="window.reoptimizeGPU('fast')">${mainText('reoptFast')}</button>
                <button class="reopt-option" onclick="window.reoptimizeGPU('reseed')">${mainText('reoptReseed')}</button>
            </div>
            ${comparisonHtml}
        `;

        // Many trays → collapse the box selector into a dropdown so it never
        // overflows the results panel (measured, not a fixed threshold).
        maybeCollapseTraySelector();

        setCalcProgress(false, 0, '', 0);

        // Store results for the report generator. Planar stacking/compartment
        // keep state.mode = 'fast', so the report labels them as Planar.
        const meshVolume = state.stlGeometry ? computeMeshVolume(state.stlGeometry) : 0;
        const matDensity = values.materialDensity || 0;
        let estPieceWeight = 0;
        if (matDensity > 0) {
            if (values.solidPiece) {
                const volForWeight = meshVolume > 0 ? meshVolume : (values.objL * values.objW * values.objH);
                estPieceWeight = (volForWeight / 1e9) * matDensity;
            } else {
                const wallT = values.wallThickness || 2;
                const saForWeight = (state.stlGeometry ? computeSurfaceArea(state.stlGeometry) : 0) || 2 * (values.objL * values.objW + values.objL * values.objH + values.objW * values.objH);
                estPieceWeight = (saForWeight * wallT / 1e9) * matDensity;
            }
        }
        state.lastResults = {
            pieceDims: { l: values.objL, w: values.objW, h: values.objH },
            boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
            pieceCount: job.pieces,
            pieceWeight: values.objWeight,
            maxWeight: values.maxWeight,
            mode: state.mode,
            stlFileName: state.stlFileName || null,
            meshVolume: meshVolume || 0,
            materialDensity: matDensity,
            estimatedPieceWeight: estPieceWeight,
            estimatedTotalWeight: estPieceWeight * job.pieces,
            fillPct: job.fill_pct ?? null,
            interlocked: job.interlocked ?? null,
            trays: job.trays ?? null,
            gpuMethod,
        };
        state.displayCount = job.pieces;
        if (elements.reportButtons) elements.reportButtons.style.display = 'block';

        // Clear comparison when switching modes
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.dataset.mode !== 'gpu') gpuHistory = [];
            }, { once: true });
        });
    } catch (err) {
        if (!isCurrent()) return; // stale run — a mode switch already cleared the UI
        console.error('[GPU]', err);
        elements.results.innerHTML = `<p class="error-text">${mainText('modeGPUError')}: ${err.message}</p>`;
        setCalcProgress(false, 0, '', 0);
    }
}

/**
 * Replay the staggered appearance animation without re-packing.
 * Used by the "Reproduir animació" button in the GPU results panel.
 */
window.replayGPUAnimation = () => {
    state.sceneManager?.replayReveal();
};

/**
 * Multi-tray: re-render the 3D scene with the placements of the chosen box.
 */
window.selectTray = (idx) => {
    idx = parseInt(idx, 10);
    const job = state._trayJob;
    if (!job || !Array.isArray(job.trays) || !job.trays[idx]) return;
    const tray = job.trays[idx];
    state._trayIdx = idx;
    document.querySelectorAll('#tray-selector .tray-opt').forEach((btn, i) => {
        btn.classList.toggle('active', i === idx);
    });
    const select = document.querySelector('#tray-selector select.tray-select');
    if (select) select.value = String(idx);
    const hero = document.getElementById('gpu-piece-count');
    if (hero) {
        hero.dataset.total = String(tray.pieces);
        hero.textContent = String(tray.pieces);
    }
    if (!state._trayBaseGeo) return;
    state.sceneManager.clearPieces();
    const trayBox = {
        boxL: parseFloat(elements.boxLength?.value) || 385,
        boxW: parseFloat(elements.boxWidth?.value) || 285,
        boxH: parseFloat(elements.boxHeight?.value) || 150,
    };
    state.sceneManager.addPackedPlacements({
        placements: tray.placements || [],
        baseGeometry: state._trayBaseGeo,
        boxL: trayBox.boxL,
        boxW: trayBox.boxW,
        boxH: trayBox.boxH,
        colorCount: parseInt(elements.optPieceColors?.value) || 10,
        fillPct: tray.fill_pct || 0,
        interlocked: tray.interlocked ? tray.interlocked.indices : null,
    });
    state._renderCtx = {
        placements: tray.placements || [],
        baseGeometry: state._trayBaseGeo,
        boxL: trayBox.boxL,
        boxW: trayBox.boxW,
        boxH: trayBox.boxH,
        fillPct: tray.fill_pct || 0,
        interlocked: tray.interlocked ? tray.interlocked.indices : null,
    };
};

/**
 * Show the auto-mode explanation popup when the user enables it.
 */
function showAutoModePopup() {
    const popup = document.getElementById('auto-mode-popup');
    if (popup) popup.style.display = 'flex';
}

/**
 * Confirm the bulk start popup: apply the chosen mode and start the sim.
 */
function confirmBulkStartPopup() {
    const popup = document.getElementById('bulk-start-popup');
    const selected = document.querySelector('input[name="bulk-mode"]:checked');
    const fixedInput = document.getElementById('bulk-fixed-pieces');

    if (selected && selected.value === 'auto') {
        state._programmaticBulkChange = true;
        if (elements.autoCapacity) elements.autoCapacity.checked = true;
        if (elements.autoCapacity) elements.autoCapacity.dispatchEvent(new Event('change'));
        state._programmaticBulkChange = false;
    } else {
        state._programmaticBulkChange = true;
        if (elements.autoCapacity) elements.autoCapacity.checked = false;
        if (elements.autoCapacity) elements.autoCapacity.dispatchEvent(new Event('change'));
        state._programmaticBulkChange = false;
        if (fixedInput && elements.maxPieces) {
            const n = Math.max(1, parseInt(fixedInput.value) || 100);
            elements.maxPieces.value = n;
        }
    }
    state.bulkConfigSet = true;
    if (popup) popup.style.display = 'none';
    startSimulation();
}

/**
 * Show the re-optimize chooser (accurate / fast / different seed).
 */
window.askReoptimize = () => {
    const chooser = document.getElementById('reoptimize-chooser');
    if (chooser) chooser.style.display = chooser.style.display === 'none' ? 'flex' : 'none';
};

/**
 * Re-run the GPU calculation with the chosen accuracy/randomizer option.
 * `option` may be 'accurate' | 'fast' | 'reseed' | 'horizontal'; for
 * 'horizontal' the second argument is the requested in-plane rotation angle
 * (0/45/90/135°) or null for the automatic best.
 */
window.reoptimizeGPU = (option, angle = null) => {
    const chooser = document.getElementById('reoptimize-chooser');
    if (chooser) chooser.style.display = 'none';
    const calcStartTime = performance.now();
    if (option === 'horizontal') {
        handleGPUCalculate(calcStartTime, { horizontalAngle: angle });
        return;
    }
    handleGPUCalculate(calcStartTime, { accuracy: option });
};

/**
 * Collapse the multi-box tray selector into a dropdown when the tray buttons
 * would overflow the results panel width.
 */
function maybeCollapseTraySelector() {
    const sel = document.getElementById('tray-selector');
    if (!sel || sel.querySelector('select')) return;
    const btns = Array.from(sel.querySelectorAll('.tray-opt'));
    if (btns.length < 2) return;
    const top0 = btns[0].offsetTop;
    if (!btns.some(b => b.offsetTop > top0 + 1)) return;
    const current = btns.findIndex(b => b.classList.contains('active'));
    const options = btns.map((b, i) => `
                <option value="${i}">${b.textContent}</option>
            `).join('');
    sel.innerHTML = `
        <select class="tray-select" onchange="window.selectTray(this.value)">
            ${options}
        </select>`;
    if (current >= 0) sel.querySelector('select').value = String(current);
}

/**
 * Ask the user how many pieces to pack (multi-box mode) before starting.
 */
let mtPopupCallback = null;
function showMtPopup(onConfirm) {
    const input = document.getElementById('mt-popup-total');
    if (input) {
        input.value = parseInt(elements.multitrayTotal?.value, 10) || 1000;
        input.focus();
        input.select();
    }
    mtPopupCallback = onConfirm;
    const popup = document.getElementById('mt-popup');
    if (popup) popup.style.display = 'flex';
}

function hideMtPopup() {
    const popup = document.getElementById('mt-popup');
    if (popup) popup.style.display = 'none';
    mtPopupCallback = null;
}

/**
 * Handle calculate button click (optimized mode)
 */
async function handleCalculate() {
    const calcGen = ++calcGeneration;
    const isCurrent = () => calcGeneration === calcGen;

    if (state.calcAbortController) {
        state.calcAbortController.abort();
    }
    const abortControllerRef = new AbortController();
    state.calcAbortController = abortControllerRef;
    const abortSignal = abortControllerRef.signal;

    const calcStartTime = performance.now();

    // ── GPU Voxel Mode (Bulk → Optimitzat) ──
    if (state.mode === 'gpu') {
        await handleGPUCalculate(calcStartTime);
        return;
    }

    // ── Planar stacking — server-side voxel packer. Reuse the GPU handler
    // (same /api/pack flow + placements rendering).
    if (state.mode === 'fast' && state.planarVariant === 'stacking') {
        await handleGPUCalculate(calcStartTime, { method: 'stacking' });
        return;
    }

    // ── Planar multi-tray — same server-side voxel packer, but pack the
    // requested piece count into as many boxes as needed (stacking per tray).
    if (state.mode === 'fast' && state.planarVariant === 'multitray') {
        showMtPopup((totalPieces) => {
            if (elements.multitrayTotal) elements.multitrayTotal.value = String(totalPieces);
            handleGPUCalculate(calcStartTime, { method: 'multitray', totalPieces });
        });
        return;
    }

    // ── Planar compartment — fast client-side grid + cardboard partitions.
    // Packing the box as a simple grid (same math as Graella, with the
    // cardboard thickness as the inter-piece gap) is instant and the cells
    // are exactly where the dividers go. Falls through to the grid path
    // below, then renders the partitions from the grid layout.
    const isCompartment = state.mode === 'fast' && state.planarVariant === 'compartment';

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

        const isAutoStrategy = false;

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

        // Compartment mode: count cells with the cardboard thickness as the
        // inter-piece gap, and only the user's chosen pose. Compartments are
        // rectangles, so the piece's footprint can be swapped 90° in-plane
        // (L↔W) — offer both and let the calculator pick the denser grid.
        if (isCompartment) {
            const card = Math.max(0, values.cardboardMm || 0);
            values.packingGap = card;
            let poseGeom = null;
            if (state.selectedOrientations?.size === 1 && state.stlStableOrientations?.length) {
                const sel = [...state.selectedOrientations][0];
                poseGeom = state.stlStableOrientations[sel]?.geometry || null;
            }
            if (poseGeom) {
                const dims = extractDimensions(poseGeom);
                values.objL = dims.length;
                values.objW = dims.width;
                values.objH = dims.height;
                orientationOverrides = [
                    { dims: [dims.length, dims.width, dims.height], perm: [0, 1, 2], name: 'Orientació seleccionada' },
                    { dims: [dims.width, dims.length, dims.height], perm: [0, 1, 2], name: 'Orientació seleccionada 90°', rotated: true },
                ];
            }
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

        // Show results immediately — unified grid-based approach guarantees correct count
        setCalcProgress(true, 4, 'Mostrant resultats...', calcStartTime);
        if (!isCurrent()) return; // mode/variant switched while calculating
        elements.results.innerHTML = result.summary;
        elements.results.classList.add('fade-in');

        // Update 3D visualization
        setCalcProgress(true, 5, 'Preparant geometria 3D...', calcStartTime);
        await nextFrame();
        if (!isCurrent()) return;
        state.sceneManager.clearPieces();

        // Always create box even if no data fits
        state.sceneManager.createBox(values.boxL, values.boxW, values.boxH);

        if (result.data) {
            const [pieceL, pieceW, pieceH] = getPieceDimensions(result.data);
            const [nx, ny, nz] = getDistribution(result.data);

            let drawn = { count: 0 };
            let realDistributionText = null;

            if (nx > 0 && ny > 0 && nz > 0) {

                // Decide what geometry to draw
                setCalcProgress(true, 6, 'Provant orientacions...', calcStartTime);
                await nextFrame();
                if (state.stlGeometry) {
                    if (state.mode === 'fast' && isCompartment) {
                        // ── Compartment: strict grid in the chosen pose, with
                        // the cardboard thickness as the gap, then render the
                        // cardboard divider walls/shelves at the exact cells.
                        setCalcProgress(true, 8, 'Generant compartiment (graella + cartró)...', calcStartTime);
                        await nextFrame();

                        const card = Math.max(0, values.cardboardMm || 0);
                        let poseGeom = null;
                        if (state.selectedOrientations?.size === 1 && state.stlStableOrientations?.length) {
                            const sel = [...state.selectedOrientations][0];
                            poseGeom = state.stlStableOrientations[sel]?.geometry || null;
                        }
                        // The calculator picks between the 0° and 90° in-plane
                        // orientations; rotate the geometry to match the winner
                        // (pieceL/pieceW come from the winning dims).
                        const poseDims = poseGeom ? extractDimensions(poseGeom) : null;
                        const rotated90 = !!poseDims &&
                            Math.abs(pieceL - poseDims.width) < 0.5 &&
                            Math.abs(pieceW - poseDims.length) < 0.5;
                        const orientedGeometry = (poseGeom || state.stlGeometry).clone();
                        if (rotated90) applyYawToGeometry(orientedGeometry, 90);
                        recenterGeometry(orientedGeometry);
                        orientedGeometry.computeVertexNormals();

                        // getDistribution returns [fitL, fitW, fitH] = [X, Z, Y]
                        // as [nx, ny, nz] (ny = Z count, nz = Y layers), but
                        // addPackedSTLPieces expects [nx=X, ny=Y, nz=Z].
                        drawn = state.sceneManager.addPackedSTLPieces({
                            stlGeometry: orientedGeometry,
                            pieceL, pieceW, pieceH,
                            nx: nx, ny: nz, nz: ny,
                            maxDraw: 500,
                            packingGap: card,
                            colorCount: values.colorCount,
                            boxL: values.boxL,
                            boxW: values.boxW,
                            boxH: values.boxH,
                            strictGeometryCheck: true
                        });

                        if (drawn && drawn.count > 0 && nx > 0 && ny > 0 && nz > 0) {
                            state.sceneManager.addPartitions({
                                boxL: values.boxL,
                                boxW: values.boxW,
                                boxH: values.boxH,
                                cellL: pieceL + card,
                                cellW: pieceW + card,
                                nLayers: nz,   // nz = layer count (Y)
                                layerPitch: pieceH + card,
                                thickness: Math.max(0.5, card),
                            });
                            // L×W×H order for the summary (nx=L, ny=W, nz=H)
                            realDistributionText = `${nx}×${ny}×${nz}`;
                        }
                    } else if (state.mode === 'fast') {
                        setCalcProgress(true, 8, 'Avaluant orientacions (Graella Optima)...', calcStartTime);
                        await nextFrame();

                        const selectedSet = state.selectedOrientations;
                        const hasExplicitSelection = selectedSet && selectedSet.size === 1;

                        const yawAngles = values.allowRotation ? [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330] : [0];
                        const orientationPool = [];

                        if (!hasExplicitSelection) {
                            const baseGeometry = state.stlGeometry.clone();
                            alignToStableBase(baseGeometry);

                            for (const yaw of yawAngles) {
                                if (abortSignal.aborted) throw new DOMException('Aborted', 'AbortError');
                                const g = baseGeometry.clone();
                                applyYawToGeometry(g, yaw);
                                recenterGeometry(g);
                                g.computeBoundingBox();
                                const bb = g.boundingBox;
                                const sx = bb.max.x - bb.min.x;
                                const sy = bb.max.y - bb.min.y;
                                const sz = bb.max.z - bb.min.z;
                                if (sx > values.boxL + 0.1 || sz > values.boxW + 0.1 || sy > values.boxH + 0.1) continue;
                                orientationPool.push({ geometry: g, yaw, name: `${yaw} deg` });
                            }
                        }

                        for (let bi = 0; bi < (state.stlStableOrientations || []).length; bi++) {
                            if (hasExplicitSelection && !selectedSet.has(bi)) continue;
                            const stableBase = state.stlStableOrientations[bi];
                            if (!stableBase.geometry) continue;
                            for (const yaw of yawAngles) {
                                if (abortSignal.aborted) throw new DOMException('Aborted', 'AbortError');
                                const g = stableBase.geometry.clone();
                                if (yaw !== 0) {
                                    applyYawToGeometry(g, yaw);
                                    recenterGeometry(g);
                                }
                                g.computeBoundingBox();
                                const bb = g.boundingBox;
                                const sx = bb.max.x - bb.min.x;
                                const sy = bb.max.y - bb.min.y;
                                const sz = bb.max.z - bb.min.z;
                                if (sx > values.boxL + 0.1 || sz > values.boxW + 0.1 || sy > values.boxH + 0.1) continue;
                                const isDup = orientationPool.some(p => {
                                    p.geometry.computeBoundingBox();
                                    const pb = p.geometry.boundingBox;
                                    return Math.abs((pb.max.x - pb.min.x) - sx) < 0.5 &&
                                           Math.abs((pb.max.y - pb.min.y) - sy) < 0.5 &&
                                           Math.abs((pb.max.z - pb.min.z) - sz) < 0.5;
                                });
                                if (!isDup) orientationPool.push({ geometry: g, yaw, name: `base+${yaw} deg` });
                            }
                        }

                        console.log(`[OptimalGrid] ${orientationPool.length} orientation candidates`);

                        if (orientationPool.length === 0) {
                            drawn = { count: 0 };
                        } else {
                            const primaryGeom = orientationPool[0].geometry;
                            const altPool = orientationPool.slice(1);

                            setCalcProgress(true, 20, 'Cercant graella optima BVH...', calcStartTime);
                            await nextFrame();

                            drawn = await state.sceneManager.addPackedSTLOptimalGrid({
                                stlGeometry: primaryGeom,
                                orientationPool: altPool.length > 0 ? altPool : null,
                                maxDraw: 500,
                                packingGap: values.packingGap,
                                colorCount: values.colorCount,
                                boxL: values.boxL,
                                boxW: values.boxW,
                                boxH: values.boxH,
                                searchEffort: values.placementSearchEffort,
                                dryRun: false,
                                abortSignal,
                                onProgress: ({ placed, maxTry, phase }) => {
                                    setCalcProgress(true, 20 + 70 * 0.5, `Graella Optima: ${phase || 'avaluant...'}`, calcStartTime);
                                }
                            });

                            if (drawn.gridInfo) {
                                const gi = drawn.gridInfo;
                                const gridDesc = gi.isBrick
                                    ? `brick(${gi.nxEven}/${gi.nxOdd}x${gi.nz})`
                                    : `${gi.nx}x${gi.nz}`;
                                realDistributionText = `${gridDesc}x${gi.nLayers}`;
                            }
                        }
                    } else if (values.heightMapNesting) {
                        setCalcProgress(true, 8, `Avaluant orientacions...`, calcStartTime);
                        await nextFrame();

                        const yawAngles = values.allowRotation ? Array.from({ length: 36 }, (_, i) => i * 10) : [0];
                        const orientationPool = [];

                        const baseSources = [];
                        const selectedSet = state.selectedOrientations;
                        const hasExplicitSelection = selectedSet && selectedSet.size === 1;
                        if (state.stlStableOrientations && state.stlStableOrientations.length > 0) {
                            for (let i = 0; i < state.stlStableOrientations.length; i++) {
                                const sb = state.stlStableOrientations[i];
                                if (selectedSet && !selectedSet.has(i)) continue;
                                if (sb.geometry) baseSources.push(sb.geometry);
                            }
                        }
                        if (baseSources.length === 0) {
                            const fallback = state.stlGeometry.clone();
                            alignToStableBase(fallback);
                            recenterGeometry(fallback);
                            baseSources.push(fallback);
                        }

                        // Only explore axis permutations when the user has not
                        // explicitly picked one orientation — the user's
                        // selection must be respected.
                        if (!hasExplicitSelection) {
                            const perms = [[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]];
                            for (const perm of perms) {
                                const g = state.stlGeometry.clone();
                                applyPermutation(g, perm);
                                recenterGeometry(g);
                                g.computeBoundingBox();
                                const bb = g.boundingBox;
                                const sx = bb.max.x - bb.min.x;
                                const sy = bb.max.y - bb.min.y;
                                const sz = bb.max.z - bb.min.z;
                                if (sx > values.boxL + 0.1 || sz > values.boxW + 0.1 || sy > values.boxH + 0.1) continue;
                                const isDup = baseSources.some(bs => {
                                    bs.computeBoundingBox();
                                    const pb = bs.boundingBox;
                                    const psx = pb.max.x - pb.min.x;
                                    const psy = pb.max.y - pb.min.y;
                                    const psz = pb.max.z - pb.min.z;
                                    return Math.abs(psx - sx) < 0.5 && Math.abs(psy - sy) < 0.5 && Math.abs(psz - sz) < 0.5;
                                });
                                if (!isDup) baseSources.push(g);
                            }
                        }

                        for (const baseGeom of baseSources) {
                            for (const yaw of yawAngles) {
                                if (abortSignal.aborted) throw new DOMException('Aborted', 'AbortError');
                                const g = baseGeom.clone();
                                if (yaw !== 0) {
                                    applyYawToGeometry(g, yaw);
                                    recenterGeometry(g);
                                }
                                g.computeBoundingBox();
                                const bb = g.boundingBox;
                                const sx = bb.max.x - bb.min.x;
                                const sy = bb.max.y - bb.min.y;
                                const sz = bb.max.z - bb.min.z;
                                if (sx > values.boxL + 0.1 || sz > values.boxW + 0.1 || sy > values.boxH + 0.1) continue;
                                const isDup = orientationPool.some(p => {
                                    p.geometry.computeBoundingBox();
                                    const pb = p.geometry.boundingBox;
                                    return Math.abs((pb.max.x - pb.min.x) - sx) < 0.5 &&
                                           Math.abs((pb.max.y - pb.min.y) - sy) < 0.5 &&
                                           Math.abs((pb.max.z - pb.min.z) - sz) < 0.5;
                                });
                                if (!isDup) orientationPool.push({ geometry: g, yaw, name: `base${baseSources.indexOf(baseGeom)}+${yaw}` });
                            }
                        }

                        let bestGeom = null;
                        let bestCap = 0;

                        for (const o of orientationPool) {
                            o.geometry.computeBoundingBox();
                            const bb = o.geometry.boundingBox;
                            const sx = bb.max.x - bb.min.x;
                            const sy = bb.max.y - bb.min.y;
                            const sz = bb.max.z - bb.min.z;
                            const cap = Math.floor(values.boxL / sx) * Math.floor(values.boxW / sz) * Math.floor(values.boxH / sy);
                            if (cap > bestCap) {
                                bestCap = cap;
                                bestGeom = o.geometry;
                            }
                        }

                        console.log(`[HeightMap] ${orientationPool.length} orientations, best grid cap=${bestCap}`);

                        if (!bestGeom) {
                            drawn = { count: 0 };
                        } else {
                            drawn = await state.sceneManager.addPackedSTLHeightMapAsync({
                                stlGeometry: bestGeom,
                                orientationPool: orientationPool.length > 1 ? orientationPool : null,
                                useMixedOrientations: orientationPool.length > 1,
                                maxDraw: 2000,
                                maxTry: Math.min(10000, Math.max(1000, bestCap * 5)),
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
                                stackingQuality: values.stackingQuality,
                                dryRun: false,
                                abortSignal,
                                onProgress: ({ placed, maxTry }) => {
                                    const t = maxTry > 0 ? (placed / maxTry) : 0;
                                    setCalcProgress(true, 70 + 25 * t, mainText('placingPiecesProgress', { placed: Math.floor(placed), maxTry }), calcStartTime);
                                }
                            });
                        }
                    } else {
                    setCalcProgress(true, 8, `Cercant millor orientacio...`, calcStartTime);
                    await nextFrame();

                    const best = result.data.bestOrientation || {};
                    const perm = (best.perm && Array.isArray(best.perm) && best.perm.length === 3)
                        ? best.perm
                        : [0, 1, 2];

                    const orientedGeometry = state.stlGeometry.clone();
                    alignToStableBase(orientedGeometry);
                    applyPermutation(orientedGeometry, perm);
                    recenterGeometry(orientedGeometry);

                    console.log(`[STL] Best orientation: ${best.name}, perm=${perm}, dims=[${pieceL.toFixed(1)}, ${pieceW.toFixed(1)}, ${pieceH.toFixed(1)}], grid=${nx}x${nz}x${ny}`);

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
            if (typeof drawn === 'object' && drawn?.distributionText && !isCompartment) {
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
            // Auto-gravity disabled: convex hull colliders are inherently larger than
            // the mesh, causing clearPieces→recreate to push pieces apart and float.
            // The heightmap InstancedMesh rendering is already optimal and correct.
            console.log(`[GravityRefine] autoGravity=disabled, strategy=${values.placementStrategy}, count=${displayCount}`);

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

            // Build final summary (calculator result is the correct count — unified grid-based approach)
            const finalConfig = { ...result.data.bestOrientation };
            if (realDistributionText) {
                finalConfig.distribution = realDistributionText;
            }

            const finalSummary = createSummary(displayCount, finalConfig, result.data.allOrientations, {
                volumeTheoreticalMax: result.data.volumeTheoreticalMax,
                meshVolumeMM3: meshVolume > 0 ? meshVolume : null,
                estimatedPieceWeight: estPieceWeight,
                estimatedTotalWeight: estTotalWeight,
                materialName: matName,
                labels: getCalculatorLabels(),
            });
            if (!isCurrent()) return; // stale run — a mode switch already cleared the UI
            elements.results.innerHTML = finalSummary + `
                <button class="reoptimize-btn" onclick="document.querySelector('#calculate-btn').click()">
                    ${mainText('reoptimize') || 'Re-optimitzar'}
                </button>
            `;
            elements.results.classList.add('fade-in');

             state.lastResults = {
                pieceDims: { l: values.objL, w: values.objW, h: values.objH },
                boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
                pieceCount: displayCount,
                pieceWeight: values.objWeight,
                maxWeight: values.maxWeight,
                mode: state.mode,
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
                // Only show gravity button for physics-assisted (experimental).
                // Stable-contact uses heightmap rendering which is already optimal.
                if (elements.applyGravityBtn) {
                    elements.applyGravityBtn.style.display =
                        values.placementStrategy === 'physics-assisted' ? 'block' : 'none';
                }
            }

        const elapsed = ((performance.now() - calcStartTime) / 1000).toFixed(1);
        console.timeEnd('[PackAssist] Càlcul total');
        console.log(`[PackAssist] Temps total: ${elapsed}s`);
        setCalcProgress(true, 100, `Completat! (${elapsed}s)`);
        setTimeout(() => setCalcProgress(false, 0), 1200);
    } catch (err) {
        // A mode switch mid-calc already cleared the UI — don't repopulate it.
        if (isCurrent()) {
            if (err?.name === 'AbortError') {
                elements.results.innerHTML = `<p class="placeholder-text">${mainText('calcCancelled')}</p>`;
                state.sceneManager?.clearPieces();
                if (elements.reportButtons) elements.reportButtons.style.display = 'none';
                if (elements.applyGravityBtn) elements.applyGravityBtn.style.display = 'none';
            } else {
                console.error(err);
                elements.results.innerHTML = `<p class="error-text">Error: ${err.message}</p>`;
            }
            setCalcProgress(false, 0);
        }
    } finally {
        if (state.calcAbortController === abortControllerRef) state.calcAbortController = null;
    }
}


function stopGravitySimulation() {
    if (!state.gravitySimulation) return;
    const sim = state.gravitySimulation;
    sim.running = false;
    if (sim.jitterInterval) {
        clearInterval(sim.jitterInterval);
        sim.jitterInterval = null;
    }
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
    const colorCount = Math.min(pieceColors.length || 1, (state.mode !== 'bulk'
        ? parseInt(elements.optPieceColors?.value) || 10
        : parseInt(elements.pieceColors?.value) || 10));

    // Convex hull shrink: 0.97 prevents explosions from hull-mesh mismatch
    // while still providing adequate support for stacked pieces.
    const hullScale = 0.97;

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
    const { lockRotations = false, settleAngularDamping = 3.0, settleLinearDamping = 1.0 } = options;
    console.log(`[GravityRefine] applyGravityTest — lockRotations=${lockRotations}`);
    if (!state.sceneManager?.lastPlacement) return;

    if (!state.gravitySimulation) {
        const sim = await initGravitySimulation();
        console.log(`[GravityRefine] init: ${sim?.physics?.meshBodies?.length || 0} bodies`);
        if (!sim) return;
        state.gravitySimulation = sim;
    }

    const sim = state.gravitySimulation;
    sim.running = true;
    sim.frameCount = 0;
    sim.jitterInterval = null;
    sim.physics.setGravity(-9810);
    sim.physics.lockAllRotations(true);

    if (elements.simulationStatus) {
        elements.simulationStatus.textContent = 'Aplicant gravetat...';
        elements.simulationStatus.style.display = 'block';
    }

    // ── Invisible warm-up: resolve convex-hull interpenetration ──
    // Pieces placed by the heightmap algorithm touch tightly. Convex hulls are
    // inherently larger than the real mesh (they wrap concavities), so even with
    // hullScale=0.93 there can be small overlaps. Running physics steps WITHOUT
    // animation lets Rapier push overlapping pieces apart gently before the user
    // sees anything — no visual explosion.
    sim.physics.setAllFriction(0.1);
    for (const { body } of sim.physics.meshBodies) {
        if (!body || !body.isValid?.()) continue;
        body.setLinearDamping(5.0);   // high damping suppresses bounce during warm-up
        body.setAngularDamping(50.0);
    }
    sim.physics.warmUp(120); // ~0.5s of physics time, resolves overlaps instantly
    console.log(`[GravityRefine] Warm-up done — overlaps resolved`);

    // ── Configure for visible settling ──
    // Stable-contact: just gravity settle — no vibration (pieces are already optimally
    // placed by the heightmap, vibration only pushes them OUT of position).
    // Physics-assisted: short vibration then settle.
    sim.physics.settleVelocityThreshold = lockRotations ? 10.0 : 5.0;
    sim.physics.settleFramesRequired = lockRotations ? 15 : 30;

    if (lockRotations) {
        sim.phase = 'settling';
        sim.physics.setAllFriction(0.3);
        for (const { body } of sim.physics.meshBodies) {
            if (!body || !body.isValid?.()) continue;
            body.setLinearDamping(settleLinearDamping);
            body.setAngularDamping(settleAngularDamping);
        }
    } else {
        // Physics-assisted: short vibration first
        sim.phase = 'vibrating';
        for (const { body } of sim.physics.meshBodies) {
            if (!body || !body.isValid?.()) continue;
            body.setLinearDamping(1.0);
            body.setAngularDamping(3.0);
        }
        sim.physics.vibrationAmplitude = 1.0;
        sim.physics.vibrationFrequency = 8.0;
        sim.physics.vibrationNoise = 0.2;
        sim.physics.startVibration(2000);
    }

    const finalizeGravity = () => {
        sim.phase = 'done';
        sim.running = false;
        if (sim.jitterInterval) { clearInterval(sim.jitterInterval); sim.jitterInterval = null; }
        if (sim.animationId) cancelAnimationFrame(sim.animationId);
        sim.physics.settleVelocityThreshold = 5.0;
        sim.physics.settleFramesRequired = 60;
        const insideCount = sim.physics.countPiecesInBox();
        console.log(`[GravityRefine] Settled — ${insideCount} pieces (was ${state.displayCount})`);
        state.displayCount = insideCount;
        if (state.lastResults) state.lastResults.pieceCount = insideCount;
        if (elements.simulationStatus) {
            elements.simulationStatus.textContent = mainText('gravitySettled', { count: insideCount });
        }
    };

    sim.physics.onSettled = (count) => {
        if (sim.phase === 'settling') {
            finalizeGravity();
        }
    };

    const animate = () => {
        if (!sim.running) return;
        sim.frameCount++;
        sim.physics.step();

        // Safety timeout: 5 seconds (~300 frames)
        if (sim.frameCount > 300) {
            sim.running = false;
            if (sim.jitterInterval) { clearInterval(sim.jitterInterval); sim.jitterInterval = null; }
            sim.physics.settleVelocityThreshold = 5.0;
            sim.physics.settleFramesRequired = 60;
            const insideCount = sim.physics.countPiecesInBox();
            state.displayCount = insideCount;
            if (state.lastResults) state.lastResults.pieceCount = insideCount;
            if (elements.simulationStatus) {
                elements.simulationStatus.textContent = mainText('gravityTimeout', { count: insideCount });
            }
            console.log(`[GravityRefine] Timeout — ${insideCount} pieces`);
            return;
        }

        // Vibration-end → transition to settling (physics-assisted only)
        if (sim.phase === 'vibrating' && !sim.physics.isVibrating) {
            sim.phase = 'settling';
            sim.physics.settledCount = 0;
            if (!lockRotations) sim.physics.lockAllRotations(false);
            sim.physics.setAllFriction(0.3);
            for (const { body } of sim.physics.meshBodies) {
                if (!body || !body.isValid?.()) continue;
                body.setLinearDamping(settleLinearDamping);
                body.setAngularDamping(settleAngularDamping);
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
    // If the user hasn't configured pieces/auto mode yet, ask first
    if (!state.bulkConfigSet) {
        const popup = document.getElementById('bulk-start-popup');
        if (popup) {
            const fixedGroup = document.getElementById('bulk-fixed-pieces-group');
            const autoRadio = document.querySelector('input[name="bulk-mode"][value="auto"]');
            const fixedRadio = document.querySelector('input[name="bulk-mode"][value="fixed"]');
            // Default to the current advanced config
            if (elements.autoCapacity?.checked && autoRadio) {
                autoRadio.checked = true;
                if (fixedGroup) fixedGroup.style.display = 'none';
            } else if (fixedRadio) {
                fixedRadio.checked = true;
                if (fixedGroup) fixedGroup.style.display = 'block';
                const fixedInput = document.getElementById('bulk-fixed-pieces');
                if (fixedInput) fixedInput.value = elements.maxPieces?.value || 100;
            }
            popup.style.display = 'flex';
            return;
        }
    }

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
            message: 'Simulació pausada'
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
    const headerSubtitleEl = document.querySelector('.app-bar-subtitle');
    const navLink = document.querySelector('.nav-link');
    if (headerSubtitleEl) headerSubtitleEl.textContent = t.headerSubtitle;
    if (navLink) navLink.textContent = t.historyLink;
    
    // Mode buttons
    const modeBtns = document.querySelectorAll('.mode-btn');
    modeBtns.forEach(btn => {
        const mode = btn.dataset.mode;
        const desc = btn.querySelector('.mode-desc');
        if (mode === 'fast') {
            btn.childNodes[0].textContent = t.modePlanar + '\n';
            if (desc) {
                if (state.planarVariant === 'grid') desc.textContent = t.planarGridDesc;
                else if (state.planarVariant === 'stacking') desc.textContent = t.planarStackingDesc;
                else if (state.planarVariant === 'compartment') desc.textContent = t.planarCompartmentDesc;
                else desc.textContent = t.modePlanarDesc;
            }
        } else if (mode === 'bulk') {
            btn.childNodes[0].textContent = t.modeBulk + '\n';
            if (desc) desc.textContent = t.modeBulkDesc;
        }
    });

    // Bulk variant sub-selector labels
    document.querySelectorAll('#bulk-variant-selector .variant-btn').forEach(btn => {
        const variant = btn.dataset.variant;
        if (variant === 'gravity') {
            btn.textContent = t.modeBulkGravity;
        } else if (variant === 'optimized') {
            btn.textContent = t.modeBulkOptimized;
        }
    });

    // Planar variant sub-selector labels (Graella / Apilat / Compartiment)
    document.querySelectorAll('#planar-variant-selector .variant-btn').forEach(btn => {
        const variant = btn.dataset.variant;
        if (variant === 'grid') {
            btn.textContent = t.planarGrid;
        } else if (variant === 'stacking') {
            btn.textContent = t.planarStacking;
        } else if (variant === 'compartment') {
            btn.textContent = t.planarCompartment;
        }
    });
    
    // Section titles
    const bulkSection = document.querySelector('.bulk-section > h2');
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
    if (optColorsLabel) optColorsLabel.textContent = t.colorCount;
    const packingGapLabel = document.querySelector('label[for="packing-gap"]');
    if (packingGapLabel) packingGapLabel.textContent = t.packingGap;
    const dropHeightLabel = document.querySelector('label[for="drop-height"]');
    if (dropHeightLabel) dropHeightLabel.textContent = t.dropHeight;
    const maxPiecesLabel = document.querySelector('label[for="max-pieces"]');
    if (maxPiecesLabel) maxPiecesLabel.textContent = t.maxPieces;
    const dropIntervalLabel = document.querySelector('label[for="drop-interval"]');
    if (dropIntervalLabel) dropIntervalLabel.textContent = t.dropInterval;
    const vibrationFrequencyLabel = document.querySelector('label[for="vibration-frequency"]');
    if (vibrationFrequencyLabel) vibrationFrequencyLabel.textContent = t.vibFreq;
    const vibrationAmplitudeLabel = document.querySelector('label[for="vibration-amplitude"]');
    if (vibrationAmplitudeLabel) vibrationAmplitudeLabel.textContent = t.vibAmp;
    const vibrationNoiseLabel = document.querySelector('label[for="vibration-noise"]');
    if (vibrationNoiseLabel) vibrationNoiseLabel.textContent = t.vibNoise;
    const pieceColorsLabel = document.querySelector('label[for="piece-colors"]');
    if (pieceColorsLabel) pieceColorsLabel.textContent = t.colorCount;
    
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
    if (placeholder) placeholder.textContent = state.mode === 'bulk' ? t.bulkPlaceholder : t.placeholder;
    
    // Also sync the report language radio
    const radioToCheck = document.querySelector(`input[name="report-lang"][value="${state.language}"]`);
    if (radioToCheck) radioToCheck.checked = true;

    // Set html lang attribute
    document.documentElement.lang = state.language === 'ca' ? 'ca' : 'en';
}

/**
 * Open report preview modal
 */
const REPORT_STORAGE_KEY = 'packassist.reportData';

/**
 * Add one packaging-component row to the report data form.
 */
function addReportItemRow(item = {}) {
    const container = document.getElementById('rp-items');
    if (!container) return;
    const row = document.createElement('div');
    row.className = 'rp-item-row';
    const mk = (ph, val, type = 'text') => {
        const inp = document.createElement('input');
        inp.type = type;
        inp.step = type === 'number' ? '0.01' : undefined;
        inp.placeholder = ph;
        inp.value = val != null ? String(val) : '';
        return inp;
    };
    row.append(
        mk('Descripció', item.desc),
        mk('Material', item.material),
        mk('L', item.l, 'number'),
        mk('W', item.w, 'number'),
        mk('H', item.h, 'number'),
        mk('Qty', item.qty, 'number'),
        mk('€/unit', item.price, 'number'),
    );
    const del = document.createElement('button');
    del.type = 'button';
    del.className = 'rp-item-remove';
    del.textContent = '×';
    del.title = 'Eliminar component';
    del.addEventListener('click', () => {
        row.remove();
        saveReportForm();
    });
    row.append(del);
    container.appendChild(row);
}

function renderReportItems(items) {
    const container = document.getElementById('rp-items');
    if (!container) return;
    container.innerHTML = '';
    if (items && items.length) {
        items.forEach(it => addReportItemRow(it));
    } else {
        addReportItemRow();
    }
}

/**
 * Populate the report data form from localStorage (saved once the user
 * fills it) — pre-filled values are never clobbered on later opens.
 */
function loadReportForm() {
    let saved = null;
    try {
        saved = JSON.parse(localStorage.getItem(REPORT_STORAGE_KEY) || 'null');
    } catch (e) { /* ignore corrupted storage */ }
    const s = saved || {};
    const set = (id, v) => {
        const el = document.getElementById(id);
        if (el && v != null && v !== '') el.value = v;
    };
    const part = s.part || {};
    const supplier = s.supplier || {};
    const cost = s.cost || {};
    const pallet = s.pallet || {};
    const approvals = s.approvals || {};
    set('rp-part-number', part.number);
    set('rp-project', part.project);
    set('rp-revision', part.revision);
    set('rp-material', part.material);
    set('rp-supplier-name', supplier.name);
    set('rp-supplier-address', supplier.address);
    set('rp-supplier-contact', supplier.contact);
    set('rp-supplier-phone', supplier.phone);
    set('rp-supplier-email', supplier.email);
    set('rp-supplier-function', supplier.function);
    set('rp-box-cost', cost.boxCost);
    set('rp-packaging-cost', cost.packagingCost);
    set('rp-freight-cost', cost.freightCost);
    set('rp-cost-part', cost.costPerPart);
    set('rp-pallet-l', pallet.l);
    set('rp-pallet-w', pallet.w);
    set('rp-pallet-h', pallet.h);
    set('rp-pallet-weight', pallet.weight);
    set('rp-pallet-boxes', pallet.boxes);
    set('rp-created-by', approvals.createdBy);
    set('rp-concept-function', approvals.conceptFunction);
    set('rp-concept-name', approvals.conceptName);
    set('rp-concept-date', approvals.conceptDate);
    set('rp-final-function', approvals.finalFunction);
    set('rp-final-name', approvals.finalName);
    set('rp-final-date', approvals.finalDate);
    set('rp-comments', s.comments);
    renderReportItems(s.items);
}

/**
 * Collect the current report data form values.
 */
function collectReportForm() {
    const val = (id) => {
        const el = document.getElementById(id);
        return el ? el.value.trim() : '';
    };
    const num = (id) => {
        const v = val(id);
        return v === '' ? null : Number(v);
    };
    const items = Array.from(document.querySelectorAll('#rp-items .rp-item-row')).map(row => {
        const inputs = row.querySelectorAll('input');
        return {
            desc: inputs[0].value.trim(),
            material: inputs[1].value.trim(),
            l: inputs[2].value === '' ? null : Number(inputs[2].value),
            w: inputs[3].value === '' ? null : Number(inputs[3].value),
            h: inputs[4].value === '' ? null : Number(inputs[4].value),
            qty: inputs[5].value === '' ? null : Number(inputs[5].value),
            price: inputs[6].value === '' ? null : Number(inputs[6].value),
        };
    }).filter(it => it.desc || it.material || it.l != null || it.w != null || it.h != null || it.qty != null || it.price != null);
    return {
        part: {
            number: val('rp-part-number'),
            project: val('rp-project'),
            revision: val('rp-revision'),
            material: val('rp-material'),
        },
        supplier: {
            name: val('rp-supplier-name'),
            address: val('rp-supplier-address'),
            contact: val('rp-supplier-contact'),
            phone: val('rp-supplier-phone'),
            email: val('rp-supplier-email'),
            function: val('rp-supplier-function'),
        },
        cost: {
            boxCost: num('rp-box-cost'),
            packagingCost: num('rp-packaging-cost'),
            freightCost: num('rp-freight-cost'),
            costPerPart: num('rp-cost-part'),
        },
        pallet: {
            l: num('rp-pallet-l'),
            w: num('rp-pallet-w'),
            h: num('rp-pallet-h'),
            weight: num('rp-pallet-weight'),
            boxes: num('rp-pallet-boxes'),
        },
        approvals: {
            createdBy: val('rp-created-by'),
            conceptFunction: val('rp-concept-function'),
            conceptName: val('rp-concept-name'),
            conceptDate: val('rp-concept-date'),
            finalFunction: val('rp-final-function'),
            finalName: val('rp-final-name'),
            finalDate: val('rp-final-date'),
        },
        comments: val('rp-comments'),
    };
}

/**
 * Persist the report data form to localStorage.
 */
function saveReportForm() {
    try {
        localStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(collectReportForm()));
    } catch (e) { /* storage full / unavailable — non fatal */ }
}

/**
 * Merge pack results with the report data form.
 */
function buildReportData() {
    saveReportForm();
    return { ...(state.lastResults || {}), ...collectReportForm() };
}

/**
 * Re-render the scene pieces with a different colour count (report slider).
 * Uses the last rendered placement context (GPU/fast results, or the
 * currently selected tray). Returns false when there is nothing to re-colour
 * (e.g. bulk simulation) — the caller can still regenerate the preview.
 */
function recolorScene(colorCount) {
    const ctx = state._renderCtx;
    if (!ctx || !state.sceneManager || !Array.isArray(ctx.placements) || ctx.placements.length === 0) {
        return false;
    }
    state.sceneManager.clearPieces();
    state.sceneManager.addPackedPlacements({
        placements: ctx.placements,
        baseGeometry: ctx.baseGeometry,
        boxL: ctx.boxL,
        boxW: ctx.boxW,
        boxH: ctx.boxH,
        colorCount,
        fillPct: ctx.fillPct,
        interlocked: ctx.interlocked,
        onProgress: (p) => {
            const el = document.getElementById('gpu-piece-count');
            if (el) el.textContent = String(p.revealed);
        }
    });
    return true;
}

async function openReportModal() {
    if (!state.lastResults) {
        alert(mainText('reportNoResults'));
        return;
    }
    
    // Keep the report color count consistent with the piece color slider
    // (the report renders the current scene, so it must match the scene colors).
    const mainColorCount = parseInt(elements.optPieceColors?.value) || 10;
    if (elements.colorCount && elements.colorCountValue) {
        elements.colorCount.value = String(mainColorCount);
        elements.colorCountValue.textContent = String(mainColorCount);
    }

    loadReportForm();
    
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
        const html = await state.reportGenerator.generatePreview(buildReportData(), language);
        
        // Create iframe with content
        const iframe = document.createElement('iframe');
        iframe.style.width = '100%';
        iframe.style.height = '1123px'; // A4 at 96dpi
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
        await state.reportGenerator.downloadReport(buildReportData(), language);
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
        await state.reportGenerator.downloadReport(buildReportData(), language);
    } catch (error) {
        console.error('Error generating report:', error);
        alert(mainText('reportGenerateError'));
    }
}

// Report data form: persist on input, add component rows.
let reportPreviewDebounce = null;
document.addEventListener('DOMContentLoaded', () => {
    const rpData = document.getElementById('report-data');
    if (rpData) {
        rpData.addEventListener('input', () => {
            saveReportForm();
            if (elements.reportModal?.style.display === 'flex') {
                clearTimeout(reportPreviewDebounce);
                reportPreviewDebounce = setTimeout(updateReportPreview, 400);
            }
        });
    }
    document.getElementById('rp-add-item')?.addEventListener('click', () => {
        addReportItemRow();
        saveReportForm();
    });
    document.getElementById('save-box-btn')?.addEventListener('click', saveCurrentBox);
    renderSavedBoxes();
    document.getElementById('mt-popup-confirm')?.addEventListener('click', () => {
        const cb = mtPopupCallback;
        const input = document.getElementById('mt-popup-total');
        const total = parseInt(input?.value, 10) || 1000;
        hideMtPopup();
        if (cb) cb(Math.max(1, total));
    });
    document.getElementById('mt-popup-cancel')?.addEventListener('click', hideMtPopup);
    const mtInput = document.getElementById('mt-popup-total');
    if (mtInput) {
        mtInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('mt-popup-confirm')?.click();
            }
        });
    }
});

// Box Options ("Comparar caixes") — ranked cost-per-part comparison
initBoxOptions();

// Initialize app on DOM ready
document.addEventListener('DOMContentLoaded', init);

// Export for debugging
window.PackAssist = { state, elements, THREE };
