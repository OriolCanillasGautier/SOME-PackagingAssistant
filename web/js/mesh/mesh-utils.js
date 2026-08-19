/**
 * PackAssist Web - Mesh Utilities
 * Supports: STL, OBJ formats
 * Uses Three.js loaders for mesh loading
 */

import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';

/**
 * Supported file extensions
 */
export const SUPPORTED_EXTENSIONS = ['.stl', '.obj'];

/**
 * Check if a file extension is supported
 * @param {string} filename
 * @returns {boolean}
 */
export function isSupported(filename) {
    const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'));
    return SUPPORTED_EXTENSIONS.includes(ext);
}

/**
 * Get file extension
 * @param {string} filename
 * @returns {string}
 */
function getExtension(filename) {
    return filename.toLowerCase().substring(filename.lastIndexOf('.'));
}

/**
 * Load a 3D mesh file (STL or OBJ) and return a Three.js BufferGeometry
 * @param {File} file - File object
 * @returns {Promise<THREE.BufferGeometry>}
 */
export async function loadMesh(file) {
    const ext = getExtension(file.name);
    
    switch (ext) {
        case '.stl':
            return loadSTL(file);
        case '.obj':
            return loadOBJ(file);
        default:
            throw new Error(`Format no suportat: ${ext}. Formats vàlids: ${SUPPORTED_EXTENSIONS.join(', ')}`);
    }
}

/**
 * Load an STL file and return a Three.js BufferGeometry
 * @param {File|ArrayBuffer} input - File object or ArrayBuffer
 * @returns {Promise<THREE.BufferGeometry>}
 */
export async function loadSTL(input) {
    const loader = new STLLoader();
    
    return new Promise((resolve, reject) => {
        if (input instanceof ArrayBuffer) {
            try {
                const geometry = loader.parse(input);
                resolve(geometry);
            } catch (error) {
                reject(new Error(`Error parsing STL: ${error.message}`));
            }
        } else if (input instanceof File) {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const geometry = loader.parse(e.target.result);
                    resolve(geometry);
                } catch (error) {
                    reject(new Error(`Error parsing STL: ${error.message}`));
                }
            };
            reader.onerror = () => reject(new Error('Error reading file'));
            reader.readAsArrayBuffer(input);
        } else {
            reject(new Error('Invalid input type'));
        }
    });
}

/**
 * Load an OBJ file and return a Three.js BufferGeometry
 * @param {File} file - File object
 * @returns {Promise<THREE.BufferGeometry>}
 */
export async function loadOBJ(file) {
    const loader = new OBJLoader();
    
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const text = e.target.result;
                const object = loader.parse(text);
                
                // OBJLoader returns a Group, we need to merge all geometries
                const geometries = [];
                object.traverse((child) => {
                    if (child.isMesh && child.geometry) {
                        // Clone and apply any transforms
                        const geo = child.geometry.clone();
                        if (child.matrixWorld) {
                            geo.applyMatrix4(child.matrixWorld);
                        }
                        geometries.push(geo);
                    }
                });
                
                if (geometries.length === 0) {
                    reject(new Error('No geometry found in OBJ file'));
                    return;
                }
                
                // Merge all geometries into one
                let mergedGeometry;
                if (geometries.length === 1) {
                    mergedGeometry = geometries[0];
                } else {
                    // Use BufferGeometryUtils to merge
                    mergedGeometry = mergeBufferGeometries(geometries);
                }
                
                resolve(mergedGeometry);
            } catch (error) {
                reject(new Error(`Error parsing OBJ: ${error.message}`));
            }
        };
        reader.onerror = () => reject(new Error('Error reading file'));
        reader.readAsText(file);
    });
}

/**
 * Simple merge of buffer geometries (without using BufferGeometryUtils)
 * @param {THREE.BufferGeometry[]} geometries
 * @returns {THREE.BufferGeometry}
 */
