/**
 * PackAssist Web - Main Application
 * Connects UI with packing calculator, 3D visualization, and physics simulation
 */

import { calcularEmpaquetatge, getDistribution, getPieceDimensions } from './packing/calculator.js';
import { loadMesh, loadSTL, extractDimensions, centerToOrigin, isSupported, SUPPORTED_EXTENSIONS } from './mesh/mesh-utils.js';
import { SceneManager } from './visualization/scene.js';
import { BulkSimulation, initRapier } from './physics/physics-world.js';
import { ReportGenerator } from './report/report-generator.js';
import { getSimplificationModal } from './mesh/simplification-modal.js';

// Application state
const state = {
    mode: 'optimized', // 'optimized' or 'bulk'
    stlGeometry: null,
    stlDimensions: null,
    sceneManager: null,
    bulkSimulation: null,
    isSimulating: false,
    reportGenerator: null,
    lastResults: null // Store last results for report generation
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
    
    // Setup event listeners
    setupEventListeners();
    
    // Initialize physics (preload)
    try {
        await initRapier();
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
    
    // Packing gap slider
    elements.packingGap.addEventListener('input', (e) => {
        elements.packingGapValue.textContent = e.target.value;
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
        
    } catch (error) {
        elements.stlStatus.className = 'stl-status error';
        elements.stlStatus.textContent = `❌ Error: ${error.message}`;
        state.stlGeometry = null;
        state.stlDimensions = null;
    }
}

/**
 * Get current input values
 * @returns {Object}
 */
function getInputValues() {
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
        colorCount: parseInt(elements.pieceColors?.value) || 10,
        randomRotation: elements.randomRotation.checked,
        autoCapacity: elements.autoCapacity.checked
    };
}

/**
 * Handle calculate button click (optimized mode)
 */
function handleCalculate() {
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
            
            // Use STL geometry if available, otherwise use cuboids
            if (state.stlGeometry) {
                drawn = state.sceneManager.addPackedSTLPieces({
                    stlGeometry: state.stlGeometry,
                    pieceL, pieceW, pieceH,
                    nx, ny, nz,
                    maxDraw: 500,
                    packingGap: values.packingGap
                });
            } else {
                drawn = state.sceneManager.addPackedPieces({
                    pieceL, pieceW, pieceH,
                    nx, ny, nz,
                    maxDraw: 500,
                    packingGap: values.packingGap
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
                safetyFactor: values.safetyFactor
            };
            
            // Show report buttons
            elements.reportButtons.style.display = 'flex';
        }
    }
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

// Initialize app on DOM ready
document.addEventListener('DOMContentLoaded', init);

// Export for debugging
window.PackAssist = { state, elements };
