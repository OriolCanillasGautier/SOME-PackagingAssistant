/**
 * PackAssist Web - Mesh Simplifier (QEM Algorithm)
 * Implementa l'algoritme Quadric Error Metrics per simplificació intel·ligent
 * Manté la forma original mentre redueix vèrtexs
 * Referència: Garland & Heckbert, "Surface Simplification Using Quadric Error Metrics", 1997
 */

import * as THREE from 'three';

/**
 * Vertex amb informació de quadric error
 */
class QEMVertex {
    constructor(x, y, z, index) {
        this.position = new THREE.Vector3(x, y, z);
        this.index = index;
        this.quadric = new Float64Array(10); // Matriu quadric 4x4 simètrica
        this.neighbors = new Set();
        this.faces = new Set();
        this.removed = false;
    }
    
    addQuadric(q) {
        for (let i = 0; i < 10; i++) {
            this.quadric[i] += q[i];
        }
    }
}

/**
 * Aresta candidata per col·lapse
 */
class QEMEdge {
    constructor(v1Index, v2Index) {
        this.v1 = Math.min(v1Index, v2Index);
        this.v2 = Math.max(v1Index, v2Index);
        this.cost = Infinity;
        this.optimalPosition = new THREE.Vector3();
    }
    
    get key() {
        return `${this.v1}_${this.v2}`;
    }
}

/**
 * Simplificador de malla basat en Quadric Error Metrics
 */
export class MeshSimplifier {
    constructor(geometry) {
        this.originalGeometry = geometry.clone();
        this.vertices = [];
        this.faces = [];
        this.edges = new Map();
        this.edgeHeap = [];
        
        this._parseGeometry();
        this._computeInitialQuadrics();
        this._initializeEdges();
        
        this.originalVertexCount = this.vertices.length;
        this.originalFaceCount = this.faces.length;
        this.originalVolume = this._calculateVolume(this.originalGeometry);
        
        console.log(`📊 Malla carregada: ${this.originalVertexCount} vèrtexs, ${this.originalFaceCount} triangles`);
    }
    
    /**
     * Parseja la geometria Three.js a estructures internes
     */
    _parseGeometry() {
        const positions = this.originalGeometry.getAttribute('position');
        const indexed = this.originalGeometry.index !== null;
        
        const vertexMap = new Map();
        const getVertexKey = (x, y, z) => `${x.toFixed(6)}_${y.toFixed(6)}_${z.toFixed(6)}`;
        
        if (indexed) {
            for (let i = 0; i < positions.count; i++) {
                const x = positions.getX(i);
                const y = positions.getY(i);
                const z = positions.getZ(i);
                const key = getVertexKey(x, y, z);
                
                if (!vertexMap.has(key)) {
                    vertexMap.set(key, this.vertices.length);
                    this.vertices.push(new QEMVertex(x, y, z, this.vertices.length));
                }
            }
            
            const indices = this.originalGeometry.index.array;
            for (let i = 0; i < indices.length; i += 3) {
                const keys = [
                    getVertexKey(positions.getX(indices[i]), positions.getY(indices[i]), positions.getZ(indices[i])),
                    getVertexKey(positions.getX(indices[i+1]), positions.getY(indices[i+1]), positions.getZ(indices[i+1])),
                    getVertexKey(positions.getX(indices[i+2]), positions.getY(indices[i+2]), positions.getZ(indices[i+2]))
                ];
                
                const face = keys.map(k => vertexMap.get(k));
                const faceIdx = this.faces.length;
                this.faces.push(face);
                
                for (const vIdx of face) {
                    this.vertices[vIdx].faces.add(faceIdx);
                }
                
                this._addNeighbors(face);
            }
        } else {
            for (let i = 0; i < positions.count; i += 3) {
                const faceVertices = [];
                
                for (let j = 0; j < 3; j++) {
                    const x = positions.getX(i + j);
                    const y = positions.getY(i + j);
                    const z = positions.getZ(i + j);
                    const key = getVertexKey(x, y, z);
                    
                    let vIdx;
                    if (vertexMap.has(key)) {
                        vIdx = vertexMap.get(key);
                    } else {
                        vIdx = this.vertices.length;
                        vertexMap.set(key, vIdx);
                        this.vertices.push(new QEMVertex(x, y, z, vIdx));
                    }
                    faceVertices.push(vIdx);
                }
                
                const faceIdx = this.faces.length;
                this.faces.push(faceVertices);
                
                for (const vIdx of faceVertices) {
                    this.vertices[vIdx].faces.add(faceIdx);
                }
                
                this._addNeighbors(faceVertices);
            }
        }
    }
    
    _addNeighbors(face) {
        for (let i = 0; i < 3; i++) {
            const v1 = face[i];
            const v2 = face[(i + 1) % 3];
            this.vertices[v1].neighbors.add(v2);
            this.vertices[v2].neighbors.add(v1);
        }
    }
    
