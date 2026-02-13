/**
 * PackAssist Web - Packing Calculator
 * Port of packing_core.py to JavaScript
 */

function calculateFit(pieceDim, boxDim, gap) {
    if (pieceDim > boxDim) return 0;
    if (Math.abs(gap) < 0.001) return Math.floor(boxDim / pieceDim);
    const fit = Math.floor((boxDim + gap) / (pieceDim + gap));
    const requiredSpace = fit * pieceDim + Math.max(0, fit - 1) * gap;
    if (requiredSpace > boxDim) return fit - 1;
    return fit;
}

/**
 * Find the best distribution limited by weight, prioritizing fewer stacking layers
 * @param {number} maxL - Max pieces in length direction
 * @param {number} maxW - Max pieces in width direction
 * @param {number} maxH - Max pieces in height direction
 * @param {number} targetUnits - Maximum units allowed by weight
 * @returns {Object|null} Best distribution {l, w, h, units}
 */
export function optimizeByWeight(maxL, maxW, maxH, targetUnits) {
    let bestDist = null;
    let bestScore = -Infinity;

    for (let l = 1; l <= maxL; l++) {
        for (let w = 1; w <= maxW; w++) {
            const h = Math.min(maxH, Math.floor(targetUnits / (l * w)));
            if (h < 1) continue;
            
            const units = l * w * h;
            if (units > targetUnits) continue;
            
            // Score: more units is better, then prefer larger base and fewer layers
            const base = l * w;
            const score = units * 1000 + base * 10 - h * 5;
            if (score > bestScore) {
                bestScore = score;
                bestDist = { l, w, h, units };
            }
        }
    }

    return bestDist;
}

/**
 * Create debug info when no pieces fit
 * @param {Array} orientations - List of orientation data
 * @param {number} maxWeight - Maximum weight capacity
 * @param {number} objWeight - Weight per unit
 * @returns {string} HTML debug info
 */
function createDebugInfo(orientations, maxWeight, objWeight) {
    const maxByWeight = objWeight > 0 ? Math.floor(maxWeight / objWeight) : 0;
    
    let debug = '<h3>Orientacions provades:</h3><ul>';
    
    for (const ori of orientations) {
        const status = ori.fitsWeight ? '' : '';
        debug += `<li>${status} <strong>${ori.name}</strong>: ${ori.units} unitats `;
        debug += `(${ori.distribution}) - Pes: ${ori.weight.toFixed(2)}kg</li>`;
    }
    debug += '</ul>';

    debug += '<h3>Diagnòstic:</h3><ul>';
    debug += `<li>Capacitat màxima: ${maxWeight.toFixed(1)} kg</li>`;
    debug += `<li>Pes per unitat: ${objWeight.toFixed(3)} kg</li>`;
    debug += `<li>Màxim teòric per pes: ${maxByWeight} unitats</li>`;
    debug += '</ul>';

    const hasUnits = orientations.some(ori => ori.units > 0);
    if (hasUnits) {
        if (maxByWeight > 0) {
            debug += `<p><strong>Solució</strong>: ${maxByWeight} unitats limitades per pes</p>`;
        } else {
            debug += '<p><strong>Problema</strong>: El pes individual és massa alt</p>';
        }
    } else {
        debug += '<p><strong>Problema</strong>: Les dimensions són massa grans per la caixa</p>';
    }

    return debug;
}

/**
 * Generate the final summary in HTML
 * @param {number} count - Number of pieces that fit
 * @param {Object} config - Best configuration
 * @param {Array} allOrientations - All orientation data
 * @returns {string} HTML summary
 */