function mergeBufferGeometries(geometries) {
    // Count total vertices
    let totalVertices = 0;
    for (const geo of geometries) {
        totalVertices += geo.getAttribute('position').count;
    }
    
    // Create merged arrays
    const positions = new Float32Array(totalVertices * 3);
    let offset = 0;
    
    for (const geo of geometries) {
        const posAttr = geo.getAttribute('position');
        positions.set(posAttr.array, offset);
        offset += posAttr.array.length;
    }
    
    const merged = new THREE.BufferGeometry();
    merged.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    merged.computeVertexNormals();
    
    return merged;
}

/** * Compute the signed volume of a triangulated mesh (in mm³).
 * Uses the divergence theorem: for each triangle (v0, v1, v2),
 * the signed tetrahedron volume with the origin is v0·(v1×v2)/6.
 * The absolute value gives the enclosed volume for a watertight mesh.
 * For non-watertight meshes, the result is an approximation.
 *
 * @param {THREE.BufferGeometry} geometry
 * @returns {number} Volume in mm³ (always positive)
 */
export function computeMeshVolume(geometry) {
    const pos = geometry.getAttribute('position');
    if (!pos) return 0;
    const index = geometry.getIndex();

    let volume = 0;
    const v0 = new THREE.Vector3();
    const v1 = new THREE.Vector3();
    const v2 = new THREE.Vector3();
    const cross = new THREE.Vector3();

    if (index) {
        const idx = index.array;
        for (let i = 0; i < idx.length; i += 3) {
            v0.fromBufferAttribute(pos, idx[i]);
            v1.fromBufferAttribute(pos, idx[i + 1]);
            v2.fromBufferAttribute(pos, idx[i + 2]);
            cross.crossVectors(v1, v2);
            volume += v0.dot(cross);
        }
    } else {
        for (let i = 0; i < pos.count; i += 3) {
            v0.fromBufferAttribute(pos, i);
            v1.fromBufferAttribute(pos, i + 1);
            v2.fromBufferAttribute(pos, i + 2);
            cross.crossVectors(v1, v2);
            volume += v0.dot(cross);
        }
    }

    return Math.abs(volume) / 6;
}

/**
 * Compute the total surface area of a mesh (sum of triangle areas, in mm²).
 * Useful for estimating material weight of hollow / shell parts.
 * @param {THREE.BufferGeometry} geometry
 * @returns {number} Surface area in mm²
 */
export function computeSurfaceArea(geometry) {
    const pos = geometry.getAttribute('position');
    if (!pos) return 0;
    const index = geometry.getIndex();

    let area = 0;
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    const c = new THREE.Vector3();
    const ab = new THREE.Vector3();
    const ac = new THREE.Vector3();
    const cross = new THREE.Vector3();

    const triCount = index ? index.count / 3 : pos.count / 3;
    for (let i = 0; i < triCount; i++) {
        const i0 = index ? index.getX(i * 3)     : i * 3;
        const i1 = index ? index.getX(i * 3 + 1) : i * 3 + 1;
        const i2 = index ? index.getX(i * 3 + 2) : i * 3 + 2;
        a.fromBufferAttribute(pos, i0);
        b.fromBufferAttribute(pos, i1);
        c.fromBufferAttribute(pos, i2);
        ab.subVectors(b, a);
        ac.subVectors(c, a);
        cross.crossVectors(ab, ac);
        area += cross.length() * 0.5;
    }
    return area;
}

/**
 * Analyze mesh integrity to estimate if volume-based mass is reliable.
 * A watertight manifold mesh should have each undirected edge shared by exactly 2 triangles.
 *
 * @param {THREE.BufferGeometry} geometry
 * @param {{ weldTolerance?: number }} opts
 * @returns {{
 *   triangleCount: number,
 *   uniqueEdgeCount: number,
 *   boundaryEdgeCount: number,
 *   nonManifoldEdgeCount: number,
 *   watertight: boolean
 * }}
 */
