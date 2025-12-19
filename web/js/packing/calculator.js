/**
 * PackAssist Web - Packing Calculator
 * Port of packing_core.py to JavaScript
 * Improved with density factor, better 3D bin packing, and physics-based optimization
 */

export const DEFAULT_SAFETY_FACTOR = 1.0;
export const DEFAULT_DENSITY_FACTOR = 1.0; // 1.0 = tight, 1.2 = loose

/**
 * Orientation definitions with rotation info
 */
export const ORIENTATIONS = [
    { name: 'Original (L×W×H)', permutation: [0, 1, 2], rotation: { x: 0, y: 0, z: 0 } },
    { name: 'Rotació Y (L×H×W)', permutation: [0, 2, 1], rotation: { x: Math.PI / 2, y: 0, z: 0 } },
    { name: 'Rotació Z (W×L×H)', permutation: [1, 0, 2], rotation: { x: 0, y: Math.PI / 2, z: 0 } },
    { name: 'Rotació XY (W×H×L)', permutation: [1, 2, 0], rotation: { x: Math.PI / 2, y: Math.PI / 2, z: 0 } },
    { name: 'Rotació XZ (H×L×W)', permutation: [2, 0, 1], rotation: { x: 0, y: 0, z: Math.PI / 2 } },
    { name: 'Rotació YZ (H×W×L)', permutation: [2, 1, 0], rotation: { x: 0, y: 0, z: -Math.PI / 2 } },
];

/**
 * Get oriented dimensions from original dims and orientation index
 */
export function getOrientedDimensions(originalDims, orientationIndex) {
    const perm = ORIENTATIONS[orientationIndex].permutation;
    return [originalDims[perm[0]], originalDims[perm[1]], originalDims[perm[2]]];
}

/**
 * Optimized 3D bin packing using guillotine algorithm
 * @param {number} boxL - Box length
 * @param {number} boxW - Box width
 * @param {number} boxH - Box height
 * @param {number} pieceL - Piece length
 * @param {number} pieceW - Piece width
 * @param {number} pieceH - Piece height
 * @param {number} densityFactor - 1.0 = tight, >1.0 = looser
 * @returns {Object} Best packing {nx, ny, nz, units}
 */
export function optimizePacking3D(boxL, boxW, boxH, pieceL, pieceW, pieceH, densityFactor = 1.0) {
    // Aplicar factor de densitat (afegir espai entre peces)
    const adjustedL = pieceL * densityFactor;
    const adjustedW = pieceW * densityFactor;
    const adjustedH = pieceH * densityFactor;
    
    // Provar totes les permutacions de orientació
    const orientations = [
        { dims: [pieceL, pieceW, pieceH], name: 'Original' },
        { dims: [pieceL, pieceH, pieceW], name: 'Rot-Y' },
        { dims: [pieceW, pieceL, pieceH], name: 'Rot-Z' },
        { dims: [pieceW, pieceH, pieceL], name: 'Rot-XY' },
        { dims: [pieceH, pieceL, pieceW], name: 'Rot-XZ' },
        { dims: [pieceH, pieceW, pieceL], name: 'Rot-YZ' }
    ];
    
    let bestConfig = null;
    let bestUnits = 0;
    
    for (const orientation of orientations) {
        const [l, w, h] = orientation.dims;
        
        // Calcular fit amb factor de densitat
        const fitX = l > 0 ? Math.floor(boxL / (l * densityFactor)) : 0;
        const fitY = w > 0 ? Math.floor(boxW / (w * densityFactor)) : 0;
        const fitZ = h > 0 ? Math.floor(boxH / (h * densityFactor)) : 0;
        
        const units = fitX * fitY * fitZ;
        
        // Preferir distribucions més equilibrades (squarer)
        const variance = Math.pow(fitX - fitY, 2) + Math.pow(fitY - fitZ, 2);
        const score = units - (variance * 0.001);
        
        if (units > bestUnits || (units === bestUnits && score > (bestConfig?.score || 0))) {
            bestUnits = units;
            bestConfig = {
                nx: fitX,
                ny: fitY,
                nz: fitZ,
                units,
                score,
                dims: [l, w, h],
                name: orientation.name
            };
        }
    }
    
    return bestConfig || { nx: 0, ny: 0, nz: 0, units: 0 };
}

