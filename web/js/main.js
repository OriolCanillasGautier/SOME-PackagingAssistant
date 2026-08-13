/**
 * PackAssist Web - Main Application
 * Connects UI with packing calculator, 3D visualization, and physics simulation
 */

import * as THREE from 'three';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { calcularEmpaquetatge, createSummary, getDistribution, getPieceDimensions } from './packing/calculator.js?v=force_update_42';
import { loadMesh, loadSTL, extractDimensions, computeMeshVolume, computeSurfaceArea, analyzeMeshIntegrity, centerToOrigin, isSupported, SUPPORTED_EXTENSIONS, guessPermForDims, applyPermutation, getSupportStability, alignToStableBase } from './mesh/mesh-utils.js?v=force_update_42';
import { SceneManager } from './visualization/scene.js?v=organic_v1';
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
    mode: 'optimized', // 'optimized', 'fast', or 'bulk'
    language: getStoredLanguage(), // 'ca' or 'en'
    locale: null,
    stlGeometry: null,
    stlAlignedGeometry: null, // transient in-memory geometry aligned to stable gravity orientation
    stlSettledQuat: null, // cached quaternion from gravity drop on current loaded geometry
    stlStableOrientations: [], // [{ quat, geometry, stability }] precomputed gravity bases
    selectedOrientations: null, // Set of selected orientation indices
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
        renderOrientationSelector();
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
    renderOrientationSelector();
    return primary?.geometry || null;
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
    animId: null
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
    renderer.setClearColor(0x16213e, 1);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x16213e, 60, 140);

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
        const dist = maxDim * 2.4;

        vs.grid.scale.set(maxDim * 4, 1, maxDim * 4);
        vs.grid.position.y = box.min.y;

        vs.camera.near = Math.max(0.001, maxDim / 100);
        vs.camera.far = maxDim * 100;
        vs.camera.position.set(dist * 0.75, dist * 0.55, dist * 0.75);
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
                tabindex="0" role="button" aria-pressed="${isActive}"
                onclick="selectOrientation(${i})">
            <canvas id="${canvasId}" class="orient-preview" width="140" height="140"></canvas>
            <div class="orient-info">
                <span class="orient-dims">${dims.length.toFixed(0)}×${dims.width.toFixed(0)}×${dims.height.toFixed(0)}mm</span>
                <span class="orient-stability">${stabilityText}</span>
            </div>
            <label class="orient-toggle" title="${mainText('orientationInclude', {}, 'Incloure a l\'empaquetatge')}" onclick="event.stopPropagation()">
                <input type="checkbox" data-index="${i}" ${isSelected ? 'checked' : ''} onchange="toggleOrientation(${i})">
                <span class="orient-toggle-track"></span>
            </label>
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
    selectOrientation(next);
}

/**
 * Set the active orientation (shown in the large viewer). Updates only the
 * card highlight classes — does not rebuild the thumbnail canvases or viewer.
 */
function selectOrientation(index) {
    if (state.activeOrientationIndex === index) return;
    state.activeOrientationIndex = index;

    document.querySelectorAll('#orientation-options .orient-card').forEach(card => {
        const idx = parseInt(card.dataset.index, 10);
        const isActive = idx === index;
        card.classList.toggle('active', isActive);
        card.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    const orientations = state.stlStableOrientations || [];
    const shown = orientations.slice(0, MAX_ORIENTATION_CARDS);
    const o = shown[index];
    if (o) setActiveOrientationMesh(o.geometry);
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
    if (!state.selectedOrientations) state.selectedOrientations = new Set();
    if (state.selectedOrientations.has(index)) {
        if (state.selectedOrientations.size > 1) state.selectedOrientations.delete(index);
    } else {
        state.selectedOrientations.add(index);
    }

    // Update just this card's UI without rebuilding the thumbnails or viewer
    const card = document.querySelector(`#orientation-options .orient-card[data-index="${index}"]`);
    if (card) {
        card.classList.toggle('selected', state.selectedOrientations.has(index));
        const cb = card.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = state.selectedOrientations.has(index);
    }
}

function setBoxPreset(l, w, h, btn) {
    document.getElementById('box-length').value = l;
    document.getElementById('box-width').value = w;
    document.getElementById('box-height').value = h;
    document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
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
    gpuOptions: document.getElementById('gpu-options'),
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

    // GPU method change — show/hide cell-size based on method
    const gpuMethod = document.getElementById('gpu-method');
    const gpuCellSize = document.getElementById('gpu-cell-size');
    if (gpuMethod && gpuCellSize) {
        const updateGPUOptions = () => {
            const isVoxel = gpuMethod.value === 'voxel';
            gpuCellSize.style.display = isVoxel ? '' : 'none';
            const cellSizeLabel = gpuCellSize.parentElement?.querySelector('label[for="gpu-cell-size"]');
            if (cellSizeLabel) cellSizeLabel.style.display = isVoxel ? '' : 'none';
        };
        gpuMethod.addEventListener('change', updateGPUOptions);
        updateGPUOptions();  // initial state
    }

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
        // Orientation alternatives UI removed — unified grid-based evaluation.
    });
}

