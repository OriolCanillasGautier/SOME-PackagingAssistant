/**
 * PackAssist Web - Main Application
 * Connects UI with packing calculator, 3D visualization, and physics simulation
 */

import * as THREE from 'three';
import { calcularEmpaquetatge, getDistribution, getPieceDimensions } from './packing/calculator.js?v=force_update_38';
import { loadMesh, loadSTL, extractDimensions, centerToOrigin, isSupported, SUPPORTED_EXTENSIONS, guessPermForDims, applyPermutation, getSupportStability } from './mesh/mesh-utils.js?v=force_update_38';
import { SceneManager } from './visualization/scene.js?v=force_update_38';
import { BulkSimulation, PhysicsWorld, initRapier } from './physics/physics-world.js?v=force_update_38';
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
    gravitySimulation: null,
    physicsWorld: null,
    orientationEval: null,
    reportGenerator: null,
    lastResults: null, // Store last results for report generation
    storage: null // StorageManager instance
};

function getPermutationCandidates() {
    const permTable = [
        { permIndex: 0, name: 'Perm 0 (X,Y,Z)', perm: [0, 1, 2] },
        { permIndex: 1, name: 'Perm 1 (X,Z,Y)', perm: [0, 2, 1] },
        { permIndex: 2, name: 'Perm 2 (Z,Y,X)', perm: [2, 1, 0] },
        { permIndex: 3, name: 'Perm 3 (Z,X,Y)', perm: [2, 0, 1] },
        { permIndex: 4, name: 'Perm 4 (Y,Z,X)', perm: [1, 2, 0] },
        { permIndex: 5, name: 'Perm 5 (Y,X,Z)', perm: [1, 0, 2] }
    ];
    return permTable;
}

