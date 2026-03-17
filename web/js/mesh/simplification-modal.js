/**
 * PackAssist Web - Simplification Modal
 * Modal interactiu per simplificar malles 3D abans d'usar-les
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { ConvexGeometry } from 'three/addons/geometries/ConvexGeometry.js';
import { MeshSimplifier } from './mesh-simplifier.js';
import { getStoredLanguage, loadLocale, t } from '../i18n.js';

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
        this.fileName = 'packassist_mesh.stl';
        this.language = getStoredLanguage();
        this.locale = null;
        
        this._createModal();
        this._refreshLanguage().catch(err => console.error('[SimplificationModal] Locale error:', err));
    }

    modalText(path, variables = {}, fallback = path) {
        return t(this.locale, `main.simplifyModal.${path}`, variables, fallback);
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
                    <h2 id="simplify-title">Simplificació de Malla 3D</h2>
                    <button class="modal-close" id="simplify-modal-close">×</button>
                </div>
                <div class="modal-body simplify-modal-body">
                    <div class="simplify-layout">
                        <!-- Panel de controls -->
                        <div class="simplify-controls">
                            <div class="control-section">
                                <h3 id="simplify-original-title">Malla Original</h3>
                                <div id="original-stats" class="stats-box">
                                    <div class="stat-row">
                                        <span id="simplify-orig-vertices-label">Vèrtexs:</span>
                                        <span id="orig-vertices">-</span>
                                    </div>
                                    <div class="stat-row">
                                        <span id="simplify-orig-triangles-label">Triangles:</span>
                                        <span id="orig-faces">-</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="control-section">
                                <h3 id="simplify-level-title">Nivell de Simplificació</h3>
                                <div class="slider-container">
                                    <input type="range" id="simplify-slider" min="0.1" max="100" step="0.1" value="50">
                                    <div class="slider-labels">
                                        <span id="simplify-minimum-label">Mínim</span>
                                        <span id="simplify-percent">50%</span>
                                        <span id="simplify-original-label">Original</span>
                                    </div>
                                </div>
                                
                                <div class="preset-buttons">
                                    <button class="preset-btn" data-value="0.5" id="preset-minimum">Mínim (0.5%)</button>
                                    <button class="preset-btn" data-value="5" id="preset-ultra-fast">Ultra ràpid (5%)</button>
                                    <button class="preset-btn" data-value="25" id="preset-fast">Ràpid (25%)</button>
                                    <button class="preset-btn" data-value="50" id="preset-balanced">Equilibrat (50%)</button>
                                    <button class="preset-btn" data-value="75" id="preset-detailed">Detallat (75%)</button>
                                    <button class="preset-btn" data-value="100" id="preset-original">Original (100%)</button>
                                </div>
                            </div>
                            
                            <div class="control-section">
                                <h3 id="simplify-options-title">Opcions</h3>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="preserve-features" checked>
                                    <span id="simplify-preserve-label">Preservar característiques importants</span>
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="create-envelope">
                                    <span id="simplify-envelope-label">Crear embolcall convex (tanca forats)</span>
                                </label>
                                <div id="simplify-backend" class="backend-indicator" style="margin-top:8px;font-size:11px;color:var(--text-muted);"></div>
                            </div>
                            
                            <div class="control-section">
                                <h3 id="simplify-result-title">Malla Resultant</h3>
                                <div id="result-stats" class="stats-box stats-result">
                                    <div class="stat-row">
                                        <span id="simplify-result-vertices-label">Vèrtexs:</span>
                                        <span id="result-vertices">-</span>
                                    </div>
                                    <div class="stat-row">
                                        <span id="simplify-result-triangles-label">Triangles:</span>
                                        <span id="result-faces">-</span>
                                    </div>
                                    <div class="stat-row reduction">
                                        <span id="simplify-reduction-label">Reducció:</span>
                                        <span id="result-reduction">-</span>
                                    </div>
                                    <div class="stat-row quality">
                                        <span id="simplify-quality-label">Qualitat volum:</span>
                                        <span id="result-quality">-</span>
                                    </div>
                                    <div class="stat-row">
                                        <span id="simplify-watertight-label">Estanqueïtat:</span>
                                        <span id="result-watertight">-</span>
                                    </div>
                                </div>
                                <div id="quality-warning" class="quality-warning" style="display:none;"></div>
                            </div>
                            
                            <div class="control-section">
                                <h3 id="simplify-visualization-title">Visualització</h3>
                                <div class="view-toggle">
                                    <button class="view-btn active" data-view="simplified" id="view-simplified">Simplificada</button>
                                    <button class="view-btn" data-view="original" id="view-original">Original</button>
                                    <button class="view-btn" data-view="compare" id="view-compare">Comparar</button>
                                </div>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="show-wireframe">
                                    <span id="simplify-wireframe-label">Mostrar wireframe</span>
                                </label>
                            </div>
                        </div>
                        
                        <!-- Visor 3D -->
                        <div class="simplify-viewer">
                            <div id="simplify-canvas"></div>
                            <div class="viewer-hint" id="simplify-viewer-hint">Arrossega per girar | Scroll per zoom</div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button id="simplify-cancel" class="btn-secondary">Cancel·lar</button>
                    <button id="simplify-download" class="btn-secondary">Descarregar STL</button>
                    <button id="simplify-apply" class="btn-primary">Aplicar Simplificació</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.modal);
        this._addStyles();
        this._setupEventListeners();
    }

    async _refreshLanguage() {
        this.language = getStoredLanguage();
        this.locale = await loadLocale(this.language);
        if (!this.modal) return;

        const setText = (id, value) => {
            const el = this.modal.querySelector(`#${id}`);
            if (el) el.textContent = value;
        };

        setText('simplify-title', this.modalText('title'));
        setText('simplify-original-title', this.modalText('originalMesh'));
        setText('simplify-orig-vertices-label', this.modalText('vertices'));
        setText('simplify-orig-triangles-label', this.modalText('triangles'));
        setText('simplify-level-title', this.modalText('simplificationLevel'));
        setText('simplify-minimum-label', this.modalText('minimum'));
        setText('simplify-original-label', this.modalText('original'));
        setText('preset-minimum', this.modalText('presetMinimum'));
        setText('preset-ultra-fast', this.modalText('presetUltraFast'));
        setText('preset-fast', this.modalText('presetFast'));
        setText('preset-balanced', this.modalText('presetBalanced'));
        setText('preset-detailed', this.modalText('presetDetailed'));
        setText('preset-original', this.modalText('presetOriginal'));
        setText('simplify-options-title', this.modalText('options'));
        setText('simplify-preserve-label', this.modalText('preserveFeatures'));
        setText('simplify-envelope-label', this.modalText('createEnvelope'));
        setText('simplify-result-title', this.modalText('resultMesh'));
        setText('simplify-result-vertices-label', this.modalText('vertices'));
        setText('simplify-result-triangles-label', this.modalText('triangles'));
        setText('simplify-reduction-label', this.modalText('reduction'));
        setText('simplify-quality-label', this.modalText('volumeQuality'));
        setText('simplify-watertight-label', this.modalText('watertight'));
        setText('simplify-visualization-title', this.modalText('visualization'));
        setText('view-simplified', this.modalText('viewSimplified'));
        setText('view-original', this.modalText('viewOriginal'));
        setText('view-compare', this.modalText('viewCompare'));
        setText('simplify-wireframe-label', this.modalText('showWireframe'));
        setText('simplify-viewer-hint', this.modalText('viewerHint'));
        setText('simplify-cancel', this.locale?.common?.buttons?.cancel || 'Cancel');
        setText('simplify-download', this.locale?.common?.buttons?.download || 'Download');
        setText('simplify-apply', this.modalText('apply'));
        this._updateResultStats();
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
                background: var(--bg-secondary);
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

            .quality-warning {
                margin-top: 10px;
                padding: 10px 12px;
                border-radius: 8px;
                background: rgba(245, 158, 11, 0.12);
                border: 1px solid rgba(245, 158, 11, 0.4);
                color: #f59e0b;
                font-size: 12px;
                line-height: 1.4;
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
            this._onSliderChange(parseFloat(e.target.value));
        });
        
        // Botons preset
        this.modal.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const value = parseFloat(btn.dataset.value);
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
            this._applySimplification().catch(err => console.error('[SimplificationModal] Apply error:', err));
        });

        this.modal.querySelector('#simplify-download').addEventListener('click', () => {
            this._downloadCurrentSTL().catch(err => console.error('[SimplificationModal] Download error:', err));
        });
    }
    
    /**
     * Obre el modal amb una geometria
     * @param {THREE.BufferGeometry} geometry - Geometria a simplificar
     * @param {Function} onComplete - Callback quan s'aplica la simplificació
     * @param {ArrayBuffer|null} rawSTLData - Raw STL binary (for server-side simplification)
     */
    open(geometry, onComplete, rawSTLData = null, fileName = 'packassist_mesh.stl') {
        this._refreshLanguage().catch(err => console.error('[SimplificationModal] Locale refresh error:', err));
        this.originalGeometry = geometry.clone();
        this.onComplete = onComplete;
        this.fileName = fileName;
        
        // Crear simplificador (pass raw STL for server path)
        this.simplifier = new MeshSimplifier(geometry, rawSTLData);
        
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

    _ensureSTLFileName(fileName) {
        if (!fileName) return 'packassist_mesh.stl';
        const dot = fileName.lastIndexOf('.');
        const base = dot >= 0 ? fileName.slice(0, dot) : fileName;
        return `${base}.stl`;
    }

    _downloadBuffer(buffer, fileName) {
        const blob = new Blob([buffer], { type: 'model/stl' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = this._ensureSTLFileName(fileName);
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    async _downloadCurrentSTL() {
        const geometry = this.simplifiedGeometry || this.originalGeometry;
        if (!geometry || !this.simplifier) return;
        const fileName = this.simplifiedGeometry
            ? this._ensureSTLFileName(this.fileName.replace(/(\.[^.]+)?$/, '_preview.stl'))
            : this._ensureSTLFileName(this.fileName);
        const buffer = this.simplifier.toBinarySTL(geometry);
        this._downloadBuffer(buffer, fileName);
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
        const vertexCount = positions?.count ?? 0;
        const faceCount = this.originalGeometry.index
            ? Math.floor(this.originalGeometry.index.count / 3)
            : Math.floor(vertexCount / 3);

        this.modal.querySelector('#orig-vertices').textContent = vertexCount.toLocaleString();
        this.modal.querySelector('#orig-faces').textContent = faceCount.toLocaleString();
    }
    
    _onSliderChange(value) {
        this.modal.querySelector('#simplify-percent').textContent = `${value < 1 ? value.toFixed(1) : Math.round(value)}%`;
        
        // Debounce per evitar càlculs excessius (longer for server requests)
        if (this._sliderTimeout) {
            clearTimeout(this._sliderTimeout);
        }
        
        this._sliderTimeout = setTimeout(() => {
            this._updateSimplification();
        }, 300);
    }
    
    async _updateSimplification() {
        const ratio = parseFloat(this.modal.querySelector('#simplify-slider').value) / 100;
        const preserveFeatures = this.modal.querySelector('#preserve-features').checked;

        // Show loading state
        const applyBtn = this.modal.querySelector('#simplify-apply');
        if (applyBtn) applyBtn.disabled = true;
        const resultBox = this.modal.querySelector('#result-stats');
        if (resultBox) resultBox.style.opacity = '0.5';
        
        try {
            // simplify() is now async (may call server)
            this.simplifiedGeometry = await this.simplifier.simplify(ratio, preserveFeatures);
            
            // Crear embolcall convex si cal
            const createEnvelope = this.modal.querySelector('#create-envelope').checked;
            if (createEnvelope) {
                const pos = this.simplifiedGeometry.getAttribute('position');
                const pointCount = pos?.count ?? 0;
                if (pointCount >= 4) {
                    const maxPoints = 5000;
                    const step = Math.max(1, Math.floor(pointCount / maxPoints));
                    const points = [];
                    for (let i = 0; i < pointCount; i += step) {
                        points.push(new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i)));
                    }
                    const hull = new ConvexGeometry(points);
                    hull.computeVertexNormals();
                    this.simplifiedGeometry = hull;
                }
            }
            
            // Actualitzar estadístiques
            this._updateResultStats();
            
            // Actualitzar visualització
            this._updateMeshDisplay();
        } catch (err) {
            console.error('[SimplificationModal] Error:', err);
        } finally {
            if (applyBtn) applyBtn.disabled = false;
            if (resultBox) resultBox.style.opacity = '1';
        }
    }
    
    _updateResultStats() {
        const stats = this.simplifier.getStats(this.simplifiedGeometry);
        
        this.modal.querySelector('#result-vertices').textContent = stats.newVertices.toLocaleString();
        this.modal.querySelector('#result-faces').textContent = stats.newFaces.toLocaleString();
        this.modal.querySelector('#result-reduction').textContent = `${stats.vertexReduction}%`;
        this.modal.querySelector('#result-quality').textContent = `${stats.volumePreservation}%`;

        // Watertight indicator
        const wtEl = this.modal.querySelector('#result-watertight');
        if (wtEl) {
            const be = stats.boundaryEdges ?? -1;
            if (be === 0) {
                wtEl.textContent = this.modalText('solid');
                wtEl.style.color = 'var(--accent-green)';
            } else if (be > 0) {
                wtEl.textContent = this.modalText('openEdges', { count: be });
                wtEl.style.color = 'var(--accent-orange, #f59e0b)';
            } else {
                wtEl.textContent = '-';
                wtEl.style.color = '';
            }
        }

        // Quality warning
        const warnEl = this.modal.querySelector('#quality-warning');
        if (warnEl) {
            const vol = parseFloat(stats.volumePreservation);
            if (vol < 80) {
                warnEl.style.display = 'block';
                warnEl.textContent = this.modalText('qualityWarning', { percent: stats.volumePreservation });
            } else {
                warnEl.style.display = 'none';
            }
        }

        // Backend indicator
        const beEl = this.modal.querySelector('#simplify-backend');
        if (beEl) {
            const usedServer = this.simplifier._serverAvailable === true;
            if (usedServer) {
                beEl.innerHTML = `<span style="color:var(--accent-green);">${this.modalText('backendServer')}</span> - ${this.modalText('backendServerNote')}`;
            } else {
                beEl.innerHTML = `<span style="color:var(--accent-orange,#f59e0b);">${this.modalText('backendFallback')}</span> - ${this.modalText('backendFallbackNote')}`;
            }
        }
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
    
    async _applySimplification() {
        if (!this.simplifiedGeometry || !this.onComplete) {
            this.close();
            return;
        }

        const percentKeep = parseFloat(this.modal.querySelector('#simplify-slider')?.value || '100');
        let simplifiedSTLData = null;
        try {
            simplifiedSTLData = this.simplifier?.toBinarySTL?.(this.simplifiedGeometry) || null;
        } catch (err) {
            console.warn('[SimplificationModal] Could not export simplified STL:', err?.message || err);
        }

        this.onComplete(this.simplifiedGeometry.clone(), simplifiedSTLData, {
            percentKeep,
            usedServer: this.simplifier?._serverAvailable === true
        });
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
