/**
 * PackAssist Web - PDF Report Generator
 * Professional one-page "Pack Report" (Pack Studio style).
 *
 * Generates a single A4 sheet with:
 *   - Header: part info (name, dims, weight) + PackAssist branding
 *   - Hero: large isometric render of the packed box (green wireframe + pieces)
 *   - Metrics: clean grid of key numbers
 *   - Small multi-views: top / front / side
 *   - Cost summary (only when cost data is present)
 */

import * as THREE from 'three';
import { loadLocale } from '../i18n.js';

export const PACKASSIST_VERSION = 'v1.0.0';

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

            // Box wireframe (null boxColor = keep current green box)
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
     * Capture a small orthographic-style view for the report.
     * Uses a black wireframe box on a white background.
     * @param {string} viewType - 'front' | 'top' | 'side'
     * @param {number} width - Image width
     * @param {number} height - Image height
     * @returns {string|null} Data URL of the image
     */
    captureView(viewType, width = 720, height = 480, framing = 1.2) {
        return this._withRenderState(() => {
            this._frameCamera(viewType, framing);
            this.scene.renderer.render(this.scene.scene, this.scene.camera);
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
     * Capture the large presentation "hero" render: green wireframe box,
     * solid colored pieces and a white ground with soft shadows.
     * @param {number} width - Image width
     * @param {number} height - Image height
     * @returns {string|null} Data URL of the image
     */
    captureHero(width = 1400, height = 1050, framing = 1.15) {
        return this._withRenderState(() => {
            this._frameCamera('isometric', framing);
            this.scene.renderer.render(this.scene.scene, this.scene.camera);
            return this.scene.renderer.domElement.toDataURL('image/png');
        }, {
            width,
            height,
            background: 0xffffff,
            boxColor: null,      // keep the green wireframe box
            hideGrid: true,
            floor: 'white',
            pieceOpacity: 1,
            pixelRatio: 1
        });
    }

    /**
     * Generate the one-page PDF report (HTML document for print / preview)
     * @param {Object} data - Report data
     * @returns {Promise<string>} HTML content
     */
    async generatePDF(data) {
        // Capture views - hero is large, small views are compact
        const views = {
            hero: this.captureHero(1400, 1050),
            top: this.captureView('top', 720, 480),
            front: this.captureView('front', 720, 480),
            side: this.captureView('side', 720, 480)
        };

        return await this.createPDFDocument(data, views);
    }

    /**
     * Create the one-page Pack Report HTML document
     * @param {Object} data - Report data
     * @param {Object} views - Captured view data URLs
     * @returns {string} HTML content
     */
    async createPDFDocument(data, views) {
        const {
            pieceDims,
            boxDims,
            pieceCount,
            pieceWeight = 0.1,
            maxWeight,
            mode = 'bulk',
            meshVolume = 0,
            materialDensity = 0,
            estimatedPieceWeight = 0,
            estimatedTotalWeight = 0,
            stlFileName = null,
            partName = null,
            cost = null
        } = data;

        // Volumes and weights - use real mesh volume if available
        const bboxVolumeMM3 = pieceDims.l * pieceDims.w * pieceDims.h;
        const realVolumeMM3 = meshVolume > 0 ? meshVolume : bboxVolumeMM3;
        const pieceVolume = realVolumeMM3 / 1000000; // cm³
        const boxVolume = (boxDims.length * boxDims.width * boxDims.height) / 1000000; // cm³
        const totalWeight = pieceCount * pieceWeight;
        const effectiveTotalWeight = estimatedTotalWeight > 0 ? estimatedTotalWeight : totalWeight;
        const volumeUsage = (pieceCount * pieceVolume / boxVolume * 100).toFixed(1);

        const localeCode = this.locale?.meta?.locale || (this.language === 'ca' ? 'ca-ES' : 'en-US');
        const currentDate = new Date().toLocaleDateString(localeCode);

        // Localized helpers
        const fmt = (v) => Number(v).toLocaleString(localeCode, { maximumFractionDigits: 2 });
        const fmtW = (v) => Number(v).toLocaleString(localeCode, { maximumFractionDigits: 4 });
        const fmtEuro = (v) => {
            if (v == null || Number.isNaN(Number(v))) return '—';
            return Number(v).toLocaleString(localeCode, {
                style: 'currency',
                currency: 'EUR',
                minimumFractionDigits: 2,
                maximumFractionDigits: 4
            });
        };

        const modeLabel = mode === 'fast'
            ? (this.t.modeFast || 'Planar')
            : mode === 'gpu'
                ? (this.t.modeGpu || 'GPU')
                : (this.t.modeBulk || 'Bulk');

        const name = partName || stlFileName || (this.t.customPiece || 'Custom piece');
        const fmtD = (v) => Number(v).toLocaleString(localeCode, { maximumFractionDigits: 2 });
        const dimsText = `${fmtD(pieceDims.l)} × ${fmtD(pieceDims.w)} × ${fmtD(pieceDims.h)} mm`;
        const weightText = fmtW(pieceWeight);

        const totalWeightText = effectiveTotalWeight > 0
            ? `${effectiveTotalWeight.toFixed(2)} kg`
            : `${totalWeight.toFixed(2)} kg`;

        // Cost section - only when cost data is present
        const hasCost = !!cost && (
            cost.boxCost != null || cost.packagingCost != null ||
            cost.freightCost != null || cost.costPerPart != null
        );

        const costRow = hasCost ? `
            <section class="cost-section">
                <div class="cost-header">
                    <span class="cost-title">${this.t.costTitle || 'Cost Summary'}</span>
                </div>
                <div class="cost-grid">
                    <div class="cost-item">
                        <div class="cost-value">${fmtEuro(cost.boxCost)}</div>
                        <div class="cost-label">${this.t.boxCost || 'Box cost'}</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">${fmtEuro(cost.packagingCost)}</div>
                        <div class="cost-label">${this.t.packagingCost || 'Packaging'}</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">${fmtEuro(cost.freightCost)}</div>
                        <div class="cost-label">${this.t.freightCost || 'Freight'}</div>
                    </div>
                    <div class="cost-item cost-item-highlight">
                        <div class="cost-value">${fmtEuro(cost.costPerPart)}</div>
                        <div class="cost-label">${this.t.costPerPart || 'Cost per part'}</div>
                    </div>
                </div>
            </section>` : '';

        const htmlContent = `<!DOCTYPE html>
<html lang="${this.language === 'ca' ? 'ca' : 'en'}">
<head>
<meta charset="UTF-8">
<title>${this.t.title} — PackAssist</title>
<style>
    @page { size: A4; margin: 0; }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body {
        background: #e5e7eb;
        font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
        color: #111827;
    }

    .sheet {
        width: 210mm;
        height: 296.5mm;
        background: #ffffff;
        margin: 0 auto;
        padding: 9mm 9mm 7mm 9mm;
        display: flex;
        flex-direction: column;
        gap: 4.5mm;
        overflow: hidden;
    }

    /* ── Header ─────────────────────────────────────── */
    .report-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        border-bottom: 1.2mm solid #111827;
        padding-bottom: 3mm;
    }
    .header-kicker {
        font-size: 2.6mm;
        font-weight: 700;
        letter-spacing: 1.6px;
        color: #059669;
        text-transform: uppercase;
        margin-bottom: 0.8mm;
    }
    .header-title {
        font-size: 6.6mm;
        font-weight: 800;
        line-height: 1.1;
        color: #111827;
        word-break: break-word;
    }
    .header-sub {
        font-size: 3.2mm;
        color: #6b7280;
        margin-top: 1.2mm;
        font-weight: 600;
    }
    .header-right {
        text-align: right;
        flex-shrink: 0;
        margin-left: 4mm;
    }
    .brand {
        font-size: 5.2mm;
        font-weight: 800;
        letter-spacing: 0.5px;
        color: #059669;
    }
    .brand-sub {
        font-size: 2.6mm;
        color: #6b7280;
        margin-top: 0.6mm;
        font-weight: 600;
    }

    /* ── Hero + Metrics ─────────────────────────────── */
    .main-row {
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        gap: 4.5mm;
    }
    .hero {
        flex: 1.55;
        min-width: 0;
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 3.5mm;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2mm;
        overflow: hidden;
    }
    .hero img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        flex: 1 1 auto;
        min-height: 0;
    }
    .hero-caption {
        font-size: 2.6mm;
        font-weight: 600;
        color: #6b7280;
        margin-top: 1.2mm;
        text-align: center;
    }

    .metrics {
        flex: 1;
        min-width: 0;
        display: grid;
        grid-template-columns: 1fr 1fr;
        grid-auto-rows: 1fr;
        gap: 2.4mm;
    }
    .metric {
        border: 1px solid #e5e7eb;
        border-radius: 2.6mm;
        background: #ffffff;
        padding: 2.4mm 2.8mm;
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 0;
    }
    .metric-value {
        font-size: 5.4mm;
        font-weight: 800;
        color: #059669;
        line-height: 1.05;
        word-break: break-word;
    }
    .metric-label {
        font-size: 2.5mm;
        color: #6b7280;
        margin-top: 1mm;
        font-weight: 600;
        line-height: 1.2;
    }

    /* ── Small views ───────────────────────────────── */
    .views-row {
        height: 42mm;
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 4.5mm;
        flex-shrink: 0;
    }
    .view {
        border: 1px solid #e5e7eb;
        border-radius: 3mm;
        background: #f8fafc;
        padding: 1.6mm;
        display: flex;
        flex-direction: column;
        align-items: center;
        overflow: hidden;
    }
    .view img {
        max-width: 100%;
        max-height: 100%;
        flex: 1 1 auto;
        min-height: 0;
        object-fit: contain;
    }
    .view-label {
        font-size: 2.5mm;
        font-weight: 600;
        color: #374151;
        margin-top: 1mm;
        text-align: center;
        flex-shrink: 0;
    }

    /* ── Cost summary ──────────────────────────────── */
    .cost-section {
        flex-shrink: 0;
        border: 0.8mm solid #059669;
        border-radius: 3mm;
        padding: 2.6mm 3mm;
        background: #f0fdf9;
    }
    .cost-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.8mm;
    }
    .cost-title {
        font-size: 3mm;
        font-weight: 800;
        color: #059669;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .cost-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr 1fr;
        gap: 2mm;
    }
    .cost-item {
        background: #ffffff;
        border: 1px solid #d1fae5;
        border-radius: 2.2mm;
        padding: 1.8mm 2.2mm;
    }
    .cost-item-highlight {
        background: #059669;
        border-color: #059669;
    }
    .cost-item-highlight .cost-value,
    .cost-item-highlight .cost-label {
        color: #ffffff;
    }
    .cost-value {
        font-size: 4mm;
        font-weight: 800;
        color: #059669;
        line-height: 1.05;
        word-break: break-word;
    }
    .cost-label {
        font-size: 2.3mm;
        color: #6b7280;
        margin-top: 0.8mm;
        font-weight: 600;
    }

    /* ── Footer ────────────────────────────────────── */
    .report-footer {
        flex-shrink: 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 0.5mm solid #e5e7eb;
        padding-top: 2mm;
        font-size: 2.6mm;
        color: #6b7280;
        font-weight: 600;
    }
    .report-footer .footer-brand {
        font-weight: 800;
        color: #059669;
    }

    .view-unavailable {
        color: #6b7280;
        font-size: 3mm;
        padding: 10mm 0;
        text-align: center;
    }

    /* ── Preview scaling (screen only) ─────────────── */
    @media screen {
        body { padding: 12px; }
    }
    @media print {
        html, body { background: #ffffff; }
        .sheet {
            margin: 0;
            transform: none !important;
            left: 0 !important;
        }
    }
</style>
</head>
<body>
    <div class="sheet">
        <!-- HEADER: part info | PackAssist -->
        <header class="report-header">
            <div class="header-left">
                <div class="header-kicker">${this.t.kicker || 'Pack Report'}</div>
                <h1 class="header-title">${name}</h1>
                <div class="header-sub">${dimsText} · ${this.t.weight} ${weightText} kg</div>
            </div>
            <div class="header-right">
                <div class="brand">PackAssist</div>
                <div class="brand-sub">${PACKASSIST_VERSION} · ${currentDate}</div>
            </div>
        </header>

        <!-- HERO + METRICS -->
        <div class="main-row">
            <div class="hero">
                ${views.hero
                    ? `<img src="${views.hero}" alt="${this.t.isometricView}">`
                    : `<div class="view-unavailable">${this.t.viewUnavailable}</div>`}
                <div class="hero-caption">${this.t.isometricView}</div>
            </div>
            <div class="metrics">
                <div class="metric">
                    <div class="metric-value">${fmt(pieceCount)}</div>
                    <div class="metric-label">${this.t.pieceCount}</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${volumeUsage}%</div>
                    <div class="metric-label">${this.t.volumeUsage}</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${boxDims.length}×${boxDims.width}×${boxDims.height}</div>
                    <div class="metric-label">${this.t.boxDims || 'Box (mm)'}</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${weightText} kg</div>
                    <div class="metric-label">${this.t.weightPerPiece || 'Weight / piece'}</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${totalWeightText}</div>
                    <div class="metric-label">${this.t.totalWeight}</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${modeLabel}</div>
                    <div class="metric-label">${this.t.modeUsed || 'Mode'}</div>
                </div>
            </div>
        </div>

        <!-- SMALL MULTI-VIEWS -->
        <div class="views-row">
            <div class="view">
                ${views.top
                    ? `<img src="${views.top}" alt="${this.t.topView}">`
                    : `<div class="view-unavailable">${this.t.viewUnavailable}</div>`}
                <div class="view-label">${this.t.topView}</div>
            </div>
            <div class="view">
                ${views.front
                    ? `<img src="${views.front}" alt="${this.t.frontView}">`
                    : `<div class="view-unavailable">${this.t.viewUnavailable}</div>`}
                <div class="view-label">${this.t.frontView}</div>
            </div>
            <div class="view">
                ${views.side
                    ? `<img src="${views.side}" alt="${this.t.sideView}">`
                    : `<div class="view-unavailable">${this.t.viewUnavailable}</div>`}
                <div class="view-label">${this.t.sideView}</div>
            </div>
        </div>

        <!-- COST SUMMARY (optional) -->
        ${costRow}

        <!-- FOOTER -->
        <footer class="report-footer">
            <span>${this.t.generatedBy}</span>
            <span><span class="footer-brand">PackAssist</span> ${PACKASSIST_VERSION} · ${currentDate}</span>
        </footer>
    </div>

    <script>
        (function () {
            // Scale the A4 sheet to fit the preview iframe width (screen only).
            // In print the @page size guarantees exactly one A4 sheet.
            function fit() {
                if (window.matchMedia('print').matches) return;
                var sheet = document.querySelector('.sheet');
                if (!sheet) return;
                var w = sheet.offsetWidth;
                var avail = (window.innerWidth || document.documentElement.clientWidth) - 24;
                if (avail > 0 && avail < w) {
                    var s = avail / w;
                    sheet.style.transformOrigin = 'top left';
                    sheet.style.transform = 'scale(' + s + ')';
                    sheet.style.marginLeft = '0';
                    sheet.style.marginRight = '0';
                    sheet.style.position = 'relative';
                    sheet.style.left = ((w - avail) / 2) + 'px';
                } else {
                    sheet.style.transform = '';
                    sheet.style.left = '0';
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
