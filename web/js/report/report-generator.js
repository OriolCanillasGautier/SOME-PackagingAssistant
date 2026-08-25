/**
 * PackAssist Web - PDF Report Generator
 * Professional multi-page "Pack Data Sheet" (generic PDS, inspired by the
 * ZF Packaging Data Sheet and Autoliv proposal sheet formats).
 *
 * Generates A4 sheets with:
 *   Page 1 - Doc header (part + metadata), renders (isometric hero + top/
 *            front/side views), box (PU) data table, pallet (SU) table.
 *   Page 2 - Packaging components & cost table, supplier block, approval
 *            signature table, additional comments.
 */

import * as THREE from 'three';
import { loadLocale } from '../i18n.js';

export const PACKASSIST_VERSION = 'v1.3.0';

/**
 * Report Generator Class
 */
export class ReportGenerator {
    constructor(sceneManager) {
        this.scene = sceneManager;
        this.language = 'ca';
        this.locale = null;
        this.t = {};
    }

    /**
     * Set language for report
     * @param {string} lang - 'ca' or 'en'
     */
    async setLanguage(lang) {
        this.language = lang;
        this.locale = await loadLocale(lang);
        this.t = this.locale?.report || {};
    }

    /**
     * Run a capture callback while the scene/renderer/camera are temporarily
     * reconfigured for a clean offscreen render, then restore everything.
     *
     * @param {Function} captureFn - () => string dataUrl
     * @param {Object} opts
     * @returns {string|null} Data URL of the captured image
     */
    _withRenderState(captureFn, opts = {}) {
        if (!this.scene || !this.scene.renderer || !this.scene.camera) {
            console.error('Scene not ready for capture');
            return null;
        }

        // Store original states
        const originalPosition = this.scene.camera.position.clone();
        const originalTarget = this.scene.controls?.target?.clone() || new THREE.Vector3();
        const originalSize = new THREE.Vector2();
        this.scene.renderer.getSize(originalSize);
        const originalPixelRatio = this.scene.renderer.getPixelRatio();
        const originalBackground = this.scene.scene.background;

        // Box material
        let originalBoxMaterial = null;
        let originalBoxColor = null;
        if (this.scene.boxMesh) {
            originalBoxMaterial = this.scene.boxMesh.material;
            originalBoxColor = originalBoxMaterial?.color ? originalBoxMaterial.color.clone() : null;
        }

        // Floor material + receiveShadow
        let originalFloorMaterial = null;
        let originalFloorVisible = true;
        let originalFloorReceiveShadow = false;
        if (this.scene.boxFloor) {
            originalFloorMaterial = this.scene.boxFloor.material;
            originalFloorVisible = this.scene.boxFloor.visible;
            originalFloorReceiveShadow = this.scene.boxFloor.receiveShadow;
        }

        // Grid
        const grid = this.scene.scene.getObjectByName('grid');
        let originalGridVisible = true;
        if (grid) originalGridVisible = grid.visible;

        // Piece materials (may be a single material or an array)
        const pieceMaterials = [];
        for (const piece of this.scene.pieces || []) {
            const mats = Array.isArray(piece.material) ? piece.material : [piece.material];
            pieceMaterials.push({ piece, mats });
        }

        try {
            const width = opts.width || 800;
            const height = opts.height || 600;

            // Background
            this.scene.scene.background = opts.background != null
                ? new THREE.Color(opts.background)
                : originalBackground;

            // Grid
            if (grid) grid.visible = opts.hideGrid === false;

            // Box wireframe (null boxColor = keep current cobalt blue box)
            if (this.scene.boxMesh && opts.boxColor != null) {
                this.scene.boxMesh.material = new THREE.LineBasicMaterial({
                    color: opts.boxColor,
                    linewidth: 2
                });
            }

            // Floor: hide entirely, or render as a white ground that receives
            // soft shadows from the pieces (professional product-shot look).
            if (this.scene.boxFloor) {
                if (opts.floor === 'none') {
                    this.scene.boxFloor.visible = false;
                } else if (opts.floor === 'white') {
                    this.scene.boxFloor.visible = true;
                    this.scene.boxFloor.receiveShadow = true;
                    this.scene.boxFloor.material = new THREE.MeshPhongMaterial({
                        color: 0xffffff,
                        opacity: 1,
                        transparent: false,
                        side: THREE.DoubleSide
                    });
                }
            }

            // Piece opacity (semi-transparent in live view, solid for report)
            if (opts.pieceOpacity != null) {
                for (const { piece, mats } of pieceMaterials) {
                    for (const m of mats) {
                        if (m && typeof m.opacity === 'number') {
                            m.userData.__reportOpacity = m.opacity;
                            m.userData.__reportTransparent = m.transparent;
                            m.opacity = opts.pieceOpacity;
                            m.transparent = opts.pieceOpacity < 1;
                            m.needsUpdate = true;
                        }
                    }
                }
            }

            this.scene.renderer.setPixelRatio(opts.pixelRatio || 1);
            this.scene.renderer.setSize(width, height, false);
            this.scene.camera.aspect = width / height;
            this.scene.camera.updateProjectionMatrix();

            return captureFn();
        } finally {
            // Restore original states
            this.scene.scene.background = originalBackground;

            if (grid) grid.visible = originalGridVisible;

            if (this.scene.boxMesh && opts.boxColor != null) {
                this.scene.boxMesh.material = originalBoxMaterial;
            }

            if (this.scene.boxFloor && (opts.floor === 'none' || opts.floor === 'white')) {
                this.scene.boxFloor.visible = originalFloorVisible;
                this.scene.boxFloor.receiveShadow = originalFloorReceiveShadow;
                this.scene.boxFloor.material = originalFloorMaterial;
            }

            if (opts.pieceOpacity != null) {
                for (const { piece, mats } of pieceMaterials) {
                    for (const m of mats) {
                        if (m && m.userData.__reportOpacity != null) {
                            m.opacity = m.userData.__reportOpacity;
                            m.transparent = m.userData.__reportTransparent;
                            m.needsUpdate = true;
                            delete m.userData.__reportOpacity;
                            delete m.userData.__reportTransparent;
                        }
                    }
                }
            }

            this.scene.renderer.setPixelRatio(originalPixelRatio);
            this.scene.renderer.setSize(originalSize.x, originalSize.y, false);
            this.scene.camera.aspect = originalSize.x / originalSize.y;
            this.scene.camera.position.copy(originalPosition);
            if (this.scene.controls) {
                this.scene.controls.target.copy(originalTarget);
                this.scene.controls.update();
            }
            this.scene.camera.updateProjectionMatrix();
            this.scene.renderer.render(this.scene.scene, this.scene.camera);
        }
    }

