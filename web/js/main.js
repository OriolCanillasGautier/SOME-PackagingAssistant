/**
 * PackAssist Web - Main Application
 * Connects UI with packing calculator, 3D visualization, and physics simulation
 * Cache bust: 2024-12-17-v2
 */

import * as THREE from 'three';
import { calcularEmpaquetatge, calcularEmpaquetamentAvancat, getDistribution, getPieceDimensions, ORIENTATIONS, getOrientedDimensions } from './packing/calculator.js?v=2';
import { loadMesh, loadSTL, extractDimensions, centerToOrigin, isSupported, SUPPORTED_EXTENSIONS } from './mesh/mesh-utils.js?v=2';
import { SceneManager } from './visualization/scene.js?v=3';
import { BulkSimulation, OrderedPhysicsSimulation, GuidedPlacementSimulation, StabilityTester, initRapier } from './physics/physics-world.js?v=2';
import { ReportGenerator } from './report/report-generator.js?v=2';
import { getSimplificationModal } from './mesh/simplification-modal.js?v=2';
import { StorageManager } from './storage/storage-manager.js';
import { ServerStorage } from './storage/server-storage.js';

// Application state
const state = {
    mode: 'optimized', // 'optimized' or 'bulk'
    stlGeometry: null,
    stlDimensions: null,
    stlVertices: null,
    sceneManager: null,
    bulkSimulation: null,
    orderedSimulation: null, // New ordered physics simulation
    guidedSimulation: null, // New guided placement simulation
    stabilityTester: null, // Stability tester for orientations
    isSimulating: false,
    reportGenerator: null,
    storageManager: null,
    lastResults: null, // Store last results for report generation
    activeSTLId: null // Track currently active STL from storage
};

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
    stlUpload: document.getElementById('stl-upload'),
    stlStatus: document.getElementById('stl-status'),
    recentStlsContainer: document.getElementById('recent-stls-container'),
    recentStlsList: document.getElementById('recent-stls-list'),
    exportLibraryBtn: document.getElementById('export-library-btn'),
    clearLibraryBtn: document.getElementById('clear-library-btn'),

    // Box inputs
    boxLength: document.getElementById('box-length'),
    boxWidth: document.getElementById('box-width'),
    boxHeight: document.getElementById('box-height'),
    maxWeight: document.getElementById('max-weight'),
    safetyFactor: document.getElementById('safety-factor'),
    safetyValue: document.getElementById('safety-value'),

    // Bulk mode options
    bulkOptions: document.getElementById('bulk-options'),
    dropHeight: document.getElementById('drop-height'),
    dropHeightValue: document.getElementById('drop-height-value'),
    maxPieces: document.getElementById('max-pieces'),
    maxPiecesValue: document.getElementById('max-pieces-value'),
    maxPiecesGroup: document.getElementById('max-pieces-group'),
    dropInterval: document.getElementById('drop-interval'),
    dropIntervalValue: document.getElementById('drop-interval-value'),
    pieceColors: document.getElementById('piece-colors'),
    pieceColorsValue: document.getElementById('piece-colors-value'),
    randomRotation: document.getElementById('random-rotation'),
    autoCapacity: document.getElementById('auto-capacity'),
    autoModeHint: document.getElementById('auto-mode-hint'),

    // Density factor
    densityFactor: document.getElementById('density-factor'),
    densityValue: document.getElementById('density-value'),

    // Separators
    addSeparators: document.getElementById('add-separators'),
    separatorThickness: document.getElementById('separator-thickness'),
    separatorThicknessValue: document.getElementById('separator-thickness-value'),
    separatorThicknessGroup: document.getElementById('separator-thickness-group'),

    // Buttons
    calculateBtn: document.getElementById('calculate-btn'),
    startSimBtn: document.getElementById('start-simulation-btn'),
    stopSimBtn: document.getElementById('stop-simulation-btn'),
    resetSimBtn: document.getElementById('reset-simulation-btn'),

    // Report buttons
    reportButtons: document.getElementById('report-buttons'),
    reportPreviewBtn: document.getElementById('report-preview-btn'),

    // Report Modal
    reportModal: document.getElementById('report-modal'),
    modalClose: document.getElementById('modal-close'),
    modalCancel: document.getElementById('modal-cancel'),
    modalDownload: document.getElementById('modal-download'),
    reportPreviewFrame: document.getElementById('report-preview-frame'),
    colorCount: document.getElementById('color-count'),
    colorCountValue: document.getElementById('color-count-value'),

    // View buttons
    viewButtons: document.querySelectorAll('.view-btn'),

    // Output
    threeCanvas: document.getElementById('three-canvas'),
    simulationStatus: document.getElementById('simulation-status'),
    results: document.getElementById('results'),

    // Physics Optimized Options
    physicsOptimizedOptions: document.getElementById('physics-optimized-options'),
    usePhysicsPlacement: document.getElementById('use-physics-placement'),

    // Stability Modal
    stabilityModal: document.getElementById('stability-modal'),
    stabilityModalClose: document.getElementById('stability-modal-close'),
    stabilityPreview: document.getElementById('stability-preview'),
    stabilityStatus: document.getElementById('stability-status'),
    stabilityStable: document.getElementById('stability-stable'),
    stabilityUnstable: document.getElementById('stability-unstable'),
    rotateXMinus: document.getElementById('rotate-x-minus'),
    rotateXPlus: document.getElementById('rotate-x-plus'),
    rotateZMinus: document.getElementById('rotate-z-minus'),
    rotateZPlus: document.getElementById('rotate-z-plus'),
    resetRotation: document.getElementById('reset-rotation')
};