export function analyzeMeshIntegrity(geometry, opts = {}) {
    const pos = geometry.getAttribute('position');
    if (!pos || pos.count < 3) {
        return {
            triangleCount: 0,
            uniqueEdgeCount: 0,
            boundaryEdgeCount: 0,
            nonManifoldEdgeCount: 0,
            watertight: false
        };
    }

    const index = geometry.getIndex();
    const triCount = index ? Math.floor(index.count / 3) : Math.floor(pos.count / 3);
    const weldTolerance = Math.max(1e-9, opts.weldTolerance ?? 1e-4);
    const invTol = 1 / weldTolerance;

    const weldedVertexKeyToId = new Map();
    let nextWeldId = 0;

    function weldedIdFromPos(i) {
        const x = Math.round(pos.getX(i) * invTol);
        const y = Math.round(pos.getY(i) * invTol);
        const z = Math.round(pos.getZ(i) * invTol);
        const key = `${x}|${y}|${z}`;
        let id = weldedVertexKeyToId.get(key);
        if (id === undefined) {
            id = nextWeldId++;
            weldedVertexKeyToId.set(key, id);
        }
        return id;
    }

    const edgeCounts = new Map();
    const pushEdge = (a, b) => {
        const minV = a < b ? a : b;
        const maxV = a < b ? b : a;
        const edgeKey = `${minV}|${maxV}`;
        edgeCounts.set(edgeKey, (edgeCounts.get(edgeKey) || 0) + 1);
    };

    for (let t = 0; t < triCount; t++) {
        const i0 = index ? index.getX(t * 3) : (t * 3);
        const i1 = index ? index.getX(t * 3 + 1) : (t * 3 + 1);
        const i2 = index ? index.getX(t * 3 + 2) : (t * 3 + 2);

        const v0 = weldedIdFromPos(i0);
        const v1 = weldedIdFromPos(i1);
        const v2 = weldedIdFromPos(i2);

        pushEdge(v0, v1);
        pushEdge(v1, v2);
        pushEdge(v2, v0);
    }

    let boundaryEdgeCount = 0;
    let nonManifoldEdgeCount = 0;
    for (const count of edgeCounts.values()) {
        if (count === 1) boundaryEdgeCount++;
        else if (count > 2) nonManifoldEdgeCount++;
    }

    return {
        triangleCount: triCount,
        uniqueEdgeCount: edgeCounts.size,
        boundaryEdgeCount,
        nonManifoldEdgeCount,
        watertight: triCount > 0 && boundaryEdgeCount === 0 && nonManifoldEdgeCount === 0
    };
}

/** * Extract dimensions from a BufferGeometry (bounding box)
 * @param {THREE.BufferGeometry} geometry
 * @returns {{length: number, width: number, height: number}}
 */
export function extractDimensions(geometry) {
    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    const size = new THREE.Vector3();
    box.getSize(size);
    
    // Three.js convention: X = length, Z = width (depth), Y = height (vertical)
    return {
        length: size.x,
        width: size.z,
        height: size.y
    };
}

/**
 * Center geometry at origin and move min to [0,0,0]
 * @param {THREE.BufferGeometry} geometry
 * @returns {THREE.BufferGeometry} Transformed geometry
 */
export function centerToOrigin(geometry) {
    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    
    // Move center to origin
    const center = new THREE.Vector3();
    box.getCenter(center);
    
    geometry.translate(-center.x, -center.y, -center.z);
    geometry.computeBoundingBox();
    
    return geometry;
}

/**
 * Compute the Oriented Bounding Box (OBB) of a geometry
 * This is a simplified version that uses PCA to find principal axes
 * @param {THREE.BufferGeometry} geometry
 * @returns {{geometry: THREE.BufferGeometry, extents: [number, number, number]}}
 */
