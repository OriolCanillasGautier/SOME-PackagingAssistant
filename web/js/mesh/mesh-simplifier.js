/**
 * PackAssist Web – Mesh Simplifier
 *
 * Two-tier approach:
 *   1. **Server (PyMeshLab)** — POST raw STL to mesh_server.py.
 *      Uses Quadric-Edge-Collapse with preserveTopology + preserveNormal
 *      → best quality, holes stay intact, flat faces stay flat.
 *   2. **Client fallback (Three.js SimplifyModifier)** — runs entirely
 *      in-browser when the server is unreachable.
 *
 * The public API (`simplify`, `getStats`) is identical regardless of
 * which backend performed the decimation.
 */

import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import { SimplifyModifier } from 'three/addons/modifiers/SimplifyModifier.js';
import * as BufferGeometryUtils from 'three/addons/utils/BufferGeometryUtils.js';

// Where the Python micro-server listens (mesh_server.py).
const MESH_SERVER = 'http://localhost:8787';

export class MeshSimplifier {
    /**
     * @param {THREE.BufferGeometry} geometry
     * @param {ArrayBuffer|null} rawSTLData  Original binary STL data (needed for server path).
     */
    constructor(geometry, rawSTLData = null) {
        this.originalGeometry = geometry.clone();
        this.rawSTLData = rawSTLData;           // kept for sending to server

        if (!this.originalGeometry.getAttribute('normal')) {
            this.originalGeometry.computeVertexNormals();
        }
        this.originalGeometry.computeBoundingBox();
        this.originalGeometry.computeBoundingSphere();

        this.originalVertexCount = this.originalGeometry.getAttribute('position')?.count ?? 0;
        this.originalFaceCount  = this._countFaces(this.originalGeometry);
        this.originalVolume     = this._calculateVolume(this.originalGeometry);

        // Pre-compute welded count for JS fallback ratio mapping.
        const welded = BufferGeometryUtils.mergeVertices(this.originalGeometry.clone());
        this._weldedCount = welded.getAttribute('position')?.count ?? 0;

        this._modifier = new SimplifyModifier();
        this._exporter = new STLExporter();

        // Server availability (lazy-checked).
        this._serverAvailable = null;  // null = unknown, true/false after probe
    }