export function createSummary(count, config, allOrientations, extra = {}) {
    const dims = config?.dimensions || [0, 0, 0];

    // Volume-based theoretical max (from real mesh volume if available)
    const volTheoretical = extra.volumeTheoreticalMax || null;
    const meshVolumeCC = extra.meshVolumeMM3 ? (extra.meshVolumeMM3 / 1000).toFixed(2) : null;
    const bboxVolumeCC = (dims[0] * dims[1] * dims[2] / 1000).toFixed(2);
    const fillRatio = extra.meshVolumeMM3 && dims[0] * dims[1] * dims[2] > 0
        ? (extra.meshVolumeMM3 / (dims[0] * dims[1] * dims[2]) * 100).toFixed(1)
        : null;

    // Estimated weight from material density
    const estPieceWeightG = extra.estimatedPieceWeight ? (extra.estimatedPieceWeight * 1000).toFixed(1) : null;
    const estTotalWeightKg = extra.estimatedTotalWeight ? extra.estimatedTotalWeight.toFixed(3) : null;
    const materialName = extra.materialName || null;

    const volEff = (config?.volEfficiency || 0).toFixed(1);
    const weightEff = (config?.weightEfficiency || 0).toFixed(1);
    const totalWeight = (config?.weight || 0).toFixed(2);

    let summary = `
    <div class="results-hero">
        <div class="hero-number">${count}</div>
        <div class="hero-label">peces</div>
    </div>

    <div class="results-cards">
        <div class="result-card">
            <div class="card-body">
                <div class="card-value">${config?.distribution || '0×0×0'}</div>
                <div class="card-label">Distribució (L×W×H)</div>
            </div>
        </div>
        <div class="result-card">
            <div class="card-body">
                <div class="card-value">${estTotalWeightKg ? estTotalWeightKg + ' kg' : totalWeight + ' kg'}</div>
                <div class="card-label">${estTotalWeightKg ? 'Pes total estimat' : 'Pes total'}</div>
                ${estPieceWeightG ? `<div class="card-sub">${estPieceWeightG} g/peça · ${materialName || 'material'}</div>` : ''}
            </div>
        </div>
        <div class="result-card">
            <div class="card-body">
                <div class="card-value">${volEff}%</div>
                <div class="card-label">Eficiència volum</div>
            </div>
        </div>
        <div class="result-card">
            <div class="card-body">
                <div class="card-value">${config?.name || '—'}</div>
                <div class="card-label">Orientació òptima</div>
            </div>
        </div>
    </div>`;

    // Volume info section (only if STL volume available)
    if (meshVolumeCC) {
        summary += `
    <div class="results-section">
        <h3>Volum STL</h3>
        <div class="info-grid">
            <div class="info-item"><span class="info-label">Volum real</span><span class="info-value">${meshVolumeCC} cm³</span></div>
            <div class="info-item"><span class="info-label">Bounding box</span><span class="info-value">${bboxVolumeCC} cm³</span></div>
            <div class="info-item"><span class="info-label">Ratio ompliment</span><span class="info-value">${fillRatio}%</span></div>`;
        if (volTheoretical !== null) {
            summary += `
            <div class="info-item"><span class="info-label">Màx. teòric (volum)</span><span class="info-value">${volTheoretical}</span></div>`;
        }
        summary += `
        </div>
    </div>`;
    }

    if (config?.limitedBy === 'weight') {
        summary += `<div class="results-warning">⚠️ Factor limitant: PES (no dimensions)</div>`;
    }

    // Orientations comparison table
    if (allOrientations.length > 1) {
        summary += `
    <details class="results-section orientations-details">
        <summary><h3>Comparació d'Orientacions</h3></summary>
        <table>
            <thead>
                <tr>
                    <th>Orientació</th>
                    <th>Units</th>
                    <th>Dist.</th>
                    <th>Pes</th>
                    <th>Vol%</th>
                </tr>
            </thead>
            <tbody>`;
        
        for (const ori of allOrientations) {
            const isBest = ori.name === config?.name;
            summary += `
                <tr${isBest ? ' class="best-row"' : ''}>
                    <td>${ori.name}</td>
                    <td>${ori.units}</td>
                    <td>${ori.distribution}</td>
                    <td>${ori.weight.toFixed(1)}</td>
                    <td>${ori.volEfficiency.toFixed(1)}</td>
                </tr>`;
        }
        
        summary += `
            </tbody>
        </table>
    </details>`;
    }

    return summary;
}

/**
 * Calculate optimal packing configuration
 * @param {Object} params - Packing parameters
 * @param {number} params.objL - Object length (mm)
 * @param {number} params.objW - Object width (mm)
 * @param {number} params.objH - Object height (mm)
 * @param {number} params.objWeight - Object weight (kg)
 * @param {number} params.boxL - Box length (mm)
 * @param {number} params.boxW - Box width (mm)
 * @param {number} params.boxH - Box height (mm)
 * @param {number} params.maxWeight - Max box weight (kg)
 * @param {boolean} params.allowRotation - Allow 6 orientations
 * @param {Array} params.orientationOverrides - Optional orientation overrides [{dims:[l,w,h], name, permIndex}]
 * @param {number} [params.meshVolume] - Real mesh volume in mm³ (from computeMeshVolume)
 * @returns {Object} {summary: string, data: Object}
 */
