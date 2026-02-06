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
    addPackedSTLHeightMap({ stlGeometry, maxDraw = 500, packingGap = 0, colorCount = null, boxL = null, boxW = null, boxH = null, dryRun = false }) {
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

        // Build BVH once for robust intersection testing
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

        // Keep footprint mask exact; collisions are handled via BVH checks
        const expandedMask = pieceMask;

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

        // Cache for fast broadphase + precise intersection
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

        const aabbInflatedOverlaps = (a, b, inflate = 0) => {
            return !(
                (a.max.x + inflate) < (b.min.x - inflate) ||
                (a.min.x - inflate) > (b.max.x + inflate) ||
                (a.max.y + inflate) < (b.min.y - inflate) ||
                (a.min.y - inflate) > (b.max.y + inflate) ||
                (a.max.z + inflate) < (b.min.z - inflate) ||
                (a.min.z - inflate) > (b.max.z + inflate)
            );
        };

        const candidateIntersectsAny = (candidateMatrix, candidateAabb) => {
            if (!geometry.boundsTree) return false;

            // Broadphase (inflated AABB for user gap)
            const inflate = Math.max(0, packingGap * 0.5);
            for (let i = 0; i < placedAabbs.length; i++) {
                const otherAabb = placedAabbs[i];
                if (!aabbInflatedOverlaps(candidateAabb, otherAabb, inflate)) continue;

                // Precise: BVH intersectsGeometry with relative transform
                const otherMatrix = placedMatrices[i];
                tmpInv.copy(otherMatrix).invert();
                tmpMatA.multiplyMatrices(tmpInv, candidateMatrix);
                if (geometry.boundsTree.intersectsGeometry(geometry, tmpMatA)) {
                    return true;
                }
            }
            return false;
        };

        const maxTry = maxDraw;
        let collisionSkips = 0;
        const maxCollisionSkips = Math.max(50, maxTry * 3);

        while (placed < maxTry) {
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
                            const top = baseH + pieceHeights[pIdx];
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

            // Build candidate transform + AABB
            const posX = bestX * cellSize + sizeX / 2;
            const posZ = bestZ * cellSize + sizeZ / 2;
            const posY = bestH;
            tmpMatB.makeTranslation(posX, posY, posZ);
            tmpBox.copy(localBbox).applyMatrix4(tmpMatB);

            // Box boundary clamp (defensive)
            const tol = 0.0001;
            if (
                tmpBox.min.x < -tol || tmpBox.min.y < -tol || tmpBox.min.z < -tol ||
                tmpBox.max.x > boxL + tol || tmpBox.max.y > boxH + tol || tmpBox.max.z > boxW + tol
            ) {
                // Mark this footprint as blocked and retry
                const bump = Math.max(0.5, Math.min(sizeY, Math.max(cellSize, packingGap, sizeY * 0.05)));
                const blockTop = Math.min(boxH, bestH + bump);
                for (let pz = 0; pz < pieceNZ; pz++) {
                    for (let px = 0; px < pieceNX; px++) {
                        const pIdx = pz * pieceNX + px;
                        if (!expandedMask[pIdx]) continue;
                        const hIdx = (bestZ + pz) * gridNX + (bestX + px);
                        if (blockTop > heightMap[hIdx]) heightMap[hIdx] = blockTop;
                    }
                }
                if (++collisionSkips > maxCollisionSkips) break;
                continue;
            }

            // Collision check against already placed pieces
            if (candidateIntersectsAny(tmpMatB, tmpBox)) {
                // Block this footprint at this height and retry a different spot
                const bump = Math.max(0.5, Math.min(sizeY, Math.max(cellSize, packingGap, sizeY * 0.08)));
                const blockTop = Math.min(boxH, bestH + bump);
                for (let pz = 0; pz < pieceNZ; pz++) {
                    for (let px = 0; px < pieceNX; px++) {
                        const pIdx = pz * pieceNX + px;
                        if (!expandedMask[pIdx]) continue;
                        const hIdx = (bestZ + pz) * gridNX + (bestX + px);
                        if (blockTop > heightMap[hIdx]) heightMap[hIdx] = blockTop;
                    }
                }

                if (++collisionSkips > maxCollisionSkips) break;
                continue;
            }

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

            // Cache placement for subsequent collision checks
            placedAabbs.push(tmpBox.clone());
            placedMatrices.push(tmpMatB.clone());

            // Update height map
            for (let pz = 0; pz < pieceNZ; pz++) {
                for (let px = 0; px < pieceNX; px++) {
                    const pIdx = pz * pieceNX + px;
                    if (!expandedMask[pIdx]) continue;
                    const hIdx = (bestZ + pz) * gridNX + (bestX + px);
                    const top = bestH + pieceHeights[pIdx] + packingGap;
                    if (top > heightMap[hIdx]) heightMap[hIdx] = top;
                }
            }

            placed++;
        }

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