    /**
     * Calcula les matrius quadric inicials
     */
    _computeInitialQuadrics() {
        for (const face of this.faces) {
            const v0 = this.vertices[face[0]].position;
            const v1 = this.vertices[face[1]].position;
            const v2 = this.vertices[face[2]].position;
            
            const edge1 = new THREE.Vector3().subVectors(v1, v0);
            const edge2 = new THREE.Vector3().subVectors(v2, v0);
            const normal = new THREE.Vector3().crossVectors(edge1, edge2);
            
            const area = normal.length() * 0.5;
            if (area < 1e-10) continue;
            
            normal.normalize();
            
            const a = normal.x;
            const b = normal.y;
            const c = normal.z;
            const d = -normal.dot(v0);
            
            // Ponderar per àrea del triangle
            const weight = area;
            const quadric = new Float64Array([
                a*a*weight, a*b*weight, a*c*weight, a*d*weight,
                b*b*weight, b*c*weight, b*d*weight,
                c*c*weight, c*d*weight,
                d*d*weight
            ]);
            
            for (const vIdx of face) {
                this.vertices[vIdx].addQuadric(quadric);
            }
        }
    }
    
    /**
     * Inicialitza totes les arestes
     */
    _initializeEdges() {
        for (const face of this.faces) {
            for (let i = 0; i < 3; i++) {
                const v1 = face[i];
                const v2 = face[(i + 1) % 3];
                const edge = new QEMEdge(v1, v2);
                
                if (!this.edges.has(edge.key)) {
                    this._computeEdgeCost(edge);
                    this.edges.set(edge.key, edge);
                }
            }
        }
        
        this._rebuildHeap();
    }
    
    /**
     * Calcula el cost de col·lapsar una aresta
     */
    _computeEdgeCost(edge) {
        const v1 = this.vertices[edge.v1];
        const v2 = this.vertices[edge.v2];
        
        if (v1.removed || v2.removed) {
            edge.cost = Infinity;
            return;
        }
        
        // Sumar quadrics
        const Q = new Float64Array(10);
        for (let i = 0; i < 10; i++) {
            Q[i] = v1.quadric[i] + v2.quadric[i];
        }
        
        // Provar posicions candidates
        const candidates = [
            v1.position.clone(),
            v2.position.clone(),
            v1.position.clone().add(v2.position).multiplyScalar(0.5),
            // Punts intermedis
            v1.position.clone().lerp(v2.position, 0.25),
            v1.position.clone().lerp(v2.position, 0.75)
        ];
        
        let minCost = Infinity;
        let bestPos = candidates[2];
        
        for (const pos of candidates) {
            const cost = this._evaluateQuadricError(Q, pos);
            if (cost < minCost) {
                minCost = cost;
                bestPos = pos;
            }
        }
        
        edge.cost = minCost;
        edge.optimalPosition.copy(bestPos);
    }
    
    /**
     * Avalua l'error quadric: v^T * Q * v
     */
    _evaluateQuadricError(Q, pos) {
        const x = pos.x, y = pos.y, z = pos.z;
        
        return Q[0]*x*x + 2*Q[1]*x*y + 2*Q[2]*x*z + 2*Q[3]*x +
               Q[4]*y*y + 2*Q[5]*y*z + 2*Q[6]*y +
               Q[7]*z*z + 2*Q[8]*z +
               Q[9];
    }
    
    _rebuildHeap() {
        this.edgeHeap = Array.from(this.edges.values())
            .filter(e => e.cost < Infinity && e.cost >= 0)
            .sort((a, b) => a.cost - b.cost);
    }
    
