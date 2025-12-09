/**
 * PackAssist Web - Packing Calculator
 * Port of packing_core.py to JavaScript
 */

export const DEFAULT_SAFETY_FACTOR = 1.0;

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
            
            // Score: more units is better, but penalize height
            const score = units - (h * 0.01);
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
    
    let debug = '<h3>📋 Orientacions provades:</h3><ul>';
    
    for (const ori of orientations) {
        const status = ori.fitsWeight ? '✅' : '⚖️';
        debug += `<li>${status} <strong>${ori.name}</strong>: ${ori.units} unitats `;
        debug += `(${ori.distribution}) - Pes: ${ori.weight.toFixed(2)}kg</li>`;
    }
    debug += '</ul>';

    debug += '<h3>💡 Diagnòstic:</h3><ul>';
    debug += `<li>Capacitat màxima: ${maxWeight.toFixed(1)} kg</li>`;
    debug += `<li>Pes per unitat: ${objWeight.toFixed(3)} kg</li>`;
    debug += `<li>Màxim teòric per pes: ${maxByWeight} unitats</li>`;
    debug += '</ul>';

    const hasUnits = orientations.some(ori => ori.units > 0);
    if (hasUnits) {
        if (maxByWeight > 0) {
            debug += `<p>✅ <strong>Solució</strong>: ${maxByWeight} unitats limitades per pes</p>`;
        } else {
            debug += '<p>❌ <strong>Problema</strong>: El pes individual és massa alt</p>';
        }
    } else {
        debug += '<p>❌ <strong>Problema</strong>: Les dimensions són massa grans per la caixa</p>';
    }

    return debug;
}

/**
 * Generate the final summary in HTML
 * @param {number} theoretical - Theoretical max units
 * @param {number} real - Real units with safety factor
 * @param {Object} config - Best configuration
 * @param {number} safety - Safety factor (0-1)
 * @param {Array} allOrientations - All orientation data
 * @returns {string} HTML summary
 */