function applyPermIndexToGeometry(geometry, permIndex) {
    const permTable = getPermutationCandidates();
    const perm = permTable.find(p => p.permIndex === permIndex)?.perm || [0, 1, 2];
    applyPermutation(geometry, perm);
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
        .map(r => {
            const disabled = r.count <= 0 ? 'disabled' : '';
            return `
                <tr>
                    <td>${r.name}</td>
                    <td>${r.count}</td>
                    <td><button class="btn-small" data-action="view-ori" data-perm="${r.permIndex}" ${disabled}>VEURE</button></td>
                </tr>
            `;
        })
        .join('');

    const html = `
        <div style="margin-top: 10px;">
            <button class="btn-small" data-action="toggle-ori">Alternatives d'orientació</button>
            <div data-role="ori-panel" style="display:none; margin-top: 8px;" class="results-content">
                <table>
                    <thead>
                        <tr>
                            <th>Orientació</th>
                            <th>Peces</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
                <p class="info-text" style="margin-top:6px;">* Comparació feta amb col·lisions reals (no travessen).</p>
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
    heightMapNesting: document.getElementById('heightmap-nesting'),
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
    state.sceneManager = new SceneManager(elements.threeCanvas);
    state.reportGenerator = new ReportGenerator(state.sceneManager);
    state.storage = new StorageManager();
    await state.storage.init();
    setupEventListeners();
    await loadSTLHistory();
    switchMode(state.mode);
    initRapier().then(() => {
        console.log('Physics engine ready');
    }).catch(() => {});
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    elements.modeButtons.forEach(btn => {
        btn.addEventListener('click', () => switchMode(btn.dataset.mode));
    });

    elements.safetyFactor?.addEventListener('input', (e) => {
        if (elements.safetyValue) {
            elements.safetyValue.textContent = e.target.value;
        }
    });

    elements.packingGap.addEventListener('input', (e) => {
        const val = e.target.value;
        elements.packingGapValue.textContent = `${val}`;
    });

    elements.optPieceColors?.addEventListener('input', (e) => {
        elements.optPieceColorsValue.textContent = e.target.value;
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
            const permIndex = parseInt(target.dataset.perm, 10);
            if (!Number.isFinite(permIndex)) return;
            const evalState = state.orientationEval;
            if (!evalState || !state.stlGeometry) return;

            const values = evalState.values;
            state.sceneManager.clearPieces();
            state.sceneManager.createBox(values.boxL, values.boxW, values.boxH);
            const oriented = state.stlGeometry.clone();
            applyPermIndexToGeometry(oriented, permIndex);
            const drawn = state.sceneManager.addPackedSTLHeightMap({
                stlGeometry: oriented,
                maxDraw: evalState.maxDraw,
                packingGap: values.packingGap,
                colorCount: values.colorCount,
                boxL: values.boxL,
                boxW: values.boxW,
                boxH: values.boxH,
                dryRun: false
            });

            const count = typeof drawn === 'number' ? drawn : drawn.count;
            console.log(`Rendered orientation perm=${permIndex} count=${count}`);
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
        elements.results.innerHTML = '<p class="placeholder-text">Configura les opcions i inicia la simulació</p>';
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
        elements.stlStatus.textContent = `Format no suportat. Formats vàlids: ${SUPPORTED_EXTENSIONS.join(', ')}`;
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
            elements.stlStatus.innerHTML = `Malla complexa (${vertexCount.toLocaleString()} vèrtexs). <button id="simplify-mesh-btn" class="btn-small">Simplificar</button>`;
            
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
                    elements.stlStatus.textContent = `Simplificat: ${newPositions.count.toLocaleString()} vèrtexs | ${state.stlDimensions.length.toFixed(2)} × ${state.stlDimensions.width.toFixed(2)} × ${state.stlDimensions.height.toFixed(2)} mm`;
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
            elements.stlStatus.textContent = `Dimensions: ${state.stlDimensions.length.toFixed(2)} × ${state.stlDimensions.width.toFixed(2)} × ${state.stlDimensions.height.toFixed(2)} mm`;
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
                <span class="stl-icon"></span>
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
                    <button class="stl-btn load" data-id="${file.id}" title="Carregar">Carregar</button>
                    <button class="stl-btn delete" data-id="${file.id}" title="Eliminar">Eliminar</button>
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
        elements.stlStatus.textContent = `${file.name}: ${file.dimensions.length.toFixed(2)} × ${file.dimensions.width.toFixed(2)} × ${file.dimensions.height.toFixed(2)} mm`;
        
        // Refresh history to show updated order and active state
        await loadSTLHistory();
        
    } catch (error) {
        console.error('Error loading STL from history:', error);
        elements.stlStatus.className = 'stl-status error';
        elements.stlStatus.textContent = `Error carregant: ${error.message}`;
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
        heightMapNesting: elements.heightMapNesting?.checked ?? true,
        safetyFactor: 1.0,
        packingGap: Math.max(0, parseFloat(elements.packingGap.value) || 0),
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
    const orientationNames = ['Original (L×W×H)'];
    const overrides = [];

    const rotations = [];
    rotations.push({ name: orientationNames[0], rotation: [0, 0, 0, 1] });

    if (allowRotation) {
        const sampleCount = 12;
        const spinSteps = 2;
        const goldenAngle = Math.PI * (3 - Math.sqrt(5));
        for (let i = 0; i < sampleCount; i++) {
            const y = 1 - (i + 0.5) * (2 / sampleCount);
            const r = Math.sqrt(Math.max(0, 1 - y * y));
            const phi = i * goldenAngle;
            const x = r * Math.cos(phi);
            const z = r * Math.sin(phi);
            const dir = new THREE.Vector3(x, y, z).normalize();
            const baseQuat = new THREE.Quaternion().setFromUnitVectors(
                new THREE.Vector3(0, 1, 0),
                dir
            );

            for (let s = 0; s < spinSteps; s++) {
                const spin = (Math.PI * 2 * s) / spinSteps;
                const spinQuat = new THREE.Quaternion().setFromAxisAngle(dir, spin);
                const q = spinQuat.multiply(baseQuat);
                rotations.push({
                    name: `Rotació ${i + 1}.${s + 1}`,
                    rotation: [q.x, q.y, q.z, q.w]
                });
            }
        }
    }

    const seen = new Set();
    for (const rot of rotations) {
        const key = rot.rotation.map(v => v.toFixed(4)).join(',');
        if (seen.has(key)) continue;
        seen.add(key);

        const orientedGeometry = geometry.clone();
        const quat = new THREE.Quaternion(...rot.rotation);
        const matrix = new THREE.Matrix4().makeRotationFromQuaternion(quat);
        orientedGeometry.applyMatrix4(matrix);
        orientedGeometry.computeBoundingBox();
        const stability = getSupportStability(orientedGeometry);
        orientedGeometry.computeBoundingBox();
        const bbox = orientedGeometry.boundingBox;
        const dims = [
            bbox.max.x - bbox.min.x,
            bbox.max.z - bbox.min.z,
            bbox.max.y - bbox.min.y
        ];
        overrides.push({
            dims,
            name: rot.name,
            permIndex: 0,
            rotation: rot.rotation,
            stable: stability.stable
        });
    }

    const stableOnly = overrides.filter(o => o.stable);
    return stableOnly.length > 0 ? stableOnly : overrides;
}

/**
 * Handle calculate button click (optimized mode)
 */
async function handleCalculate() {
    elements.results.innerHTML = '<p class="loading-text">Calculant...</p>';
    
    // Delay to allow UI update
    await new Promise(resolve => setTimeout(resolve, 10));

    // Get input values
    const values = getInputValues();

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
    
    // Run packing calculation
    const result = calcularEmpaquetatge({
        ...values,
        orientationOverrides
    });

    
    // Display results
    elements.results.innerHTML = result.summary;
    elements.results.classList.add('fade-in');
    
    // Update 3D visualization
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
            if (state.stlGeometry) {
                if (values.heightMapNesting) {
                    const maxDraw = 500;

                    // Try multiple axis permutations (at least 4) and pick the densest by real collision-aware placement
                    const candidates = values.allowRotation ? getPermutationCandidates() : getPermutationCandidates().slice(0, 1);
                    const evalResults = [];
                    for (const c of candidates) {
                        const oriented = state.stlGeometry.clone();
                        applyPermIndexToGeometry(oriented, c.permIndex);

                        const footprintArea = computeFootprintArea(oriented);

                        // Stability heuristic (support polygon / COM)
                        const stability = getSupportStability(oriented);
                        const trial = state.sceneManager.addPackedSTLHeightMap({
                            stlGeometry: oriented,
                            maxDraw,
                            packingGap: values.packingGap,
                            colorCount: values.colorCount,
                            boxL: values.boxL,
                            boxW: values.boxW,
                            boxH: values.boxH,
                            dryRun: true
                        });
                        const count = typeof trial === 'number' ? trial : trial.count;
                        evalResults.push({
                            permIndex: c.permIndex,
                            name: c.name,
                            count: count || 0,
                            stable: !!stability?.stable,
                            baseArea: footprintArea || 0
                        });
                    }

                    // Sort by count desc, then stable desc, then base footprint desc
                    evalResults.sort((a, b) => {
                        if (b.count !== a.count) return b.count - a.count;
                        if (b.stable !== a.stable) return b.stable ? 1 : -1;
                        return (b.baseArea || 0) - (a.baseArea || 0);
                    });

                    let best = evalResults[0] || { permIndex: 0, name: 'Perm 0 (X,Y,Z)', count: 0, stable: false, baseArea: 0 };

                    // If another orientation is almost as dense, prefer a more stable / larger-base one
                    const nearBestSlack = 0.98;
                    const bestCount = Math.max(0, best.count || 0);
                    if (bestCount > 0) {
                        const nearBest = evalResults.filter(r => (r.count || 0) >= bestCount * nearBestSlack);
                        if (nearBest.length > 0) {
                            nearBest.sort((a, b) => {
                                if ((b.stable !== a.stable)) return b.stable ? 1 : -1;
                                const areaDelta = (b.baseArea || 0) - (a.baseArea || 0);
                                if (areaDelta !== 0) return areaDelta;
                                return (b.count || 0) - (a.count || 0);
                            });
                            best = nearBest[0];
                        }
                    }

                    state.orientationEval = {
                        values: { ...values },
                        maxDraw,
                        results: evalResults
                    };

                    const bestGeom = state.stlGeometry.clone();
                    applyPermIndexToGeometry(bestGeom, best.permIndex);

                    drawn = state.sceneManager.addPackedSTLHeightMap({
                        stlGeometry: bestGeom,
                        maxDraw,
                        packingGap: values.packingGap,
                        colorCount: values.colorCount,
                        boxL: values.boxL,
                        boxW: values.boxW,
                        boxH: values.boxH,
                        dryRun: false
                    });

                    // Add a small UI block so you can inspect other orientations
                    renderOrientationAlternativesUI(state.orientationEval);
                } else {
                    // Non-heightmap path keeps the calculator-chosen orientation
                    const orientedGeometry = state.stlGeometry.clone();
                    const best = result.data.bestOrientation || {};
                    if (best.rotation && Array.isArray(best.rotation)) {
                        const quat = new THREE.Quaternion(...best.rotation);
                        const matrix = new THREE.Matrix4().makeRotationFromQuaternion(quat);
                        orientedGeometry.applyMatrix4(matrix);
                    } else {
                        applyPermIndexToGeometry(orientedGeometry, best.permIndex ?? 0);
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
            
            const displayCount = drawnCount;

            console.log(`Rendered ${drawnCount} items (${displayCount} pieces)`);

            // If render count differs due to real geometry, warn and use rendered count for reports
            const resultRealUnits = result.data.realUnits; // This is already multiplied
            
            if (displayCount < resultRealUnits || realDistributionText) {
                if (displayCount < resultRealUnits) {
                    const safetyPercent = Math.round(values.safetyFactor * 100);
                    const listItems = elements.results.querySelectorAll('li');
                    listItems.forEach(li => {
                        if (li.textContent.includes('Unitats reals (seguretat')) {
                            li.innerHTML = `<strong>Unitats reals (seguretat ${safetyPercent}%):</strong> ${displayCount}`;
                        }
                    });
                }
                if (realDistributionText) {
                    const listItems = elements.results.querySelectorAll('li');
                    listItems.forEach(li => {
                        if (li.textContent.includes('Distribució:')) {
                            li.innerHTML = `<strong>Distribució:</strong> ${realDistributionText} (L×W×H)`;
                        }
                    });
                }
            }
            
            // Store results logic ...
             state.lastResults = {
                pieceDims: { l: values.objL, w: values.objW, h: values.objH },
                boxDims: { length: values.boxL, width: values.boxW, height: values.boxH },
                pieceCount: displayCount,
                pieceWeight: values.objWeight,
                maxWeight: values.maxWeight,
                mode: 'optimized',
                safetyFactor: values.safetyFactor,
                stlFileName: state.stlFileName || null
            };
            
            await saveCalculationToHistory(state.lastResults);
            
             // Show report buttons
            elements.reportButtons.style.display = 'flex';
            if (elements.applyGravityBtn) {
                elements.applyGravityBtn.style.display = 'block';
            }
        }
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

    placement.positions.forEach((pos, idx) => {
        const color = pieceColors.length > 0 ? pieceColors[idx % colorCount] : 0x3b82f6;
        let mesh;

        if (placement.type === 'stl' && placement.geometry) {
            const geometry = placement.geometry.clone();
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

            if (placement.vertices) {
                // Recenter vertices so Rapier body translation is at COM
                const verts = placement.vertices;
                const centered = new Float32Array(verts.length);
                for (let i = 0; i < verts.length; i += 3) {
                    centered[i] = verts[i] - center.x;
                    centered[i + 1] = verts[i + 1] - center.y;
                    centered[i + 2] = verts[i + 2] - center.z;
                }

                const bodyPos = new THREE.Vector3(pos.x + center.x, pos.y + center.y, pos.z + center.z);
                physics.addConvexHull(centered, bodyPos, null, mesh, center);
            } else {
                const bodyPos = new THREE.Vector3(pos.x + center.x, pos.y + center.y, pos.z + center.z);
                physics.addCuboid({
                    l: placement.dims.l,
                    w: placement.dims.w,
                    h: placement.dims.h
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

            physics.addCuboid({
                l: placement.dims.l,
                w: placement.dims.w,
                h: placement.dims.h
            }, pos, null, mesh);
        }
    });

    physics.start();

    return {
        physics,
        running: true,
        animationId: null
    };
}


async function applyGravityTest() {
    if (!state.sceneManager?.lastPlacement) return;

    if (!state.gravitySimulation) {
        const sim = await initGravitySimulation();
        if (!sim) return;
        state.gravitySimulation = sim;
    }

    const sim = state.gravitySimulation;
    sim.running = true;
    sim.physics.setGravity(-9810);
    sim.physics.lockAllRotations(false);

    if (elements.simulationStatus) {
        elements.simulationStatus.textContent = '⚖️ Gravetat aplicada (rotacions lliures)';
        elements.simulationStatus.style.display = 'block';
    }

    const animate = () => {
        if (!sim.running) return;
        sim.physics.step();
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
        elements.results.innerHTML = '<p>Totes les dimensions han de ser majors que 0</p>';
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
        elements.results.innerHTML = `<p>Error inicialitzant simulació: ${error.message}</p>`;
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
    
    elements.results.innerHTML = '<p class="placeholder-text">Configura les opcions i inicia la simulació</p>';
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
            <h1>Resultat Simulació a Granel</h1>
            <ul>
                <li><strong>Peces deixades caure:</strong> ${status.dropped}</li>
                <li><strong>Peces dins la caixa:</strong> ${status.inside}</li>
                ${removedText}
                <li><strong>Eficiència:</strong> ${((status.inside / status.dropped) * 100).toFixed(1)}%</li>
            </ul>
            <p>En mode a granel, les peces s'acomoden de forma natural per gravetat. 
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