    /**
     * Col·lapsa una aresta
     */
    _collapseEdge(edge) {
        const v1 = this.vertices[edge.v1];
        const v2 = this.vertices[edge.v2];
        
        if (v1.removed || v2.removed) return false;
        
        // Moure v1 a la posició òptima
        v1.position.copy(edge.optimalPosition);
        
        // Acumular quadric
        for (let i = 0; i < 10; i++) {
            v1.quadric[i] += v2.quadric[i];
        }
        
        // Transferir veïns
        for (const neighbor of v2.neighbors) {
            if (neighbor !== edge.v1 && !this.vertices[neighbor].removed) {
                v1.neighbors.add(neighbor);
                this.vertices[neighbor].neighbors.delete(edge.v2);
                this.vertices[neighbor].neighbors.add(edge.v1);
            }
        }
        
        // Actualitzar cares
        const facesToRemove = new Set();
        
        for (const faceIdx of v2.faces) {
            const face = this.faces[faceIdx];
            if (!face) continue;
            
            const v2Idx = face.indexOf(edge.v2);
            if (v2Idx !== -1) {
                face[v2Idx] = edge.v1;
            }
            
            // Verificar triangle degenerat
            const unique = new Set(face);
            if (unique.size < 3) {
                facesToRemove.add(faceIdx);
            } else {
                v1.faces.add(faceIdx);
            }
        }
        
        for (const faceIdx of facesToRemove) {
            const face = this.faces[faceIdx];
            if (face) {
                for (const vIdx of face) {
                    if (this.vertices[vIdx]) {
                        this.vertices[vIdx].faces.delete(faceIdx);
                    }
                }
            }
            this.faces[faceIdx] = null;
        }
        
        // Eliminar v2
        v2.removed = true;
        v2.neighbors.clear();
        v2.faces.clear();
        v1.neighbors.delete(edge.v2);
        
        // Actualitzar arestes
        const edgesToRemove = [];
        const edgesToUpdate = [];
        
        for (const [key, e] of this.edges) {
            if (e.v1 === edge.v2 || e.v2 === edge.v2) {
                edgesToRemove.push(key);
            } else if (e.v1 === edge.v1 || e.v2 === edge.v1) {
                edgesToUpdate.push(e);
            }
        }
        
        for (const key of edgesToRemove) {
            this.edges.delete(key);
        }
        
        for (const e of edgesToUpdate) {
            this._computeEdgeCost(e);
        }
        
        // Crear noves arestes
        for (const neighbor of v1.neighbors) {
            if (this.vertices[neighbor].removed) continue;
            const newEdge = new QEMEdge(edge.v1, neighbor);
            if (!this.edges.has(newEdge.key)) {
                this._computeEdgeCost(newEdge);
                this.edges.set(newEdge.key, newEdge);
            }
        }
        
        return true;
    }
    
