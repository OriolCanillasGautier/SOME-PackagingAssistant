/**
 * PackAssist Web - Main Application
 * Connects UI with packing calculator, 3D visualization, and physics simulation
 */

import { calcularEmpaquetatge, getDistribution, getPieceDimensions } from './packing/calculator.js?v=force_update_38';
import { loadMesh, loadSTL, extractDimensions, centerToOrigin, isSupported, SUPPORTED_EXTENSIONS, guessPermForDims, applyPermutation } from './mesh/mesh-utils.js?v=force_update_38';
import { SceneManager } from './visualization/scene.js?v=force_update_38';
import { BulkSimulation, initRapier } from './physics/physics-world.js?v=force_update_38';
import { ReportGenerator } from './report/report-generator.js?v=force_update_38';
import { getSimplificationModal } from './mesh/simplification-modal.js?v=force_update_38';
import { StorageManager } from './storage/storage-manager.js?v=force_update_38';

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
    stlGeometry: null,
    stlDimensions: null,
    stlFileName: null,
    stlFileData: null, // Store the raw file data for saving
    sceneManager: null,
    bulkSimulation: null,
    isSimulating: false,
    reportGenerator: null,
    lastResults: null, // Store last results for report generation
    storage: null // StorageManager instance
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
    optPieceColors: document.getElementById('opt-piece-colors'),
    optPieceColorsValue: document.getElementById('opt-piece-colors-value'),
    
    // Box inputs
    boxLength: document.getElementById('box-length'),
    boxWidth: document.getElementById('box-width'),
    boxHeight: document.getElementById('box-height'),
    maxWeight: document.getElementById('max-weight'),
    safetyFactor: document.getElementById('safety-factor'),
    safetyValue: document.getElementById('safety-value'),
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

/**
 * Initialize the application
 */
async function init() {
    // Initialize 3D scene
    state.sceneManager = new SceneManager(elements.threeCanvas);
    
    // Initialize report generator
    state.reportGenerator = new ReportGenerator(state.sceneManager);
    
    // Initialize storage manager
    state.storage = new StorageManager();
    await state.storage.init();
    
    // Setup event listeners
    setupEventListeners();
    
    // Load STL history
    await loadSTLHistory();
    
    // Check for URL parameters (from history page)
    loadFromURLParams();
    
    // Initialize physics (preload)
    try {
        await initRapier();
        console.log('Physics engine ready');
    } catch (e) {
        console.warn('Physics engine not available:', e);
    }
}

/**
 * Load data from URL parameters (for history page integration)
 */
