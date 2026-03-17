/**
 * PackAssist Web - 3D Scene Manager
 * Handles Three.js scene setup, rendering, and camera controls
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import {
    acceleratedRaycast,
    computeBoundsTree,
    disposeBoundsTree
} from 'https://unpkg.com/three-mesh-bvh@0.7.8/build/index.module.js';

// Enable BVH acceleration utilities (safe no-ops if already applied)
if (!THREE.BufferGeometry.prototype.computeBoundsTree) {
    THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
}
if (!THREE.BufferGeometry.prototype.disposeBoundsTree) {
    THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
}
if (THREE.Mesh.prototype.raycast !== acceleratedRaycast) {
    THREE.Mesh.prototype.raycast = acceleratedRaycast;
}

// ─── Packing score function (lower = better placement) ───
function _packingScore(baseH, gx, gz, od, heightMap, gridNX, gridNZ, placed, boxH) {
    const { pieceNX, pieceNZ } = od;

    // Primary: strongly prefer lower base height
    let score = baseH * 1000;

    // Wall contact
    if (gx === 0) score -= 20;
    if (gz === 0) score -= 20;
    if (gx + pieceNX >= gridNX) score -= 20;
    if (gz + pieceNZ >= gridNZ) score -= 20;

    // Adjacency: prefer positions next to already-placed pieces
    let adj = 0;
    if (gx > 0) {
        for (let pz = 0; pz < pieceNZ; pz++)
            if (heightMap[(gz + pz) * gridNX + (gx - 1)] > 0) adj++;
    }
    if (gx + pieceNX < gridNX) {
        for (let pz = 0; pz < pieceNZ; pz++)
            if (heightMap[(gz + pz) * gridNX + (gx + pieceNX)] > 0) adj++;
    }
    if (gz > 0) {
        for (let px = 0; px < pieceNX; px++)
            if (heightMap[(gz - 1) * gridNX + (gx + px)] > 0) adj++;
    }
    if (gz + pieceNZ < gridNZ) {
        for (let px = 0; px < pieceNX; px++)
            if (heightMap[(gz + pieceNZ) * gridNX + (gx + px)] > 0) adj++;
    }
    score -= adj * 3;

    // Fill from edges inward
    const edgeDistX = Math.min(gx, Math.max(0, gridNX - gx - pieceNX));
    const edgeDistZ = Math.min(gz, Math.max(0, gridNZ - gz - pieceNZ));
    score += (edgeDistX + edgeDistZ) * 0.01;

    return score;
}

function _gridSpacingCollides(od, dx, dz) {
    if (!od?.geometry?.boundsTree) return false;
    const matrix = new THREE.Matrix4().makeTranslation(dx, 0, dz);
    return od.geometry.boundsTree.intersectsGeometry(od.geometry, matrix);
}

function _findBestGridLayoutForOrientation(od, boxL, boxW, packingGap) {
    const factors = [1.0, 0.98, 0.96, 0.94, 0.92, 0.9, 0.88];
    let best = null;

    for (const fx of factors) {
        for (const fz of factors) {
            const stepX = Math.max(od.sizeX + packingGap * 0.35, (od.sizeX + packingGap) * fx);
            const stepZ = Math.max(od.sizeZ + packingGap * 0.35, (od.sizeZ + packingGap) * fz);

            // Validate neighbor placements for a repeated grid.
            if (_gridSpacingCollides(od, stepX, 0)) continue;
            if (_gridSpacingCollides(od, 0, stepZ)) continue;
            if (_gridSpacingCollides(od, stepX, stepZ)) continue;

            const nx = Math.max(1, Math.floor((boxL - od.sizeX + 0.01) / stepX) + 1);
            const nz = Math.max(1, Math.floor((boxW - od.sizeZ + 0.01) / stepZ) + 1);
            const count = nx * nz;
            const usedL = od.sizeX + Math.max(0, nx - 1) * stepX;
            const usedW = od.sizeZ + Math.max(0, nz - 1) * stepZ;
            const leftoverL = Math.max(0, boxL - usedL);
            const leftoverW = Math.max(0, boxW - usedW);
            const leftoverArea = leftoverL * boxW + leftoverW * boxL - leftoverL * leftoverW;

            if (!best || count > best.count || (count === best.count && leftoverArea < best.leftoverArea)) {
                best = { stepX, stepZ, nx, nz, count, leftoverArea, fx, fz };
            }
        }
    }

    if (best) return best;

    const stepX = od.sizeX + packingGap;
    const stepZ = od.sizeZ + packingGap;
    return {
        stepX,
        stepZ,
        nx: Math.max(1, Math.floor((boxL - od.sizeX + 0.01) / stepX) + 1),
        nz: Math.max(1, Math.floor((boxW - od.sizeZ + 0.01) / stepZ) + 1),
        count: Math.max(1, Math.floor((boxL - od.sizeX + 0.01) / stepX) + 1) * Math.max(1, Math.floor((boxW - od.sizeZ + 0.01) / stepZ) + 1),
        leftoverArea: Infinity,
        fx: 1,
        fz: 1
    };
}

function _expandBaseFootprintMask(mask, pieceNX, pieceNZ) {
    const expanded = mask.slice();

    for (let z = 0; z < pieceNZ; z++) {
        let first = -1;
        let last = -1;
        for (let x = 0; x < pieceNX; x++) {
            if (!mask[z * pieceNX + x]) continue;
            if (first < 0) first = x;
            last = x;
        }
        if (first < 0 || last < 0) continue;
        for (let x = first; x <= last; x++) {
            expanded[z * pieceNX + x] = 1;
        }
    }

    for (let x = 0; x < pieceNX; x++) {
        let first = -1;
        let last = -1;
        for (let z = 0; z < pieceNZ; z++) {
            if (!expanded[z * pieceNX + x]) continue;
            if (first < 0) first = z;
            last = z;
        }
        if (first < 0 || last < 0) continue;
        for (let z = first; z <= last; z++) {
            expanded[z * pieceNX + x] = 1;
        }
    }

    return expanded;
}

function _fillPieceHeights(pieceHeights, footprintMask, pieceNX, pieceNZ, fallbackHeight) {
    const filled = pieceHeights.slice();

    for (let z = 0; z < pieceNZ; z++) {
        let rowMax = 0;
        for (let x = 0; x < pieceNX; x++) {
            const idx = z * pieceNX + x;
            if (filled[idx] > rowMax) rowMax = filled[idx];
        }
        if (rowMax <= 0) continue;
        for (let x = 0; x < pieceNX; x++) {
            const idx = z * pieceNX + x;
            if (footprintMask[idx] && filled[idx] <= 0) {
                filled[idx] = rowMax;
            }
        }
    }

    for (let x = 0; x < pieceNX; x++) {
        let colMax = 0;
        for (let z = 0; z < pieceNZ; z++) {
            const idx = z * pieceNX + x;
            if (filled[idx] > colMax) colMax = filled[idx];
        }
        if (colMax <= 0) continue;
        for (let z = 0; z < pieceNZ; z++) {
            const idx = z * pieceNX + x;
            if (footprintMask[idx] && filled[idx] <= 0) {
                filled[idx] = colMax;
            }
        }
    }

    const conservativeHeight = Math.max(fallbackHeight, Math.max(...filled));
    for (let i = 0; i < filled.length; i++) {
        if (footprintMask[i] && filled[i] <= 0) {
            filled[i] = conservativeHeight;
        }
    }

    return filled;
}

async function _rasterizePieceHeights(geometry, sizeX, sizeZ, cellSize, pieceNX, pieceNZ, maybeYield = null) {
    const raster = new Float32Array(pieceNX * pieceNZ);
    const positions = geometry.getAttribute('position');
    const index = geometry.getIndex();
    const triCount = index ? Math.floor(index.count / 3) : Math.floor(positions.count / 3);
    const insideEps = 1e-5;

    const readVertex = (vertexIndex, out) => {
        out.x = positions.getX(vertexIndex) + sizeX / 2;
        out.y = positions.getY(vertexIndex);
        out.z = positions.getZ(vertexIndex) + sizeZ / 2;
    };

    const v0 = { x: 0, y: 0, z: 0 };
    const v1 = { x: 0, y: 0, z: 0 };
    const v2 = { x: 0, y: 0, z: 0 };

    for (let tri = 0; tri < triCount; tri++) {
        const i0 = index ? index.getX(tri * 3) : tri * 3;
        const i1 = index ? index.getX(tri * 3 + 1) : tri * 3 + 1;
        const i2 = index ? index.getX(tri * 3 + 2) : tri * 3 + 2;
        readVertex(i0, v0);
        readVertex(i1, v1);
        readVertex(i2, v2);

        const minX = Math.max(0, Math.min(v0.x, v1.x, v2.x));
        const maxX = Math.min(sizeX, Math.max(v0.x, v1.x, v2.x));
        const minZ = Math.max(0, Math.min(v0.z, v1.z, v2.z));
        const maxZ = Math.min(sizeZ, Math.max(v0.z, v1.z, v2.z));
        const denom = ((v1.z - v2.z) * (v0.x - v2.x)) + ((v2.x - v1.x) * (v0.z - v2.z));

        if (Math.abs(denom) <= insideEps) {
            const vertices = [v0, v1, v2];
            for (const vertex of vertices) {
                const ix = Math.min(pieceNX - 1, Math.max(0, Math.floor(vertex.x / cellSize)));
                const iz = Math.min(pieceNZ - 1, Math.max(0, Math.floor(vertex.z / cellSize)));
                const idx = iz * pieceNX + ix;
                if (vertex.y > raster[idx]) raster[idx] = vertex.y;
            }
            if (maybeYield && (tri & 255) === 0) await maybeYield();
            continue;
        }

        const startX = Math.max(0, Math.floor(minX / cellSize));
        const endX = Math.min(pieceNX - 1, Math.floor(Math.max(0, maxX - insideEps) / cellSize));
        const startZ = Math.max(0, Math.floor(minZ / cellSize));
        const endZ = Math.min(pieceNZ - 1, Math.floor(Math.max(0, maxZ - insideEps) / cellSize));

        for (let iz = startZ; iz <= endZ; iz++) {
            const cz = (iz + 0.5) * cellSize;
            for (let ix = startX; ix <= endX; ix++) {
                const cx = (ix + 0.5) * cellSize;
                const a = (((v1.z - v2.z) * (cx - v2.x)) + ((v2.x - v1.x) * (cz - v2.z))) / denom;
                const b = (((v2.z - v0.z) * (cx - v2.x)) + ((v0.x - v2.x) * (cz - v2.z))) / denom;
                const c = 1 - a - b;
                if (a < -insideEps || b < -insideEps || c < -insideEps) continue;
                const y = (a * v0.y) + (b * v1.y) + (c * v2.y);
                const idx = iz * pieceNX + ix;
                if (y > raster[idx]) raster[idx] = y;
            }
        }

        if (maybeYield && (tri & 255) === 0) await maybeYield();
    }

    return raster;
}

// ─── Build orient data for a single piece geometry ───
async function _buildOrientData(srcGeometry, cellSize, boxL, boxW, boxH, maybeYield) {
    const geometry = srcGeometry.clone();
    geometry.computeVertexNormals();
    geometry.computeBoundingBox();

    const bbox = geometry.boundingBox;
    const center = new THREE.Vector3();
    bbox.getCenter(center);
    const sizeX = bbox.max.x - bbox.min.x;
    const sizeY = bbox.max.y - bbox.min.y;
    const sizeZ = bbox.max.z - bbox.min.z;

    if (sizeX > boxL || sizeZ > boxW || sizeY > boxH) return null;

    geometry.translate(-center.x, -bbox.min.y, -center.z);
    if (typeof geometry.computeBoundsTree === 'function') geometry.computeBoundsTree();

    const positions = geometry.getAttribute('position');
    const vertexCount = positions ? positions.count : 0;
    if (!positions || vertexCount === 0) return null;

    const pieceNX = Math.max(1, Math.ceil(sizeX / cellSize));
    const pieceNZ = Math.max(1, Math.ceil(sizeZ / cellSize));
    const pieceHeights = await _rasterizePieceHeights(geometry, sizeX, sizeZ, cellSize, pieceNX, pieceNZ, maybeYield);
    const pieceMask = new Uint8Array(pieceNX * pieceNZ);

    let minY = Infinity;
    for (let i = 0; i < vertexCount; i++) {
        minY = Math.min(minY, positions.getY(i));
        if ((i & 4095) === 0) await maybeYield();
    }
    const baseEps = Math.max(0.5, sizeY * 0.02);

    for (let i = 0; i < vertexCount; i++) {
        const x = positions.getX(i) + sizeX / 2;
        const y = positions.getY(i);
        const z = positions.getZ(i) + sizeZ / 2;
        const ix = Math.min(pieceNX - 1, Math.max(0, Math.floor(x / cellSize)));
        const iz = Math.min(pieceNZ - 1, Math.max(0, Math.floor(z / cellSize)));
        const idx = iz * pieceNX + ix;
        if (y <= minY + baseEps) pieceMask[idx] = 1;
        if ((i & 4095) === 0) await maybeYield();
    }

    const localBbox = new THREE.Box3(
        new THREE.Vector3(-sizeX / 2, 0, -sizeZ / 2),
        new THREE.Vector3(sizeX / 2, sizeY, sizeZ / 2)
    );

    const expandedMask = _expandBaseFootprintMask(pieceMask, pieceNX, pieceNZ);

    const filledHeights = _fillPieceHeights(pieceHeights, expandedMask, pieceNX, pieceNZ, sizeY);

    let baseCellCount = 0;
    for (let i = 0; i < expandedMask.length; i++) {
        if (expandedMask[i]) baseCellCount++;
    }
    const footprintArea = baseCellCount * cellSize * cellSize;

    return {
        geometry, positions, sizeX, sizeY, sizeZ,
        pieceNX, pieceNZ, pieceHeights: filledHeights, pieceMask: expandedMask, localBbox,
        footprintArea
    };
}

export class SceneManager {
    constructor(container) {
        this.container = container;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.animationId = null;
        this.pieces = [];
        this.boxMesh = null;
        this.gridHelper = null;
        this.lastPlacement = null;
        this.boxFloor = null;
        
        // 20 distinct colors for pieces - matching physics-world.js
        this.pieceColors = [
            0x3b82f6, // Blue
            0x10b981, // Green  
            0xf59e0b, // Orange
            0xef4444, // Red
            0x8b5cf6, // Purple
            0x06b6d4, // Cyan
            0xec4899, // Pink
            0x84cc16, // Lime
            0xf97316, // Deep Orange
            0x6366f1, // Indigo
            0x14b8a6, // Teal
            0xeab308, // Yellow
            0xa855f7, // Violet
            0x22c55e, // Emerald
            0xe11d48, // Rose
            0x0ea5e9, // Sky
            0xd946ef, // Fuchsia
            0x65a30d, // Green-600
            0xdc2626, // Red-600
            0x2563eb  // Blue-600
        ];
        this.colorCount = 10; // Default number of colors to use
        
        this.init();
    }

    init() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e);

        // Camera
        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 10000);
        this.camera.position.set(400, 400, 400);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ 
            antialias: true,
            alpha: true 
        });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.container.appendChild(this.renderer.domElement);

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.minDistance = 50;
        this.controls.maxDistance = 5000;

        // Lighting
        this.setupLighting();

        // Grid
        this.setupGrid();

        // Handle resize
        window.addEventListener('resize', () => this.onResize());

        // Start render loop
        this.animate();
    }

    setupLighting() {
        // Ambient light
        const ambient = new THREE.AmbientLight(0xffffff, 0.4);
        this.scene.add(ambient);

        // Main directional light
        const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
        mainLight.position.set(200, 400, 300);
        mainLight.castShadow = true;
        mainLight.shadow.mapSize.width = 2048;
        mainLight.shadow.mapSize.height = 2048;
        mainLight.shadow.camera.near = 10;
        mainLight.shadow.camera.far = 2000;
        mainLight.shadow.camera.left = -500;
        mainLight.shadow.camera.right = 500;
        mainLight.shadow.camera.top = 500;
        mainLight.shadow.camera.bottom = -500;
        this.scene.add(mainLight);

        // Fill light
        const fillLight = new THREE.DirectionalLight(0x88ccff, 0.3);
        fillLight.position.set(-200, 200, -100);
        this.scene.add(fillLight);

        // Hemisphere light for sky/ground
        const hemiLight = new THREE.HemisphereLight(0x87ceeb, 0x362d26, 0.3);
        this.scene.add(hemiLight);
    }

    setupGrid() {
        this.gridHelper = new THREE.GridHelper(1000, 20, 0x444444, 0x333333);
        this.gridHelper.position.y = -0.5;
        this.gridHelper.name = 'grid'; // Name for easy lookup
        this.scene.add(this.gridHelper);
    }

    /**
     * Create and add the box wireframe
     * @param {number} length - Box length (mm)
     * @param {number} width - Box width (mm)
     * @param {number} height - Box height (mm)
     */
    createBox(length, width, height) {
        // Remove existing box
        if (this.boxMesh) {
            this.scene.remove(this.boxMesh);
            this.boxMesh.geometry.dispose();
            this.boxMesh.material.dispose();
        }
        // Remove existing floor
        if (this.boxFloor) {
            this.scene.remove(this.boxFloor);
            this.boxFloor.geometry.dispose();
            this.boxFloor.material.dispose();
            this.boxFloor = null;
        }

        // Create wireframe box
        const geometry = new THREE.BoxGeometry(length, height, width);
        const edges = new THREE.EdgesGeometry(geometry);
        const material = new THREE.LineBasicMaterial({ 
            color: 0x22c55e,
            linewidth: 3
        });
        this.boxMesh = new THREE.LineSegments(edges, material);
        
        // Position so bottom is at y=0
        this.boxMesh.position.set(length / 2, height / 2, width / 2);
        this.scene.add(this.boxMesh);

        // Also create a semi-transparent floor
        const floorGeometry = new THREE.PlaneGeometry(length, width);
        const floorMaterial = new THREE.MeshPhongMaterial({
            color: 0x22c55e,
            opacity: 0.1,
            transparent: true,
            side: THREE.DoubleSide
        });
        this.boxFloor = new THREE.Mesh(floorGeometry, floorMaterial);
        this.boxFloor.rotation.x = -Math.PI / 2;
        this.boxFloor.position.set(length / 2, 0.1, width / 2);
        this.boxFloor.name = 'boxFloor';
        this.scene.add(this.boxFloor);

        // Update grid
        const maxDim = Math.max(length, width, height);
        this.gridHelper.scale.setScalar(maxDim / 500);

        // Center camera on box
        this.focusOnBox(length, width, height);
    }

    /**
     * Clear all pieces from the scene
     */
    clearPieces() {
        for (const piece of this.pieces) {
            this.scene.remove(piece);
            if (piece.geometry) piece.geometry.dispose();
            if (piece.material) {
                if (Array.isArray(piece.material)) {
                    piece.material.forEach(m => m.dispose());
                } else {
                    piece.material.dispose();
                }
            }
        }
        this.pieces = [];
    }

    /**
     * Add packed pieces as cuboids
     * @param {Object} params
     * @param {number} params.pieceL - Piece length
     * @param {number} params.pieceW - Piece width  
     * @param {number} params.pieceH - Piece height
     * @param {number} params.nx - Number in X direction
     * @param {number} params.ny - Number in Y direction
     * @param {number} params.nz - Number in Z direction
     * @param {number} params.maxDraw - Maximum pieces to draw
     * @param {number} [params.packingGap=0] - Gap between pieces in mm
     * @param {number} [params.boxL] - Box length (for boundary check)
     * @param {number} [params.boxW] - Box width (for boundary check)
     * @param {number} [params.boxH] - Box height (for boundary check)
     */
    addPackedPieces({ pieceL, pieceW, pieceH, nx, ny, nz, maxDraw = 500, packingGap = 0, colorCount = null, boxL = null, boxW = null, boxH = null }) {
        this.clearPieces();
        
        // Use provided colorCount or default
        const numColors = colorCount || this.colorCount;

        const geometry = new THREE.BoxGeometry(pieceL, pieceH, pieceW);
        const material = new THREE.MeshPhongMaterial({
            color: 0xffffff, // White base for vertex colors
            opacity: 0.92,
            transparent: true,
            flatShading: false,
            shininess: 60,
            specular: 0x444444
        });

        // Use instancing for performance
        const totalPieces = Math.min(nx * ny * nz, maxDraw);
        const instancedMesh = new THREE.InstancedMesh(geometry, material, totalPieces);
        instancedMesh.castShadow = true;
        instancedMesh.receiveShadow = true;

        const dummy = new THREE.Object3D();
        let index = 0;
        const positions = [];

        for (let iz = 0; iz < nz && index < totalPieces; iz++) {
            for (let iy = 0; iy < ny && index < totalPieces; iy++) {
                for (let ix = 0; ix < nx && index < totalPieces; ix++) {
                    // Calculate position with gap spacing
                    const posX = ix * (pieceL + packingGap) + pieceL / 2;
                    const posY = iz * (pieceH + packingGap) + pieceH / 2;
                    const posZ = iy * (pieceW + packingGap) + pieceW / 2;
                    
                    // Skip pieces that would overflow the box (with relaxed tolerance)
                    const tolerance = 0.1;
                    if (boxL !== null && posX + pieceL / 2 > boxL + tolerance) continue;
                    if (boxW !== null && posZ + pieceW / 2 > boxW + tolerance) continue;
                    if (boxH !== null && posY + pieceH / 2 > boxH + tolerance) continue;
                    
                    dummy.position.set(posX, posY, posZ);
                    dummy.updateMatrix();
                    instancedMesh.setMatrixAt(index, dummy.matrix);

                    positions.push(new THREE.Vector3(posX, posY, posZ));
                    
                    // Use colors from pieceColors array
                    const colorIndex = index % numColors;
                    const color = new THREE.Color(this.pieceColors[colorIndex]);
                    instancedMesh.setColorAt(index, color);
                    
                    index++;
                }
            }
        }

        instancedMesh.count = index;
        instancedMesh.instanceMatrix.needsUpdate = true;
        if (instancedMesh.instanceColor) {
            instancedMesh.instanceColor.needsUpdate = true;
        }

        this.scene.add(instancedMesh);
        this.pieces.push(instancedMesh);

        this.lastPlacement = {
            type: 'box',
            dims: { l: pieceL, w: pieceW, h: pieceH },
            positions,
            boxDims: boxL !== null && boxW !== null && boxH !== null
                ? { l: boxL, w: boxW, h: boxH }
                : null
        };

        return index; // Return actual count drawn (may be less if pieces were skipped)
    }

    /**
     * Add packed STL pieces in a grid
     * @param {Object} params
     * @param {THREE.BufferGeometry} params.stlGeometry - STL geometry to instance
     * @param {number} params.pieceL - Piece length
     * @param {number} params.pieceW - Piece width  
     * @param {number} params.pieceH - Piece height
     * @param {number} params.nx - Number in X direction
     * @param {number} params.nz - Number in Z direction
     * @param {number} [params.maxDraw=500] - Maximum pieces to draw
     * @param {number} [params.packingGap=0] - Gap between pieces in mm
     * @param {number} [params.boxL] - Box length (for boundary check)
     * @param {number} [params.boxW] - Box width (for boundary check)
     * @param {number} [params.boxH] - Box height (for boundary check)
     */
    addPackedSTLPieces({ stlGeometry, pieceL, pieceW, pieceH, nx, ny, nz, maxDraw = 500, packingGap = 0, colorCount = null, boxL = null, boxW = null, boxH = null, strictGeometryCheck = true }) {
        this.clearPieces();
        
        // Use provided colorCount or default
        const numColors = colorCount || this.colorCount;

        // Clone and prepare geometry
        const geometry = stlGeometry.clone();
        geometry.computeVertexNormals();
        geometry.computeBoundingBox();

        // Use real geometry bounds for placement (avoid floating/protrusion)
        let sizeX = pieceL;
        let sizeY = pieceH;
        let sizeZ = pieceW;
        let baseAlignedY = false;
        if (geometry.boundingBox) {
            const bbox = geometry.boundingBox;
            const center = new THREE.Vector3();
            bbox.getCenter(center);
            sizeX = bbox.max.x - bbox.min.x;
            sizeY = bbox.max.y - bbox.min.y;
            sizeZ = bbox.max.z - bbox.min.z;

            // Align base to y=0 and center in X/Z
            geometry.translate(-center.x, -bbox.min.y, -center.z);
            baseAlignedY = true;
        }

        const material = new THREE.MeshPhongMaterial({
            color: 0xffffff, // White base for vertex colors
            opacity: 0.92,
            transparent: true,
            flatShading: false,
            shininess: 60,
            specular: 0x444444
        });

        // Use instancing for performance
        const totalPieces = Math.min(nx * ny * nz, maxDraw);
        const instancedMesh = new THREE.InstancedMesh(geometry, material, totalPieces);
        instancedMesh.castShadow = true;
        instancedMesh.receiveShadow = true;

        const dummy = new THREE.Object3D();
        const positions = geometry.getAttribute('position');
        const vertexCount = positions ? positions.count : 0;
        const boxTolerance = 0.1;
        const hasBoxLimits = boxL !== null && boxW !== null && boxH !== null;
        let maxNx = 0;
        let maxNy = 0;
        let maxNz = 0;
        const placementPositions = [];

        // Compute a conservative footprint size from base vertices to allow slightly tighter packing
        let footprintX = sizeX;
        let footprintZ = sizeZ;
        if (positions && vertexCount > 0) {
            let minY = Infinity;
            for (let i = 0; i < vertexCount; i++) {
                minY = Math.min(minY, positions.getY(i));
            }
            const epsilon = Math.max(0.5, sizeY * 0.02);
            const maxY = minY + epsilon;
            let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
            let count = 0;
            for (let i = 0; i < vertexCount; i++) {
                const y = positions.getY(i);
                if (y <= maxY) {
                    const x = positions.getX(i);
                    const z = positions.getZ(i);
                    minX = Math.min(minX, x);
                    maxX = Math.max(maxX, x);
                    minZ = Math.min(minZ, z);
                    maxZ = Math.max(maxZ, z);
                    count++;
                }
            }
            if (count >= 3) {
                footprintX = Math.max(0.1, maxX - minX);
                footprintZ = Math.max(0.1, maxZ - minZ);
            }
        }

        const spacingX = Math.max(sizeX, footprintX) + packingGap;
        const spacingZ = Math.max(sizeZ, footprintZ) + packingGap;
        let index = 0;

        for (let iz = 0; iz < nz && index < totalPieces; iz++) {
            for (let iy = 0; iy < ny && index < totalPieces; iy++) {
                for (let ix = 0; ix < nx && index < totalPieces; ix++) {
                    // Calculate position with gap spacing
                    const posX = ix * spacingX + sizeX / 2;
                    const posY = baseAlignedY
                        ? iy * (sizeY + packingGap)
                        : iy * (sizeY + packingGap) + sizeY / 2;
                    const posZ = iz * spacingZ + sizeZ / 2;
                    
                    // Skip pieces that would overflow the box (with relaxed tolerance)
                    if (boxL !== null && posX + sizeX / 2 > boxL + boxTolerance) continue;
                    if (boxW !== null && posZ + sizeZ / 2 > boxW + boxTolerance) continue;
                    const topY = baseAlignedY ? posY + sizeY : posY + sizeY / 2;
                    if (boxH !== null && topY > boxH + boxTolerance) continue;
                    
                    dummy.position.set(posX, posY, posZ);
                    dummy.updateMatrix();

                    // Strict geometry check: ensure no vertex protrudes the box
                    if (strictGeometryCheck && hasBoxLimits && vertexCount > 0) {
                        let fits = true;
                        for (let vi = 0; vi < vertexCount; vi++) {
                            const x = positions.getX(vi);
                            const y = positions.getY(vi);
                            const z = positions.getZ(vi);
                            const vx = x + dummy.position.x;
                            const vy = y + dummy.position.y;
                            const vz = z + dummy.position.z;
                            if (
                                vx < -boxTolerance || vx > boxL + boxTolerance ||
                                vy < -boxTolerance || vy > boxH + boxTolerance ||
                                vz < -boxTolerance || vz > boxW + boxTolerance
                            ) {
                                fits = false;
                                break;
                            }
                        }
                        if (!fits) continue;
                    }

                    instancedMesh.setMatrixAt(index, dummy.matrix);
                    maxNx = Math.max(maxNx, ix + 1);
                    maxNy = Math.max(maxNy, iy + 1);
                    maxNz = Math.max(maxNz, iz + 1);

                    placementPositions.push(new THREE.Vector3(posX, posY, posZ));
                    
                    // Use colors from pieceColors array
                    const colorIndex = index % numColors;
                    const color = new THREE.Color(this.pieceColors[colorIndex]);
                    instancedMesh.setColorAt(index, color);
                    
                    index++;
                }
            }
        }

        instancedMesh.count = index;
        instancedMesh.instanceMatrix.needsUpdate = true;
        if (instancedMesh.instanceColor) {
            instancedMesh.instanceColor.needsUpdate = true;
        }

        this.scene.add(instancedMesh);
        this.pieces.push(instancedMesh);

        this.lastPlacement = {
            type: 'stl',
            dims: { l: sizeX, w: sizeZ, h: sizeY },
            geometry,
            vertices: positions ? new Float32Array(positions.array) : null,
            positions: placementPositions,
            boxDims: boxL !== null && boxW !== null && boxH !== null
                ? { l: boxL, w: boxW, h: boxH }
                : null
        };

        return {
            count: index,
            distribution: { nx: maxNx, ny: maxNy, nz: maxNz },
            distributionText: `${maxNx}×${maxNy}×${maxNz}`
        };
    }

    /**
     * Add packed STL pieces using a simple height-map nesting (experimental)
     * @param {Object} params
     * @param {THREE.BufferGeometry} params.stlGeometry
     * @param {number} [params.maxDraw=500]
     * @param {number} [params.packingGap=0]
     * @param {number} [params.boxL]
     * @param {number} [params.boxW]
     * @param {number} [params.boxH]
     */
    addPackedSTLHeightMap({ stlGeometry, maxDraw = 500, maxTry = null, packingGap = 0, colorCount = null, boxL = null, boxW = null, boxH = null, dryRun = false }) {
        if (!dryRun) {
            this.clearPieces();
        }

        if (boxL === null || boxW === null || boxH === null) {
            // Fallback to regular packing if box dims are missing
            return this.addPackedSTLPieces({
                stlGeometry,
                pieceL: 0,
                pieceW: 0,
                pieceH: 0,
                nx: 0,
                ny: 0,
                nz: 0,
                maxDraw,
                packingGap,
                colorCount,
                boxL,
                boxW,
                boxH,
                strictGeometryCheck: true
            });
        }

        const numColors = colorCount || this.colorCount;

        // Clone and prepare geometry
        const geometry = stlGeometry.clone();
        geometry.computeVertexNormals();
        geometry.computeBoundingBox();

        const bbox = geometry.boundingBox;
        const center = new THREE.Vector3();
        bbox.getCenter(center);
        const sizeX = bbox.max.x - bbox.min.x;
        const sizeY = bbox.max.y - bbox.min.y;
        const sizeZ = bbox.max.z - bbox.min.z;

        if (sizeX > boxL || sizeZ > boxW || sizeY > boxH) {
            return { count: 0 };
        }

        // Align base to y=0 and center in X/Z
        geometry.translate(-center.x, -bbox.min.y, -center.z);

        // Build BVH for lateral collision testing
        if (typeof geometry.computeBoundsTree === 'function') {
            geometry.computeBoundsTree();
        }

        const positions = geometry.getAttribute('position');
        const vertexCount = positions ? positions.count : 0;
        if (!positions || vertexCount === 0) return { count: 0 };

        // Height-map resolution (finer grid => less artificial spacing)
        // Keep it bounded to avoid pathological O(n^3) scans.
        const cellSize = Math.max(1, Math.min(4, Math.min(sizeX, sizeZ) / 20));
        const pieceNX = Math.max(1, Math.ceil(sizeX / cellSize));
        const pieceNZ = Math.max(1, Math.ceil(sizeZ / cellSize));
        const pieceHeights = new Float32Array(pieceNX * pieceNZ);
        const pieceMask = new Uint8Array(pieceNX * pieceNZ);
        const heightEps = Math.max(0.5, packingGap * 0.25);

        // Build piece height map + base footprint mask
        let minY = Infinity;
        for (let i = 0; i < vertexCount; i++) {
            minY = Math.min(minY, positions.getY(i));
        }
        const baseEps = Math.max(0.5, sizeY * 0.02);

        for (let i = 0; i < vertexCount; i++) {
            const x = positions.getX(i) + sizeX / 2;
            const y = positions.getY(i);
            const z = positions.getZ(i) + sizeZ / 2;
            const ix = Math.min(pieceNX - 1, Math.max(0, Math.floor(x / cellSize)));
            const iz = Math.min(pieceNZ - 1, Math.max(0, Math.floor(z / cellSize)));
            const idx = iz * pieceNX + ix;
            if (y > pieceHeights[idx]) pieceHeights[idx] = y;
            if (y <= minY + baseEps) pieceMask[idx] = 1;
        }

        const expandedMask = _expandBaseFootprintMask(pieceMask, pieceNX, pieceNZ);
        const filledHeights = _fillPieceHeights(pieceHeights, expandedMask, pieceNX, pieceNZ, sizeY);

        // Container height map
        const gridNX = Math.max(1, Math.ceil(boxL / cellSize));
        const gridNZ = Math.max(1, Math.ceil(boxW / cellSize));
        const heightMap = new Float32Array(gridNX * gridNZ);

        const material = new THREE.MeshPhongMaterial({
            color: 0xffffff,
            opacity: 0.92,
            transparent: true,
            flatShading: false,
            shininess: 60,
            specular: 0x444444
        });

        const positionsOut = dryRun ? null : [];
        let placed = 0;

        // Adaptive maxTry from volume ratio if not provided
        const pieceBBoxVol = sizeX * sizeY * sizeZ;
        const boxVolume = boxL * boxW * boxH;
        const effectiveMaxTry = maxTry != null ? maxTry : Math.min(2000, Math.max(maxDraw, Math.ceil(boxVolume / pieceBBoxVol * 1.2)));

        // BVH collision infrastructure — prevents lateral mesh penetration
        const placedAabbs = [];
        const placedMatrices = [];
        const localBbox = new THREE.Box3(
            new THREE.Vector3(-sizeX / 2, 0, -sizeZ / 2),
            new THREE.Vector3(sizeX / 2, sizeY, sizeZ / 2)
        );
        const tmpMatA = new THREE.Matrix4();
        const tmpMatB = new THREE.Matrix4();
        const tmpInv = new THREE.Matrix4();
        const tmpBox = new THREE.Box3();

        const candidateIntersectsAny = (candidateMatrix, candidateAabb) => {
            if (!geometry.boundsTree) return false;
            const inflate = Math.max(0, packingGap * 0.5);
            for (let i = 0; i < placedAabbs.length; i++) {
                const otherAabb = placedAabbs[i];
                // Broadphase AABB check
                if ((candidateAabb.max.x + inflate) < (otherAabb.min.x - inflate) ||
                    (candidateAabb.min.x - inflate) > (otherAabb.max.x + inflate) ||
                    (candidateAabb.max.y + inflate) < (otherAabb.min.y - inflate) ||
                    (candidateAabb.min.y - inflate) > (otherAabb.max.y + inflate) ||
                    (candidateAabb.max.z + inflate) < (otherAabb.min.z - inflate) ||
                    (candidateAabb.min.z - inflate) > (otherAabb.max.z + inflate)) continue;
                // Precise BVH triangle-triangle
                tmpInv.copy(placedMatrices[i]).invert();
                tmpMatA.multiplyMatrices(tmpInv, candidateMatrix);
                if (geometry.boundsTree.intersectsGeometry(geometry, tmpMatA)) return true;
            }
            return false;
        };

        // Consecutive-failure counter: resets on each successful placement
        let consecutiveSkips = 0;
        const maxConsecutiveSkips = Math.max(200, Math.ceil(boxVolume / pieceBBoxVol) * 3);

        while (placed < effectiveMaxTry) {
            let bestX = -1;
            let bestZ = -1;
            let bestH = Infinity;

            for (let gz = 0; gz <= gridNZ - pieceNZ; gz++) {
                for (let gx = 0; gx <= gridNX - pieceNX; gx++) {
                    const x0 = gx * cellSize;
                    const z0 = gz * cellSize;
                    if (x0 + sizeX > boxL || z0 + sizeZ > boxW) continue;

                    let baseH = 0;
                    for (let pz = 0; pz < pieceNZ; pz++) {
                        for (let px = 0; px < pieceNX; px++) {
                            const pIdx = pz * pieceNX + px;
                            if (!expandedMask[pIdx]) continue;
                            const hIdx = (gz + pz) * gridNX + (gx + px);
                            if (heightMap[hIdx] > baseH) baseH = heightMap[hIdx];
                        }
                    }

                    if (baseH >= bestH) continue;

                    let fits = true;
                    for (let pz = 0; pz < pieceNZ && fits; pz++) {
                        for (let px = 0; px < pieceNX; px++) {
                            const pIdx = pz * pieceNX + px;
                            if (!expandedMask[pIdx]) continue;
                            const top = baseH + filledHeights[pIdx];
                            if (top + heightEps > boxH) {
                                fits = false;
                                break;
                            }
                        }
                    }

                    if (fits) {
                        bestH = baseH;
                        bestX = gx;
                        bestZ = gz;
                    }
                }
            }

            if (bestX < 0 || bestZ < 0 || !Number.isFinite(bestH)) break;

            // Full bounding box height guard — piece must fit entirely within box
            if (bestH + sizeY > boxH + 0.01) break;

            // Build candidate transform + AABB
            const posX = bestX * cellSize + sizeX / 2;
            const posZ = bestZ * cellSize + sizeZ / 2;
            const posY = bestH;
            tmpMatB.makeTranslation(posX, posY, posZ);
            tmpBox.copy(localBbox).applyMatrix4(tmpMatB);

            // BVH collision check — prevent lateral penetration
            if (candidateIntersectsAny(tmpMatB, tmpBox)) {
                // Small bump: just cellSize to try the next height level
                const bump = cellSize;
                for (let pz = 0; pz < pieceNZ; pz++) {
                    for (let px = 0; px < pieceNX; px++) {
                        const pIdx = pz * pieceNX + px;
                        if (!expandedMask[pIdx]) continue;
                        const hIdx = (bestZ + pz) * gridNX + (bestX + px);
                        const newH = bestH + bump;
                        if (newH > heightMap[hIdx]) heightMap[hIdx] = newH;
                    }
                }
                if (++consecutiveSkips > maxConsecutiveSkips) break;
                continue;
            }
            consecutiveSkips = 0; // Reset on successful placement

            if (!dryRun) {
                const mesh = new THREE.Mesh(geometry.clone(), material.clone());
                mesh.castShadow = true;
                mesh.receiveShadow = true;
                mesh.position.set(posX, posY, posZ);
                this.scene.add(mesh);
                this.pieces.push(mesh);

                const colorIndex = placed % numColors;
                mesh.material.color = new THREE.Color(this.pieceColors[colorIndex]);

                positionsOut.push(new THREE.Vector3(posX, posY, posZ));
            }

            // Cache placement for collision checks
            placedAabbs.push(tmpBox.clone());
            placedMatrices.push(tmpMatB.clone());

            // Update height map
            for (let pz = 0; pz < pieceNZ; pz++) {
                for (let px = 0; px < pieceNX; px++) {
                    const pIdx = pz * pieceNX + px;
                    if (!expandedMask[pIdx]) continue;
                    const hIdx = (bestZ + pz) * gridNX + (bestX + px);
                    const top = bestH + filledHeights[pIdx] + packingGap;
                    if (top > heightMap[hIdx]) heightMap[hIdx] = top;
                }
            }

            placed++;
        }

        console.log(`[HeightMap] placed=${placed}, maxTry=${effectiveMaxTry}, consecutiveSkips=${consecutiveSkips}`);

        if (!dryRun) {
            this.lastPlacement = {
                type: 'stl',
                dims: { l: sizeX, w: sizeZ, h: sizeY },
                geometry,
                vertices: positions ? new Float32Array(positions.array) : null,
                positions: positionsOut,
                boxDims: { l: boxL, w: boxW, h: boxH }
            };
        }

        return { count: placed };
    }

    /**
     * Async + abortable version of addPackedSTLHeightMap.
     * Yields to the browser regularly to keep UI responsive and to allow cancellation.
     *
     * @param {Object} params
     * @param {THREE.BufferGeometry} params.stlGeometry
     * @param {Array<{geometry:THREE.BufferGeometry}>} [params.orientationPool] - alternate orientations
     * @param {boolean} [params.useMixedOrientations=false]
     * @param {number} [params.maxDraw=500]
     * @param {number} [params.packingGap=0]
     * @param {number} [params.colorCount]
     * @param {number} params.boxL
     * @param {number} params.boxW
     * @param {number} params.boxH
     * @param {boolean} [params.dryRun=false]
     * @param {AbortSignal} [params.abortSignal]
     * @param {(p:{placed:number,maxTry:number})=>void} [params.onProgress]
     */
    async addPackedSTLHeightMapAsync({
        stlGeometry,
        orientationPool = null,
        useMixedOrientations = false,
        lockPrimaryFirstLayer = false,
        maxDraw = 500,
        maxTry = null,
        packingGap = 0,
        colorCount = null,
        boxL = null,
        boxW = null,
        boxH = null,
        placementStrategy = 'stable-contact',
        stabilityMode = 'strict',
        allowSideStacking = true,
        useSettleCheck = true,
        searchEffort = 'balanced',
        dryRun = false,
        abortSignal = null,
        onProgress = null
    }) {
        const abortError = () => new DOMException('Aborted', 'AbortError');
        const yieldBudgetMs = 8;
        let lastYieldAt = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
        const maybeYield = async (force = false) => {
            if (abortSignal?.aborted) throw abortError();
            const now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
            if (!force && (now - lastYieldAt) < yieldBudgetMs) return;
            await new Promise(resolve => requestAnimationFrame(() => resolve()));
            lastYieldAt = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
            if (abortSignal?.aborted) throw abortError();
        };

        if (!dryRun) this.clearPieces();

        if (boxL === null || boxW === null || boxH === null) {
            return this.addPackedSTLPieces({
                stlGeometry, pieceL: 0, pieceW: 0, pieceH: 0,
                nx: 0, ny: 0, nz: 0, maxDraw, packingGap, colorCount,
                boxL, boxW, boxH, strictGeometryCheck: true
            });
        }

        const numColors = colorCount || this.colorCount;

        // Cell size from primary geometry
        stlGeometry.computeBoundingBox();
        const primBbox = stlGeometry.boundingBox;
        const primSX = primBbox.max.x - primBbox.min.x;
        const primSZ = primBbox.max.z - primBbox.min.z;
        const cellSize = Math.max(1, Math.min(4, Math.min(primSX, primSZ) / 20));

        // Build orientation data: primary + pool alternates
        const allSrcGeometries = [stlGeometry];
        if (useMixedOrientations && orientationPool && orientationPool.length > 0) {
            for (const p of orientationPool) {
                if (p.geometry) allSrcGeometries.push(p.geometry);
            }
        }
        const orientData = [];
        for (const src of allSrcGeometries) {
            const od = await _buildOrientData(src, cellSize, boxL, boxW, boxH, maybeYield);
            if (od) orientData.push(od);
        }
        if (orientData.length === 0) return { count: 0 };

        const primary = orientData[0];
        const multiOrient = orientData.length > 1;
        const heightEps = Math.max(0.1, packingGap * 0.1);

        console.log(`[HeightMapAsync] ${orientData.length} orientation(s) prepared (cell=${cellSize.toFixed(1)}mm)`);

        // Container height map
        const gridNX = Math.max(1, Math.ceil(boxL / cellSize));
        const gridNZ = Math.max(1, Math.ceil(boxW / cellSize));
        const heightMap = new Float32Array(gridNX * gridNZ);

        const material = new THREE.MeshPhongMaterial({
            color: 0xffffff, opacity: 0.92, transparent: true,
            flatShading: false, shininess: 60, specular: 0x444444
        });

        const positionsOut = dryRun ? null : [];
        let placed = 0;

        // Adaptive maxTry from volume ratio
        const pieceBBoxVol = primary.sizeX * primary.sizeY * primary.sizeZ;
        const boxVolume = boxL * boxW * boxH;
        const effectiveMaxTry = maxTry != null
            ? maxTry
            : Math.min(2000, Math.max(maxDraw, Math.ceil(boxVolume / pieceBBoxVol * 1.2)));

        // BVH collision infrastructure (proven accurate for complex meshes)
        const placedAabbs = [];
        const placedMatrices = [];
        const placedOrientIdxs = [];
        const tmpMatA = new THREE.Matrix4();
        const tmpMatB = new THREE.Matrix4();
        const tmpInv = new THREE.Matrix4();
        const tmpBox = new THREE.Box3();

        const candidateIntersectsAny = (candidateMatrix, candidateAabb, candOrientIdx) => {
            const candGeom = orientData[candOrientIdx].geometry;
            if (!candGeom.boundsTree) return false;
            const inflate = 0;
            const touchEps = Math.max(0.6, cellSize * 0.35);
            for (let i = 0; i < placedAabbs.length; i++) {
                const otherAabb = placedAabbs[i];
                if ((candidateAabb.max.x + inflate) < (otherAabb.min.x - inflate) ||
                    (candidateAabb.min.x - inflate) > (otherAabb.max.x + inflate) ||
                    (candidateAabb.max.y + inflate) < (otherAabb.min.y - inflate) ||
                    (candidateAabb.min.y - inflate) > (otherAabb.max.y + inflate) ||
                    (candidateAabb.max.z + inflate) < (otherAabb.min.z - inflate) ||
                    (candidateAabb.min.z - inflate) > (otherAabb.max.z + inflate)) continue;

                const overlapX = Math.min(candidateAabb.max.x, otherAabb.max.x) - Math.max(candidateAabb.min.x, otherAabb.min.x);
                const overlapY = Math.min(candidateAabb.max.y, otherAabb.max.y) - Math.max(candidateAabb.min.y, otherAabb.min.y);
                const overlapZ = Math.min(candidateAabb.max.z, otherAabb.max.z) - Math.max(candidateAabb.min.z, otherAabb.min.z);
                const verticalTouch = overlapX > heightEps && overlapZ > heightEps && overlapY <= touchEps;
                if (verticalTouch) continue;

                const placedGeom = orientData[placedOrientIdxs[i]].geometry;
                if (!placedGeom.boundsTree) continue;
                tmpInv.copy(placedMatrices[i]).invert();
                tmpMatA.multiplyMatrices(tmpInv, candidateMatrix);
                if (placedGeom.boundsTree.intersectsGeometry(candGeom, tmpMatA)) return true;
            }
            return false;
        };

        const stabilityProfiles = {
            strict: { minSupportRatio: 0.72, minSupportCells: 3, centerTolerance: 0.32, levelTolerance: Math.max(0.8, cellSize * 0.85) },
            medium: { minSupportRatio: 0.55, minSupportCells: 2, centerTolerance: 0.45, levelTolerance: Math.max(1.0, cellSize * 1.05) },
            loose: { minSupportRatio: 0.38, minSupportCells: 1, centerTolerance: 0.62, levelTolerance: Math.max(1.4, cellSize * 1.3) }
        };
        const activeStability = stabilityProfiles[stabilityMode] || stabilityProfiles.strict;
        const isLegacyStrategy = placementStrategy === 'legacy';
        const runStableContact = !isLegacyStrategy;
        const stackedClearance = placementStrategy === 'stable-contact' ? Math.max(0.04, cellSize * 0.02) : 0;
        const allowMixedUpperLayers = isLegacyStrategy
            ? multiOrient
            : allowSideStacking || placementStrategy === 'stable-contact';
        const replicationProfiles = isLegacyStrategy
            ? [activeStability]
            : placementStrategy === 'stable-contact'
                ? [activeStability, stabilityProfiles.medium, stabilityProfiles.loose]
                : placementStrategy === 'hybrid'
                    ? [activeStability, stabilityProfiles.medium]
                    : [activeStability, stabilityProfiles.medium, stabilityProfiles.loose];

        const evaluateSupport = (gx, gz, od, baseH, profile, settleCheckEnabled = useSettleCheck) => {
            if (baseH <= heightEps) {
                return { supported: true, supportRatio: 1, supportCount: 1, drift: 0 };
            }

            const { pieceNX, pieceNZ, pieceMask } = od;
            let supportCount = 0;
            let baseCellCount = 0;
            let sumX = 0;
            let sumZ = 0;
            let minSupportH = Infinity;
            let maxSupportH = -Infinity;

            for (let pz = 0; pz < pieceNZ; pz++) {
                for (let px = 0; px < pieceNX; px++) {
                    const pIdx = pz * pieceNX + px;
                    if (!pieceMask[pIdx]) continue;
                    baseCellCount++;
                    const hIdx = (gz + pz) * gridNX + (gx + px);
                    const supportH = heightMap[hIdx];
                    if (Math.abs(supportH - baseH) <= profile.levelTolerance) {
                        supportCount++;
                        sumX += gx + px + 0.5;
                        sumZ += gz + pz + 0.5;
                        minSupportH = Math.min(minSupportH, supportH);
                        maxSupportH = Math.max(maxSupportH, supportH);
                    }
                }
            }

            if (baseCellCount === 0) {
                return { supported: false, supportRatio: 0, supportCount: 0, drift: Infinity };
            }

            const supportRatio = supportCount / baseCellCount;
            if (supportCount < profile.minSupportCells || supportRatio < profile.minSupportRatio) {
                return { supported: false, supportRatio, supportCount, drift: Infinity };
            }

            const supportCx = sumX / supportCount;
            const supportCz = sumZ / supportCount;
            const pieceCx = gx + pieceNX / 2;
            const pieceCz = gz + pieceNZ / 2;
            const normDx = Math.abs(supportCx - pieceCx) / Math.max(1, pieceNX / 2);
            const normDz = Math.abs(supportCz - pieceCz) / Math.max(1, pieceNZ / 2);
            const drift = Math.max(normDx, normDz);

            if (drift > profile.centerTolerance) {
                return { supported: false, supportRatio, supportCount, drift };
            }

            if (settleCheckEnabled && Number.isFinite(minSupportH) && Number.isFinite(maxSupportH)) {
                if ((maxSupportH - minSupportH) > profile.levelTolerance * 1.35) {
                    return { supported: false, supportRatio, supportCount, drift };
                }
            }

            return { supported: true, supportRatio, supportCount, drift };
        };

        const evaluateColumnSupport = (gx, gz, od, baseH, profile) => {
            if (baseH <= heightEps) {
                return { supported: true, supportRatio: 1, supportCount: 1, drift: 0 };
            }

            const { pieceNX, pieceNZ, pieceMask } = od;
            let supportCount = 0;
            let baseCellCount = 0;

            for (let pz = 0; pz < pieceNZ; pz++) {
                for (let px = 0; px < pieceNX; px++) {
                    const pIdx = pz * pieceNX + px;
                    if (!pieceMask[pIdx]) continue;
                    baseCellCount++;
                    const hIdx = (gz + pz) * gridNX + (gx + px);
                    const supportH = heightMap[hIdx];
                    if (Math.abs(supportH - baseH) <= profile.levelTolerance * 1.8) {
                        supportCount++;
                    }
                }
            }

            if (baseCellCount === 0) {
                return { supported: false, supportRatio: 0, supportCount: 0, drift: Infinity };
            }

            const supportRatio = supportCount / baseCellCount;
            const minRatio = Math.max(0.28, profile.minSupportRatio * 0.55);
            const minCells = Math.max(1, profile.minSupportCells - 1);
            return {
                supported: supportCount >= minCells && supportRatio >= minRatio,
                supportRatio,
                supportCount,
                drift: 0
            };
        };

        let consecutiveSkips = 0;
        const maxConsecutiveSkips = Math.max(200, Math.ceil(boxVolume / pieceBBoxVol) * 3);

        // Instanced rendering — one InstancedMesh per orientation
        const instancedMeshes = [];
        const orientCounts = new Array(orientData.length).fill(0);
        const tmpObj = new THREE.Object3D();
        if (!dryRun) {
            for (const od of orientData) {
                const im = new THREE.InstancedMesh(od.geometry, material.clone(), effectiveMaxTry);
                im.castShadow = true;
                im.receiveShadow = true;
                instancedMeshes.push(im);
            }
        }

        // ═══════════════ PHASE 1: FIRST LAYER — deterministic grid ═══════════════
        // For each orientation, search a slightly compacted regular grid.
        // This follows the grid, but is not forced to use pure bbox spacing.
        let bestGridOi = 0;
        let bestGridNX = 0, bestGridNZ = 0, bestGridCount = 0;
        let bestStepX = 0, bestStepZ = 0;

        const firstLayerOrientLimit = lockPrimaryFirstLayer ? 1 : orientData.length;
        for (let oi = 0; oi < firstLayerOrientLimit; oi++) {
            const od = orientData[oi];
            const layout = _findBestGridLayoutForOrientation(od, boxL, boxW, packingGap);
            const { stepX, stepZ, nx, nz, count, fx, fz } = layout;
            console.log(`[Grid] orient${oi}: ${nx}×${nz}=${count}  piece ${od.sizeX.toFixed(1)}×${od.sizeZ.toFixed(1)}  step ${stepX.toFixed(1)}×${stepZ.toFixed(1)}  compact=${fx.toFixed(2)}×${fz.toFixed(2)}`);
            if (count > bestGridCount) {
                bestGridCount = count;
                bestGridOi = oi;
                bestGridNX = nx;
                bestGridNZ = nz;
                bestStepX = stepX;
                bestStepZ = stepZ;
            }
        }

        // Place first layer as a regular grid, corner-aligned (touching walls)
        const gridOd = orientData[bestGridOi];
        const { pieceNX: gPNX, pieceNZ: gPNZ, pieceMask: gMask,
                pieceHeights: gPH, sizeX: gSX, sizeY: gSY, sizeZ: gSZ } = gridOd;
        const firstLayerSlots = [];

        console.log(`[Grid] Best: orient${bestGridOi} → ${bestGridNX}×${bestGridNZ} = ${bestGridCount} pieces`);

        for (let iz = 0; iz < bestGridNZ && placed < effectiveMaxTry; iz++) {
            for (let ix = 0; ix < bestGridNX && placed < effectiveMaxTry; ix++) {
                if (abortSignal?.aborted) throw abortError();
                await maybeYield();

                // Piece center — starts flush with corner (0,0)
                const posX = ix * bestStepX + gSX / 2;
                const posZ = iz * bestStepZ + gSZ / 2;
                const baseH = 0;

                // Grid positions are mathematically non-overlapping (step ≥ size),
                // so we SKIP the BVH collision check — it would only produce
                // false-positive rejections where bounding boxes exactly touch.
                tmpMatB.makeTranslation(posX, baseH, posZ);
                tmpBox.copy(gridOd.localBbox).applyMatrix4(tmpMatB);

                // Render
                if (!dryRun) {
                    const im = instancedMeshes[bestGridOi];
                    const idx = orientCounts[bestGridOi];
                    tmpObj.position.set(posX, baseH, posZ);
                    tmpObj.rotation.set(0, 0, 0);
                    tmpObj.updateMatrix();
                    im.setMatrixAt(idx, tmpObj.matrix);
                    im.setColorAt(idx, new THREE.Color(this.pieceColors[placed % numColors]));
                    positionsOut.push(new THREE.Vector3(posX, baseH, posZ));
                }

                orientCounts[bestGridOi]++;
                placedAabbs.push(tmpBox.clone());
                placedMatrices.push(tmpMatB.clone());
                placedOrientIdxs.push(bestGridOi);

                // Update heightmap (floor-based cell mapping)
                const hgx = Math.floor((posX - gSX / 2) / cellSize);
                const hgz = Math.floor((posZ - gSZ / 2) / cellSize);
                firstLayerSlots.push({ hgx, hgz, posX, posZ, oi: bestGridOi });
                for (let pz = 0; pz < gPNZ; pz++) {
                    for (let px = 0; px < gPNX; px++) {
                        const pIdx = pz * gPNX + px;
                        if (!gMask[pIdx]) continue;
                        const hx = hgx + px, hz = hgz + pz;
                        if (hx < 0 || hx >= gridNX || hz < 0 || hz >= gridNZ) continue;
                        const hIdx = hz * gridNX + hx;
                        const top = baseH + gPH[pIdx];
                        if (top > heightMap[hIdx]) heightMap[hIdx] = top;
                    }
                }

                placed++;
                if (onProgress && (placed % 5) === 0) {
                    onProgress({ placed, maxTry: effectiveMaxTry });
                }
            }
        }

        if (runStableContact && orientData.length > 1 && placed < effectiveMaxTry) {
            let floorFilled = 0;

            while (placed < effectiveMaxTry) {
                if (abortSignal?.aborted) throw abortError();
                await maybeYield();

                let bestFloorScore = Infinity;
                let bestFloorOi = -1;
                let bestFloorGX = -1;
                let bestFloorGZ = -1;

                for (let oi = 1; oi < orientData.length; oi++) {
                    const od = orientData[oi];
                    const { pieceNX, pieceNZ, pieceMask: mask, pieceHeights: pH, sizeX: sx, sizeZ: sz } = od;

                    for (let gz = 0; gz <= gridNZ - pieceNZ; gz++) {
                        for (let gx = 0; gx <= gridNX - pieceNX; gx++) {
                            let baseH = 0;
                            for (let pz = 0; pz < pieceNZ; pz++) {
                                for (let px = 0; px < pieceNX; px++) {
                                    const pIdx = pz * pieceNX + px;
                                    if (!mask[pIdx]) continue;
                                    const hIdx = (gz + pz) * gridNX + (gx + px);
                                    if (heightMap[hIdx] > baseH) baseH = heightMap[hIdx];
                                }
                            }

                            if (baseH > heightEps) continue;
                            if (gx * cellSize + sx > boxL || gz * cellSize + sz > boxW) continue;

                            let fits = true;
                            for (let pz = 0; pz < pieceNZ && fits; pz++) {
                                for (let px = 0; px < pieceNX; px++) {
                                    const pIdx = pz * pieceNX + px;
                                    if (!mask[pIdx]) continue;
                                    if (pH[pIdx] + heightEps > boxH) {
                                        fits = false;
                                        break;
                                    }
                                }
                            }
                            if (!fits) continue;

                            const posX = gx * cellSize + sx / 2;
                            const posZ = gz * cellSize + sz / 2;
                            tmpMatB.makeTranslation(posX, 0, posZ);
                            tmpBox.copy(od.localBbox).applyMatrix4(tmpMatB);
                            if (candidateIntersectsAny(tmpMatB, tmpBox, oi)) continue;

                            const score = _packingScore(0, gx, gz, od, heightMap, gridNX, gridNZ, placed, boxH);
                            if (score >= bestFloorScore) continue;

                            bestFloorScore = score;
                            bestFloorOi = oi;
                            bestFloorGX = gx;
                            bestFloorGZ = gz;
                        }
                    }
                }

                if (bestFloorOi < 0) break;

                const od = orientData[bestFloorOi];
                const { pieceNX, pieceNZ, pieceMask: mask, pieceHeights: pH, sizeX: sx, sizeZ: sz } = od;
                const posX = bestFloorGX * cellSize + sx / 2;
                const posZ = bestFloorGZ * cellSize + sz / 2;
                tmpMatB.makeTranslation(posX, 0, posZ);
                tmpBox.copy(od.localBbox).applyMatrix4(tmpMatB);

                if (!dryRun) {
                    const im = instancedMeshes[bestFloorOi];
                    const idx = orientCounts[bestFloorOi];
                    tmpObj.position.set(posX, 0, posZ);
                    tmpObj.rotation.set(0, 0, 0);
                    tmpObj.updateMatrix();
                    im.setMatrixAt(idx, tmpObj.matrix);
                    im.setColorAt(idx, new THREE.Color(this.pieceColors[placed % numColors]));
                    positionsOut.push(new THREE.Vector3(posX, 0, posZ));
                }

                orientCounts[bestFloorOi]++;
                placedAabbs.push(tmpBox.clone());
                placedMatrices.push(tmpMatB.clone());
                placedOrientIdxs.push(bestFloorOi);

                // Record slot for Phase 1B replication
                const floorHgx = Math.floor((posX - sx / 2) / cellSize);
                const floorHgz = Math.floor((posZ - sz / 2) / cellSize);
                firstLayerSlots.push({ hgx: floorHgx, hgz: floorHgz, posX, posZ, oi: bestFloorOi });

                for (let pz = 0; pz < pieceNZ; pz++) {
                    for (let px = 0; px < pieceNX; px++) {
                        const pIdx = pz * pieceNX + px;
                        if (!mask[pIdx]) continue;
                        const hIdx = (bestFloorGZ + pz) * gridNX + (bestFloorGX + px);
                        const top = pH[pIdx];
                        if (top > heightMap[hIdx]) heightMap[hIdx] = top;
                    }
                }

                placed++;
                floorFilled++;
            }

            if (floorFilled > 0) {
                console.log(`[HeightMapAsync] Floor fill: +${floorFilled} pieces`);
            }
        }

        const firstLayerCount = placed;
        console.log(`[HeightMapAsync] First layer: ${placed} pieces (grid ${bestGridNX}×${bestGridNZ}, orient${bestGridOi})`);

        // ═══════════════ PHASE 1B: REPLICATE FIRST-LAYER LAYOUT UPWARD ═══════════════
        // Reuse first-layer slots for all strategies because they are the most obvious,
        // dense upper placements. Non-legacy modes still require support and collision
        // checks before accepting each repeated slot.
        while (placed < effectiveMaxTry) {
            if (abortSignal?.aborted) throw abortError();
            let replicatedThisLayer = 0;

            for (const slot of firstLayerSlots) {
                if (placed >= effectiveMaxTry) break;
                await maybeYield();

                const slotOi = slot.oi ?? bestGridOi;
                const slotOd = orientData[slotOi];
                const {
                    pieceNX: slotPNX,
                    pieceNZ: slotPNZ,
                    pieceMask: slotMask,
                    pieceHeights: slotPH
                } = slotOd;

                let baseH = 0;
                for (let pz = 0; pz < slotPNZ; pz++) {
                    for (let px = 0; px < slotPNX; px++) {
                        const pIdx = pz * slotPNX + px;
                        if (!slotMask[pIdx]) continue;
                        const hx1b = slot.hgx + px, hz1b = slot.hgz + pz;
                        if (hx1b < 0 || hx1b >= gridNX || hz1b < 0 || hz1b >= gridNZ) continue;
                        const hIdx = hz1b * gridNX + hx1b;
                        if (heightMap[hIdx] > baseH) baseH = heightMap[hIdx];
                    }
                }

                let fits = true;
                for (let pz = 0; pz < slotPNZ && fits; pz++) {
                    for (let px = 0; px < slotPNX; px++) {
                        const pIdx = pz * slotPNX + px;
                        if (!slotMask[pIdx]) continue;
                        if (baseH + slotPH[pIdx] + heightEps > boxH) {
                            fits = false;
                            break;
                        }
                    }
                }
                if (!fits) continue;

                tmpMatB.makeTranslation(slot.posX, baseH, slot.posZ);
                tmpBox.copy(slotOd.localBbox).applyMatrix4(tmpMatB);

                if (!isLegacyStrategy && baseH > heightEps) {
                    if (candidateIntersectsAny(tmpMatB, tmpBox, slotOi)) continue;
                }

                if (!dryRun) {
                    const im = instancedMeshes[slotOi];
                    const idx = orientCounts[slotOi];
                    tmpObj.position.set(slot.posX, baseH, slot.posZ);
                    tmpObj.rotation.set(0, 0, 0);
                    tmpObj.updateMatrix();
                    im.setMatrixAt(idx, tmpObj.matrix);
                    im.setColorAt(idx, new THREE.Color(this.pieceColors[placed % numColors]));
                    positionsOut.push(new THREE.Vector3(slot.posX, baseH, slot.posZ));
                }

                orientCounts[slotOi]++;
                placedAabbs.push(tmpBox.clone());
                placedMatrices.push(tmpMatB.clone());
                placedOrientIdxs.push(slotOi);

                for (let pz = 0; pz < slotPNZ; pz++) {
                    for (let px = 0; px < slotPNX; px++) {
                        const pIdx = pz * slotPNX + px;
                        if (!slotMask[pIdx]) continue;
                        const hxW = slot.hgx + px, hzW = slot.hgz + pz;
                        if (hxW < 0 || hxW >= gridNX || hzW < 0 || hzW >= gridNZ) continue;
                        const hIdx = hzW * gridNX + hxW;
                        const top = baseH + slotPH[pIdx];
                        if (top > heightMap[hIdx]) heightMap[hIdx] = top;
                    }
                }

                placed++;
                replicatedThisLayer++;
                if (onProgress && (placed % 5) === 0) {
                    onProgress({ placed, maxTry: effectiveMaxTry });
                }
            }

            if (replicatedThisLayer === 0) break;
            console.log(`[HeightMapAsync] Replicated stable layer: +${replicatedThisLayer} pieces`);
        }

        // ═══════════════ PHASE 2: UPPER LAYERS — greedy heightmap scan ═══════════════
        while (placed < effectiveMaxTry) {
            if (abortSignal?.aborted) throw abortError();
            await maybeYield();

            // Scan every (orientation × grid position) and pick the single best
            let bestScore = Infinity;
            let bestOi = -1, bestGX = -1, bestGZ = -1, bestBaseH = Infinity;
            let bestSupport = null;

            const supportProfilesToTry = (!runStableContact || isLegacyStrategy)
                ? [activeStability]
                : (placementStrategy === 'physics-assisted')
                    ? [activeStability, stabilityProfiles.medium, stabilityProfiles.loose]
                    : (placementStrategy === 'hybrid')
                        ? [activeStability, stabilityProfiles.medium]
                        : [activeStability];

            for (let oi = 0; oi < orientData.length; oi++) {
                const od = orientData[oi];
                const { pieceNX, pieceNZ, pieceMask: mask, pieceHeights: pH,
                        sizeX: sx, sizeY: sy, sizeZ: sz } = od;

                if (!allowMixedUpperLayers && placed >= firstLayerCount && oi !== bestGridOi) {
                    continue;
                }

                for (let gz = 0; gz <= gridNZ - pieceNZ; gz++) {
                    for (let gx = 0; gx <= gridNX - pieceNX; gx++) {
                        if (((gx + gz) & 255) === 0) {
                            await maybeYield();
                            if (onProgress) onProgress({ placed, maxTry: effectiveMaxTry });
                        }

                        if (gx * cellSize + sx > boxL || gz * cellSize + sz > boxW) continue;

                        // Mask-filtered heightmap read
                        let baseH = 0;
                        for (let pz = 0; pz < pieceNZ; pz++) {
                            for (let px = 0; px < pieceNX; px++) {
                                const pIdx = pz * pieceNX + px;
                                if (!mask[pIdx]) continue;
                                const hIdx = (gz + pz) * gridNX + (gx + px);
                                if (heightMap[hIdx] > baseH) baseH = heightMap[hIdx];
                            }
                        }

                        // Height check
                        let fits = true;
                        for (let pz = 0; pz < pieceNZ && fits; pz++) {
                            for (let px = 0; px < pieceNX; px++) {
                                const pIdx = pz * pieceNX + px;
                                if (!mask[pIdx]) continue;
                                const extraClearance = baseH > heightEps ? stackedClearance : 0;
                                if (baseH + pH[pIdx] + extraClearance + heightEps > boxH) { fits = false; break; }
                            }
                        }
                        if (!fits) continue;

                        let supportInfo = null;
                        if (runStableContact && !isLegacyStrategy && baseH > heightEps) {
                            for (const supportProfile of supportProfilesToTry) {
                                const evaluated = evaluateSupport(gx, gz, od, baseH, supportProfile, useSettleCheck);
                                if (evaluated.supported) {
                                    supportInfo = evaluated;
                                    break;
                                }
                            }
                            if (!supportInfo) continue;
                            if (placementStrategy === 'stable-contact') {
                                if (supportInfo.supportRatio < 0.88) continue;
                                if (supportInfo.drift > 0.24) continue;
                            }
                        }

                        const supportBonus = supportInfo ? supportInfo.supportRatio * 0.25 : 0;
                        const score = _packingScore(baseH, gx, gz, od, heightMap, gridNX, gridNZ, placed, boxH) - supportBonus;
                        if (score >= bestScore) continue;

                        bestScore = score;
                        bestOi = oi;
                        bestGX = gx;
                        bestGZ = gz;
                        bestBaseH = baseH;
                        bestSupport = supportInfo;
                    }
                }
            }

            if (bestOi < 0) break;

            const od = orientData[bestOi];
            const { pieceNX, pieceNZ, pieceMask: mask, pieceHeights: pH,
                    sizeX: sx, sizeY: sy, sizeZ: sz } = od;

            // BVH collision check
            const posX = bestGX * cellSize + sx / 2;
            const posZ = bestGZ * cellSize + sz / 2;
            tmpMatB.makeTranslation(posX, bestBaseH, posZ);
            tmpBox.copy(od.localBbox).applyMatrix4(tmpMatB);

            if (candidateIntersectsAny(tmpMatB, tmpBox, bestOi)) {
                for (let pz = 0; pz < pieceNZ; pz++) {
                    for (let px = 0; px < pieceNX; px++) {
                        const pIdx = pz * pieceNX + px;
                        if (!mask[pIdx]) continue;
                        const hIdx = (bestGZ + pz) * gridNX + (bestGX + px);
                        const newH = bestBaseH + Math.max(cellSize, od.sizeY * 0.2);
                        if (newH > heightMap[hIdx]) heightMap[hIdx] = newH;
                    }
                }
                consecutiveSkips++;
                if (consecutiveSkips > maxConsecutiveSkips) break;
                continue;
            }

            if (runStableContact && !isLegacyStrategy && bestBaseH > heightEps && bestSupport && !bestSupport.supported) {
                consecutiveSkips++;
                if (consecutiveSkips > maxConsecutiveSkips) break;
                continue;
            }
            consecutiveSkips = 0;

            // Place piece
            if (!dryRun) {
                const im = instancedMeshes[bestOi];
                const idx = orientCounts[bestOi];
                tmpObj.position.set(posX, bestBaseH, posZ);
                tmpObj.rotation.set(0, 0, 0);
                tmpObj.updateMatrix();
                im.setMatrixAt(idx, tmpObj.matrix);
                im.setColorAt(idx, new THREE.Color(this.pieceColors[placed % numColors]));
                positionsOut.push(new THREE.Vector3(posX, bestBaseH, posZ));
            }

            orientCounts[bestOi]++;
            placedAabbs.push(tmpBox.clone());
            placedMatrices.push(tmpMatB.clone());
            placedOrientIdxs.push(bestOi);

            for (let pz = 0; pz < pieceNZ; pz++) {
                for (let px = 0; px < pieceNX; px++) {
                    const pIdx = pz * pieceNX + px;
                    if (!mask[pIdx]) continue;
                    const hIdx = (bestGZ + pz) * gridNX + (bestGX + px);
                    const top = bestBaseH + pH[pIdx];
                    if (top > heightMap[hIdx]) heightMap[hIdx] = top;
                }
            }

            placed++;
            if (onProgress && (placed % 5) === 0) {
                onProgress({ placed, maxTry: effectiveMaxTry });
            }
        }

        // ── Debug stats ──
        const hmMin = Math.min(...heightMap);
        const hmMax = Math.max(...heightMap);
        const orientBreakdown = orientCounts.map((c, i) => `orient${i}=${c}`).join(', ');
        console.log(`[HeightMapAsync] placed=${placed} (${orientBreakdown}), maxTry=${effectiveMaxTry}, skips=${consecutiveSkips}`);
        console.log(`[HeightMapAsync] heightMap range: [${hmMin.toFixed(1)}, ${hmMax.toFixed(1)}], utilization: ${(hmMax / boxH * 100).toFixed(1)}%`);

        if (!dryRun) {
            for (let oi = 0; oi < instancedMeshes.length; oi++) {
                const im = instancedMeshes[oi];
                const cnt = orientCounts[oi];
                im.count = cnt;
                im.instanceMatrix.needsUpdate = true;
                if (im.instanceColor) im.instanceColor.needsUpdate = true;
                if (cnt > 0) {
                    this.scene.add(im);
                    this.pieces.push(im);
                }
            }

            this.lastPlacement = {
                type: 'stl',
                dims: { l: primary.sizeX, w: primary.sizeZ, h: primary.sizeY },
                geometry: primary.geometry,
                vertices: primary.positions ? new Float32Array(primary.positions.array) : null,
                positions: positionsOut,
                boxDims: { l: boxL, w: boxW, h: boxH }
            };
        }

        return { count: placed };
    }

    /**
     * Add a single STL piece at a position
     * @param {THREE.BufferGeometry} geometry
     * @param {THREE.Vector3} position
     * @param {THREE.Euler} rotation
     * @returns {THREE.Mesh}
     */
    addSTLPiece(geometry, position, rotation = null) {
        const material = new THREE.MeshPhongMaterial({
            color: 0x3b82f6,
            opacity: 0.9,
            transparent: true,
            flatShading: true
        });

        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(geometry.clone(), material);
        mesh.position.copy(position);
        if (rotation) mesh.rotation.copy(rotation);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        this.scene.add(mesh);
        this.pieces.push(mesh);

        return mesh;
    }

    /**
     * Focus camera on the box
     */
    focusOnBox(length, width, height) {
        const center = new THREE.Vector3(length / 2, height / 2, width / 2);
        const maxDim = Math.max(length, width, height);
        
        this.controls.target.copy(center);
        this.camera.position.set(
            center.x + maxDim * 1.5,
            center.y + maxDim * 1.2,
            center.z + maxDim * 1.5
        );
        this.controls.update();
    }

    /**
     * Set camera to a preset view
     * @param {string} view - 'iso', 'isometric', 'top', 'front', 'right', 'side', 'back', 'left', 'bottom'
     */
    setView(view) {
        if (!this.boxMesh) return;

        const box = new THREE.Box3().setFromObject(this.boxMesh);
        const center = new THREE.Vector3();
        const size = new THREE.Vector3();
        box.getCenter(center);
        box.getSize(size);
        
        const maxDim = Math.max(size.x, size.y, size.z);
        const distance = maxDim * 2.5;

        const positions = {
            iso: new THREE.Vector3(distance, distance, distance),
            isometric: new THREE.Vector3(distance, distance, distance),
            top: new THREE.Vector3(0, distance * 1.5, 0.01), // Slight offset to avoid gimbal lock
            front: new THREE.Vector3(0, distance * 0.3, distance),
            right: new THREE.Vector3(distance, distance * 0.3, 0),
            side: new THREE.Vector3(distance, distance * 0.3, 0),
            back: new THREE.Vector3(0, distance * 0.3, -distance),
            left: new THREE.Vector3(-distance, distance * 0.3, 0),
            bottom: new THREE.Vector3(0, -distance * 1.5, 0.01)
        };

        const pos = positions[view] || positions.iso;
        this.camera.position.set(
            center.x + pos.x,
            center.y + pos.y,
            center.z + pos.z
        );
        this.controls.target.copy(center);
        this.controls.update();
    }

    /**
     * Toggle fullscreen mode
     */
    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this.container.requestFullscreen?.() ||
            this.container.webkitRequestFullscreen?.() ||
            this.container.mozRequestFullScreen?.();
        } else {
            document.exitFullscreen?.() ||
            document.webkitExitFullscreen?.() ||
            document.mozCancelFullScreen?.();
        }
    }

    onResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    /**
     * Stop animation loop and clean up
     */
    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        
        this.clearPieces();
        
        if (this.boxMesh) {
            this.scene.remove(this.boxMesh);
            this.boxMesh.geometry.dispose();
            this.boxMesh.material.dispose();
        }

        this.scene.traverse((object) => {
            if (object.geometry) object.geometry.dispose();
            if (object.material) {
                if (Array.isArray(object.material)) {
                    object.material.forEach(m => m.dispose());
                } else {
                    object.material.dispose();
                }
            }
        });

        this.renderer.dispose();
        this.container.removeChild(this.renderer.domElement);

        window.removeEventListener('resize', this.onResize);
    }
}

export default SceneManager;