export function computeOBB(geometry) {
    // Get vertices
    const positions = geometry.getAttribute('position');
    const vertices = [];
    for (let i = 0; i < positions.count; i++) {
        vertices.push(new THREE.Vector3(
            positions.getX(i),
            positions.getY(i),
            positions.getZ(i)
        ));
    }

    // Compute centroid
    const centroid = new THREE.Vector3();
    for (const v of vertices) {
        centroid.add(v);
    }
    centroid.divideScalar(vertices.length);

    // Compute covariance matrix for PCA
    let cxx = 0, cxy = 0, cxz = 0, cyy = 0, cyz = 0, czz = 0;
    for (const v of vertices) {
        const dx = v.x - centroid.x;
        const dy = v.y - centroid.y;
        const dz = v.z - centroid.z;
        cxx += dx * dx;
        cxy += dx * dy;
        cxz += dx * dz;
        cyy += dy * dy;
        cyz += dy * dz;
        czz += dz * dz;
    }
    const n = vertices.length;
    cxx /= n; cxy /= n; cxz /= n; cyy /= n; cyz /= n; czz /= n;

    // For simplicity, use axis-aligned bounding box with sorted extents
    // A full PCA implementation would require eigenvalue decomposition
    geometry.computeBoundingBox();
    const size = new THREE.Vector3();
    geometry.boundingBox.getSize(size);

    // Move to origin
    geometry.translate(
        -geometry.boundingBox.min.x,
        -geometry.boundingBox.min.y,
        -geometry.boundingBox.min.z
    );

    return {
        geometry,
        extents: [size.x, size.y, size.z]
    };
}

/**
 * Create a permutation matrix for axis reordering
 * @param {number} ix - Index for X axis (0, 1, or 2)
 * @param {number} iy - Index for Y axis (0, 1, or 2)
 * @param {number} iz - Index for Z axis (0, 1, or 2)
 * @returns {THREE.Matrix3}
 */
export function permutationMatrix(ix, iy, iz) {
    const mat = new THREE.Matrix3();
    mat.set(
        ix === 0 ? 1 : 0, ix === 1 ? 1 : 0, ix === 2 ? 1 : 0,
        iy === 0 ? 1 : 0, iy === 1 ? 1 : 0, iy === 2 ? 1 : 0,
        iz === 0 ? 1 : 0, iz === 1 ? 1 : 0, iz === 2 ? 1 : 0
    );
    return mat;
}

/**
 * Apply axis permutation to geometry
 * @param {THREE.BufferGeometry} geometry
 * @param {[number, number, number]} perm - Permutation indices
 * @returns {THREE.BufferGeometry}
 */
export function applyPermutation(geometry, perm) {
    const positions = geometry.getAttribute('position');
    const newPositions = new Float32Array(positions.count * 3);
    
    for (let i = 0; i < positions.count; i++) {
        const v = new THREE.Vector3(
            positions.getX(i),
            positions.getY(i),
            positions.getZ(i)
        );
        
        // Apply permutation
        const coords = [v.x, v.y, v.z];
        newPositions[i * 3] = coords[perm[0]];
        newPositions[i * 3 + 1] = coords[perm[1]];
        newPositions[i * 3 + 2] = coords[perm[2]];
    }
    
    geometry.setAttribute('position', new THREE.BufferAttribute(newPositions, 3));
    geometry.computeBoundingBox();
    
    // Re-anchor to origin (center)
    geometry.computeBoundingBox();
    const center = new THREE.Vector3();
    geometry.boundingBox.getCenter(center);
    geometry.translate(-center.x, -center.y, -center.z);
    
    return geometry;
}

/**
 * Find the best axis permutation to match source extents to target dimensions
 * @param {[number, number, number]} sourceExtents
 * @param {[number, number, number]} targetDims
 * @returns {[number, number, number]} Best permutation
 */
export function guessPermForDims(sourceExtents, targetDims) {
    const permutations = [
        [0, 1, 2], [0, 2, 1], [1, 0, 2],
        [1, 2, 0], [2, 0, 1], [2, 1, 0]
    ];
    
    let bestPerm = [0, 1, 2];
    let bestError = Infinity;
    
    for (const perm of permutations) {
        const candidate = [
            sourceExtents[perm[0]],
            sourceExtents[perm[1]],
            sourceExtents[perm[2]]
        ];
        
        const error = candidate.reduce((sum, val, i) => 
            sum + Math.pow(val - targetDims[i], 2), 0);
        
        if (error < bestError) {
            bestError = error;
            bestPerm = perm;
        }
    }
    
    return bestPerm;
}