export function calcularEmpaquetatge(params) {
    const {
        objL, objW, objH, objWeight,
        boxL, boxW, boxH, maxWeight,
        allowRotation = true,
        packingGap = 0, // Separació entre peces en mm (0 = sense gap)
        orientationOverrides = null,
        meshVolume = 0 // Real mesh volume in mm³ (0 = use bounding box)
    } = params;

    // Validation
    if ([objL, objW, objH, objWeight, boxL, boxW, boxH, maxWeight].some(v => v <= 0)) {
        return {
            summary: '<p>Tots els valors han de ser majors que 0.</p>',
            data: null
        };
    }

    if (objWeight > maxWeight) {
        return {
            summary: '<p>El pes d\'una sola unitat supera la capacitat màxima de la caixa.</p>',
            data: null
        };
    }

    // Object dimensions
    const objDims = [objL, objW, objH];
    const boxDims = [boxL, boxW, boxH];
    const volBox = boxDims[0] * boxDims[1] * boxDims[2];

    // Generate orientations (6 permutations or just 1)
    let orientations, orientationNames;
    
    if (Array.isArray(orientationOverrides) && orientationOverrides.length > 0) {
        orientations = orientationOverrides.map(o => o.dims);
        orientationNames = orientationOverrides.map((o, i) => o.name || `Orientació ${i + 1}`);
    } else if (allowRotation) {
        orientations = [
            [objDims[0], objDims[1], objDims[2]],
            [objDims[0], objDims[2], objDims[1]],
            [objDims[1], objDims[0], objDims[2]],
            [objDims[1], objDims[2], objDims[0]],
            [objDims[2], objDims[0], objDims[1]],
            [objDims[2], objDims[1], objDims[0]],
        ];
        orientationNames = [
            'Original (L×W×H)',
            'Rotació Y (L×H×W)',
            'Rotació Z (W×L×H)',
            'Rotació XY (W×H×L)',
            'Rotació XZ (H×L×W)',
            'Rotació YZ (H×W×L)',
        ];
    } else {
        orientations = [[objDims[0], objDims[1], objDims[2]]];
        orientationNames = ['Sense rotació'];
    }

    let bestFit = 0;
    let bestConfig = null;
    const allOrientations = [];

    const isMoreStable = (a, b) => {
        if (!b) return true;
        if (!a) return false;
        const baseA = (a.fitL || 0) * (a.fitW || 0);
        const baseB = (b.fitL || 0) * (b.fitW || 0);
        if (baseA !== baseB) return baseA > baseB;
        return (a.fitH || 0) < (b.fitH || 0);
    };

    for (let i = 0; i < orientations.length; i++) {
        const [ol, ow, oh] = orientations[i];
        
        // Calculate how many fit in each direction (amb gap entre peces)
        // Correct formula: gap only applies BETWEEN pieces, not after the last one
        // So for N pieces we need: N * pieceDim + (N-1) * gap <= boxDim
        // Solving: N <= (boxDim + gap) / (pieceDim + gap)
        // First check that at least one piece fits (without gap requirement)
        
        let fitL = calculateFit(ol, boxDims[0], packingGap);
        let fitW = calculateFit(ow, boxDims[1], packingGap);
        let fitH = calculateFit(oh, boxDims[2], packingGap);
        
        // Safety cap to prevent infinite loop or memory crash with extreme nesting
        fitL = Math.max(0, Math.min(fitL, 1000));
        fitW = Math.max(0, Math.min(fitW, 1000));
        fitH = Math.max(0, Math.min(fitH, 1000));

        const totalUnits = fitL * fitW * fitH;
        const totalWeight = totalUnits * objWeight;

        const volObj = meshVolume > 0 ? meshVolume : (ol * ow * oh);
        const volEfficiency = volBox > 0 ? (totalUnits * volObj / volBox * 100) : 0;
        const weightEfficiency = maxWeight > 0 ? (totalWeight / maxWeight * 100) : 0;

        const orientationData = {
            name: orientationNames[i],
            dimensions: [ol, ow, oh],
            permIndex: Array.isArray(orientationOverrides) && orientationOverrides[i]?.permIndex !== undefined
                ? orientationOverrides[i].permIndex
                : i,
            rotation: Array.isArray(orientationOverrides) && orientationOverrides[i]?.rotation
                ? orientationOverrides[i].rotation
                : null,
            units: totalUnits,
            distribution: `${fitL}×${fitW}×${fitH}`,
            maxFit: { l: fitL, w: fitW, h: fitH },
            fitL,
            fitW,
            fitH,
            weight: totalWeight,
            volEfficiency,
            weightEfficiency,
            fitsWeight: totalWeight <= maxWeight,
        };
        allOrientations.push(orientationData);

        // If fits both dimensions and weight
        if (totalUnits > 0 && totalWeight <= maxWeight) {
            if (totalUnits > bestFit || (totalUnits === bestFit && isMoreStable(orientationData, bestConfig))) {
                bestFit = totalUnits;
                bestConfig = { ...orientationData };
                continue;
            }
        }

        // If doesn't fit due to weight, try optimization
        if (totalUnits <= 0) continue;

        const maxByWeight = Math.floor(maxWeight / objWeight);
        if (maxByWeight <= bestFit) continue;

        const bestDist = optimizeByWeight(fitL, fitW, fitH, maxByWeight);
        if (!bestDist) continue;

        const weightConfig = {
            name: `${orientationNames[i]} (Limitat per pes)`,
            dimensions: [ol, ow, oh],
            rotation: Array.isArray(orientationOverrides) && orientationOverrides[i]?.rotation
                ? orientationOverrides[i].rotation
                : null,
            units: bestDist.units,
            distribution: `${bestDist.l}×${bestDist.w}×${bestDist.h}`,
            maxFit: { l: fitL, w: fitW, h: fitH },
            fitL: bestDist.l,
            fitW: bestDist.w,
            fitH: bestDist.h,
            weight: bestDist.units * objWeight,
            volEfficiency: volBox > 0 ? (bestDist.units * volObj / volBox * 100) : 0,
            weightEfficiency: maxWeight > 0 ? (bestDist.units * objWeight / maxWeight * 100) : 0,
            fitsWeight: true,
            limitedBy: 'weight',
        };

        if (bestDist.units > bestFit || (bestDist.units === bestFit && isMoreStable(weightConfig, bestConfig))) {
            bestFit = bestDist.units;
            bestConfig = weightConfig;
        }
    }

    // No solution found
    if (bestFit === 0 || !bestConfig) {
        const debug = createDebugInfo(allOrientations, maxWeight, objWeight);
        return {
            summary: `<p>No cap cap unitat a la caixa.</p>${debug}`,
            data: null
        };
    }

    // Volume-based theoretical max (using real mesh volume if available)
    const volumeTheoreticalMax = meshVolume > 0 && volBox > 0
        ? Math.floor(volBox / meshVolume)
        : null;

    const summary = createSummary(bestFit, bestConfig, allOrientations, {
        volumeTheoreticalMax,
        meshVolumeMM3: meshVolume > 0 ? meshVolume : null,
    });

    return {
        summary,
        data: {
            theoreticalUnits: bestFit,
            volumeTheoreticalMax,
            realUnits: bestFit,
            bestOrientation: bestConfig,
            allOrientations,
            realDistribution: bestConfig.distribution,
            packingGap: packingGap,
            meshVolume: meshVolume > 0 ? meshVolume : null,
        }
    };
}

/**
 * Get distribution array from packing result
 * @param {Object} data - Packing result data
 * @returns {Array} [nx, ny, nz] distribution
 */
export function getDistribution(data) {
    const distribution = data?.realDistribution || data?.bestOrientation?.distribution;
    if (!distribution) {
        return [0, 0, 0];
    }
    const parts = distribution.split('×');
    return parts.map(p => parseInt(p, 10) || 0);
}

/**
 * Get piece dimensions from packing result
 * @param {Object} data - Packing result data
 * @returns {Array} [l, w, h] dimensions
 */
export function getPieceDimensions(data) {
    if (!data?.bestOrientation?.dimensions) {
        return [0, 0, 0];
    }
    return [...data.bestOrientation.dimensions];
}