    /**
     * Export a geometry to binary STL (ArrayBuffer).
     * Used to persist the simplified mesh.
     * @param {THREE.BufferGeometry} geometry
     * @returns {ArrayBuffer}
     */
    toBinarySTL(geometry) {
        const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial());
        const exported = this._exporter.parse(mesh, { binary: true });
        // STLExporter returns ArrayBuffer in binary mode.
        if (exported instanceof ArrayBuffer) return exported;
        // Defensive fallback (should not happen with {binary:true}).
        if (exported?.buffer instanceof ArrayBuffer) return exported.buffer;
        throw new Error('Binary STL export failed');
    }

    // ------------------------------------------------------------------ public

    /**
     * Simplify the mesh to `targetRatio` (0 – 1, fraction to **keep**).
     * Tries the Python server first; falls back to JS SimplifyModifier.
     *
     * @param {number} targetRatio
     * @param {boolean} _preserveFeatures  API compat
     * @returns {Promise<THREE.BufferGeometry>}
     */
    async simplify(targetRatio, _preserveFeatures = true) {
        const ratio = THREE.MathUtils.clamp(Number(targetRatio) || 0, 0, 1);

        if (ratio >= 0.999) {
            return this.originalGeometry.clone();
        }

        // --- Try server (PyMeshLab) first ---
        if (this.rawSTLData && await this._isServerAvailable()) {
            try {
                const result = await this._simplifyViaServer(ratio);
                if (result) {
                    console.log('[MeshSimplifier] Simplified via PyMeshLab server');
                    return result;
                }
            } catch (err) {
                console.warn('[MeshSimplifier] Server simplification failed, using JS fallback:', err.message);
            }
        }

        // --- JS fallback (SimplifyModifier) ---
        return this._simplifyLocal(ratio);
    }

    /**
     * Return statistics for a simplified geometry.
     */
    getStats(simplifiedGeometry) {
        const newVertexCount = simplifiedGeometry.getAttribute('position')?.count ?? 0;
        const newFaceCount   = this._countFaces(simplifiedGeometry);
        const newVolume      = this._calculateVolume(simplifiedGeometry);
        const volumeRatio    = this.originalVolume > 0
            ? (newVolume / this.originalVolume) * 100
            : 100;
        const pct = (part, whole) => (whole > 0 ? (part / whole) * 100 : 100);

        return {
            originalVertices:   this.originalVertexCount,
            originalFaces:      this.originalFaceCount,
            newVertices:        newVertexCount,
            newFaces:           newFaceCount,
            vertexReduction:    (100 - pct(newVertexCount, this.originalVertexCount)).toFixed(1),
            faceReduction:      (100 - pct(newFaceCount, this.originalFaceCount)).toFixed(1),
            volumePreservation: volumeRatio.toFixed(1),
            boundaryEdges:      this._countBoundaryEdges(simplifiedGeometry),
            surfacePreservation: '~'
        };
    }

    // ---------------------------------------------------- server path

    /**
     * Probe the mesh_server.py health endpoint (cached).
     */
    async _isServerAvailable() {
        if (this._serverAvailable !== null) return this._serverAvailable;
        try {
            const resp = await fetch(`${MESH_SERVER}/api/health`, {
                signal: AbortSignal.timeout(1500),
            });
            const json = await resp.json();
            this._serverAvailable = resp.ok && json.pymeshlab === true;
        } catch {
            this._serverAvailable = false;
        }
        return this._serverAvailable;
    }

    /**
     * Send the raw STL to the Python server and parse the result.
     * @returns {Promise<THREE.BufferGeometry|null>}
     */
    async _simplifyViaServer(ratio) {
        const resp = await fetch(`${MESH_SERVER}/api/simplify?ratio=${ratio}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/octet-stream',
                'X-Target-Ratio': String(ratio),
            },
            body: this.rawSTLData,
            signal: AbortSignal.timeout(60_000), // generous for large meshes
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: resp.statusText }));
            throw new Error(err.error || `Server returned ${resp.status}`);
        }

        const resultBuffer = await resp.arrayBuffer();
        const loader = new STLLoader();
        const geometry = loader.parse(resultBuffer);

        if (!geometry.getAttribute('normal')) {
            geometry.computeVertexNormals();
        }
        geometry.computeBoundingBox();
        geometry.computeBoundingSphere();

        return geometry;
    }

    // ---------------------------------------------------- JS fallback

    /**
     * Pure-JS decimation via Three.js SimplifyModifier.
     * No hole-filling — SimplifyModifier output is used as-is.
     */
    _simplifyLocal(ratio) {
        const minKeep   = Math.max(24, Math.floor(this._weldedCount * 0.005));
        const targetKeep = Math.max(minKeep, Math.floor(this._weldedCount * ratio));
        const collapses  = Math.max(0, this._weldedCount - targetKeep);

        if (collapses === 0) {
            return this.originalGeometry.clone();
        }

        let simplified;
        try {
            simplified = this._modifier.modify(this.originalGeometry, collapses);
        } catch (err) {
            console.warn('[MeshSimplifier] SimplifyModifier error, returning original:', err);
            return this.originalGeometry.clone();
        }

        if (!simplified.getAttribute('normal')) {
            simplified.computeVertexNormals();
        }
        simplified.computeBoundingBox();
        simplified.computeBoundingSphere();

        return simplified;
    }

    // --------------------------------------------------------- utilities

    _countBoundaryEdges(geometry) {
        if (!geometry.index) return -1;
        const idx = geometry.index;
        const triCount = Math.floor(idx.count / 3);
        const map = new Map();
        const ek = (a, b) => (a < b ? `${a}_${b}` : `${b}_${a}`);
        for (let f = 0; f < triCount; f++) {
            const base = f * 3;
            const i0 = idx.getX(base), i1 = idx.getX(base + 1), i2 = idx.getX(base + 2);
            for (const [a, b] of [[i0, i1], [i1, i2], [i2, i0]]) {
                const key = ek(a, b);
                map.set(key, (map.get(key) || 0) + 1);
            }
        }
        let boundary = 0;
        for (const cnt of map.values()) if (cnt === 1) boundary++;
        return boundary;
    }

    _countFaces(geometry) {
        const pos = geometry.getAttribute('position');
        if (!pos) return 0;
        if (geometry.index) return Math.floor(geometry.index.count / 3);
        return Math.floor(pos.count / 3);
    }

    _calculateVolume(geometry) {
        const positions = geometry.getAttribute('position');
        if (!positions) return 0;

        let volume = 0;
        const v1 = new THREE.Vector3(), v2 = new THREE.Vector3();
        const v3 = new THREE.Vector3(), cross = new THREE.Vector3();

        if (geometry.index) {
            const indices = geometry.index.array;
            for (let i = 0; i < indices.length; i += 3) {
                v1.set(positions.getX(indices[i]),     positions.getY(indices[i]),     positions.getZ(indices[i]));
                v2.set(positions.getX(indices[i + 1]), positions.getY(indices[i + 1]), positions.getZ(indices[i + 1]));
                v3.set(positions.getX(indices[i + 2]), positions.getY(indices[i + 2]), positions.getZ(indices[i + 2]));
                cross.crossVectors(v2, v3);
                volume += v1.dot(cross) / 6;
            }
        } else {
            for (let i = 0; i < positions.count; i += 3) {
                v1.set(positions.getX(i),     positions.getY(i),     positions.getZ(i));
                v2.set(positions.getX(i + 1), positions.getY(i + 1), positions.getZ(i + 1));
                v3.set(positions.getX(i + 2), positions.getY(i + 2), positions.getZ(i + 2));
                cross.crossVectors(v2, v3);
                volume += v1.dot(cross) / 6;
            }
        }

        return Math.abs(volume);
    }
}

export default MeshSimplifier;