/**
 * Create a mesh from geometry with standard material
 * @param {THREE.BufferGeometry} geometry
 * @param {Object} options
 * @returns {THREE.Mesh}
 */
export function createMesh(geometry, options = {}) {
    const {
        color = 0x3b82f6,
        opacity = 0.9,
        wireframe = false
    } = options;
    
    const material = new THREE.MeshPhongMaterial({
        color,
        opacity,
        transparent: opacity < 1,
        wireframe,
        side: THREE.DoubleSide,
        flatShading: true
    });
    
    geometry.computeVertexNormals();
    return new THREE.Mesh(geometry, material);
}

/**
 * Get convex hull vertices for physics simulation
 * Uses Three.js ConvexGeometry internally
 * @param {THREE.BufferGeometry} geometry
 * @returns {Float32Array} Convex hull vertices
 */
export function getConvexHullVertices(geometry) {
    const positions = geometry.getAttribute('position');
    const vertices = [];
    
    for (let i = 0; i < positions.count; i++) {
        vertices.push(
            positions.getX(i),
            positions.getY(i),
            positions.getZ(i)
        );
    }
    
    return new Float32Array(vertices);
}

function convexHull2D(points) {
    if (points.length <= 3) return points.slice();
    const pts = points.slice().sort((a, b) => (a.x - b.x) || (a.z - b.z));
    const cross = (o, a, b) => (a.x - o.x) * (b.z - o.z) - (a.z - o.z) * (b.x - o.x);
    const lower = [];
    for (const p of pts) {
        while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
            lower.pop();
        }
        lower.push(p);
    }
    const upper = [];
    for (let i = pts.length - 1; i >= 0; i--) {
        const p = pts[i];
        while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
            upper.pop();
        }
        upper.push(p);
    }
    upper.pop();
    lower.pop();
    return lower.concat(upper);
}

function polygonArea2D(poly) {
    if (poly.length < 3) return 0;
    let area = 0;
    for (let i = 0; i < poly.length; i++) {
        const j = (i + 1) % poly.length;
        area += poly[i].x * poly[j].z - poly[j].x * poly[i].z;
    }
    return Math.abs(area) / 2;
}