function createSummary(theoretical, real, config, safety, allOrientations) {
    const dims = config?.dimensions || [0, 0, 0];
    const safetyPercent = Math.round(safety * 100);
    
    let summary = `
    <h1>📦 RESULTATS</h1>
    
    <h2>🎯 Resultat Principal</h2>
    <ul>
        <li><strong>Unitats teòriques màximes:</strong> ${theoretical} <em>(per volum)</em></li>
        <li><strong>Unitats reals (seguretat ${safetyPercent}%):</strong> ${real}</li>
        <li><strong>Orientació òptima:</strong> ${config?.name || '—'}</li>
        <li><strong>Distribució:</strong> ${config?.distribution || '0×0×0'} (L×W×H)</li>
    </ul>

    <h2>⚖️ Anàlisi de Pes i Volum</h2>
    <ul>
        <li><strong>Pes total:</strong> ${(config?.weight || 0).toFixed(2)} kg</li>
        <li><strong>Eficiència volumètrica:</strong> ${(config?.volEfficiency || 0).toFixed(1)}%</li>
        <li><strong>Eficiència de pes:</strong> ${(config?.weightEfficiency || 0).toFixed(1)}%</li>
    </ul>

    <h2>📐 Dimensions de l'Orientació Òptima</h2>
    <ul>
        <li><strong>Llargada:</strong> ${dims[0].toFixed(2)} mm</li>
        <li><strong>Amplada:</strong> ${dims[1].toFixed(2)} mm</li>
        <li><strong>Alçada:</strong> ${dims[2].toFixed(2)} mm</li>
    </ul>
    `;

    if (config?.limitedBy === 'weight') {
        summary += '<p>⚖️ <strong>Factor limitant:</strong> PES (no dimensions)</p>';
    }

    if (allOrientations.length > 1) {
        summary += `
        <h2>📊 Comparació d'Orientacions</h2>
        <table>
            <thead>
                <tr>
                    <th>Orientació</th>
                    <th>Unitats</th>
                    <th>Distribució</th>
                    <th>Pes (kg)</th>
                    <th>Vol (%)</th>
                    <th>Pes (%)</th>
                </tr>
            </thead>
            <tbody>
        `;
        
        for (const ori of allOrientations) {
            const status = ori.fitsWeight ? '✅' : '❌';
            summary += `
                <tr>
                    <td>${status} ${ori.name}</td>
                    <td>${ori.units}</td>
                    <td>${ori.distribution}</td>
                    <td>${ori.weight.toFixed(1)}</td>
                    <td>${ori.volEfficiency.toFixed(1)}</td>
                    <td>${ori.weightEfficiency.toFixed(1)}</td>
                </tr>
            `;
        }
        
        summary += '</tbody></table>';
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
 * @param {number} params.safetyFactor - Safety factor (0.5-1.0)
 * @returns {Object} {summary: string, data: Object}
 */
export function calcularEmpaquetatge(params) {
    const {
        objL, objW, objH, objWeight,
        boxL, boxW, boxH, maxWeight,
        allowRotation = true,
        safetyFactor = DEFAULT_SAFETY_FACTOR,
        packingGap = 0 // Separació entre peces en mm (0 = sense gap)
    } = params;

    // Validation
    if ([objL, objW, objH, objWeight, boxL, boxW, boxH, maxWeight].some(v => v <= 0)) {
        return {
            summary: '<p>❌ Tots els valors han de ser majors que 0.</p>',
            data: null
        };
    }

    if (objWeight > maxWeight) {
        return {
            summary: '<p>❌ El pes d\'una sola unitat supera la capacitat màxima de la caixa.</p>',
            data: null
        };
    }

    // Object dimensions
    const objDims = [objL, objW, objH];
    const boxDims = [boxL, boxW, boxH];

    // Generate orientations (6 permutations or just 1)
    let orientations, orientationNames;
    
    if (allowRotation) {
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

    for (let i = 0; i < orientations.length; i++) {
        const [ol, ow, oh] = orientations[i];
        
        // Calculate how many fit in each direction (amb gap entre peces)
        const fitL = (ol + packingGap) <= boxDims[0] ? Math.floor(boxDims[0] / (ol + packingGap)) : 0;
        const fitW = (ow + packingGap) <= boxDims[1] ? Math.floor(boxDims[1] / (ow + packingGap)) : 0;
        const fitH = (oh + packingGap) <= boxDims[2] ? Math.floor(boxDims[2] / (oh + packingGap)) : 0;

        const totalUnits = fitL * fitW * fitH;
        const totalWeight = totalUnits * objWeight;

        const volObj = ol * ow * oh;
        const volBox = boxDims[0] * boxDims[1] * boxDims[2];
        const volEfficiency = volBox > 0 ? (totalUnits * volObj / volBox * 100) : 0;
        const weightEfficiency = maxWeight > 0 ? (totalWeight / maxWeight * 100) : 0;

        const orientationData = {
            name: orientationNames[i],
            dimensions: [ol, ow, oh],
            units: totalUnits,
            distribution: `${fitL}×${fitW}×${fitH}`,
            weight: totalWeight,
            volEfficiency,
            weightEfficiency,
            fitsWeight: totalWeight <= maxWeight,
        };
        allOrientations.push(orientationData);

        // If fits both dimensions and weight
        if (totalUnits > 0 && totalWeight <= maxWeight && totalUnits > bestFit) {
            bestFit = totalUnits;
            bestConfig = { ...orientationData };
            continue;
        }

        // If doesn't fit due to weight, try optimization
        if (totalUnits <= 0) continue;

        const maxByWeight = Math.floor(maxWeight / objWeight);
        if (maxByWeight <= bestFit) continue;

        const bestDist = optimizeByWeight(fitL, fitW, fitH, maxByWeight);
        if (!bestDist || bestDist.units <= bestFit) continue;

        bestFit = bestDist.units;
        bestConfig = {
            name: `${orientationNames[i]} (Limitat per pes)`,
            dimensions: [ol, ow, oh],
            units: bestDist.units,
            distribution: `${bestDist.l}×${bestDist.w}×${bestDist.h}`,
            weight: bestDist.units * objWeight,
            volEfficiency: volBox > 0 ? (bestDist.units * volObj / volBox * 100) : 0,
            weightEfficiency: maxWeight > 0 ? (bestDist.units * objWeight / maxWeight * 100) : 0,
            fitsWeight: true,
            limitedBy: 'weight',
        };
    }

    // No solution found
    if (bestFit === 0 || !bestConfig) {
        const debug = createDebugInfo(allOrientations, maxWeight, objWeight);
        return {
            summary: `<p>❌ No cap cap unitat a la caixa.</p>${debug}`,
            data: null
        };
    }

    // Apply safety factor
    const safety = Math.max(0.0, Math.min(1.0, safetyFactor));
    let realFit = Math.max(1, Math.floor(bestFit * safety));
    realFit = Math.min(realFit, bestFit);

    const summary = createSummary(bestFit, realFit, bestConfig, safety, allOrientations);

    return {
        summary,
        data: {
            theoreticalUnits: bestFit,
            realUnits: realFit,
            bestOrientation: bestConfig,
            allOrientations,
            packingGap: packingGap,
        }
    };
}

/**
 * Get distribution array from packing result
 * @param {Object} data - Packing result data
 * @returns {Array} [nx, ny, nz] distribution
 */
export function getDistribution(data) {
    if (!data?.bestOrientation?.distribution) {
        return [0, 0, 0];
    }
    const parts = data.bestOrientation.distribution.split('×');
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
