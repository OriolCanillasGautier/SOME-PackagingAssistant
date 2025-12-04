/**
 * PackAssist Web - Simplification Modal
 * Modal interactiu per simplificar malles 3D abans d'usar-les
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { MeshSimplifier } from './mesh-simplifier.js';

/**
 * Classe per gestionar el modal de simplificació de malla
 */
export class SimplificationModal {
    constructor() {
        this.modal = null;
        this.renderer = null;
        this.scene = null;
        this.camera = null;
        this.controls = null;
        this.originalGeometry = null;
        this.simplifiedGeometry = null;
        this.simplifier = null;
        this.currentMesh = null;
        this.onComplete = null;
        this.animationId = null;
        
        this._createModal();
    }
    
    _createModal() {
        // Crear estructura del modal
        this.modal = document.createElement('div');
        this.modal.id = 'simplification-modal';
        this.modal.className = 'modal';
        this.modal.style.display = 'none';
        
        this.modal.innerHTML = `
            <div class="modal-content modal-xlarge">
                <div class="modal-header">
                    <h2>🔧 Simplificació de Malla 3D</h2>
                    <button class="modal-close" id="simplify-modal-close">×</button>
                </div>
                <div class="modal-body simplify-modal-body">
                    <div class="simplify-layout">
                        <!-- Panel de controls -->
                        <div class="simplify-controls">
                            <div class="control-section">
                                <h3>📊 Malla Original</h3>
                                <div id="original-stats" class="stats-box">
                                    <div class="stat-row">
                                        <span>Vèrtexs:</span>
                                        <span id="orig-vertices">-</span>
                                    </div>
                                    <div class="stat-row">
                                        <span>Triangles:</span>
                                        <span id="orig-faces">-</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="control-section">
                                <h3>🎚️ Nivell de Simplificació</h3>
                                <div class="slider-container">
                                    <input type="range" id="simplify-slider" min="1" max="100" value="50">
                                    <div class="slider-labels">
                                        <span>Mínim</span>
                                        <span id="simplify-percent">50%</span>
                                        <span>Original</span>
                                    </div>
                                </div>
                                
                                <div class="preset-buttons">
                                    <button class="preset-btn" data-value="10">Ultra ràpid (10%)</button>
                                    <button class="preset-btn" data-value="25">Ràpid (25%)</button>
                                    <button class="preset-btn" data-value="50">Equilibrat (50%)</button>
                                    <button class="preset-btn" data-value="75">Detallat (75%)</button>
                                    <button class="preset-btn" data-value="100">Original (100%)</button>
                                </div>
                            </div>
                            
                            <div class="control-section">
                                <h3>⚙️ Opcions</h3>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="preserve-features" checked>
                                    Preservar característiques importants
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="create-envelope">
                                    Crear embolcall convex (tanca forats)
                                </label>
                            </div>
                            
                            <div class="control-section">
                                <h3>📈 Malla Resultant</h3>
                                <div id="result-stats" class="stats-box stats-result">
                                    <div class="stat-row">
                                        <span>Vèrtexs:</span>
                                        <span id="result-vertices">-</span>
                                    </div>
                                    <div class="stat-row">
                                        <span>Triangles:</span>
                                        <span id="result-faces">-</span>
                                    </div>
                                    <div class="stat-row reduction">
                                        <span>Reducció:</span>
                                        <span id="result-reduction">-</span>
                                    </div>
                                    <div class="stat-row quality">
                                        <span>Qualitat volum:</span>
                                        <span id="result-quality">-</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="control-section">
                                <h3>👁️ Visualització</h3>
                                <div class="view-toggle">
                                    <button class="view-btn active" data-view="simplified">Simplificada</button>
                                    <button class="view-btn" data-view="original">Original</button>
                                    <button class="view-btn" data-view="compare">Comparar</button>
                                </div>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="show-wireframe">
                                    Mostrar wireframe
                                </label>
                            </div>
                        </div>
                        
                        <!-- Visor 3D -->
                        <div class="simplify-viewer">
                            <div id="simplify-canvas"></div>
                            <div class="viewer-hint">🖱️ Arrossega per girar | Scroll per zoom</div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button id="simplify-cancel" class="btn-secondary">Cancel·lar</button>
                    <button id="simplify-apply" class="btn-primary">✅ Aplicar Simplificació</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.modal);
        this._addStyles();
        this._setupEventListeners();
    }
    
    _addStyles() {
        // Afegir estils específics si no existeixen
        if (document.getElementById('simplify-modal-styles')) return;
        
        const styles = document.createElement('style');
        styles.id = 'simplify-modal-styles';
        styles.textContent = `
            .modal-xlarge {
                max-width: 1200px;
                width: 95%;
            }
            
            .simplify-modal-body {
                padding: 0 !important;
            }
            
            .simplify-layout {
                display: flex;
                height: 600px;
            }
            
            .simplify-controls {
                width: 320px;
                padding: 20px;
                background: var(--bg-card);
                border-right: 1px solid var(--border-color);
                overflow-y: auto;
            }
            
            .simplify-viewer {
                flex: 1;
                position: relative;
                background: #1a1a2e;
            }
            
            #simplify-canvas {
                width: 100%;
                height: 100%;
            }
            