/**
 * Optimize distribution by weight when geometry exceeds capacity
 * @param {number} maxL - Max in L direction
 * @param {number} maxW - Max in W direction  
 * @param {number} maxH - Max in H direction
 * @param {number} targetUnits - Max units by weight
 * @returns {Object} Optimized {l, w, h, units}
 */
function optimizeByWeight(maxL, maxW, maxH, targetUnits) {
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
 * @param {number} params.densityFactor - Density factor (1.0=tight, 1.2=loose)
 * @returns {Object} {summary: string, data: Object}
 */
export function calcularEmpaquetatge(params) {
    const {
        objL, objW, objH, objWeight,
        boxL, boxW, boxH, maxWeight,
        allowRotation = true,
        safetyFactor = DEFAULT_SAFETY_FACTOR,
        densityFactor = DEFAULT_DENSITY_FACTOR
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
        
        // Calculate how many fit in each direction, applying density factor
        const fitL = ol > 0 ? Math.floor(boxDims[0] / (ol * densityFactor)) : 0;
        const fitW = ow > 0 ? Math.floor(boxDims[1] / (ow * densityFactor)) : 0;
        const fitH = oh > 0 ? Math.floor(boxDims[2] / (oh * densityFactor)) : 0;

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

/**
 * ADVANCED PACKING with stability-filtered orientations
 * Calculates optimal packing using only stable orientations
 * and supports multiple orientations within each layer for better space usage
 */
export function calcularEmpaquetamentAvancat(params) {
    const {
        objL, objW, objH, objWeight,
        boxL, boxW, boxH, maxWeight,
        stableOrientations = [], // Array of stable orientation indices
        safetyFactor = DEFAULT_SAFETY_FACTOR,
        densityFactor = DEFAULT_DENSITY_FACTOR
    } = params;

    // Validation
    if ([objL, objW, objH, objWeight, boxL, boxW, boxH, maxWeight].some(v => v <= 0)) {
        return {
            summary: '<p>❌ Tots els valors han de ser majors que 0.</p>',
            data: null
        };
    }

    const objDims = [objL, objW, objH];
    const boxDims = [boxL, boxW, boxH];

    // Filter orientations to only stable ones (or use all if no stability test done)
    const orientationsToUse = stableOrientations.length > 0
        ? ORIENTATIONS.filter((_, i) => stableOrientations.includes(i))
        : ORIENTATIONS;

    const maxUnits = Math.floor(maxWeight / objWeight);
    
    // Try different strategies and pick the best
    const strategies = [
        packWithSingleOrientation(objDims, boxDims, orientationsToUse, densityFactor, maxUnits),
        packWithMixedOrientationsPerLayer(objDims, boxDims, orientationsToUse, densityFactor, maxUnits),
        packWithInterleavedOrientations(objDims, boxDims, orientationsToUse, densityFactor, maxUnits)
    ];
    
    // Pick the best strategy (most units)
    let best = strategies[0];
    for (const s of strategies) {
        if (s.totalUnits > best.totalUnits) {
            best = s;
        }
    }

    const { layerPlan, fillerPieces, totalUnits: theoreticalUnits } = best;

    // Apply safety factor
    const safety = Math.max(0.0, Math.min(1.0, safetyFactor));
    const realUnits = Math.max(1, Math.floor(theoreticalUnits * safety));

    // Generate summary
    const summaryHtml = createAdvancedSummary(theoreticalUnits, realUnits, layerPlan, fillerPieces, safety);

    return {
        summary: summaryHtml,
        data: {
            theoreticalUnits,
            realUnits,
            layerPlan,
            fillerPieces,
            stableOrientationsUsed: orientationsToUse.map(o => o.name),
            isMultiOrientation: new Set(layerPlan.map(l => l.orientation.name)).size > 1 || fillerPieces.length > 0
        }
    };
}

/**
 * Strategy 1: Single best orientation (original greedy approach)
 */
function packWithSingleOrientation(objDims, boxDims, orientations, densityFactor, maxUnits) {
    let totalUnits = 0;
    const layerPlan = [];
    let currentHeight = 0;

    while (currentHeight < boxDims[2] && totalUnits < maxUnits) {
        let bestLayerConfig = null;
        let bestLayerUnits = 0;

        for (const ori of orientations) {
            const [ol, ow, oh] = getOrientedDimensions(objDims, ORIENTATIONS.indexOf(ori));
            if (currentHeight + oh > boxDims[2]) continue;
            
            const fitX = Math.floor(boxDims[0] / (ol * densityFactor));
            const fitY = Math.floor(boxDims[1] / (ow * densityFactor));
            const layerUnits = fitX * fitY;
            const allowedUnits = Math.min(layerUnits, maxUnits - totalUnits);
            
            if (allowedUnits > bestLayerUnits) {
                bestLayerUnits = allowedUnits;
                bestLayerConfig = {
                    orientation: ori,
                    dims: [ol, ow, oh],
                    nx: fitX,
                    ny: fitY,
                    units: allowedUnits,
                    startHeight: currentHeight,
                    endHeight: currentHeight + oh,
                    placements: generateGridPlacements(fitX, fitY, [ol, ow, oh], currentHeight, densityFactor, ori)
                };
            }
        }

        if (!bestLayerConfig || bestLayerUnits === 0) break;

        layerPlan.push(bestLayerConfig);
        totalUnits += bestLayerUnits;
        currentHeight = bestLayerConfig.endHeight;
    }

    return { layerPlan, fillerPieces: [], totalUnits };
}

/**
 * Strategy 2: Mix orientations within each layer to fill gaps
 */
function packWithMixedOrientationsPerLayer(objDims, boxDims, orientations, densityFactor, maxUnits) {
    let totalUnits = 0;
    const layerPlan = [];
    let currentHeight = 0;

    while (currentHeight < boxDims[2] && totalUnits < maxUnits) {
        // Find all orientations that fit at this height
        const fittingOrientations = [];
        for (const ori of orientations) {
            const [ol, ow, oh] = getOrientedDimensions(objDims, ORIENTATIONS.indexOf(ori));
            if (currentHeight + oh <= boxDims[2]) {
                fittingOrientations.push({ ori, dims: [ol, ow, oh] });
            }
        }

        if (fittingOrientations.length === 0) break;

        // Sort by height to group similar heights
        fittingOrientations.sort((a, b) => a.dims[2] - b.dims[2]);

        // Use the primary orientation for the main grid
        const primary = fittingOrientations[0];
        const [pl, pw, ph] = primary.dims;
        const fitX = Math.floor(boxDims[0] / (pl * densityFactor));
        const fitY = Math.floor(boxDims[1] / (pw * densityFactor));
        const mainUnits = Math.min(fitX * fitY, maxUnits - totalUnits);

        if (mainUnits === 0) break;

        // Calculate remaining space in X direction
        const usedX = fitX * pl * densityFactor;
        const remainingX = boxDims[0] - usedX;
        
        // Calculate remaining space in Y direction
        const usedY = fitY * pw * densityFactor;
        const remainingY = boxDims[1] - usedY;

        // Generate placements for main grid
        const placements = generateGridPlacements(fitX, fitY, primary.dims, currentHeight, densityFactor, primary.ori);

        // Try to fill gap in X direction with a different orientation
        let gapUnitsX = 0;
        for (const alt of fittingOrientations) {
            if (alt.dims[2] !== ph) continue; // Must have same height
            const [al, aw] = alt.dims;
            if (al * densityFactor <= remainingX) {
                const gapFitX = Math.floor(remainingX / (al * densityFactor));
                const gapFitY = fitY;
                gapUnitsX = Math.min(gapFitX * gapFitY, maxUnits - totalUnits - mainUnits);
                
                if (gapUnitsX > 0) {
                    // Add gap placements
                    for (let ix = 0; ix < gapFitX && placements.length < mainUnits + gapUnitsX; ix++) {
                        for (let iy = 0; iy < gapFitY; iy++) {
                            placements.push({
                                x: usedX + ix * al * densityFactor + al / 2,
                                y: currentHeight,
                                z: iy * aw * densityFactor + aw / 2,
                                orientation: alt.ori,
                                dims: alt.dims
                            });
                        }
                    }
                    break;
                }
            }
        }

        layerPlan.push({
            orientation: primary.ori,
            dims: primary.dims,
            nx: fitX,
            ny: fitY,
            units: mainUnits + gapUnitsX,
            startHeight: currentHeight,
            endHeight: currentHeight + ph,
            placements
        });

        totalUnits += mainUnits + gapUnitsX;
        currentHeight += ph;
    }

    return { layerPlan, fillerPieces: [], totalUnits };
}

/**
 * Strategy 3: Interleaved orientations (alternating patterns)
 * Good for pieces where L and W are similar but H is different
 */
function packWithInterleavedOrientations(objDims, boxDims, orientations, densityFactor, maxUnits) {
    let totalUnits = 0;
    const layerPlan = [];
    let currentHeight = 0;

    // Find pairs of complementary orientations (same footprint dimensions, different arrangement)
    const pairs = [];
    for (let i = 0; i < orientations.length; i++) {
        const dims1 = getOrientedDimensions(objDims, ORIENTATIONS.indexOf(orientations[i]));
        for (let j = i + 1; j < orientations.length; j++) {
            const dims2 = getOrientedDimensions(objDims, ORIENTATIONS.indexOf(orientations[j]));
            // Same height and complementary footprints
            if (dims1[2] === dims2[2]) {
                // Check if they can interleave
                const combined1 = dims1[0] + dims2[0];
                const combined2 = dims1[1] + dims2[1];
                
                if (combined1 <= boxDims[0] * 2 || combined2 <= boxDims[1] * 2) {
                    pairs.push({
                        ori1: orientations[i], dims1,
                        ori2: orientations[j], dims2,
                        height: dims1[2]
                    });
                }
            }
        }
    }

    // If no good pairs, fall back to single orientation
    if (pairs.length === 0) {
        return packWithSingleOrientation(objDims, boxDims, orientations, densityFactor, maxUnits);
    }

    // Try each pair and see which fits best
    for (const pair of pairs) {
        const testResult = tryInterleavedPair(pair, boxDims, densityFactor, maxUnits);
        if (testResult.totalUnits > totalUnits) {
            totalUnits = testResult.totalUnits;
            layerPlan.length = 0;
            layerPlan.push(...testResult.layers);
        }
    }

    if (layerPlan.length === 0) {
        return packWithSingleOrientation(objDims, boxDims, orientations, densityFactor, maxUnits);
    }

    return { layerPlan, fillerPieces: [], totalUnits };
}

function tryInterleavedPair(pair, boxDims, densityFactor, maxUnits) {
    const { ori1, dims1, ori2, dims2, height } = pair;
    const layers = [];
    let total = 0;
    let currentHeight = 0;

    while (currentHeight + height <= boxDims[2] && total < maxUnits) {
        // Try alternating rows with different orientations
        const placements = [];
        let rowY = 0;
        let useFirst = true;

        while (rowY + (useFirst ? dims1[1] : dims2[1]) <= boxDims[1]) {
            const dims = useFirst ? dims1 : dims2;
            const ori = useFirst ? ori1 : ori2;
            const [l, w] = dims;
            
            const fitX = Math.floor(boxDims[0] / (l * densityFactor));
            
            for (let ix = 0; ix < fitX && total + placements.length < maxUnits; ix++) {
                placements.push({
                    x: ix * l * densityFactor + l / 2,
                    y: currentHeight,
                    z: rowY + w / 2,
                    orientation: ori,
                    dims: dims
                });
            }

            rowY += w * densityFactor;
            useFirst = !useFirst;
        }

        if (placements.length === 0) break;

        layers.push({
            orientation: ori1,
            dims: dims1,
            nx: Math.floor(boxDims[0] / (dims1[0] * densityFactor)),
            ny: Math.floor(boxDims[1] / (dims1[1] * densityFactor)),
            units: placements.length,
            startHeight: currentHeight,
            endHeight: currentHeight + height,
            placements,
            isInterleaved: true
        });

        total += placements.length;
        currentHeight += height;
    }

    return { layers, totalUnits: total };
}

/**
 * Generate grid placements for a layer
 */
function generateGridPlacements(nx, ny, dims, startHeight, densityFactor, orientation) {
    const placements = [];
    const [l, w, h] = dims;
    
    for (let ix = 0; ix < nx; ix++) {
        for (let iy = 0; iy < ny; iy++) {
            placements.push({
                x: ix * l * densityFactor + l / 2,
                y: startHeight,
                z: iy * w * densityFactor + w / 2,
                orientation,
                dims
            });
        }
    }
    
    return placements;
}

/**
 * Find empty spaces in the layer plan that could fit additional pieces
 */
function findEmptySpacesInPlan(layerPlan, boxDims, objDims, orientations, densityFactor) {
    const emptySpaces = [];
    
    for (const layer of layerPlan) {
        const { nx, ny, dims, startHeight } = layer;
        const usedWidth = nx * dims[0] * densityFactor;
        const usedDepth = ny * dims[1] * densityFactor;
        
        // Space at the end of X direction
        if (usedWidth < boxDims[0]) {
            emptySpaces.push({
                x: usedWidth,
                y: startHeight,
                z: 0,
                width: boxDims[0] - usedWidth,
                height: dims[2],
                depth: boxDims[1]
            });
        }
        
        // Space at the end of Z direction
        if (usedDepth < boxDims[1]) {
            emptySpaces.push({
                x: 0,
                y: startHeight,
                z: usedDepth,
                width: usedWidth,
                height: dims[2],
                depth: boxDims[1] - usedDepth
            });
        }
    }
    
    // Sort by volume (largest first)
    emptySpaces.sort((a, b) => 
        (b.width * b.height * b.depth) - (a.width * a.height * a.depth)
    );
    
    return emptySpaces;
}

/**
 * Generate summary for advanced packing
 */
function createAdvancedSummary(theoretical, real, layerPlan, fillerPieces, safety) {
    const safetyPercent = Math.round(safety * 100);
    const totalLayers = layerPlan.length;
    const orientationsUsed = [...new Set(layerPlan.map(l => l.orientation.name))];
    
    let summary = `
    <h1>📦 RESULTATS (Mode Avançat)</h1>
    
    <h2>🎯 Resultat Principal</h2>
    <ul>
        <li><strong>Unitats totals:</strong> ${theoretical} (${real} amb ${safetyPercent}% seguretat)</li>
        <li><strong>Capes:</strong> ${totalLayers}</li>
        <li><strong>Orientacions usades:</strong> ${orientationsUsed.join(', ')}</li>
        ${fillerPieces.length > 0 ? `<li><strong>Peces omplidores:</strong> ${fillerPieces.length}</li>` : ''}
    </ul>
    
    <h2>📊 Detall per Capa</h2>
    <table>
        <thead>
            <tr><th>Capa</th><th>Orientació</th><th>Distribució</th><th>Unitats</th><th>Alçada</th></tr>
        </thead>
        <tbody>
    `;
    
    for (let i = 0; i < layerPlan.length; i++) {
        const layer = layerPlan[i];
        summary += `
            <tr>
                <td>${i + 1}</td>
                <td>${layer.orientation.name}</td>
                <td>${layer.nx}×${layer.ny}</td>
                <td>${layer.units}</td>
                <td>${layer.startHeight.toFixed(1)} - ${layer.endHeight.toFixed(1)} mm</td>
            </tr>
        `;
    }
    
    summary += '</tbody></table>';
    
    if (fillerPieces.length > 0) {
        summary += `
        <h2>🧩 Peces Omplidores</h2>
        <p>${fillerPieces.length} peces addicionals col·locades en espais buits amb orientacions variades.</p>
        `;
    }
    
    return summary;
}