/**
 * PackAssist Web - PDF Report Generator
 * Generates professional reports with multiple views
 */

import * as THREE from 'three';
import { loadLocale } from '../i18n.js';

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
     * Capture a view from the scene for report (white bg, black box, no grid)
     * @param {string} viewType - 'front', 'top', 'side', 'isometric'
     * @param {number} width - Image width
     * @param {number} height - Image height
     * @returns {string} Data URL of the image
     */
    captureView(viewType, width = 400, height = 300) {
        if (!this.scene || !this.scene.renderer || !this.scene.camera) {
            console.error('Scene not ready for capture');
            return null;
        }

        // Store original states
        const originalPosition = this.scene.camera.position.clone();
        const originalTarget = this.scene.controls?.target?.clone() || new THREE.Vector3();
        const originalSize = new THREE.Vector2();
        this.scene.renderer.getSize(originalSize);
        
        // Store original scene background
        const originalBackground = this.scene.scene.background;
        
        // Store original box material if exists
        let originalBoxMaterial = null;
        if (this.scene.boxMesh) {
            originalBoxMaterial = this.scene.boxMesh.material;
        }
        
        // Store original grid visibility
        let originalGridVisible = true;
        const grid = this.scene.scene.getObjectByName('grid');
        if (grid) {
            originalGridVisible = grid.visible;
            grid.visible = false; // Hide grid for report
        }
        
        // Set white background
        this.scene.scene.background = new THREE.Color(0xffffff);
        
        // Set black wireframe for box
        if (this.scene.boxMesh) {
            this.scene.boxMesh.material = new THREE.LineBasicMaterial({ 
                color: 0x000000,
                linewidth: 2
            });
        }

        // Resize for capture
        this.scene.renderer.setSize(width, height, false);
        this.scene.camera.aspect = width / height;
        this.scene.camera.updateProjectionMatrix();

        // Set view
        this.scene.setView(viewType);
        
        // Zoom in closer for report - move camera closer to target
        // The standard setView uses distance = maxDim * 2.5, we want tighter framing
        if (this.scene.boxMesh && this.scene.controls) {
            const target = this.scene.controls.target.clone();
            const cameraPos = this.scene.camera.position.clone();
            const direction = cameraPos.sub(target).normalize();
            
            // Calculate optimal distance based on box size and camera FOV
            const box = new THREE.Box3().setFromObject(this.scene.boxMesh);
            const size = new THREE.Vector3();
            box.getSize(size);
            
            // For perspective camera, calculate distance to fill frame
            const fov = this.scene.camera.fov * (Math.PI / 180);
            const maxDim = Math.max(size.x, size.y, size.z);
            
            // Distance that fills ~80% of the frame (tighter framing)
            const optimalDistance = maxDim / (2 * Math.tan(fov / 2)) * 1.3;
            
            // Apply new position
            this.scene.camera.position.copy(target).add(direction.multiplyScalar(optimalDistance));
            this.scene.camera.updateProjectionMatrix();
        }
        
        // Render
        this.scene.renderer.render(this.scene.scene, this.scene.camera);
        
        // Capture
        const dataUrl = this.scene.renderer.domElement.toDataURL('image/png');

        // Restore original states
        this.scene.scene.background = originalBackground;
        
        if (this.scene.boxMesh && originalBoxMaterial) {
            this.scene.boxMesh.material = originalBoxMaterial;
        }
        
        if (grid) {
            grid.visible = originalGridVisible;
        }
        
        this.scene.renderer.setSize(originalSize.x, originalSize.y, false);
        this.scene.camera.aspect = originalSize.x / originalSize.y;
        this.scene.camera.position.copy(originalPosition);
        if (this.scene.controls) {
            this.scene.controls.target.copy(originalTarget);
            this.scene.controls.update();
        }
        this.scene.camera.updateProjectionMatrix();
        this.scene.renderer.render(this.scene.scene, this.scene.camera);

        return dataUrl;
    }

    /**
     * Generate PDF report
     * @param {Object} data - Report data
     * @returns {Promise<Blob>} PDF blob
     */
    async generatePDF(data) {
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
            estimatedTotalWeight = 0
        } = data;

        // Calculate volumes and weights - use real mesh volume if available
        const bboxVolumeMM3 = pieceDims.l * pieceDims.w * pieceDims.h;
        const realVolumeMM3 = meshVolume > 0 ? meshVolume : bboxVolumeMM3;
        const pieceVolume = realVolumeMM3 / 1000000000; // m³
        const boxVolume = (boxDims.length * boxDims.width * boxDims.height) / 1000000000; // m³
        const totalWeight = pieceCount * pieceWeight;
        const effectiveTotalWeight = estimatedTotalWeight > 0 ? estimatedTotalWeight : totalWeight;
        const volumeUsage = (pieceCount * pieceVolume / boxVolume * 100).toFixed(1);

        // Capture views - MUCH LARGER for report
        const views = {
            isometric: this.captureView('isometric', 1200, 900),
            front: this.captureView('front', 1000, 700),
            top: this.captureView('top', 1000, 700),
            side: this.captureView('side', 1000, 700)
        };

        // Create PDF content using jsPDF
        // We'll use a canvas-based approach for browser compatibility
        const pdf = await this.createPDFDocument(data, views);
        
        return pdf;
    }

    /**
     * Create PDF document using canvas
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
            estimatedTotalWeight = 0
        } = data;

        // Calculate values - use real mesh volume if available
        const bboxVolumeMM3 = pieceDims.l * pieceDims.w * pieceDims.h;
        const realVolumeMM3 = meshVolume > 0 ? meshVolume : bboxVolumeMM3;
        const pieceVolume = realVolumeMM3 / 1000000; // cm³
        const pieceVolumeBBox = bboxVolumeMM3 / 1000000; // cm³ (for reference)
        const boxVolume = (boxDims.length * boxDims.width * boxDims.height) / 1000000; // cm³
        const totalWeight = pieceCount * pieceWeight;
        const effectiveTotalWeight = estimatedTotalWeight > 0 ? estimatedTotalWeight : totalWeight;
        const volumeUsage = (pieceCount * pieceVolume / boxVolume * 100).toFixed(1);
        const currentDate = new Date().toLocaleDateString(this.locale?.meta?.locale || (this.language === 'ca' ? 'ca-ES' : 'en-US'));

        // Create HTML for PDF - 2 PAGES with LARGE images
        const htmlContent = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${this.t.title} — PackAssist</title>
    <style>
        @page {
            size: A4;
            margin: 12mm;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            font-size: 11px;
            color: #333;
            background: white;
        }
        
        /* PAGE 1 */
        .page {
            width: 100%;
            height: 273mm; /* A4 height minus margins */
            padding: 20px;
            page-break-after: always;
            overflow: hidden;
        }
        .page:last-child {
            page-break-after: avoid;
        }
        
        .header {
            text-align: center;
            border-bottom: 3px solid #1e40af;
            padding-bottom: 8px;
            margin-bottom: 10px;
        }
        .header h1 { 
            color: #1e40af; 
            font-size: 24px;
            margin-bottom: 2px;
        }
        .header .subtitle { 
            color: #666; 
            font-size: 11px;
        }
        
        .info-row {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }
        .info-box {
            flex: 1;
            border: 1px solid #d1d5db;
            padding: 8px;
            background: #f9fafb;
            border-radius: 6px;
        }
        .info-box h3 {
            color: #1e40af;
            font-size: 11px;
            margin-bottom: 6px;
            padding-bottom: 4px;
            border-bottom: 1px solid #e5e7eb;
        }
        .results-box {
            background: #ecfdf5;
            border: 2px solid #10b981;
        }
        .results-box h3 {
            color: #059669;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 10px;
        }
        table td {
            padding: 3px 6px;
        }
        table td:first-child {
            color: #666;
        }
        table td:last-child {
            font-weight: 600;
            text-align: right;
        }
        .result-value {
            font-size: 20px;
            color: #059669;
        }
        
        /* MAIN IMAGE - LARGE */
        .main-view {
            text-align: center;
            margin-top: 10px;
        }
        .main-view img {
            max-width: 100%;
            max-height: 460px;
            border: 2px solid #1e40af;
            border-radius: 8px;
        }
        .main-view .view-label {
            margin-top: 5px;
            font-size: 13px;
            font-weight: 600;
            color: #1e40af;
        }
        
        /* PAGE 2 - OTHER VIEWS */
        .page-title {
            text-align: center;
            font-size: 16px;
            font-weight: bold;
            color: #1e40af;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 2px solid #1e40af;
        }
        
        .views-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto auto;
            gap: 10px;
        }
        .views-grid .view-box:first-child {
            grid-column: 1 / -1; /* Front view spans full width */
        }
        .view-box {
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .view-box img {
            max-width: 100%;
            max-height: 300px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            object-fit: contain;
        }
        .views-grid .view-box:first-child img {
            max-height: 380px;
        }
        .view-box .view-label {
            margin-top: 4px;
            font-size: 11px;
            font-weight: 600;
            color: #374151;
        }
        
        .footer {
            margin-top: 10px;
            padding-top: 6px;
            border-top: 1px solid #e5e7eb;
            text-align: center;
            color: #666;
            font-size: 9px;
        }
        
        @media print {
            @page {
                margin: 12mm;
                size: A4;
            }
            body {
                margin: 0;
                padding: 0;
            }
            .page {
                height: auto;
                max-height: 273mm;
                page-break-after: always;
                padding: 0;
                overflow: hidden;
            }
            .page:last-child { page-break-after: avoid; }
        }
    </style>
</head>
<body>
    <!-- PAGE 1: Info + Isometric View -->
    <div class="page">
        <div class="header">
            <h1>${this.t.title}</h1>
            <div class="subtitle">${this.t.subtitle} — ${currentDate}</div>
        </div>

        <div class="info-row">
            <div class="info-box">
                <h3>${this.t.pieceInfo}</h3>
                <table>
                    <tr><td>${this.t.dimensions}</td><td>${pieceDims.l} × ${pieceDims.w} × ${pieceDims.h} mm</td></tr>
                    <tr><td>${this.t.weight}</td><td>${pieceWeight} kg</td></tr>
                    <tr><td>${this.t.volume}</td><td>${pieceVolume.toFixed(2)} cm³${meshVolume > 0 ? this.t.realVolumeSuffix : this.t.bboxVolumeSuffix}</td></tr>
                </table>
            </div>
            <div class="info-box">
                <h3>${this.t.containerInfo}</h3>
                <table>
                    <tr><td>${this.t.innerDims}</td><td>${boxDims.length} × ${boxDims.width} × ${boxDims.height} mm</td></tr>
                    <tr><td>${this.t.maxWeight}</td><td>${maxWeight} kg</td></tr>
                    <tr><td>${this.t.innerVolume}</td><td>${boxVolume.toFixed(2)} cm³</td></tr>
                </table>
            </div>
            <div class="info-box results-box">
                <h3>${this.t.results}</h3>
                <table>
                    <tr><td>${this.t.pieceCount}</td><td class="result-value">${pieceCount}</td></tr>
                    <tr><td>${this.t.totalWeight}</td><td>${totalWeight.toFixed(2)} kg</td></tr>
                    ${estimatedTotalWeight > 0 ? `<tr><td>${this.t.estimatedTotalWeight}</td><td>${estimatedTotalWeight.toFixed(3)} kg</td></tr>` : ''}
                    ${materialDensity > 0 ? `<tr><td>${this.t.materialDensity}</td><td>${materialDensity} kg/m³</td></tr>` : ''}
                    <tr><td>${this.t.volumeUsage}</td><td>${volumeUsage}%</td></tr>
                </table>
            </div>
        </div>

        <div class="main-view">
            ${views.isometric ? `<img src="${views.isometric}" alt="${this.t.isometricView}">` : `<p>${this.t.viewUnavailable}</p>`}
            <div class="view-label">${this.t.isometricView}</div>
        </div>
        
        <div class="footer">
            ${this.t.generatedBy}
        </div>
    </div>

    <!-- PAGE 2: Other Views -->
    <div class="page">
        <div class="page-title">${this.t.views}</div>
        
        <div class="views-grid">
            <div class="view-box">
                ${views.front ? `<img src="${views.front}" alt="${this.t.frontView}">` : `<p>${this.t.viewUnavailable}</p>`}
                <div class="view-label">${this.t.frontView}</div>
            </div>
            <div class="view-box">
                ${views.top ? `<img src="${views.top}" alt="${this.t.topView}">` : `<p>${this.t.viewUnavailable}</p>`}
                <div class="view-label">${this.t.topView}</div>
            </div>
            <div class="view-box">
                ${views.side ? `<img src="${views.side}" alt="${this.t.sideView}">` : `<p>${this.t.viewUnavailable}</p>`}
                <div class="view-label">${this.t.sideView}</div>
            </div>
        </div>
        
        <div class="footer">
            ${this.t.generatedBy} — ${currentDate}
        </div>
    </div>
</body>
</html>
        `;

        return htmlContent;
    }

    /**
     * Generate and download report
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