    /**
     * Verifica que el col·lapse no inverteix normals
     */
    _isValidCollapse(edge) {
        const v1 = this.vertices[edge.v1];
        const v2 = this.vertices[edge.v2];
        const newPos = edge.optimalPosition;
        
        const affectedFaces = new Set([...v1.faces, ...v2.faces]);
        
        for (const faceIdx of affectedFaces) {
            const face = this.faces[faceIdx];
            if (!face) continue;
            
            // Normal actual
            const positions = face.map(vIdx => this.vertices[vIdx].position);
            const oldNormal = new THREE.Vector3()
                .crossVectors(
                    new THREE.Vector3().subVectors(positions[1], positions[0]),
                    new THREE.Vector3().subVectors(positions[2], positions[0])
                );
            
            if (oldNormal.lengthSq() < 1e-10) continue;
            
            // Nova normal
            const newPositions = face.map(vIdx => {
                if (vIdx === edge.v1 || vIdx === edge.v2) return newPos;
                return this.vertices[vIdx].position;
            });
            
            // Verificar triangle degenerat
            if (newPositions[0].distanceTo(newPositions[1]) < 1e-6 ||
                newPositions[1].distanceTo(newPositions[2]) < 1e-6 ||
                newPositions[0].distanceTo(newPositions[2]) < 1e-6) {
                continue;
            }
            
            const newNormal = new THREE.Vector3()
                .crossVectors(
                    new THREE.Vector3().subVectors(newPositions[1], newPositions[0]),
                    new THREE.Vector3().subVectors(newPositions[2], newPositions[0])
                );
            
            if (newNormal.lengthSq() < 1e-10) continue;
            
            // Normal invertida?
            if (oldNormal.dot(newNormal) < 0) {
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * Simplifica a un ratio (0.0 - 1.0)
     */
    simplify(targetRatio, preserveFeatures = true) {
        const activeVertices = this.vertices.filter(v => !v.removed).length;
        const targetCount = Math.max(12, Math.floor(activeVertices * targetRatio));
        return this.simplifyToVertexCount(targetCount, preserveFeatures);
    }
    
    /**
     * Simplifica a un nombre específic de vèrtexs
     */
    simplifyToVertexCount(targetVertices, preserveFeatures = true) {
        console.log(`🔄 Simplificant a ${targetVertices} vèrtexs...`);
        const startTime = performance.now();
        
        // Reset
        this._resetState();
        
        targetVertices = Math.max(12, targetVertices);
        
        let currentVertexCount = this.vertices.filter(v => !v.removed).length;
        
        if (targetVertices >= currentVertexCount) {
            return this._buildOutputGeometry();
        }
        
        let iterations = 0;
        const maxIterations = currentVertexCount * 3;
        let lastRebuild = 0;
        
        while (currentVertexCount > targetVertices && iterations < maxIterations) {
            iterations++;
            
            // Rebuild heap periòdicament
            if (iterations - lastRebuild > 50) {
                this._rebuildHeap();
                lastRebuild = iterations;
            }
            
            let collapsed = false;
            
            while (this.edgeHeap.length > 0 && !collapsed) {
                const edge = this.edgeHeap.shift();
                
                if (!this.edges.has(edge.key)) continue;
                if (edge.cost === Infinity || edge.cost < 0) continue;
                
                const v1 = this.vertices[edge.v1];
                const v2 = this.vertices[edge.v2];
                
                if (v1.removed || v2.removed) {
                    this.edges.delete(edge.key);
                    continue;
                }
                
                // Verificar validesa
                if (preserveFeatures && !this._isValidCollapse(edge)) {
                    edge.cost = Infinity;
                    continue;
                }
                
                // Col·lapsar
                if (this._collapseEdge(edge)) {
                    this.edges.delete(edge.key);
                    currentVertexCount--;
                    collapsed = true;
                }
            }
            
            if (!collapsed) {
                this._rebuildHeap();
                if (this.edgeHeap.length === 0) break;
            }
        }
        
        const elapsed = performance.now() - startTime;
        const finalCount = this.vertices.filter(v => !v.removed).length;
        console.log(`✅ Simplificació completada en ${elapsed.toFixed(0)}ms (${finalCount} vèrtexs)`);
        
        return this._buildOutputGeometry();
    }
    
    _resetState() {
        this.vertices = [];
        this.faces = [];
        this.edges.clear();
        this.edgeHeap = [];
        
        this._parseGeometry();
        this._computeInitialQuadrics();
        this._initializeEdges();
    }
    
    _buildOutputGeometry() {
        const activeVertices = this.vertices.filter(v => !v.removed);
        const activeFaces = this.faces.filter(f => f !== null);
        
        const indexMap = new Map();
        activeVertices.forEach((v, newIdx) => {
            indexMap.set(v.index, newIdx);
        });
        
        const positions = [];
        for (const v of activeVertices) {
            positions.push(v.position.x, v.position.y, v.position.z);
        }
        
        const indices = [];
        for (const face of activeFaces) {
            const newIndices = face.map(vIdx => indexMap.get(vIdx));
            if (newIndices.every(i => i !== undefined)) {
                indices.push(...newIndices);
            }
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        
        if (indices.length > 0) {
            geometry.setIndex(indices);
        }
        
        geometry.computeVertexNormals();
        
        return geometry;
    }
    
    /**
     * Retorna estadístiques
     */
    getStats(simplifiedGeometry) {
        const positions = simplifiedGeometry.getAttribute('position');
        const newVertexCount = positions.count;
        const newFaceCount = simplifiedGeometry.index 
            ? simplifiedGeometry.index.count / 3 
            : positions.count / 3;
        
        const newVolume = this._calculateVolume(simplifiedGeometry);
        const volumeRatio = this.originalVolume > 0 
            ? (newVolume / this.originalVolume * 100) 
            : 100;
        
        return {
            originalVertices: this.originalVertexCount,
            originalFaces: this.originalFaceCount,
            newVertices: newVertexCount,
            newFaces: Math.floor(newFaceCount),
            vertexReduction: ((this.originalVertexCount - newVertexCount) / this.originalVertexCount * 100).toFixed(1),
            faceReduction: ((this.originalFaceCount - newFaceCount) / this.originalFaceCount * 100).toFixed(1),
            volumePreservation: volumeRatio.toFixed(1),
            surfacePreservation: '~'
        };
    }
    
    _calculateVolume(geometry) {
        const positions = geometry.getAttribute('position');
        let volume = 0;
        
        if (geometry.index) {
            const indices = geometry.index.array;
            for (let i = 0; i < indices.length; i += 3) {
                const v1 = new THREE.Vector3(
                    positions.getX(indices[i]),
                    positions.getY(indices[i]),
                    positions.getZ(indices[i])
                );
                const v2 = new THREE.Vector3(
                    positions.getX(indices[i+1]),
                    positions.getY(indices[i+1]),
                    positions.getZ(indices[i+1])
                );
                const v3 = new THREE.Vector3(
                    positions.getX(indices[i+2]),
                    positions.getY(indices[i+2]),
                    positions.getZ(indices[i+2])
                );
                volume += v1.dot(new THREE.Vector3().crossVectors(v2, v3)) / 6;
            }
        } else {
            for (let i = 0; i < positions.count; i += 3) {
                const v1 = new THREE.Vector3(positions.getX(i), positions.getY(i), positions.getZ(i));
                const v2 = new THREE.Vector3(positions.getX(i+1), positions.getY(i+1), positions.getZ(i+1));
                const v3 = new THREE.Vector3(positions.getX(i+2), positions.getY(i+2), positions.getZ(i+2));
                volume += v1.dot(new THREE.Vector3().crossVectors(v2, v3)) / 6;
            }
        }
        
        return Math.abs(volume);
    }
}

export default MeshSimplifier;