            .viewer-hint {
                position: absolute;
                bottom: 10px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0,0,0,0.7);
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 12px;
            }
            
            .control-section {
                margin-bottom: 20px;
            }
            
            .control-section h3 {
                font-size: 14px;
                margin-bottom: 10px;
                color: var(--text-primary);
            }
            
            .stats-box {
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 12px;
            }
            
            .stats-result {
                background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(59, 130, 246, 0.1));
                border-color: var(--accent-green);
            }
            
            .stat-row {
                display: flex;
                justify-content: space-between;
                padding: 4px 0;
                font-size: 13px;
            }
            
            .stat-row span:last-child {
                font-weight: 600;
                color: var(--accent-blue);
            }
            
            .stat-row.reduction span:last-child {
                color: var(--accent-green);
            }
            
            .stat-row.quality span:last-child {
                color: var(--accent-purple);
            }
            
            .slider-container {
                margin: 15px 0;
            }
            
            .slider-container input[type="range"] {
                width: 100%;
                height: 8px;
                border-radius: 4px;
                background: var(--bg-secondary);
                outline: none;
                -webkit-appearance: none;
            }
            
            .slider-container input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: var(--accent-blue);
                cursor: pointer;
            }
            
            .slider-labels {
                display: flex;
                justify-content: space-between;
                font-size: 11px;
                color: var(--text-muted);
                margin-top: 5px;
            }
            
            .slider-labels span:nth-child(2) {
                font-weight: 700;
                color: var(--accent-blue);
                font-size: 14px;
            }
            
            .preset-buttons {
                display: flex;
                flex-direction: column;
                gap: 6px;
                margin-top: 10px;
            }
            
            .preset-btn {
                padding: 8px 12px;
                border: 1px solid var(--border-color);
                border-radius: 6px;
                background: var(--bg-secondary);
                color: var(--text-primary);
                cursor: pointer;
                font-size: 12px;
                transition: all 0.2s;
            }
            
            .preset-btn:hover {
                background: var(--accent-blue);
                color: white;
                border-color: var(--accent-blue);
            }
            
            .checkbox-label {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 6px 0;
                cursor: pointer;
                font-size: 13px;
            }
            
            .checkbox-label input[type="checkbox"] {
                width: 18px;
                height: 18px;
                accent-color: var(--accent-blue);
            }
            
            .view-toggle {
                display: flex;
                gap: 5px;
                margin-bottom: 10px;
            }
            
            .view-toggle .view-btn {
                flex: 1;
                padding: 8px;
                border: 1px solid var(--border-color);
                border-radius: 6px;
                background: var(--bg-secondary);
                color: var(--text-secondary);
                cursor: pointer;
                font-size: 11px;
                transition: all 0.2s;
            }
            
            .view-toggle .view-btn.active {
                background: var(--accent-blue);
                color: white;
                border-color: var(--accent-blue);
            }
        `;
        
        document.head.appendChild(styles);
    }
    
    _setupEventListeners() {
        // Tancar modal
        this.modal.querySelector('#simplify-modal-close').addEventListener('click', () => this.close());
        this.modal.querySelector('#simplify-cancel').addEventListener('click', () => this.close());
        
        // Click fora del modal
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) this.close();
        });
        
        // Slider de simplificació
        const slider = this.modal.querySelector('#simplify-slider');
        slider.addEventListener('input', (e) => {
            this._onSliderChange(parseInt(e.target.value));
        });
        
        // Botons preset
        this.modal.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const value = parseInt(btn.dataset.value);
                slider.value = value;
                this._onSliderChange(value);
            });
        });
        
        // Opcions
        this.modal.querySelector('#preserve-features').addEventListener('change', () => {
            this._updateSimplification();
        });
        
        this.modal.querySelector('#create-envelope').addEventListener('change', () => {
            this._updateSimplification();
        });
        
        // Wireframe
        this.modal.querySelector('#show-wireframe').addEventListener('change', (e) => {
            this._toggleWireframe(e.target.checked);
        });
        
        // Vista
        this.modal.querySelectorAll('.view-toggle .view-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.modal.querySelectorAll('.view-toggle .view-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this._changeView(btn.dataset.view);
            });
        });
        
        // Aplicar
        this.modal.querySelector('#simplify-apply').addEventListener('click', () => {
            this._applySimplification();
        });
    }
    
    /**
     * Obre el modal amb una geometria
     * @param {THREE.BufferGeometry} geometry - Geometria a simplificar
     * @param {Function} onComplete - Callback quan s'aplica la simplificació
     */
    open(geometry, onComplete) {
        this.originalGeometry = geometry.clone();
        this.onComplete = onComplete;
        
        // Crear simplificador
        this.simplifier = new MeshSimplifier(geometry);
        
        // Mostrar estadístiques originals
        this._updateOriginalStats();
        
        // Mostrar modal
        this.modal.style.display = 'flex';
        
        // Inicialitzar visor 3D
        this._initViewer();
        
        // Simplificació inicial al 50%
        this.modal.querySelector('#simplify-slider').value = 50;
        this._onSliderChange(50);
    }
    
    close() {
        this.modal.style.display = 'none';
        
        // Aturar animació
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        
        // Netejar renderer
        if (this.renderer) {
            this.renderer.dispose();
            this.renderer = null;
        }
        
        // Netejar escena
        if (this.scene) {
            while (this.scene.children.length > 0) {
                const obj = this.scene.children[0];
                this.scene.remove(obj);
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) obj.material.dispose();
            }
        }
    }
    
    _initViewer() {
        const container = this.modal.querySelector('#simplify-canvas');
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        // Escena
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e);
        
        // Càmera
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 10000);
        this.camera.position.set(200, 200, 200);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        container.innerHTML = '';
        container.appendChild(this.renderer.domElement);
        
        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        
        // Llums
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(100, 200, 100);
        this.scene.add(directionalLight);
        
        // Grid
        const gridHelper = new THREE.GridHelper(500, 20, 0x444444, 0x333333);
        this.scene.add(gridHelper);
        
        // Animar
        this._animate();
    }
    
    _animate() {
        this.animationId = requestAnimationFrame(() => this._animate());
        
        if (this.controls) {
            this.controls.update();
        }
        
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }
    
    _updateOriginalStats() {
        const positions = this.originalGeometry.getAttribute('position');
        
        this.modal.querySelector('#orig-vertices').textContent = positions.count.toLocaleString();
        this.modal.querySelector('#orig-faces').textContent = Math.floor(positions.count / 3).toLocaleString();
    }
    
    _onSliderChange(value) {
        this.modal.querySelector('#simplify-percent').textContent = `${value}%`;
        
        // Debounce per evitar càlculs excessius
        if (this._sliderTimeout) {
            clearTimeout(this._sliderTimeout);
        }
        
        this._sliderTimeout = setTimeout(() => {
            this._updateSimplification();
        }, 150);
    }
    
    _updateSimplification() {
        const ratio = parseInt(this.modal.querySelector('#simplify-slider').value) / 100;
        const preserveFeatures = this.modal.querySelector('#preserve-features').checked;
        
        // Simplificar
        this.simplifiedGeometry = this.simplifier.simplify(ratio, preserveFeatures);
        
        // Crear embolcall si cal
        const createEnvelope = this.modal.querySelector('#create-envelope').checked;
        if (createEnvelope && ratio < 0.5) {
            // Per ratios baixos, l'embolcall ajuda a mantenir la forma tancada
            // Però per ara només ajustem la malla
        }
        
        // Actualitzar estadístiques
        this._updateResultStats();
        
        // Actualitzar visualització
        this._updateMeshDisplay();
    }
    
    _updateResultStats() {
        const stats = this.simplifier.getStats(this.simplifiedGeometry);
        
        this.modal.querySelector('#result-vertices').textContent = stats.newVertices.toLocaleString();
        this.modal.querySelector('#result-faces').textContent = stats.newFaces.toLocaleString();
        this.modal.querySelector('#result-reduction').textContent = `${stats.vertexReduction}%`;
        this.modal.querySelector('#result-quality').textContent = `${stats.volumePreservation}%`;
    }
    
    _updateMeshDisplay() {
        // Eliminar malla anterior
        if (this.currentMesh) {
            this.scene.remove(this.currentMesh);
            if (this.currentMesh.geometry) this.currentMesh.geometry.dispose();
            if (this.currentMesh.material) this.currentMesh.material.dispose();
        }
        
        // Crear nova malla
        const material = new THREE.MeshPhongMaterial({
            color: 0x3b82f6,
            flatShading: true,
            side: THREE.DoubleSide
        });
        
        this.currentMesh = new THREE.Mesh(this.simplifiedGeometry.clone(), material);
        
        // Centrar i ajustar càmera
        const bbox = new THREE.Box3().setFromObject(this.currentMesh);
        const center = new THREE.Vector3();
        const size = new THREE.Vector3();
        bbox.getCenter(center);
        bbox.getSize(size);
        
        this.currentMesh.position.sub(center);
        
        const maxDim = Math.max(size.x, size.y, size.z);
        this.camera.position.set(maxDim * 1.5, maxDim * 1.5, maxDim * 1.5);
        this.controls.target.set(0, 0, 0);
        
        this.scene.add(this.currentMesh);
        
        // Wireframe si està activat
        if (this.modal.querySelector('#show-wireframe').checked) {
            this._addWireframe();
        }
    }
    
    _toggleWireframe(show) {
        // Eliminar wireframe existent
        const existing = this.scene.getObjectByName('wireframe');
        if (existing) {
            this.scene.remove(existing);
            existing.geometry.dispose();
            existing.material.dispose();
        }
        
        if (show && this.currentMesh) {
            this._addWireframe();
        }
    }
    
    _addWireframe() {
        if (!this.currentMesh) return;
        
        const wireframeGeometry = new THREE.WireframeGeometry(this.currentMesh.geometry);
        const wireframeMaterial = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 1 });
        const wireframe = new THREE.LineSegments(wireframeGeometry, wireframeMaterial);
        wireframe.name = 'wireframe';
        wireframe.position.copy(this.currentMesh.position);
        
        this.scene.add(wireframe);
    }
    
    _changeView(view) {
        // TODO: Implementar vistes comparatives
        console.log('Vista:', view);
    }
    
    _applySimplification() {
        if (this.simplifiedGeometry && this.onComplete) {
            this.onComplete(this.simplifiedGeometry.clone());
        }
        this.close();
    }
}

// Singleton
let modalInstance = null;

/**
 * Obté la instància del modal de simplificació
 * @returns {SimplificationModal}
 */
export function getSimplificationModal() {
    if (!modalInstance) {
        modalInstance = new SimplificationModal();
    }
    return modalInstance;
}

export default SimplificationModal;