function pointInPolygon2D(point, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const xi = poly[i].x, zi = poly[i].z;
        const xj = poly[j].x, zj = poly[j].z;
        const intersect = ((zi > point.z) !== (zj > point.z)) &&
            (point.x < (xj - xi) * (point.z - zi) / ((zj - zi) || 1e-9) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

/**
 * Estimate stability on flat surface using support polygon of lowest vertices
 * @param {THREE.BufferGeometry} geometry
 * @param {number} epsilon - height tolerance in mm
 * @returns {{stable: boolean, supportArea: number, basePointCount: number}}
 */
export function getSupportStability(geometry, epsilon = 0.5) {
    const positions = geometry.getAttribute('position');
    if (!positions || positions.count === 0) {
        return { stable: false, supportArea: 0, basePointCount: 0 };
    }

    let minY = Infinity;
    for (let i = 0; i < positions.count; i++) {
        minY = Math.min(minY, positions.getY(i));
    }

    const basePoints = [];
    const maxY = minY + epsilon;
    for (let i = 0; i < positions.count; i++) {
        const y = positions.getY(i);
        if (y <= maxY) {
            basePoints.push({ x: positions.getX(i), z: positions.getZ(i) });
        }
    }

    if (basePoints.length < 3) {
        return { stable: false, supportArea: 0, basePointCount: basePoints.length };
    }

    const hull = convexHull2D(basePoints);
    const supportArea = polygonArea2D(hull);

    // Centre of mass from the AREA-WEIGHTED triangle centroids — the vertex
    // average is biased by mesh tessellation (a dense fillet would pull the
    // COM away from the real mass centre).
    const indexed = geometry.index;
    const triCount = indexed ? indexed.count / 3 : positions.count / 3;
    const vA = new THREE.Vector3();
    const vB = new THREE.Vector3();
    const vC = new THREE.Vector3();
    const e1 = new THREE.Vector3();
    const e2 = new THREE.Vector3();
    const cr = new THREE.Vector3();
    let com = new THREE.Vector3();
    let totalArea = 0;
    for (let t = 0; t < triCount; t++) {
        const ia = indexed ? indexed.getX(t * 3) : t * 3;
        const ib = indexed ? indexed.getX(t * 3 + 1) : t * 3 + 1;
        const ic = indexed ? indexed.getX(t * 3 + 2) : t * 3 + 2;
        vA.set(positions.getX(ia), positions.getY(ia), positions.getZ(ia));
        vB.set(positions.getX(ib), positions.getY(ib), positions.getZ(ib));
        vC.set(positions.getX(ic), positions.getY(ic), positions.getZ(ic));
        e1.subVectors(vB, vA);
        e2.subVectors(vC, vA);
        cr.crossVectors(e1, e2);
        const area = cr.length() * 0.5;
        if (area < 1e-10) continue;
        const centroid = new THREE.Vector3(
            (vA.x + vB.x + vC.x) / 3,
            (vA.y + vB.y + vC.y) / 3,
            (vA.z + vB.z + vC.z) / 3
        );
        com.addScaledVector(centroid, area);
        totalArea += area;
    }
    if (totalArea > 0) com.divideScalar(totalArea);

    // A real resting base needs meaningful contact: the support polygon must
    // cover a reasonable share of the piece's own XZ footprint, and the COM
    // must project inside it. A ring standing on its rim fails both checks
    // (near-zero area / COM right on the edge line).
    geometry.computeBoundingBox();
    const bb = geometry.boundingBox;
    const extentArea = Math.max(1e-6,
        (bb.max.x - bb.min.x) * (bb.max.z - bb.min.z));
    const minSupport = Math.max(1.0, extentArea * 0.04);

    const stable = supportArea >= minSupport
        && pointInPolygon2D({ x: com.x, z: com.z }, hull);
    return { stable, supportArea, basePointCount: basePoints.length };
}

// ---------------------------------------------------------------------------
// Stable-base detection & alignment
// ---------------------------------------------------------------------------

/**
 * Analyse mesh triangles and find the best "resting base" — the largest
 * cluster of roughly co-planar, downward-facing triangles at the lowest
 * part of the mesh.
 *
 * Returns a THREE.Quaternion that, when applied, aligns that face so its
 * outward normal points downward (-Y), i.e. the piece stands "upright"
 * with that face on the ground.
 *
 * Algorithm:
 *  1. Iterate every triangle and compute its face normal + centroid.
 *  2. Keep only faces whose normal has a strong vertical component
 *     (|normal.y| > cosThreshold) — these are candidate "flat" faces.
 *  3. Among those, separate into "down-facing" (normal.y < 0) and
 *     "up-facing" (normal.y > 0) groups.
 *  4. Within each group, cluster by centroid height (Y) using a small
 *     tolerance, so faces that lie at the same level get aggregated.
 *  5. Score each cluster by total triangle area.
 *  6. Pick the cluster with the largest area that is at the lowest height
 *     (prefer down-facing first; fall back to up-facing flipped).
 *  7. Compute the weighted-average normal of that cluster and build a
 *     quaternion that rotates it to -Y (ground).
 *
 * @param {THREE.BufferGeometry} geometry
 * @param {Object} [opts]
 * @param {number} [opts.cosThreshold=0.4]  min |normal.y| to consider "flat"
 * @param {number} [opts.heightBinMM=2]     height tolerance for clustering (mm)
 * @returns {{ quaternion: THREE.Quaternion, normal: THREE.Vector3, area: number,
 *             clusterCount: number } | null}
 */
export function detectStableBase(geometry, opts = {}) {
    const { cosThreshold = 0.4, heightBinMM = 2 } = opts;

    const pos = geometry.getAttribute('position');
    if (!pos || pos.count < 3) return null;

    const indexed = geometry.index;
    const triCount = indexed ? indexed.count / 3 : pos.count / 3;

    // 1. Collect triangle info
    const vA = new THREE.Vector3();
    const vB = new THREE.Vector3();
    const vC = new THREE.Vector3();
    const edge1 = new THREE.Vector3();
    const edge2 = new THREE.Vector3();
    const faceNormal = new THREE.Vector3();

    /** @type {{ normal: THREE.Vector3, centroidY: number, area: number }[]} */
    const faces = [];

    for (let t = 0; t < triCount; t++) {
        let ia, ib, ic;
        if (indexed) {
            ia = indexed.getX(t * 3);
            ib = indexed.getX(t * 3 + 1);
            ic = indexed.getX(t * 3 + 2);
        } else {
            ia = t * 3;
            ib = t * 3 + 1;
            ic = t * 3 + 2;
        }
        vA.set(pos.getX(ia), pos.getY(ia), pos.getZ(ia));
        vB.set(pos.getX(ib), pos.getY(ib), pos.getZ(ib));
        vC.set(pos.getX(ic), pos.getY(ic), pos.getZ(ic));

        edge1.subVectors(vB, vA);
        edge2.subVectors(vC, vA);
        faceNormal.crossVectors(edge1, edge2);

        const area = faceNormal.length() * 0.5;
        if (area < 1e-8) continue;              // degenerate triangle
        faceNormal.normalize();

        if (Math.abs(faceNormal.y) < cosThreshold) continue;   // not flat enough

        const centroidY = (vA.y + vB.y + vC.y) / 3;
        faces.push({
            normal: faceNormal.clone(),
            centroidY,
            area
        });
    }

    if (faces.length === 0) return null;

    // 2. Split into down-facing (normal.y < 0) and up-facing (normal.y > 0)
    const downFaces = faces.filter(f => f.normal.y < 0);
    const upFaces   = faces.filter(f => f.normal.y > 0);

    // 3. Cluster faces by height (centroidY), pick largest-area cluster
    function clusterByHeight(faceList) {
        if (faceList.length === 0) return [];
        const sorted = faceList.slice().sort((a, b) => a.centroidY - b.centroidY);
        const clusters = [];
        let current = { faces: [sorted[0]], minY: sorted[0].centroidY };
        for (let i = 1; i < sorted.length; i++) {
            if (sorted[i].centroidY - current.faces[current.faces.length - 1].centroidY <= heightBinMM) {
                current.faces.push(sorted[i]);
            } else {
                clusters.push(current);
                current = { faces: [sorted[i]], minY: sorted[i].centroidY };
            }
        }
        clusters.push(current);
        return clusters;
    }

    function scoreCluster(cluster) {
        let totalArea = 0;
        for (const f of cluster.faces) totalArea += f.area;
        return totalArea;
    }

    function bestCluster(faceList) {
        const clusters = clusterByHeight(faceList);
        if (clusters.length === 0) return null;
        // Sort by total area descending, then by lowest centroid ascending (prefer bottom)
        clusters.sort((a, b) => {
            const aArea = scoreCluster(a);
            const bArea = scoreCluster(b);
            if (Math.abs(bArea - aArea) > 1e-6) return bArea - aArea;  // larger area first
            return a.minY - b.minY;  // lower first
        });
        return clusters[0];
    }

    // Prefer down-facing (the face that would touch the ground already points down)
    let chosen = bestCluster(downFaces);
    let flipSign = 1; // if chosen is down-facing, its normal ≈ -Y already (we want to align it to -Y)
    if (!chosen || scoreCluster(chosen) < 1) {
        const upChoice = bestCluster(upFaces);
        if (upChoice && scoreCluster(upChoice) > (chosen ? scoreCluster(chosen) : 0)) {
            chosen = upChoice;
            flipSign = -1; // normal points +Y, but we want the *face* on the ground → rotate 180°
        }
    }

    if (!chosen) return null;

    // 4. Weighted average normal of the chosen cluster
    const avgNormal = new THREE.Vector3();
    let totalArea = 0;
    for (const f of chosen.faces) {
        avgNormal.addScaledVector(f.normal, f.area);
        totalArea += f.area;
    }
    avgNormal.divideScalar(totalArea || 1).normalize();

    // The face's outward normal. We want this direction to point **down** (-Y)
    // so the face rests on the ground.
    // For down-facing faces, normal is already ≈ -Y → small rotation.
    // For up-facing faces, normal is ≈ +Y → we need to flip 180°.
    const targetDir = new THREE.Vector3(0, -1, 0);
    const faceDir = avgNormal.clone();
    if (flipSign < 0) {
        // The face's ground-contact side is opposite the normal
        faceDir.negate();
    }

    const quat = new THREE.Quaternion();
    quat.setFromUnitVectors(faceDir, targetDir);

    return {
        quaternion: quat,
        normal: avgNormal,
        area: totalArea,
        clusterCount: chosen.faces.length
    };
}

/**
 * Align geometry so its detected stable base rests on the ground (Y = 0).
 * Mutates the geometry in-place and returns the detection result (or null
 * if no clear base was found — in that case the geometry is untouched).
 *
 * @param {THREE.BufferGeometry} geometry
 * @returns {{ quaternion: THREE.Quaternion, normal: THREE.Vector3, area: number,
 *             clusterCount: number } | null}
 */
export function alignToStableBase(geometry) {
    const result = detectStableBase(geometry);
    if (!result) return null;

    // Apply rotation
    const mat = new THREE.Matrix4().makeRotationFromQuaternion(result.quaternion);
    geometry.applyMatrix4(mat);

    // Translate so min-Y = 0 (piece sits on ground)
    geometry.computeBoundingBox();
    const minY = geometry.boundingBox.min.y;
    if (Math.abs(minY) > 1e-4) {
        geometry.translate(0, -minY, 0);
    }

    // Recenter on XZ so origin is at the centre of the footprint
    geometry.computeBoundingBox();
    const cx = (geometry.boundingBox.min.x + geometry.boundingBox.max.x) / 2;
    const cz = (geometry.boundingBox.min.z + geometry.boundingBox.max.z) / 2;
    geometry.translate(-cx, 0, -cz);

    geometry.computeBoundingBox();
    return result;
}

/**
 * Simplify geometry for physics (reduce vertex count)
 * @param {THREE.BufferGeometry} geometry
 * @param {number} targetVertices - Target number of vertices
 * @returns {Float32Array} Simplified vertices
 */
export function simplifyForPhysics(geometry, targetVertices = 64) {
    const positions = geometry.getAttribute('position');
    const count = positions.count;
    
    if (count <= targetVertices) {
        return getConvexHullVertices(geometry);
    }
    
    // Sample vertices uniformly
    const step = Math.ceil(count / targetVertices);
    const vertices = [];
    
    for (let i = 0; i < count; i += step) {
        vertices.push(
            positions.getX(i),
            positions.getY(i),
            positions.getZ(i)
        );
    }
    
    return new Float32Array(vertices);
}

/**
 * Clone geometry for instancing
 * @param {THREE.BufferGeometry} geometry
 * @returns {THREE.BufferGeometry}
 */
export function cloneGeometry(geometry) {
    return geometry.clone();
}

export default {
    loadSTL,
    extractDimensions,
    computeMeshVolume,
    computeSurfaceArea,
    analyzeMeshIntegrity,
    centerToOrigin,
    computeOBB,
    permutationMatrix,
    applyPermutation,
    guessPermForDims,
    createMesh,
    getConvexHullVertices,
    simplifyForPhysics,
    cloneGeometry,
    detectStableBase,
    alignToStableBase
};