/**
 * Switch between optimized and bulk modes
 * @param {string} mode
 */
function switchMode(mode) {
    state.mode = mode;
    
    elements.modeButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    
    const isBulk = mode === 'bulk';
    const isGPU = mode === 'gpu';
    
    elements.bulkOptions.style.display = isBulk ? 'block' : 'none';
    elements.gpuOptions.style.display = isGPU ? 'block' : 'none';
    elements.calculateBtn.style.display = isBulk ? 'none' : 'block';
    elements.startSimBtn.style.display = isBulk ? 'block' : 'none';

    elements.stopSimBtn.style.display = 'none';
    elements.resetSimBtn.style.display = 'none';

    if (elements.applyGravityBtn) {
        elements.applyGravityBtn.style.display = 'none';
    }

    if (isBulk) {
        elements.results.innerHTML = `<p class="placeholder-text">${mainText('bulkPlaceholder')}</p>`;
        state.sceneManager.clearPieces();
    }
    if (isGPU) {
        elements.results.innerHTML = `<p class="placeholder-text">${mainText('gpuPlaceholder')}</p>`;
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

async function handleGPUCalculate(calcStartTime) {
    if (!state.stlGeometry) {
        elements.results.innerHTML = `<p class="error-text">${mainText('modeGPURequiresSTL')}</p>`;
        return;
    }

    const values = getInputValues();
    const cellSize = document.getElementById('gpu-cell-size')?.value || '0.5';
    const gpuMethod = document.getElementById('gpu-method')?.value || 'voxel';
    setCalcProgress(true, 5, mainText('modeGPUSubmitting'), calcStartTime);
    await nextFrame();

    try {
        const stlBlob = new Blob([state.stlFileData], { type: 'application/octet-stream' });

        const formData = new FormData();
        formData.append('stl', stlBlob, state.stlFileName || 'piece.stl');
        formData.append('box_l', values.boxL);
        formData.append('box_w', values.boxW);
        formData.append('box_h', values.boxH);
        formData.append('cell', cellSize);
        formData.append('method', gpuMethod);

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
        do {
            const r = await fetch(`/api/pack/${job_id}`);
            job = await r.json();
            pollCount++;

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

        setCalcProgress(true, 80, 'Carregant resultats...', calcStartTime);
        await nextFrame();

        // Download and display merged STL
        const stlResp = await fetch(`/api/pack/${job_id}/stl`);
        const stlBuf = await stlResp.arrayBuffer();
        const mergedGeom = await loadSTL(stlBuf);
        if (!mergedGeom) throw new Error('No s\'ha pogut carregar el STL');

        state.sceneManager.clearPieces();
        state.sceneManager.createBox(values.boxL, values.boxW, values.boxH);
        mergedGeom.computeVertexNormals();
        state.sceneManager.addSTLPiece(mergedGeom, new THREE.Vector3(0, 0, 0));

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
                const marker = r.pieces === best.pieces && r.id === best.id ? ' 🏆' : '';
                return `<tr${isCurrent ? ' class="current-run"' : ''}>
                    <td>${r.timestamp}</td>
                    <td>${r.cellSize}mm</td>
                    <td><strong>${r.pieces}${marker}</strong></td>
                    <td>${r.fillPct}%</td>
                    <td>${r.timeS}s</td>
                    <td>${r.boxL}×${r.boxW}×${r.boxH}</td>
                </tr>`;
            }).join('');
            comparisonHtml = `
                <details open class="gpu-comparison">
                    <summary>📊 ${mainText('gpuComparison') || 'Comparació de resultats'}</summary>
                    <table class="comparison-table">
                        <tr><th>Hora</th><th>Cel·la</th><th>Peces</th><th>Fill</th><th>Temps</th><th>Caixa</th></tr>
                        ${rows}
                    </table>
                </details>`;
        }

        const clampedFill = Math.max(0, Math.min(100, job.fill_pct || 0));
        elements.results.innerHTML = `
            <div class="results-hero">
                <div class="hero-number">${job.pieces}</div>
                <div class="hero-label">${mainText('pieces')}</div>
            </div>
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
                <a class="report-link" href="${stlUrl}" target="_blank">⬇ ${mainText('modeGPUStlUrl')}</a>
                <button class="reoptimize-btn" onclick="document.querySelector('#calculate-btn').click()">🔄 ${mainText('reoptimize')}</button>
            </div>
            ${comparisonHtml}
        `;

        setCalcProgress(false, 0, '', 0);

        // Clear comparison when switching modes
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.dataset.mode !== 'gpu') gpuHistory = [];
            }, { once: true });
        });
    } catch (err) {
        console.error('[GPU]', err);
        elements.results.innerHTML = `<p class="error-text">${mainText('modeGPUError')}: ${err.message}</p>`;
        setCalcProgress(false, 0, '', 0);
    }
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

    // ── GPU Voxel Mode ──
    if (state.mode === 'gpu') {
        await handleGPUCalculate(calcStartTime);
        return;
    }

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
        elements.results.innerHTML = result.summary;
        elements.results.classList.add('fade-in');

        // Update 3D visualization
        setCalcProgress(true, 5, 'Preparant geometria 3D...', calcStartTime);
        await nextFrame();
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
                    if (state.mode === 'fast') {
                        setCalcProgress(true, 8, 'Avaluant orientacions (Graella Optima)...', calcStartTime);
                        await nextFrame();

                        const baseGeometry = state.stlGeometry.clone();
                        alignToStableBase(baseGeometry);

                        const yawAngles = values.allowRotation ? [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330] : [0];
                        const orientationPool = [];

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

                        for (const stableBase of (state.stlStableOrientations || [])) {
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
            elements.results.innerHTML = finalSummary + `
                <button class="reoptimize-btn" onclick="document.querySelector('#calculate-btn').click()">
                    🔄 ${mainText('reoptimize') || 'Re-optimitzar'}
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
    } finally {
        state.calcAbortController = null;
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
        } else if (mode === 'fast') {
            btn.childNodes[0].textContent = t.modeFast + '\n';
            if (desc) desc.textContent = t.modeFastDesc;
        } else if (mode === 'bulk') {
            btn.childNodes[0].textContent = t.modeBulk + '\n';
            if (desc) desc.textContent = t.modeBulkDesc;
        } else if (mode === 'gpu') {
            btn.childNodes[0].textContent = t.modeGPU + '\n';
            if (desc) desc.textContent = t.modeGPUDesc;
        }
    });
    
    // Section titles
    const objSection = document.querySelector('.object-section .section-header h2');
    const boxSummary = document.querySelector('details.box-section > summary');
    const bulkSection = document.querySelector('.bulk-section > h2');
    if (objSection) objSection.textContent = t.objectTitle;
    if (boxSummary) boxSummary.textContent = t.boxTitle;
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
async function openReportModal() {
    if (!state.lastResults) {
        alert(mainText('reportNoResults'));
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