function loadFromURLParams() {
    const params = new URLSearchParams(window.location.search);
    
    // Check if we have parameters
    if (params.has('objL')) {
        elements.objLength.value = params.get('objL') || elements.objLength.value;
    }
    if (params.has('objW')) {
        elements.objWidth.value = params.get('objW') || elements.objWidth.value;
    }
    if (params.has('objH')) {
        elements.objHeight.value = params.get('objH') || elements.objHeight.value;
    }
    if (params.has('objWeight')) {
        elements.objWeight.value = params.get('objWeight') || elements.objWeight.value;
    }
    if (params.has('boxL')) {
        elements.boxLength.value = params.get('boxL') || elements.boxLength.value;
    }
    if (params.has('boxW')) {
        elements.boxWidth.value = params.get('boxW') || elements.boxWidth.value;
    }
    if (params.has('boxH')) {
        elements.boxHeight.value = params.get('boxH') || elements.boxHeight.value;
    }
    if (params.has('maxWeight')) {
        elements.maxWeight.value = params.get('maxWeight') || elements.maxWeight.value;
    }
    if (params.has('mode')) {
        const mode = params.get('mode');
        if (mode === 'bulk' || mode === 'optimized') {
            switchMode(mode);
        }
    }
    
    // Clear URL params after loading (clean URL)
    if (params.toString()) {
        window.history.replaceState({}, document.title, window.location.pathname);
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
    
    // Packing gap slider
    elements.packingGap.addEventListener('input', (e) => {
        const val = e.target.value;
        const label = val < 0 ? `Solapament: ${Math.abs(val)}` : `Espaiat: ${val}`;
        elements.packingGapValue.textContent = label;
        // Optionally update text content of span next to slider if exists, here it's elements.packingGapValue
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
    
    // Piece colors slider (for optimized mode)
    elements.optPieceColors?.addEventListener('input', (e) => {
        elements.optPieceColorsValue.textContent = e.target.value;
    });
    
    // Piece colors slider (for bulk mode)
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
    
    // Weights change
    elements.objWeight.addEventListener('input', updateMaxPiecesLimit);
    elements.maxWeight.addEventListener('input', updateMaxPiecesLimit);

    // STL upload
    elements.stlUpload.addEventListener('change', handleSTLUpload);
    
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
    
    // Reset button is now redundant as Start handles reset, but we can keep it hidden
    elements.stopSimBtn.style.display = 'none';
    elements.resetSimBtn.style.display = 'none'; // User requested to remove it
    
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
    
    // Store the raw file data for saving to history
    const fileData = await file.arrayBuffer();
    state.stlFileName = file.name;
    state.stlFileData = fileData;
    
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
        elements.stlStatus.textContent = `❌ Error: ${error.message}`;
        state.stlGeometry = null;
        state.stlDimensions = null;
        state.stlFileName = null;
        state.stlFileData = null;
    }
}

/**
 * Save the current STL file to history
 */
async function saveSTLToHistory() {
    if (!state.stlFileData || !state.stlDimensions || !state.stlFileName) return;
    
    try {
        const weight = parseFloat(elements.objWeight.value) || 0;
        await state.storage.saveFile(
            state.stlFileName,
            state.stlFileData,
            state.stlDimensions,
            weight
        );
        
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
                <span class="stl-icon">📦</span>
                <div class="stl-info">
                    <input type="text" class="stl-name-input" value="${escapeHtml(file.name)}" 
                           data-id="${file.id}" data-field="name" 
                           title="Clic per editar el nom">
                    <div class="stl-meta">
                        <span class="stl-dims">${dims} mm</span>
                        <input type="number" class="stl-weight-input" value="${file.weight || 0}" 
                               step="0.001" min="0" data-id="${file.id}" data-field="weight"
                               title="Pes per unitat">
                        <span class="stl-weight-unit">kg</span>
                    </div>
                </div>
                <div class="stl-actions">
                    <button class="stl-btn load" data-id="${file.id}" title="Carregar">📥</button>
                    <button class="stl-btn delete" data-id="${file.id}" title="Eliminar">🗑️</button>
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
    
    // Load button
    elements.stlHistoryList.querySelectorAll('.stl-btn.load').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = parseInt(e.target.dataset.id);
            await loadSTLFromHistory(id);
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
        state.stlDimensions = file.dimensions;
        state.stlFileName = file.name;
        state.stlFileData = file.data;
        
        // Update dimension inputs
        elements.objLength.value = file.dimensions.length.toFixed(2);
        elements.objWidth.value = file.dimensions.width.toFixed(2);
        elements.objHeight.value = file.dimensions.height.toFixed(2);
        
        // Always update weight from stored value
        if (file.weight !== undefined && file.weight !== null) {
            elements.objWeight.value = file.weight;
        }
        
        elements.stlStatus.className = 'stl-status success';
        elements.stlStatus.textContent = `✅ ${file.name}: ${file.dimensions.length.toFixed(2)} × ${file.dimensions.width.toFixed(2)} × ${file.dimensions.height.toFixed(2)} mm`;
        
        // Refresh history to show updated order and active state
        await loadSTLHistory();
        
    } catch (error) {
        console.error('Error loading STL from history:', error);
        elements.stlStatus.className = 'stl-status error';
        elements.stlStatus.textContent = `❌ Error carregant: ${error.message}`;
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
        safetyFactor: parseInt(elements.safetyFactor.value) / 100,
        packingGap: parseFloat(elements.packingGap.value) || 0,
        // Bulk mode
        dropHeight: parseInt(elements.dropHeight.value),
        maxPieces: parseInt(elements.maxPieces.value),
        dropIntervalMs: parseInt(elements.dropInterval.value),
        colorCount: colorCount,
        randomRotation: elements.randomRotation.checked,
        autoCapacity: elements.autoCapacity.checked
    };
}

/**
 * Handle calculate button click (optimized mode)
 */
async function handleCalculate() {
    const values = getInputValues();
    
    // Run packing calculation
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
        
        if (nx > 0 && ny > 0 && nz > 0) {
            let drawn;
            
            if (state.stlGeometry) {
                // Deterministic permutation based on calculator's permIndex
                // Calculator inputs: L(X=0), W(Z=2), H(Y=1) -> Note: main.js inputs order matches X,Z,Y
                // But extractDimensions returns {length:x, width:z, height:y}
                // Handler input mapped: objL=X, objW=Z, objH=Y
                
                // Calculator permutations (resL, resW, resH):
                // 0: L, W, H (X, Z, Y) -> NewX=X(0), NewY=Y(1), NewZ=Z(2) -> [0, 1, 2]
                // 1: L, H, W (X, Y, Z) -> NewX=X(0), NewY=Z(2), NewZ=Y(1) -> [0, 2, 1]
                // 2: W, L, H (Z, X, Y) -> NewX=Z(2), NewY=Y(1), NewZ=X(0) -> [2, 1, 0]
                // 3: W, H, L (Z, Y, X) -> NewX=Z(2), NewY=X(0), NewZ=Y(1) -> [2, 0, 1]
                // 4: H, L, W (Y, X, Z) -> NewX=Y(1), NewY=Z(2), NewZ=X(0) -> [1, 2, 0]
                // 5: H, W, L (Y, Z, X) -> NewX=Y(1), NewY=X(0), NewZ=Z(2) -> [1, 0, 2]
                
                const permIndex = result.data.bestOrientation.permIndex;
                const permTable = [
                    [0, 1, 2], // 0
                    [0, 2, 1], // 1
                    [2, 1, 0], // 2
                    [2, 0, 1], // 3
                    [1, 2, 0], // 4
                    [1, 0, 2]  // 5
                ];
                
                // Fallback to 0 if undefined (should be defined)
                const perm = permTable[permIndex !== undefined ? permIndex : 0];
                
                // Clone and permute geometry
                const orientedGeometry = state.stlGeometry.clone();
                applyPermutation(orientedGeometry, perm);
                
                drawn = state.sceneManager.addPackedSTLPieces({
                    stlGeometry: orientedGeometry,
                    pieceL, pieceW, pieceH,
                    nx, ny, nz,
                    maxDraw: 500,
                    packingGap: values.packingGap,
                    colorCount: values.colorCount,
                    boxL: values.boxL,
                    boxW: values.boxW,
                    boxH: values.boxH
                });
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
            
            console.log(`Rendered ${drawn} pieces with ${values.packingGap}mm gap`);
            
            // Store results for report
            state.lastResults = {
                pieceDims: { l: values.objL, w: values.objW, h: values.objH },
                boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
                pieceCount: result.data.totalUnitats,
                pieceWeight: values.objWeight,
                maxWeight: values.maxWeight,
                mode: 'optimized',
                safetyFactor: values.safetyFactor,
                stlFileName: state.stlFileName || null
            };
            
            // Save to calculation history
            await saveCalculationToHistory(state.lastResults);
            
            // Show report buttons
            elements.reportButtons.style.display = 'flex';
        }
    }
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
async function updateSimulationStatus(status) {
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
            safetyFactor: values.safetyFactor,
            stlFileName: state.stlFileName || null
        };
        
        // Save to calculation history
        await saveCalculationToHistory(state.lastResults);
        
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

// Initialize app on DOM ready
document.addEventListener('DOMContentLoaded', init);

// Export for debugging
window.PackAssist = { state, elements };