    /**
     * Position the camera to frame the packed box for a given view.
     * Distance fills ~framing * 100% of the frame height.
     * @param {string} viewType - 'isometric' | 'front' | 'top' | 'side'
     * @param {number} framing - 1.0 = box fills the frame
     */
    _frameCamera(viewType, framing = 1.3) {
        if (!this.scene.boxMesh) return;

        const box = new THREE.Box3().setFromObject(this.scene.boxMesh);
        const center = new THREE.Vector3();
        const size = new THREE.Vector3();
        box.getCenter(center);
        box.getSize(size);

        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = this.scene.camera.fov * (Math.PI / 180);
        const distance = (maxDim / (2 * Math.tan(fov / 2))) * framing;

        const positions = {
            iso: new THREE.Vector3(distance, distance, distance),
            isometric: new THREE.Vector3(distance, distance, distance),
            top: new THREE.Vector3(0, distance, 0.01),
            front: new THREE.Vector3(0, distance * 0.4, distance),
            side: new THREE.Vector3(distance, distance * 0.4, 0),
            right: new THREE.Vector3(distance, distance * 0.4, 0)
        };

        const pos = positions[viewType] || positions.isometric;
        this.scene.camera.position.set(center.x + pos.x, center.y + pos.y, center.z + pos.z);
        if (this.scene.controls) {
            this.scene.controls.target.copy(center);
            this.scene.controls.update();
        }
        this.scene.camera.lookAt(center);
    }

    /**
     * Capture a true 2D orthographic view for the report (blueprint-style):
     * top = plan view, front/side = elevations, with no perspective
     * convergence. Uses a black wireframe box on a white background.
     * @param {string} viewType - 'front' | 'top' | 'side'
     * @param {number} width - Image width
     * @param {number} height - Image height
     * @returns {string|null} Data URL of the image
     */
    captureView(viewType, width = 720, height = 480, framing = 1.2) {
        return this._withRenderState(() => {
            if (!this.scene.boxMesh) return null;

            const box = new THREE.Box3().setFromObject(this.scene.boxMesh);
            const center = new THREE.Vector3();
            const size = new THREE.Vector3();
            box.getCenter(center);
            box.getSize(size);

            // View plane dims + look direction per view type.
            // Scene axes: box L=x, H=y, W=z. Top = L×W plane from above,
            // front = L×H elevation, side = W×H elevation.
            const plane = {
                top: { h: size.x, v: size.z, dir: new THREE.Vector3(0, 1, 0), up: new THREE.Vector3(0, 0, -1) },
                front: { h: size.x, v: size.y, dir: new THREE.Vector3(0, 0, 1), up: new THREE.Vector3(0, 1, 0) },
                side: { h: size.z, v: size.y, dir: new THREE.Vector3(1, 0, 0), up: new THREE.Vector3(0, 1, 0) }
            }[viewType] || null;
            if (!plane) return null;

            // Orthographic frustum fitted to the box (framing margin around)
            const aspect = width / height;
            let hExtent = (plane.h * framing) / 2;
            let vExtent = (plane.v * framing) / 2;
            if (hExtent / vExtent > aspect) {
                vExtent = hExtent / aspect;
            } else {
                hExtent = vExtent * aspect;
            }
            const maxDim = Math.max(size.x, size.y, size.z);
            const near = 0.1;
            const far = maxDim * 6;
            const camera = new THREE.OrthographicCamera(-hExtent, hExtent, vExtent, -vExtent, near, far);
            camera.position.copy(center).addScaledVector(plane.dir, far / 2);
            camera.up.copy(plane.up);
            camera.lookAt(center);
            camera.updateProjectionMatrix();

            this.scene.renderer.render(this.scene.scene, camera);
            return this.scene.renderer.domElement.toDataURL('image/png');
        }, {
            width,
            height,
            background: 0xffffff,
            boxColor: 0x000000,
            hideGrid: true,
            floor: 'none',
            pieceOpacity: 1,
            pixelRatio: 1
        });
    }

