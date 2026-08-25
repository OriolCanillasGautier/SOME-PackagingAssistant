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
export function getSupportStability(geometry, epsilon = null) {
    const positions = geometry.getAttribute('position');
    if (!positions || positions.count === 0) {
        return { stable: false, supportArea: 0, basePointCount: 0 };
    }

    geometry.computeBoundingBox();
    const bb = geometry.boundingBox;
    const maxDim = Math.max(bb.max.x - bb.min.x, bb.max.y - bb.min.y, bb.max.z - bb.min.z);
    // The contact band must be TINY: a real rest touches the floor only
    // where the piece is actually at the lowest level. CAD flat faces have
    // exactly coplanar vertices, so 0.3mm catches the whole face; a curved
    // or edge contact only contributes its sliver.
    if (epsilon === null) epsilon = 0.3;

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

    // The CONTACT area is the sum of the projected (onto the floor) areas
    // of the DOWNWARD-facing triangles whose centroid is inside the contact
    // band above the lowest point. A piece resting on a flat face gets the
    // full face area; a piece resting on a curved side (a cone lying on its
    // side) only touches along a line — the band's side facets have
    // near-horizontal normals, so their projected area is ~0. A vertex-band
    // hull cannot tell these apart (the band of a slightly tilted curved
    // side is a wide strip), which is exactly why the lying cone passed.
    let contactArea = 0;
    const bandTop = minY + epsilon;
    const nTris = positions.count / 3;
    const cvA = new THREE.Vector3();
    const cvB = new THREE.Vector3();
    const cvC = new THREE.Vector3();
    const ce1 = new THREE.Vector3();
    const ce2 = new THREE.Vector3();
    const cnrm = new THREE.Vector3();
    for (let t = 0; t < nTris; t++) {
        const ia = t * 3, ib = t * 3 + 1, ic = t * 3 + 2;
        cvA.set(positions.getX(ia), positions.getY(ia), positions.getZ(ia));
        cvB.set(positions.getX(ib), positions.getY(ib), positions.getZ(ib));
        cvC.set(positions.getX(ic), positions.getY(ic), positions.getZ(ic));
        const triMinY = Math.min(cvA.y, cvB.y, cvC.y);
        const triMaxY = Math.max(cvA.y, cvB.y, cvC.y);
        if (triMinY > bandTop) continue;
        // Only the portion of the triangle inside the band touches the
        // floor. Long side triangles of a curved rest span far up: counting
        // their full area would inflate a line contact into a face.
        const ySpan = triMaxY - triMinY;
        const frac = ySpan < 1e-6 ? 1 : Math.min(1, Math.max(0, (bandTop - triMinY) / ySpan));
        ce1.subVectors(cvB, cvA);
        ce2.subVectors(cvC, cvA);
        cnrm.crossVectors(ce1, ce2);
        const area = cnrm.length() * 0.5;
        if (area < 1e-10) continue;
        const ny = cnrm.y / (area * 2);
        if (ny >= -0.05) continue;      // not pointing down (or flat)
        contactArea += area * (-ny) * frac;    // projected on the floor, band-limited
    }

    // A real resting base needs meaningful contact. The contact must be a
    // 2D REGION, not a line or a point: the convex hull of the band
    // vertices of a flat rest spans the full face in both axes; a curved-
    // side rest (a cone lying on its side) produces a long thin strip
    // (min-extent / max-extent → 0). A hollow flat base still passes — the
    // hull of its rim ring is the outer disc.
    const hull = convexHull2D(basePoints);
    const supportArea = contactArea;
    const hullMinX = Math.min(...hull.map(p => p.x));
    const hullMaxX = Math.max(...hull.map(p => p.x));
    const hullMinZ = Math.min(...hull.map(p => p.z));
    const hullMaxZ = Math.max(...hull.map(p => p.z));
    const hx = hullMaxX - hullMinX;
    const hz = hullMaxZ - hullMinZ;
    const shapeRatio = Math.min(hx, hz) / Math.max(1e-6, Math.max(hx, hz));

    // The footprint for the area ratio.
    const extentArea = Math.max(1e-6,
        (bb.max.x - bb.min.x) * (bb.max.z - bb.min.z));
    const minSupport = Math.max(1.0, extentArea * 0.3);

    // Centre of mass from the AREA-WEIGHTED triangle centroids — the vertex
    // average is biased by mesh tessellation (a dense fillet would pull the
    // COM away from the real mass centre).
    const indexed = geometry.index;
    const triCount = indexed ? indexed.count / 3 : positions.count / 3;
    const cvA2 = new THREE.Vector3();
    const cvB2 = new THREE.Vector3();
    const cvC2 = new THREE.Vector3();
    const ce12 = new THREE.Vector3();
    const ce22 = new THREE.Vector3();
    const cr2 = new THREE.Vector3();
    const com = new THREE.Vector3();
    let comArea = 0;
    for (let t = 0; t < triCount; t++) {
        const ia = indexed ? indexed.getX(t * 3) : t * 3;
        const ib = indexed ? indexed.getX(t * 3 + 1) : t * 3 + 1;
        const ic = indexed ? indexed.getX(t * 3 + 2) : t * 3 + 2;
        cvA2.set(positions.getX(ia), positions.getY(ia), positions.getZ(ia));
        cvB2.set(positions.getX(ib), positions.getY(ib), positions.getZ(ib));
        cvC2.set(positions.getX(ic), positions.getY(ic), positions.getZ(ic));
        ce12.subVectors(cvB2, cvA2);
        ce22.subVectors(cvC2, cvA2);
        cr2.crossVectors(ce12, ce22);
        const area = cr2.length() * 0.5;
        if (area < 1e-10) continue;
        com.addScaledVector(
            new THREE.Vector3(
                (cvA2.x + cvB2.x + cvC2.x) / 3,
                (cvA2.y + cvB2.y + cvC2.y) / 3,
                (cvA2.z + cvB2.z + cvC2.z) / 3
            ),
            area
        );
        comArea += area;
    }
    if (comArea > 0) com.divideScalar(comArea);

    const stable = supportArea >= minSupport
        && shapeRatio >= 0.3
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
    const { normalTol = 0.985, planeTolMM = 0.8 } = opts;

    const pos = geometry.getAttribute('position');
    if (!pos || pos.count < 3) return null;

    const indexed = geometry.index;
    const triCount = indexed ? indexed.count / 3 : pos.count / 3;

    // 1. Collect triangle normals + centroids + COM (area-weighted).
    const vA = new THREE.Vector3();
    const vB = new THREE.Vector3();
    const vC = new THREE.Vector3();
    const edge1 = new THREE.Vector3();
    const edge2 = new THREE.Vector3();
    const faceNormal = new THREE.Vector3();

    /** @type {{ normal: THREE.Vector3, centroid: THREE.Vector3, area: number }[]} */
    const faces = [];
    const com = new THREE.Vector3();
    let totalArea = 0;

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

        const centroid = new THREE.Vector3(
            (vA.x + vB.x + vC.x) / 3,
            (vA.y + vB.y + vC.y) / 3,
            (vA.z + vB.z + vC.z) / 3
        );
        faces.push({ normal: faceNormal.clone(), centroid, area });
        com.addScaledVector(centroid, area);
        totalArea += area;
    }
    if (faces.length === 0) return null;
    com.divideScalar(totalArea || 1);

    // 2. Cluster by normal direction AND coplanarity (distance to the
    //    cluster's plane). ORIENTATION-AGNOSTIC: the largest flat region of
    //    the mesh wins whatever direction it faces in the raw STL — e.g.
    //    the base disc of a cone whose axis points sideways. The old
    //    |normal.y| filter + height-bin clustering was frame-biased and
    //    silently missed exactly that case (producing the lying pose as the
    //    "flat base").
    const clusters = [];   // { normal, planePt, area, faces }
    for (const f of faces) {
        let best = -1;
        for (let c = 0; c < clusters.length; c++) {
            const cn = clusters[c].normal;
            if (Math.abs(f.normal.dot(cn)) < normalTol) continue;
            const d = Math.abs(
                (f.centroid.x - clusters[c].planePt.x) * cn.x +
                (f.centroid.y - clusters[c].planePt.y) * cn.y +
                (f.centroid.z - clusters[c].planePt.z) * cn.z);
            if (d > planeTolMM) continue;
            best = c;
            break;
        }
        if (best < 0) {
            clusters.push({
                normal: f.normal.clone(),
                planePt: f.centroid.clone(),
                area: 0,
                faces: [],
            });
            best = clusters.length - 1;
        }
        const c = clusters[best];
        c.faces.push(f);
        c.area += f.area;
        // Weighted refinement of the plane (normal + centroid)
        const w = f.area;
        c.normal.addScaledVector(f.normal, w).normalize();
        c.planePt.x = (c.planePt.x * (c.faces.length - 1) + f.centroid.x) / c.faces.length;
        c.planePt.y = (c.planePt.y * (c.faces.length - 1) + f.centroid.y) / c.faces.length;
        c.planePt.z = (c.planePt.z * (c.faces.length - 1) + f.centroid.z) / c.faces.length;
    }

    // 3. The largest flat region = the resting base candidate.
    clusters.sort((a, b) => b.area - a.area);
    const chosen = clusters[0];
    if (!chosen || chosen.area < 1.0) return null;

    const avgNormal = chosen.normal.clone().normalize();

    // 4. The face's OUTWARD normal: away from the material (the COM is on
    //    the material side, the ground-contact side faces outward).
    const faceDir = avgNormal.clone();
    const outward = new THREE.Vector3(
        chosen.planePt.x - com.x,
        chosen.planePt.y - com.y,
        chosen.planePt.z - com.z);
    if (outward.dot(faceDir) < 0) {
        faceDir.negate();
    }

    // 5. Align the outward normal to -Y (ground).
    const quat = new THREE.Quaternion();
    quat.setFromUnitVectors(faceDir, new THREE.Vector3(0, -1, 0));

    return {
        quaternion: quat,
        normal: avgNormal,
        area: chosen.area,
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
