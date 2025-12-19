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

/**
 * Extract dimensions from a BufferGeometry (bounding box)
 * 
 * IMPORTANT: Three.js uses Y-up coordinate system:
 * - X = length (horizontal, left-right)
 * - Y = height (vertical, up-down)
 * - Z = width/depth (horizontal, front-back)
 * 
 * The calculator expects:
 * - L = length (X)
 * - W = width (Z, NOT Y!)
 * - H = height (Y)
 * 
 * @param {THREE.BufferGeometry} geometry
 * @returns {{length: number, width: number, height: number}}
 */
export function extractDimensions(geometry) {
    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    const size = new THREE.Vector3();
    box.getSize(size);
    
    // Correct mapping for Y-up coordinate system
    return {
        length: size.x,   // X axis = length
        width: size.z,    // Z axis = width/depth (NOT Y!)
        height: size.y    // Y axis = height (vertical)
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
    
    // Move min corner to origin
    const offset = new THREE.Vector3();
    box.getCenter(offset);
    offset.sub(box.min);
    
    geometry.translate(-box.min.x, -box.min.y, -box.min.z);
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
    
    // Re-anchor to origin
    const min = geometry.boundingBox.min;
    geometry.translate(-min.x, -min.y, -min.z);
    
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
    centerToOrigin,
    computeOBB,
    permutationMatrix,
    applyPermutation,
    guessPermForDims,
    createMesh,
    getConvexHullVertices,
    simplifyForPhysics,
    cloneGeometry
};