    /**
     * Capture the large presentation "hero" render: cobalt blue wireframe box,
     * solid colored pieces on a pure white background.
     * @param {number} width - Image width
     * @param {number} height - Image height
     * @returns {string|null} Data URL of the image
     */
    captureHero(width = 1680, height = 640, framing = 0.76) {
        return this._withRenderState(() => {
            this._frameCamera('isometric', 1.0);
            // Zoom to the projected box: perspective size scales linearly
            // with 1/distance, so project the 8 box corners once and pull
            // the camera in until the box fills `framing` of the frame's
            // smaller dimension (the isometric projection otherwise shrinks
            // the box to roughly half the frame).
            if (this.scene.boxMesh) {
                const box = new THREE.Box3().setFromObject(this.scene.boxMesh);
                const center = new THREE.Vector3();
                box.getCenter(center);
                const corners = [];
                for (const sx of [0, 1]) {
                    for (const sy of [0, 1]) {
                        for (const sz of [0, 1]) {
                            corners.push(new THREE.Vector3(
                                sx ? box.max.x : box.min.x,
                                sy ? box.max.y : box.min.y,
                                sz ? box.max.z : box.min.z));
                        }
                    }
                }
                this.scene.camera.updateMatrixWorld(true);
                this.scene.camera.updateProjectionMatrix();
                const proj = corners.map(c => c.clone().project(this.scene.camera));
                const xs = proj.map(p => p.x);
                const ys = proj.map(p => p.y);
                // Fit the box's LARGEST projected extent to `framing` of the
                // frame's smaller dimension — targeting the smaller span
                // lets the other dimension overflow the frame (the box then
                // touches the top and bottom edges, which reads as "too
                // zoomed in").
                const cur = Math.max(Math.max(...xs) - Math.min(...xs),
                                     Math.max(...ys) - Math.min(...ys));
                const target = framing * 2; // NDC span is 2
                if (cur > 1e-6 && Math.abs(target - cur) > 1e-4) {
                    const scale = target / cur;
                    const camToCenter = center.clone().sub(this.scene.camera.position);
                    const d = camToCenter.length();
                    const dir = camToCenter.normalize();
                    this.scene.camera.position.copy(center).addScaledVector(dir, -d / scale);
                    this.scene.camera.lookAt(center);
                    this.scene.camera.updateProjectionMatrix();
                }
            }
            this.scene.renderer.render(this.scene.scene, this.scene.camera);
            return this.scene.renderer.domElement.toDataURL('image/png');
        }, {
            width,
            height,
            background: 0xffffff,
            boxColor: null,      // keep the cobalt blue wireframe box
            hideGrid: true,
            floor: 'none',
            pieceOpacity: 1,
            pixelRatio: 1
        });
    }

    // ── formatting helpers ──────────────────────────────────
    _num(v) {
        const n = Number(v);
        return Number.isFinite(n) ? n : null;
    }

    _fmt(v, maxFrac = 2) {
        const n = this._num(v);
        if (n === null) return '—';
        return n.toLocaleString(this.localeCode, { maximumFractionDigits: maxFrac });
    }

    _fmtEuro(v, maxFrac = 4) {
        const n = this._num(v);
        if (n === null) return '—';
        return n.toLocaleString(this.localeCode, {
            style: 'currency', currency: 'EUR',
            minimumFractionDigits: 2, maximumFractionDigits: maxFrac
        });
    }

    _fmtDim(v) {
        const n = this._num(v);
        return n === null ? '—' : n.toLocaleString(this.localeCode, { maximumFractionDigits: 1 });
    }

    _fmtDate(isoOrText) {
        if (!isoOrText) return '';
        if (/^\d{4}-\d{2}-\d{2}/.test(String(isoOrText))) {
            const d = new Date(isoOrText);
            return d.toLocaleDateString(this.localeCode);
        }
        return String(isoOrText);
    }

    // ── section builders ────────────────────────────────────
    _sectionTitle(label) {
        return `<div class="sec-title">${label}</div>`;
    }

    /**
     * Generate the multi-page PDF report (HTML document for print / preview)
     * @param {Object} data - Report data (pack results + report form fields)
     * @returns {Promise<string>} HTML content
     */
    async generatePDF(data) {
        const views = {
            hero: this.captureHero(1680, 640),
            top: this.captureView('top', 820, 500),
            front: this.captureView('front', 820, 500),
            side: this.captureView('side', 820, 500)
        };

        return await this.createPDFDocument(data, views);
    }