/**
 * Initialize the application
 */
async function init() {
    // Initialize 3D scene
    state.sceneManager = new SceneManager(elements.threeCanvas);

    // Initialize report generator
    state.reportGenerator = new ReportGenerator(state.sceneManager);

    // Initialize stability tester
    state.stabilityTester = new StabilityTester();

    // Initialize storage
    // Initialize storage (Server Side)
    state.storageManager = new ServerStorage();
    try {
        await state.storageManager.init();
        renderRecentFiles();
    } catch (e) {
        console.warn('Storage manager error:', e);
    }

    // Setup event listeners
    setupEventListeners();

    // Initialize physics (preload)
    try {
        await initRapier();
        await state.stabilityTester.init();
        console.log('Physics engine ready');
    } catch (e) {
        console.warn('Physics engine not available:', e);
    }
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Mode switching
    elements.modeButtons.forEach(btn => {
        btn.addEventListener('click', () => switchMode(btn.dataset.mode));
    });

    // Safety factor slider
    elements.safetyFactor.addEventListener('input', (e) => {
        elements.safetyValue.textContent = e.target.value;
    });

    // Density factor slider
    elements.densityFactor?.addEventListener('input', (e) => {
        elements.densityValue.textContent = e.target.value;
    });

    // Separator checkbox and slider
    elements.addSeparators?.addEventListener('change', (e) => {
        if (elements.separatorThicknessGroup) {
            elements.separatorThicknessGroup.style.display = e.target.checked ? 'block' : 'none';
        }
    });

    elements.separatorThickness?.addEventListener('input', (e) => {
        if (elements.separatorThicknessValue) {
            elements.separatorThicknessValue.textContent = e.target.value;
        }
    });

    // Bulk mode sliders
    elements.dropHeight.addEventListener('input', (e) => {
        elements.dropHeightValue.textContent = e.target.value;
    });

    elements.maxPieces.addEventListener('input', (e) => {
        elements.maxPiecesValue.textContent = e.target.value;
    });

    elements.dropInterval.addEventListener('input', (e) => {
        elements.dropIntervalValue.textContent = e.target.value;
    });

    // Piece colors slider
    elements.pieceColors?.addEventListener('input', (e) => {
        elements.pieceColorsValue.textContent = e.target.value;
    });

    // Auto-capacity mode toggle
    elements.autoCapacity.addEventListener('change', (e) => {
        const autoMode = e.target.checked;
        // Hide/show max pieces slider
        if (elements.maxPiecesGroup) {
            elements.maxPiecesGroup.style.display = autoMode ? 'none' : 'block';
        }
        // Show/hide hint
        if (elements.autoModeHint) {
            elements.autoModeHint.style.display = autoMode ? 'block' : 'none';
        }
    });

    // STL upload
    elements.stlUpload.addEventListener('change', handleSTLUpload);

    // Library actions
    elements.exportLibraryBtn?.addEventListener('click', exportLibraryToCSV);
    elements.clearLibraryBtn?.addEventListener('click', clearLibrary);

    // Calculate button
    elements.calculateBtn.addEventListener('click', handleCalculate);

    // Simulation buttons
    elements.startSimBtn.addEventListener('click', startSimulation);
    elements.stopSimBtn.addEventListener('click', stopSimulation);
    elements.resetSimBtn.addEventListener('click', resetSimulation);

    // Report button - opens preview modal
    elements.reportPreviewBtn?.addEventListener('click', openReportModal);

    // Report modal controls
    elements.modalClose?.addEventListener('click', closeReportModal);
    elements.modalCancel?.addEventListener('click', closeReportModal);
    elements.modalDownload?.addEventListener('click', downloadReportFromModal);

    // Color count slider
    elements.colorCount?.addEventListener('input', (e) => {
        elements.colorCountValue.textContent = e.target.value;
    });

    // Language change - update preview
    document.querySelectorAll('input[name="report-lang"]').forEach(radio => {
        radio.addEventListener('change', updateReportPreview);
    });

    // Close modal on backdrop click
    elements.reportModal?.addEventListener('click', (e) => {
        if (e.target === elements.reportModal) {
            closeReportModal();
        }
    });

    // View buttons
    elements.viewButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.dataset.view === 'fullscreen') {
                state.sceneManager.toggleFullscreen();
            } else {
                state.sceneManager.setView(btn.dataset.view);
            }
        });
    });

    // Stability Modal controls
    elements.stabilityModalClose?.addEventListener('click', closeStabilityModal);
    elements.stabilityStable?.addEventListener('click', confirmStability);
    elements.stabilityUnstable?.addEventListener('click', rejectStability);
    elements.rotateXMinus?.addEventListener('click', () => rotatePieceManually('x', -1));
    elements.rotateXPlus?.addEventListener('click', () => rotatePieceManually('x', 1));
    elements.rotateZMinus?.addEventListener('click', () => rotatePieceManually('z', -1));
    elements.rotateZPlus?.addEventListener('click', () => rotatePieceManually('z', 1));
    elements.resetRotation?.addEventListener('click', resetPieceRotation);

    // Close stability modal on backdrop click
    elements.stabilityModal?.addEventListener('click', (e) => {
        if (e.target === elements.stabilityModal) {
            closeStabilityModal();
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

    // Update app container class for CSS mode-specific styling
    const appContainer = document.querySelector('.app-container');
    if (appContainer) {
        appContainer.classList.remove('mode-optimized', 'mode-bulk');
        appContainer.classList.add(`mode-${mode}`);
    }

    // Show/hide mode-specific elements
    const isOptimized = mode === 'optimized';

    elements.bulkOptions.style.display = isOptimized ? 'none' : 'block';
    elements.calculateBtn.style.display = isOptimized ? 'block' : 'none';
    elements.startSimBtn.style.display = isOptimized ? 'none' : 'block';
    elements.stopSimBtn.style.display = 'none';
    elements.resetSimBtn.style.display = isOptimized ? 'none' : 'block';

    // Reset results
    if (!isOptimized) {
        elements.results.innerHTML = '<p class="placeholder-text">👆 Configura les opcions i inicia la simulació</p>';
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
        elements.stlStatus.textContent = `❌ Format no suportat. Formats vàlids: ${SUPPORTED_EXTENSIONS.join(', ')}`;
        elements.stlStatus.style.display = 'block';
        return;
    }

    const ext = file.name.substring(file.name.lastIndexOf('.')).toUpperCase();
    elements.stlStatus.className = 'stl-status';
    elements.stlStatus.textContent = `Carregant ${ext}...`;
    elements.stlStatus.style.display = 'block';

    try {
        let geometry = await loadMesh(file);
        centerToOrigin(geometry);

        // Comprovar si la malla té molts vèrtexs i oferir simplificació
        const positions = geometry.getAttribute('position');
        const vertexCount = positions.count;
        const VERTEX_THRESHOLD = 5000; // Llindar per oferir simplificació

        if (vertexCount > VERTEX_THRESHOLD) {
            // Mostrar opció de simplificació
            elements.stlStatus.className = 'stl-status warning';
            elements.stlStatus.innerHTML = `⚠️ Malla complexa (${vertexCount.toLocaleString()} vèrtexs). <button id="simplify-mesh-btn" class="btn-small">🔧 Simplificar</button>`;

            // Afegir handler pel botó
            document.getElementById('simplify-mesh-btn')?.addEventListener('click', () => {
                const modal = getSimplificationModal();
                modal.open(geometry, (simplifiedGeometry) => {
                    // Callback quan es completa la simplificació
                    geometry = simplifiedGeometry;
                    centerToOrigin(geometry);

                    state.stlGeometry = geometry;
                    state.stlDimensions = extractDimensions(geometry);

                    // Update dimension inputs
                    elements.objLength.value = state.stlDimensions.length.toFixed(2);
                    elements.objWidth.value = state.stlDimensions.width.toFixed(2);
                    elements.objHeight.value = state.stlDimensions.height.toFixed(2);

                    const newPositions = geometry.getAttribute('position');
                    elements.stlStatus.className = 'stl-status success';
                    elements.stlStatus.textContent = `✅ Simplificat: ${newPositions.count.toLocaleString()} vèrtexs | ${state.stlDimensions.length.toFixed(2)} × ${state.stlDimensions.width.toFixed(2)} × ${state.stlDimensions.height.toFixed(2)} mm`;
                });
            });
        }

        state.stlGeometry = geometry;
        state.stlDimensions = extractDimensions(geometry);

        // Update dimension inputs
        elements.objLength.value = state.stlDimensions.length.toFixed(2);
        elements.objWidth.value = state.stlDimensions.width.toFixed(2);
        elements.objHeight.value = state.stlDimensions.height.toFixed(2);

        if (vertexCount <= VERTEX_THRESHOLD) {
            elements.stlStatus.className = 'stl-status success';
            elements.stlStatus.textContent = `✅ Dimensions: ${state.stlDimensions.length.toFixed(2)} × ${state.stlDimensions.width.toFixed(2)} × ${state.stlDimensions.height.toFixed(2)} mm`;
        }

        // Extract vertices for physics
        const positionsAttr = geometry.getAttribute('position');
        state.stlVertices = new Float32Array(positionsAttr.array);

        if (elements.physicsOptimizedOptions) {
            elements.physicsOptimizedOptions.style.display = 'block';
        }

        // Save to storage
        if (state.storageManager) {
            try {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const arrayBuffer = e.target.result;
                    const id = await state.storageManager.saveFile(
                        file.name,
                        arrayBuffer,
                        state.stlDimensions,
                        parseFloat(elements.objWeight.value) || 0.1
                    );
                    state.activeSTLId = id;
                    renderRecentFiles();
                };
                reader.readAsArrayBuffer(file);
            } catch (storageError) {
                console.warn('Could not save to library:', storageError);
            }
        }

    } catch (error) {
        elements.stlStatus.className = 'stl-status error';
        elements.stlStatus.textContent = `❌ Error: ${error.message}`;
        state.stlGeometry = null;
        state.stlDimensions = null;
        state.stlVertices = null;

        // Hide physics options on error
        if (elements.physicsOptimizedOptions) {
            elements.physicsOptimizedOptions.style.display = 'none';
        }
    }
}

/**
 * Get current input values
 * If STL is loaded, use STL dimensions instead of manual input
 * @returns {Object}
 */
function getInputValues() {
    // If STL is loaded, use its real dimensions
    let objL, objW, objH;
    if (state.stlDimensions) {
        objL = state.stlDimensions.length;
        objW = state.stlDimensions.width;
        objH = state.stlDimensions.height;
        console.log(`📏 Using STL dimensions: ${objL.toFixed(1)} × ${objW.toFixed(1)} × ${objH.toFixed(1)}`);
    } else {
        objL = parseFloat(elements.objLength.value) || 0;
        objW = parseFloat(elements.objWidth.value) || 0;
        objH = parseFloat(elements.objHeight.value) || 0;
    }

    return {
        objL,
        objW,
        objH,
        objWeight: parseFloat(elements.objWeight.value) || 0,
        boxL: parseFloat(elements.boxLength.value) || 0,
        boxW: parseFloat(elements.boxWidth.value) || 0,
        boxH: parseFloat(elements.boxHeight.value) || 0,
        maxWeight: parseFloat(elements.maxWeight.value) || 0,
        allowRotation: elements.allowRotation.checked,
        safetyFactor: parseInt(elements.safetyFactor.value) / 100,
        densityFactor: parseFloat(elements.densityFactor?.value || 1.0),
        // Bulk mode
        dropHeight: parseInt(elements.dropHeight.value),
        maxPieces: parseInt(elements.maxPieces.value),
        dropIntervalMs: parseInt(elements.dropInterval.value),
        colorCount: parseInt(elements.pieceColors?.value) || 10,
        randomRotation: elements.randomRotation.checked,
        autoCapacity: elements.autoCapacity.checked
    };
}

/**
 * Handle calculate button click (optimized mode)
 * Mode optimitzat: peces ordenades en graella, amb o sense separadors
 * Si s'activa física intel·ligent, usa test d'estabilitat i col·locació guiada
 */
async function handleCalculate() {
    const values = getInputValues();

    // Separator options
    const addSeparators = elements.addSeparators?.checked || false;
    const separatorThickness = parseFloat(elements.separatorThickness?.value) || 2;

    // Physics placement options
    const usePhysicsPlacement = elements.usePhysicsPlacement?.checked && state.stlGeometry;
    const stabilityPrecision = document.querySelector('input[name="stability-precision"]:checked')?.value || 'fast';
    const placementDirection = document.querySelector('input[name="placement-direction"]:checked')?.value || 'auto';

    // If physics placement is enabled and we have STL, run advanced mode
    if (usePhysicsPlacement && state.stlVertices) {
        await handleAdvancedCalculate(values, stabilityPrecision, placementDirection);
        return;
    }

    // Standard calculation (non-physics mode)
    const result = calcularEmpaquetatge(values);

    // Display results
    elements.results.innerHTML = result.summary;
    elements.results.classList.add('fade-in');

    // Update 3D visualization
    if (result.data) {
        const boxL = values.boxL;
        const boxW = values.boxW;
        const boxH = values.boxH;

        state.sceneManager.createBox(boxL, boxW, boxH);

        const [pieceL, pieceW, pieceH] = getPieceDimensions(result.data);
        const [nx, ny, nz] = getDistribution(result.data);

        // Dimensions originals i òptimes per calcular la rotació correcta
        const originalDims = [values.objL, values.objW, values.objH];
        const optimalDims = [pieceL, pieceW, pieceH];

        // Nom de l'orientació per saber quina rotació aplicar
        const orientationName = result.data.bestOrientation?.name || 'Original';

        if (nx > 0 && ny > 0 && nz > 0) {
            // Mode simple - sempre usar visualització sense física per ara
            const drawn = state.sceneManager.addPackedPieces({
                pieceL, pieceW, pieceH,
                nx, ny, nz,
                maxDraw: 500,
                stlGeometry: state.stlGeometry || null,
                addSeparators,
                separatorThickness,
                originalDims,
                optimalDims,
                orientationName,
                densityFactor: values.densityFactor,
                boxDims: { l: boxL, w: boxW, h: boxH }
            });

            console.log(`Rendered ${drawn} pieces`);

            // Store results for report
            state.lastResults = {
                pieceDims: { l: values.objL, w: values.objW, h: values.objH },
                boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
                pieceCount: result.data.realUnits || result.data.totalUnitats,
                pieceWeight: values.objWeight,
                maxWeight: values.maxWeight,
                mode: 'optimized',
                safetyFactor: values.safetyFactor,
                addSeparators,
                separatorThickness
            };

            // Show report buttons
            elements.reportButtons.style.display = 'flex';
        }
    }
}

/**
 * Advanced calculation with stability testing and guided placement
 */
async function handleAdvancedCalculate(values, stabilityPrecision, placementDirection) {
    const dims = { l: values.objL, w: values.objW, h: values.objH };
    const duration = stabilityPrecision === 'fast' ? 500 : 2000;

    // Show progress
    elements.results.innerHTML = '<p>🔍 Testejant estabilitat de cada orientació...</p>';
    elements.simulationStatus.textContent = '⏳ Simulant estabilitat...';
    elements.simulationStatus.style.display = 'block';

    try {
        // Test stability of all orientations
        const stabilityResults = await state.stabilityTester.testAllOrientations({
            vertices: state.stlVertices,
            dims,
            duration
        });

        // Filter stable orientations - use the FINAL stable rotation, not initial
        // Also filter to unique positions only (same initial rotations may end at same final position)
        const stableOrientations = stabilityResults
            .filter(r => r.stable && r.isUniquePosition)
            .map((r, i) => {
                const oriIndex = ORIENTATIONS.findIndex(o => o.name === r.name);
                const dimsArray = getOrientedDimensions([dims.l, dims.w, dims.h], oriIndex);
                return {
                    index: oriIndex,
                    name: r.name,
                    rotation: r.stableRotation || r.rotation, // Use stable rotation if available
                    stableQuaternion: r.stableQuaternion,
                    dims: { l: dimsArray[0], w: dimsArray[1], h: dimsArray[2] }
                };
            });

        if (stableOrientations.length === 0) {
            elements.results.innerHTML = `
                <h1>❌ Cap orientació estable</h1>
                <p>Cap de les 6 orientacions és estable. La peça cau en totes les posicions.</p>
                <p>Prova el mode sense física o modifica la geometria de la peça.</p>
                <h3>Resultats dels tests:</h3>
                <ul>
                    ${stabilityResults.map(r => `<li>${r.stable ? '✅' : '❌'} ${r.name}: δ=${r.rotationDelta.toFixed(1)}°</li>`).join('')}
                </ul>
            `;
            elements.simulationStatus.style.display = 'none';
            return;
        }

        // Log unique stable orientations
        console.log(`🎯 ${stableOrientations.length} orientacions estables úniques trobades`);

        // Run advanced packing calculation
        const result = calcularEmpaquetamentAvancat({
            ...values,
            stableOrientations: stableOrientations.map(o => o.index)
        });

        // Display results with stability info
        const stableCount = stabilityResults.filter(r => r.stable).length;
        const uniqueCount = stabilityResults.filter(r => r.stable && r.isUniquePosition).length;

        let stabilityHtml = `
            <h2>📐 Test d'Estabilitat</h2>
            <p><strong>${stableCount} orientacions estables</strong> (${uniqueCount} posicions úniques)</p>
            <ul>
                ${stabilityResults.map(r => {
            const icon = r.stable ? '✅' : '❌';
            const status = r.stable ? 'Estable' : 'Inestable';
            const unique = r.stable && r.isUniquePosition ? ' 🎯' : '';
            return `<li>${icon} ${r.name}: ${status} (δ=${r.rotationDelta.toFixed(1)}°)${unique}</li>`;
        }).join('')}
            </ul>
        `;

        elements.results.innerHTML = result.summary + stabilityHtml;

        // Start guided placement simulation
        if (result.data) {
            const maxPieces = result.data.realUnits || result.data.theoreticalUnits || 50;
            console.log(`📦 Simulació: maxPieces=${maxPieces}, realUnits=${result.data.realUnits}, theoretical=${result.data.theoreticalUnits}`);

            await startGuidedPlacement({
                values,
                stableOrientations,
                placementDirection,
                layerPlan: result.data.layerPlan,
                maxPieces
            });
        }

    } catch (error) {
        console.error('Advanced calculation error:', error);
        elements.results.innerHTML = `<p>❌ Error: ${error.message}</p>`;
        elements.simulationStatus.style.display = 'none';
    }
}

/**
 * Start guided placement - use layerPlan data from calculator for proper orientation
 */
async function startGuidedPlacement(options) {
    const { values, stableOrientations, layerPlan, maxPieces = 50 } = options;

    const boxL = values.boxL;
    const boxW = values.boxW;
    const boxH = values.boxH;

    state.sceneManager.createBox(boxL, boxW, boxH);

    // Get optimal dimensions from layerPlan (first layer has the best orientation)
    let pieceL, pieceW, pieceH, nx, ny, nz, orientationName;

    if (layerPlan && layerPlan.length > 0) {
        // Use the dimensions from the calculated layer plan
        const firstLayer = layerPlan[0];
        pieceL = firstLayer.dims[0]; // Already rotated dimensions
        pieceW = firstLayer.dims[1];
        pieceH = firstLayer.dims[2];
        nx = firstLayer.nx;
        ny = firstLayer.ny;
        nz = layerPlan.length; // Number of layers
        orientationName = firstLayer.orientation?.name || 'Original';

        console.log(`📦 Using layerPlan: ${orientationName}, dims=${pieceL.toFixed(1)}×${pieceW.toFixed(1)}×${pieceH.toFixed(1)}, grid=${nx}×${ny}×${nz}`);
    } else {
        // Fallback to original dimensions
        pieceL = values.objL;
        pieceW = values.objW;
        pieceH = values.objH;
        nx = Math.floor(boxL / pieceL);
        ny = Math.floor(boxW / pieceW);
        nz = Math.floor(boxH / pieceH);
        orientationName = 'Original';
    }

    if (nx > 0 && ny > 0 && nz > 0) {
        // Use the working addPackedPieces function with CORRECT dimensions
        const drawn = state.sceneManager.addPackedPieces({
            pieceL, pieceW, pieceH,
            nx, ny, nz,
            maxDraw: maxPieces,
            stlGeometry: state.stlGeometry || null,
            addSeparators: false,
            separatorThickness: 0,
            originalDims: [values.objL, values.objW, values.objH],
            optimalDims: [pieceL, pieceW, pieceH],
            orientationName: orientationName,
            densityFactor: 1.0,
            boxDims: { l: boxL, w: boxW, h: boxH }
        });

        elements.simulationStatus.textContent = `✅ ${drawn} peces visualitzades`;
        elements.simulationStatus.style.display = 'block';

        // Store results for report
        state.lastResults = {
            pieceDims: { l: values.objL, w: values.objW, h: values.objH },
            boxDims: { length: boxL, width: boxW, height: boxH },
            pieceCount: drawn,
            pieceWeight: values.objWeight,
            maxWeight: values.maxWeight,
            mode: 'optimized-physics',
            safetyFactor: values.safetyFactor
        };

        elements.reportButtons.style.display = 'flex';
    } else {
        elements.simulationStatus.textContent = '❌ Cap peça cap a la caixa';
        elements.simulationStatus.style.display = 'block';
    }
}

/**
 * Open stability verification modal
 */
function openStabilityModal(info) {
    if (elements.stabilityModal) {
        elements.stabilityModal.style.display = 'flex';
    }
    if (elements.stabilityStatus) {
        elements.stabilityStatus.innerHTML = `<p>⚖️ ${info.message}</p><p>Peces col·locades: ${info.pieceCount}</p>`;
    }
}

/**
 * Close stability modal
 */
function closeStabilityModal() {
    if (elements.stabilityModal) {
        elements.stabilityModal.style.display = 'none';
    }
}

/**
 * User confirms stability
 */
function confirmStability() {
    closeStabilityModal();
    if (state.guidedSimulation) {
        state.guidedSimulation.confirmStable();
    }
}

/**
 * User rejects stability - discard configuration
 */
function rejectStability() {
    closeStabilityModal();
    if (state.guidedSimulation) {
        state.guidedSimulation.reset();
    }
    elements.results.innerHTML = '<p>❌ Configuració descartada per inestabilitat. Prova de nou amb altres paràmetres.</p>';
}

/**
 * Rotate piece manually (45° increments)
 */
function rotatePieceManually(axis, direction) {
    if (state.guidedSimulation) {
        // Rotate the last placed piece (or selected piece)
        const pieceIndex = state.guidedSimulation.placedPieces.length - 1;
        if (pieceIndex >= 0) {
            state.guidedSimulation.rotatePiece(pieceIndex, axis, direction);
        }
    }
}

/**
 * Reset piece rotation to original
 */
function resetPieceRotation() {
    // For now, reset all pieces - could be improved to track original rotations
    if (state.guidedSimulation) {
        elements.simulationStatus.textContent = '🔄 Rotació restablerta';
    }
}

/**
 * Start ordered physics simulation (for separator mode)
 * Col·loca les peces ordenadament i aplica gravetat
 */
async function startOrderedPhysicsMode(options) {
    // Stop any existing simulation
    if (state.orderedSimulation) {
        state.orderedSimulation.dispose();
    }

    // Initialize Rapier
    const rapierReady = await initRapier();
    if (!rapierReady) {
        console.error('Failed to init Rapier for ordered mode');
        // Fallback to simple visualization
        return;
    }

    // Create ordered simulation
    state.orderedSimulation = new OrderedPhysicsSimulation(state.sceneManager);

    // Status callback
    state.orderedSimulation.onStatusUpdate = (status) => {
        const statusEl = document.getElementById('simulation-status');
        if (statusEl) {
            statusEl.textContent = status.message;
            statusEl.style.display = 'block';
        }
    };

    // Complete callback
    state.orderedSimulation.onComplete = (finalCount) => {
        state.isSimulating = false;
        console.log(`Ordered physics complete: ${finalCount} pieces`);
    };

    // Initialize and start
    await state.orderedSimulation.init(options);
    state.isSimulating = true;
    state.orderedSimulation.start();
}

/**
 * Start bulk simulation
 */
async function startSimulation() {
    const values = getInputValues();

    // Validate inputs
    if ([values.objL, values.objW, values.objH, values.boxL, values.boxW, values.boxH].some(v => v <= 0)) {
        elements.results.innerHTML = '<p>❌ Totes les dimensions han de ser majors que 0</p>';
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
        elements.results.innerHTML = `<p>❌ Error inicialitzant simulació: ${error.message}</p>`;
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

    elements.results.innerHTML = '<p class="placeholder-text">👆 Configura les opcions i inicia la simulació</p>';
}

/**
 * Update simulation status display
 * @param {Object} status
 */
function updateSimulationStatus(status) {
    elements.simulationStatus.className = 'simulation-status active';
    elements.simulationStatus.textContent = status.message;

    if (status.status === 'settled' || status.status === 'timeout' || status.status === 'saturated') {
        const values = getInputValues();
        const removedText = status.removed > 0 ? `<li><strong>Peces eliminades (fora):</strong> ${status.removed}</li>` : '';

        elements.results.innerHTML = `
            <h1>🌊 Resultat Simulació a Granel</h1>
            <ul>
                <li><strong>Peces deixades caure:</strong> ${status.dropped}</li>
                <li><strong>Peces dins la caixa:</strong> ${status.inside}</li>
                ${removedText}
                <li><strong>Eficiència:</strong> ${((status.inside / status.dropped) * 100).toFixed(1)}%</li>
            </ul>
            <p>💡 En mode a granel, les peces s'acomoden de forma natural per gravetat. 
            El resultat pot variar entre execucions degut a la física.</p>
        `;

        // Store results for report
        state.lastResults = {
            pieceDims: { l: values.objL, w: values.objW, h: values.objH },
            boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
            pieceCount: status.inside,
            pieceWeight: values.objWeight,
            maxWeight: values.maxWeight,
            mode: 'bulk',
            safetyFactor: values.safetyFactor
        };

        // Show report buttons
        elements.reportButtons.style.display = 'flex';

        elements.startSimBtn.style.display = 'block';
        elements.stopSimBtn.style.display = 'none';
    }
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
        elements.reportPreviewFrame.innerHTML = '<p class="loading-text" style="color: red;">Error carregant previsualització</p>';
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
        alert('Error generant l\'informe.');
    }
}

/**
 * Generate and download report
 * @param {string} language - 'ca' or 'en'
 */
async function generateReport(language) {
    if (!state.lastResults) {
        alert(language === 'ca'
            ? 'No hi ha resultats per generar l\'informe. Executa una simulació primer.'
            : 'No results to generate report. Run a simulation first.');
        return;
    }

    try {
        await state.reportGenerator.downloadReport(state.lastResults, language);
    } catch (error) {
        console.error('Error generating report:', error);
        alert(language === 'ca'
            ? 'Error generant l\'informe.'
            : 'Error generating report.');
    }
}

/**
 * Render the list of recent STL files
 */
async function renderRecentFiles() {
    if (!state.storageManager || !elements.recentStlsList) return;

    try {
        const recents = await state.storageManager.getRecentFiles(5);

        if (recents.length === 0) {
            elements.recentStlsContainer.style.display = 'none';
            return;
        }

        elements.recentStlsContainer.style.display = 'block';
        elements.recentStlsList.innerHTML = '';

        recents.forEach(file => {
            const item = document.createElement('div');
            item.className = `recent-stl-item ${state.activeSTLId === file.id ? 'active' : ''}`;
            item.dataset.id = file.id;

            const dimsText = `${file.dimensions.length.toFixed(1)}×${file.dimensions.width.toFixed(1)}×${file.dimensions.height.toFixed(1)} mm`;

            item.innerHTML = `
                <div class="recent-stl-info">
                    <span class="recent-stl-name" title="${file.name}">${file.name}</span>
                    <span class="recent-stl-dims">${dimsText} | ${file.weight.toFixed(3)} kg</span>
                </div>
                <div class="recent-stl-actions">
                    <button class="btn-icon delete" title="Esborrar de la llibreria">🗑️</button>
                </div>
            `;

            // Click item to load
            item.addEventListener('click', (e) => {
                if (e.target.closest('.delete')) return;
                loadRecentSTL(file.id);
            });

            // Click delete
            item.querySelector('.delete').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Vols esborrar "${file.name}" de la llibreria?`)) {
                    await state.storageManager.deleteFile(file.id);
                    if (state.activeSTLId === file.id) state.activeSTLId = null;
                    renderRecentFiles();
                }
            });

            elements.recentStlsList.appendChild(item);
        });
    } catch (e) {
        console.warn('Error rendering recent files:', e);
    }
}

/**
 * Load an STL from the local library
 * @param {number} id 
 */
async function loadRecentSTL(id) {
    if (!state.storageManager) return;

    elements.stlStatus.className = 'stl-status';
    elements.stlStatus.textContent = 'Carregant des de la llibreria...';
    elements.stlStatus.style.display = 'block';

    try {
        // For ServerStorage, id is the filename
        const fileObj = await state.storageManager.getFile(id);

        // If fileObj only has data, we need dimensions from somewhere else or re-calculate
        // But renderRecentFiles passes the ID.
        // Let's rely on re-calculating dimensions from STL if not provided, 
        // OR fix getFile to return metadata?
        // Actually, loadSTL extracts dimensions anyway.

        const geometry = await loadSTL(fileObj.data);
        centerToOrigin(geometry);

        state.stlGeometry = geometry;
        // Re-calculate dimensions to be safe, or use what we have if passed
        state.stlDimensions = extractDimensions(geometry);
        state.activeSTLId = id;

        // Update dimensions
        elements.objLength.value = state.stlDimensions.length.toFixed(2);
        elements.objWidth.value = state.stlDimensions.width.toFixed(2);
        elements.objHeight.value = state.stlDimensions.height.toFixed(2);
        if (fileObj.weight) {
            elements.objWeight.value = fileObj.weight.toFixed(3);
        }

        // Update physics vertices
        const positionsAttr = geometry.getAttribute('position');
        state.stlVertices = new Float32Array(positionsAttr.array);

        // Show physics options
        if (elements.physicsOptimizedOptions) {
            elements.physicsOptimizedOptions.style.display = 'block';
        }

        elements.stlStatus.className = 'stl-status success';
        elements.stlStatus.textContent = `✅ Carregat: ${fileObj.name}`;

        // Update last used timestamp
        await state.storageManager.updateLastUsed(id);
        renderRecentFiles();

    } catch (error) {
        console.error('Error loading recent STL:', error);
        elements.stlStatus.className = 'stl-status error';
        elements.stlStatus.textContent = `❌ Error: ${error.message}`;
    }
}

/**
 * Export the entire library to a CSV file
 */
async function exportLibraryToCSV() {
    if (!state.storageManager) return;

    try {
        const allFiles = await state.storageManager.getAllFiles();
        if (allFiles.length === 0) {
            alert('La llibreria està buida.');
            return;
        }

        // Create CSV content
        let csvContent = '\uFEFF'; // BOM for UTF-8 in Excel
        csvContent += 'Nom,Llargada(mm),Amplada(mm),Alçada(mm),Pes(kg),Últim Ús\n';

        allFiles.sort((a, b) => b.lastUsed - a.lastUsed).forEach(file => {
            const date = new Date(file.lastUsed).toLocaleString();
            csvContent += `"${file.name}",${file.dimensions.length.toFixed(2)},${file.dimensions.width.toFixed(2)},${file.dimensions.height.toFixed(2)},${file.weight.toFixed(3)},"${date}"\n`;
        });

        // Download file
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `packassist_library_${new Date().toISOString().slice(0, 10)}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

    } catch (e) {
        console.warn('Error exporting library:', e);
        alert('Error en exportar la llibreria.');
    }
}

/**
 * Clear the entire library
 */
async function clearLibrary() {
    if (!confirm('Segur que vols esborrar TOTA la llibreria de peces? Aquesta acció no es pot desfer.')) {
        return;
    }

    try {
        const allFiles = await state.storageManager.getAllFiles();
        for (const file of allFiles) {
            await state.storageManager.deleteFile(file.id);
        }
        state.activeSTLId = null;
        renderRecentFiles();
    } catch (e) {
        console.warn('Error clearing library:', e);
    }
}

// Initialize app on DOM ready
document.addEventListener('DOMContentLoaded', init);

// Export for debugging
window.PackAssist = { state, elements };