    /**
     * Create the multi-page Pack Data Sheet HTML document.
     * @param {Object} data - Report data (merged with form fields)
     * @param {Object} views - Captured view data URLs
     * @returns {string} HTML content
     */
    async createPDFDocument(data, views) {
        const {
            pieceDims = { l: 0, w: 0, h: 0 },
            boxDims = { length: 0, width: 0, height: 0 },
            pieceCount = 0,
            pieceWeight = 0,
            mode = 'bulk',
            meshVolume = 0,
            fillPct = null,
            interlocked = null,
            trays = null,
            gpuMethod = null,
            stlFileName = null,
            partName = null,
        } = data;

        // ── report form fields (merged in main.js) ──
        const part = data.part || {};
        const supplier = data.supplier || {};
        const cost = data.cost || {};
        const items = Array.isArray(data.items) ? data.items : [];
        const pallet = data.pallet || {};
        const approvals = data.approvals || {};
        const comments = data.comments || '';

        this.localeCode = this.locale?.meta?.locale || (this.language === 'ca' ? 'ca-ES' : 'en-US');
        const t = this.t;
        const fmt = (v) => this._fmt(v);
        const fmtW = (v) => this._fmt(v, 4);
        const fmtEuro = (v) => this._fmtEuro(v, 4);
        const fmtEuro2 = (v) => this._fmtEuro(v, 2);
        const fmtD = (v) => this._fmtDim(v);
        const currentDate = this._fmtDate(new Date().toISOString());

        // ── derived values ──
        const name = part.name || partName || stlFileName || (t.customPiece || 'Custom piece');
        const partNumber = part.number || '';
        const revision = part.revision || '';
        const dimsText = `${fmtD(pieceDims.l)} × ${fmtD(pieceDims.w)} × ${fmtD(pieceDims.h)} mm`;
        const boxDimsText = `${fmtD(boxDims.length)} × ${fmtD(boxDims.width)} × ${fmtD(boxDims.height)} mm`;

        const modeLabel = mode === 'fast'
            ? (t.modeFast || 'Planar')
            : mode === 'gpu'
                ? (t.modeGpu || 'GPU')
                : (t.modeBulk || 'Bulk');

        // fill %
        let fillRate = fillPct;
        if (fillRate == null) {
            const bboxVolumeMM3 = (pieceDims.l || 0) * (pieceDims.w || 0) * (pieceDims.h || 0);
            const realVolumeMM3 = meshVolume > 0 ? meshVolume : bboxVolumeMM3;
            const pieceVolume = realVolumeMM3 / 1000000; // cm³
            const boxVolume = (boxDims.length * boxDims.width * boxDims.height) / 1000000;
            fillRate = boxVolume > 0 ? (pieceCount * pieceVolume / boxVolume * 100) : 0;
        }
        fillRate = this._num(fillRate) ?? 0;

        // weights
        const totalWeight = this._num(data.estimatedTotalWeight) ?? (pieceCount * this._num(pieceWeight) ?? 0);

        // cost rows
        const itemRows = items
            .map(it => {
                const qty = this._num(it.qty) ?? 0;
                const price = this._num(it.price) ?? 0;
                const lineCost = qty * price;
                return {
                    desc: it.desc || '',
                    material: it.material || '',
                    dims: `${fmtD(it.l)}×${fmtD(it.w)}×${fmtD(it.h)}`,
                    qty,
                    price,
                    cost: lineCost,
                    hasDims: this._num(it.l) != null || this._num(it.w) != null || this._num(it.h) != null
                };
            })
            .filter(r => r.desc || r.material);

        const itemsTotal = itemRows.reduce((s, r) => s + r.cost, 0);
        const boxCost = this._num(cost.boxCost);
        const packagingCost = this._num(cost.packagingCost);
        const freightCost = this._num(cost.freightCost);
        const hasItems = itemRows.length > 0;
        const hasCostInputs = boxCost != null || packagingCost != null || freightCost != null || hasItems;
        let costPerPart = this._num(cost.costPerPart);
        if (costPerPart == null && hasCostInputs && pieceCount > 0) {
            costPerPart = ((itemsTotal + (boxCost ?? 0)) / pieceCount);
        }
        const hasCost = hasCostInputs || costPerPart != null;

        // multitray info
        const trayCount = Array.isArray(trays) ? trays.length : 0;
        const trayPieces = Array.isArray(trays) ? trays.map(tr => tr.pieces) : [];
        const interlockCount = interlocked ? (this._num(interlocked.count) ?? 0) : 0;
        // The interlocking warning can be hidden from the report (checkbox
        // in the report popup) — some users want a clean PDF without it.
        const showInterlockWarning = data.showInterlockWarning !== false;

        // pallet info
        const hasPallet = Object.keys(pallet).some(k => this._num(pallet[k]) != null || pallet[k]);

        // approvals
        const hasSupplier = Object.keys(supplier).some(k => supplier[k]);
        const hasApprovals = approvals.conceptName || approvals.finalName || approvals.createdBy;
        const approvalRows = [
            ['CONCEPT', approvals.conceptFunction, approvals.conceptName, approvals.conceptDate],
            ['FINAL APPROVAL', approvals.finalFunction, approvals.finalName, approvals.finalDate],
        ];

        // ── helpers for HTML ──
        const imgOrPlaceholder = (src, alt, label, phLabel) => src
            ? `<img src="${src}" alt="${alt}">`
            : `<div class="view-unavailable">${phLabel || (t.viewUnavailable || '—')}</div>`;

        const pageNum = (n) => `<div class="page-num">${t.page || 'Pàgina'} ${n}/2</div>`;

        // ══════════════ PAGE 1 ══════════════
        const page1 = `
        <div class="sheet">
            <!-- DOC HEADER -->
            <header class="doc-header">
                <div class="doc-header-left">
                    <div class="doc-kicker">${t.kicker || 'Pack Data Sheet'}</div>
                    <h1 class="doc-title">${name}</h1>
                    <div class="doc-sub">${partNumber ? `PN ${partNumber} · ` : ''}${dimsText} · ${t.weight || 'Pes'} ${fmtW(pieceWeight)} kg</div>
                </div>
                <div class="doc-header-right">
                    <div class="brand">PackAssist</div>
                    <div class="brand-sub">${PACKASSIST_VERSION} · ${currentDate}</div>
                    ${revision ? `<div class="brand-sub">${t.revision || 'Rev'} ${revision}</div>` : ''}
                </div>
            </header>

            <!-- PART INFO -->
            <section class="table-section">
                ${this._sectionTitle(t.partInfo || 'Part information')}
                <table class="data-table part-table">
                    <tbody>
                        <tr>
                            <th>${t.partNumber || 'Part number'}</th>
                            <td>${part.number || '—'}</td>
                            <th>${t.project || 'Project'}</th>
                            <td>${part.project || '—'}</td>
                            <th>${t.material || 'Material'}</th>
                            <td>${part.material || '—'}</td>
                            <th>${t.supplierName || 'Supplier'}</th>
                            <td>${supplier.name || '—'}</td>
                        </tr>
                        <tr>
                            <th>${t.dimensions || 'Dimensions'}</th>
                            <td>${dimsText}</td>
                            <th>${t.weightPerPiece || 'Weight / part'}</th>
                            <td>${fmtW(pieceWeight)} kg</td>
                            <th>${t.modeUsed || 'Mode'}</th>
                            <td>${mode === 'gpu' ? `${modeLabel}${gpuMethod ? ` · ${gpuMethod}` : ''}` : modeLabel}</td>
                            <th>${t.fillRate || 'Fill rate'}</th>
                            <td>${fmt(fillRate)} %</td>
                        </tr>
                    </tbody>
                </table>
            </section>

            <!-- RENDERS -->
            <section class="views-section">
                <div class="hero">
                    ${imgOrPlaceholder(views.hero, t.isometricView, t.isometricView)}
                    <div class="view-label">${t.isometricView}</div>
                </div>
                <div class="views-small">
                    <div class="view">${imgOrPlaceholder(views.top, t.topView)}<div class="view-label">${t.topView}</div></div>
                    <div class="view">${imgOrPlaceholder(views.front, t.frontView)}<div class="view-label">${t.frontView}</div></div>
                    <div class="view">${imgOrPlaceholder(views.side, t.sideView)}<div class="view-label">${t.sideView}</div></div>
                </div>
            </section>

            <!-- PACK METRICS TABLE -->
            <section class="table-section">
                <table class="data-table metrics-table">
                    <tbody>
                        <tr>
                            <th>${t.pieceCount || 'Piece count'}</th>
                            <td>${fmt(pieceCount)}</td>
                            <th>${t.fillRate || 'Fill rate'}</th>
                            <td>${fmt(fillRate)} %</td>
                            <th>${t.boxDims || 'Box (mm)'}</th>
                            <td>${boxDimsText}</td>
                            <th>${t.totalWeight || 'Total weight'}</th>
                            <td>${fmt(totalWeight)} kg</td>
                        </tr>
                    </tbody>
                </table>
            </section>

            <!-- WARNINGS -->
            ${interlockCount > 0 && showInterlockWarning ? `<div class="warn-box">${t.interlockedWarning || 'Interlocked pieces'}:
                ${interlockCount} ${t.pieces || 'pieces'}</div>` : ''}
            ${trayCount > 1 ? `<div class="info-box">${t.traySummary || 'Multi-box packing'}:
                ${trayCount} ${t.boxes || 'boxes'} (${trayPieces.join(' + ')}) = ${fmt(pieceCount)} ${t.pieces || 'pieces'}</div>` : ''}

            <!-- BOX (PU) TABLE -->
            <section class="table-section">
                ${this._sectionTitle(t.boxInfo || 'Packing unit (box)')}
                <table class="data-table">
                    <tbody>
                        <tr>
                            <th>${t.boxDims || 'External size (mm)'}</th>
                            <td>${boxDimsText}</td>
                            <th>${t.pieceCount || 'Pieces / box'}</th>
                            <td>${fmt(pieceCount)}</td>
                            <th>${t.fillRate || 'Fill rate'}</th>
                            <td>${fmt(fillRate)} %</td>
                        </tr>
                        <tr>
                            <th>${t.modeUsed || 'Mode'}</th>
                            <td>${mode === 'gpu' ? `${modeLabel}${gpuMethod ? ` · ${gpuMethod}` : ''}` : modeLabel}</td>
                            <th>${t.totalWeight || 'Total weight (kg)'}</th>
                            <td>${fmt(totalWeight)}</td>
                            <th>${t.maxWeight || 'Max weight (kg)'}</th>
                            <td>${fmt(data.maxWeight)}</td>
                        </tr>
                    </tbody>
                </table>
            </section>

            <!-- PALLET (SU) TABLE -->
            ${hasPallet ? `
            <section class="table-section">
                ${this._sectionTitle(t.palletInfo || 'Shipping unit (pallet)')}
                <table class="data-table">
                    <tbody>
                        <tr>
                            <th>${t.palletDims || 'External size (mm)'}</th>
                            <td>${fmtD(pallet.l)} × ${fmtD(pallet.w)} × ${fmtD(pallet.h)}</td>
                            <th>${t.palletWeight || 'Weight (kg)'}</th>
                            <td>${fmt(pallet.weight)}</td>
                            <th>${t.boxesPerPallet || 'Boxes / pallet'}</th>
                            <td>${fmt(pallet.boxes)}</td>
                        </tr>
                    </tbody>
                </table>
            </section>` : ''}

            ${pageNum(1)}
        </div>`;

        // ══════════════ PAGE 2 ══════════════
        const page2 = `
        <div class="sheet">
            <header class="doc-header doc-header-thin">
                <div class="doc-header-left">
                    <div class="doc-kicker">${t.kicker || 'Pack Data Sheet'}</div>
                    <div class="doc-sub">${name}${partNumber ? ` · PN ${partNumber}` : ''}</div>
                </div>
                <div class="doc-header-right">
                    <div class="brand-sub">${PACKASSIST_VERSION} · ${currentDate}</div>
                </div>
            </header>

            <!-- COMPONENTS + COST -->
            <section class="table-section">
                ${this._sectionTitle(t.components || 'Packaging components')}
                <table class="data-table components-table">
                    <thead>
                        <tr>
                            <th class="w40">${t.desc || 'Description'}</th>
                            <th>${t.matType || 'Material'}</th>
                            <th>${t.dimsCol || 'L×W×H (mm)'}</th>
                            <th class="w8">${t.qty || 'Qty'}</th>
                            <th>${t.priceUnit || 'Price / unit'}</th>
                            <th>${t.costCol || 'Cost'}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${hasItems ? itemRows.map(r => `
                        <tr>
                            <td>${r.desc}</td>
                            <td>${r.material || '—'}</td>
                            <td>${r.hasDims ? r.dims : '—'}</td>
                            <td>${fmt(r.qty)}</td>
                            <td>${fmtEuro(r.price)}</td>
                            <td>${fmtEuro(r.cost)}</td>
                        </tr>`).join('') : `
                        <tr><td colspan="6" class="empty-cell">${t.noComponents || 'No packaging components defined'}</td></tr>`}
                    </tbody>
                </table>
            </section>

            ${hasCost ? `
            <section class="table-section">
                ${this._sectionTitle(t.costSummary || 'Cost summary')}
                ${hasItems ? `<div class="cost-total">${t.itemsTotal || 'Components / box'}: ${fmtEuro2(itemsTotal)}</div>` : ''}
                <table class="data-table cost-table">
                    <tbody>
                        <tr>
                            <th>${t.boxCost || 'Box cost'}</th>
                            <td>${fmtEuro2(boxCost)}</td>
                            <th>${t.packagingCost || 'Packaging'}</th>
                            <td>${fmtEuro2(packagingCost)}</td>
                            <th>${t.freightCost || 'Freight'}</th>
                            <td>${fmtEuro2(freightCost)}</td>
                            <th class="cost-highlight">${t.costPerPart || 'Cost per part'}</th>
                            <td class="cost-highlight">${fmtEuro2(costPerPart)}</td>
                        </tr>
                    </tbody>
                </table>
            </section>` : ''}

            <!-- SUPPLIER -->
            ${hasSupplier ? `
            <section class="table-section">
                ${this._sectionTitle(t.supplierInfo || 'Supplier information')}
                <table class="data-table">
                    <tbody>
                        <tr>
                            <th>${t.supplierName || 'Name'}</th><td>${supplier.name || '—'}</td>
                            <th>${t.supplierAddress || 'Address'}</th><td>${supplier.address || '—'}</td>
                            <th>${t.supplierContact || 'Contact'}</th><td>${supplier.contact || '—'}</td>
                        </tr>
                        <tr>
                            <th>${t.supplierPhone || 'Phone'}</th><td>${supplier.phone || '—'}</td>
                            <th>${t.supplierEmail || 'Email'}</th><td>${supplier.email || '—'}</td>
                            <th>${t.supplierFunction || 'Function'}</th><td>${supplier.function || '—'}</td>
                        </tr>
                    </tbody>
                </table>
            </section>` : ''}

            <!-- APPROVALS -->
            ${hasApprovals ? `
            <section class="table-section">
                ${this._sectionTitle(t.approvals || 'Approvals')}
                <table class="data-table approvals-table">
                    <thead>
                        <tr>
                            <th>${t.step || 'Step'}</th>
                            <th>${t.function || 'Function'}</th>
                            <th>${t.name || 'Name'}</th>
                            <th>${t.signature || 'Signature'}</th>
                            <th>${t.date || 'Date'}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${approvalRows.map(([step, fn, nm, dt]) => `
                        <tr>
                            <td><strong>${step}</strong></td>
                            <td>${fn || '—'}</td>
                            <td>${nm || '—'}</td>
                            <td></td>
                            <td>${this._fmtDate(dt)}</td>
                        </tr>`).join('')}
                        ${approvals.createdBy ? `<tr><td><strong>${t.createdBy || 'Created by'}</strong></td><td colspan="4">${approvals.createdBy}</td></tr>` : ''}
                    </tbody>
                </table>
            </section>` : ''}

            <!-- COMMENTS -->
            ${comments ? `
            <section class="table-section">
                ${this._sectionTitle(t.additionalComments || 'Additional comments')}
                <div class="comments-box">${comments}</div>
            </section>` : ''}

            ${pageNum(2)}
        </div>`;

        const htmlContent = `<!DOCTYPE html>
<html lang="${this.language === 'ca' ? 'ca' : 'en'}">
<head>
<meta charset="UTF-8">
<title>${t.title} — ${name}</title>
<style>
    @page { size: A4; margin: 0; }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body {
        background: #e5e7eb;
        font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
        color: #111827;
        font-size: 3mm;
    }

    .sheet {
        width: 210mm;
        min-height: 296.5mm;
        background: #ffffff;
        margin: 0 auto;
        padding: 9mm 10mm;
        position: relative;
    }
    .sheet + .sheet { page-break-before: always; }

    /* ── Doc header ───────────────────────────────── */
    .doc-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        border-bottom: 1.2mm solid #111827;
        padding-bottom: 3mm;
    }
    .doc-header-thin { border-bottom: 0.6mm solid #111827; padding-bottom: 2mm; }
    .doc-kicker {
        font-size: 2.6mm; font-weight: 700; letter-spacing: 1.6px;
        color: #0047ab; text-transform: uppercase; margin-bottom: 0.8mm;
    }
    .doc-title { font-size: 6mm; font-weight: 800; line-height: 1.1; word-break: break-word; }
    .doc-sub { font-size: 3mm; color: #6b7280; margin-top: 1.2mm; font-weight: 600; }
    .doc-header-right { text-align: right; flex-shrink: 0; margin-left: 4mm; }
    .brand { font-size: 4.6mm; font-weight: 800; letter-spacing: 0.5px; color: #0047ab; }
    .brand-sub { font-size: 2.5mm; color: #6b7280; margin-top: 0.6mm; font-weight: 600; }

    /* ── Sections ─────────────────────────────────── */
    .sec-title {
        font-size: 2.7mm; font-weight: 800; color: #0047ab;
        text-transform: uppercase; letter-spacing: 1px;
        border-left: 1.4mm solid #0047ab; padding-left: 2mm;
        margin: 0 0 2.2mm 0;
    }
    .table-section { margin-top: 5mm; }

    /* ── Renders ──────────────────────────────────── */
    .views-section { margin-top: 4mm; }
    .hero {
        width: 100%; height: 75mm;
        background: #ffffff; border: 0.4mm solid #e5e7eb; border-radius: 2.6mm;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        padding: 1.5mm; overflow: hidden;
    }
    .hero img { max-width: 100%; max-height: 100%; object-fit: contain; flex: 1 1 auto; min-height: 0; }
    .hero .view-label { font-size: 2.4mm; font-weight: 600; color: #6b7280; margin-top: 1mm; flex-shrink: 0; }

    .views-small { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2.5mm; height: 42mm; margin-top: 2.5mm; }
    .view {
        border: 0.4mm solid #e5e7eb; border-radius: 2.2mm; background: #ffffff;
        padding: 1.4mm; display: flex; flex-direction: column; align-items: center; overflow: hidden;
    }
    .view img { max-width: 100%; max-height: 100%; flex: 1 1 auto; min-height: 0; object-fit: contain; }
    .view-label { font-size: 2.3mm; font-weight: 600; color: #374151; margin-top: 0.8mm; text-align: center; flex-shrink: 0; }
    .view-unavailable { color: #9ca3af; font-size: 2.6mm; padding: 8mm 0; text-align: center; }

    /* ── Warning / info boxes ─────────────────────── */
    .warn-box {
        margin-top: 4mm; padding: 2mm 3mm; border-radius: 2mm;
        background: #fef2f2; border: 0.4mm solid #fecaca; color: #b91c1c;
        font-size: 2.8mm; font-weight: 700;
    }
    .info-box {
        margin-top: 4mm; padding: 2mm 3mm; border-radius: 2mm;
        background: #eff6ff; border: 0.4mm solid #bfdbfe; color: #1d4ed8;
        font-size: 2.8mm; font-weight: 700;
    }

    /* ── Tables ───────────────────────────────────── */
    .data-table { width: 100%; border-collapse: collapse; margin-top: 2mm; }
    .data-table th, .data-table td {
        border: 0.3mm solid #e5e7eb; padding: 1.8mm 2.2mm;
        font-size: 2.6mm; vertical-align: middle;
    }
    .data-table th { background: #eef4ff; color: #003a8c; text-align: left; font-weight: 700; width: 20%; }
    .data-table td { color: #111827; }
    .components-table th { background: #0047ab; color: #ffffff; width: auto; }
    .components-table td { text-align: center; }
    .components-table td:first-child { text-align: left; font-weight: 600; }
    .components-table .w40 { width: 40%; }
    .components-table .w8 { width: 8%; }
    .empty-cell { text-align: center !important; color: #9ca3af; }
    .approvals-table th { background: #0047ab; color: #ffffff; width: auto; }
    .approvals-table td { height: 9mm; }
    .part-table th { width: 15%; }
    .part-table td { width: 10%; }
    .cost-table th { width: 15%; }
    .cost-table td { width: 10%; }
    .cost-table .cost-highlight { background: #0047ab; color: #ffffff; }
    .metrics-table th { width: 15%; }
    .metrics-table td { width: 10%; }

    /* ── Cost summary ─────────────────────────────── */
    .cost-total {
        margin-top: 2mm; font-size: 2.6mm; color: #003a8c; font-weight: 700;
    }

    /* ── Comments ─────────────────────────────────── */
    .comments-box {
        margin-top: 2mm; padding: 2.5mm 3mm; min-height: 16mm;
        border: 0.3mm solid #e5e7eb; border-radius: 2mm;
        font-size: 2.7mm; line-height: 1.5; color: #374151; white-space: pre-wrap;
    }

    /* ── Page numbers / footer ────────────────────── */
    .page-num {
        position: absolute; bottom: 4mm; right: 10mm;
        font-size: 2.4mm; color: #9ca3af; font-weight: 600;
    }

    /* ── Preview scaling (screen only) ────────────── */
    @media screen { body { padding: 12px; } }
    @media print {
        html, body { background: #ffffff; }
        .sheet { margin: 0; transform: none !important; left: 0 !important; }
    }
</style>
</head>
<body>
    ${page1}
    ${page2}
    <script>
        (function () {
            function fit() {
                if (window.matchMedia('print').matches) return;
                var sheets = document.querySelectorAll('.sheet');
                if (!sheets.length) return;
                var w = sheets[0].offsetWidth;
                var avail = (window.innerWidth || document.documentElement.clientWidth) - 24;
                if (avail > 0 && avail < w) {
                    var s = avail / w;
                    var y = 0;
                    sheets.forEach(function (sh) {
                        sh.style.transformOrigin = 'top left';
                        sh.style.transform = 'scale(' + s + ')';
                        sh.style.marginTop = (y === 0 ? '0' : '6px') + 'px';
                        sh.style.position = 'relative';
                        sh.style.left = ((w - avail) / 2) + 'px';
                        y += sh.offsetHeight * s + 6;
                    });
                } else {
                    sheets.forEach(function (sh) { sh.style.transform = ''; sh.style.left = '0'; });
                }
            }
            window.addEventListener('load', fit);
            window.addEventListener('resize', fit);
            fit();
        })();
    </script>
</body>
</html>`;

        return htmlContent;
    }

    /**
     * Generate and download the report (open print window)
     * @param {Object} data - Report data
     * @param {string} language - 'ca' or 'en'
     */
    async downloadReport(data, language = 'ca') {
        await this.setLanguage(language);

        try {
            const htmlContent = await this.generatePDF(data);

            // Create a new window for printing/PDF
            const printWindow = window.open('', '_blank');
            printWindow.document.write(htmlContent);
            printWindow.document.close();

            // Set title to avoid "about:blank" in PDF headers
            printWindow.document.title = `${this.t.title} — PackAssist`;

            // Wait for images to load then print
            printWindow.onload = () => {
                setTimeout(() => {
                    printWindow.print();
                }, 500);
            };

        } catch (error) {
            console.error('Error generating report:', error);
            throw error;
        }
    }

    /**
     * Generate HTML preview of report
     * @param {Object} data - Report data
     * @param {string} language - 'ca' or 'en'
     * @returns {Promise<string>} HTML content
     */
    async generatePreview(data, language = 'ca') {
        await this.setLanguage(language);
        return await this.generatePDF(data);
    }
}

export default ReportGenerator;
