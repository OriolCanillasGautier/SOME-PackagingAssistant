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

/**
 * Compute placement score for heightmap packing.
 * Lower score = better placement.
 * Strategy:
 *   - Fill lowest positions first (baseH * 1000)
 *   - Gentle adjacency bonus (density without excessive clustering)
 *   - Wall-proximity bonus (fill edges first for stability)
 *   - Stability bonus on ground layer (prefer larger footprint orientations)
 *   - Small layer-balance penalty (discourage going too high too fast)
 */
function _packingScore(baseH, gx, gz, od, heightMap, gridNX, gridNZ, placed, boxH) {
    const { pieceNX, pieceNZ } = od;

    // Primary: strongly prefer lower base height (fill floor, then stack)
    let score = baseH * 1000;

    // Layer-balance: small penalty that grows with height.
    // Prevents the algorithm from being too greedy about filling
    // a single column all the way up before moving to the next.
    if (boxH > 0) {
        score += (baseH / boxH) * 5;
    }

    // Stability bonus: on the ground layer (baseH ≈ 0), prefer orientations
    // with a larger base footprint (more stable under gravity).
    if (baseH < 0.5 && od.footprintArea) {
        // Normalise: larger footprint → lower score → preferred.
        // Max footprint ≈ sizeX * sizeZ, so normalise against that.
        const maxFP = od.sizeX * od.sizeZ;
        const fpRatio = maxFP > 0 ? od.footprintArea / maxFP : 0;
        score -= fpRatio * 2;  // up to -2 bonus for full-footprint orientations
    }

    // Gentle adjacency bonus: prefer positions next to already-placed pieces
    // (density), but not so strong it causes excessive clustering.
    let adjacentOccupied = 0;
    if (gx > 0) {
        for (let pz = 0; pz < pieceNZ; pz++) {
            if (heightMap[(gz + pz) * gridNX + (gx - 1)] > 0) adjacentOccupied++;
        }
    }
    if (gx + pieceNX < gridNX) {
        for (let pz = 0; pz < pieceNZ; pz++) {
            if (heightMap[(gz + pz) * gridNX + (gx + pieceNX)] > 0) adjacentOccupied++;
        }
    }
    if (gz > 0) {
        for (let px = 0; px < pieceNX; px++) {
            if (heightMap[(gz - 1) * gridNX + (gx + px)] > 0) adjacentOccupied++;
        }
    }
    if (gz + pieceNZ < gridNZ) {
        for (let px = 0; px < pieceNX; px++) {
            if (heightMap[(gz + pieceNZ) * gridNX + (gx + px)] > 0) adjacentOccupied++;
        }
    }
    score -= adjacentOccupied * 0.15;

    // Wall-proximity bonus: prefer positions touching container walls
    // for more stable, efficient packing (fill from edges inward).
    let wallBonus = 0;
    if (gx === 0) wallBonus++;
    if (gz === 0) wallBonus++;
    if (gx + pieceNX >= gridNX - 1) wallBonus++;
    if (gz + pieceNZ >= gridNZ - 1) wallBonus++;
    score -= wallBonus * 0.3;

    // Tie-break: prefer positions closer to origin (consistent, predictable fill)
    score += (gx + gz) * 0.01;

    return score;
}

/**
 * Build orientation data (heightmap, mask, BVH) for a single piece geometry.
 * Returns null if piece does not fit in box.
 */
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

    // Align base to y=0 and center in X/Z
    geometry.translate(-center.x, -bbox.min.y, -center.z);

    // Build BVH for lateral collision testing
    if (typeof geometry.computeBoundsTree === 'function') {
        geometry.computeBoundsTree();
    }

    const positions = geometry.getAttribute('position');
    const vertexCount = positions ? positions.count : 0;
    if (!positions || vertexCount === 0) return null;

    const pieceNX = Math.max(1, Math.ceil(sizeX / cellSize));
    const pieceNZ = Math.max(1, Math.ceil(sizeZ / cellSize));
    const pieceHeights = new Float32Array(pieceNX * pieceNZ);
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
        if (y > pieceHeights[idx]) pieceHeights[idx] = y;
        if (y <= minY + baseEps) pieceMask[idx] = 1;
        if ((i & 4095) === 0) await maybeYield();
    }

    const localBbox = new THREE.Box3(
        new THREE.Vector3(-sizeX / 2, 0, -sizeZ / 2),
        new THREE.Vector3(sizeX / 2, sizeY, sizeZ / 2)
    );

    // Compute base footprint area: count how many cells have base-contact
    // vertices. Larger footprint = more stable placement on ground.
    let baseCellCount = 0;
    for (let i = 0; i < pieceMask.length; i++) {
        if (pieceMask[i]) baseCellCount++;
    }
    const footprintArea = baseCellCount * cellSize * cellSize;

    return {
        geometry, positions, sizeX, sizeY, sizeZ,
        pieceNX, pieceNZ, pieceHeights, pieceMask, localBbox,
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
        const heightEps = Math.max(0.1, packingGap * 0.1);

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

        // Keep footprint mask exact
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
            // Contact tolerance: ignore face-touching (coplanar triangle false positives)
            const ct = 0.15;
            for (let i = 0; i < placedAabbs.length; i++) {
                const o = placedAabbs[i];
                if ((candidateAabb.max.x - ct) <= (o.min.x + ct) ||
                    (candidateAabb.min.x + ct) >= (o.max.x - ct) ||
                    (candidateAabb.max.y - ct) <= (o.min.y + ct) ||
                    (candidateAabb.min.y + ct) >= (o.max.y - ct) ||
                    (candidateAabb.max.z - ct) <= (o.min.z + ct) ||
                    (candidateAabb.min.z + ct) >= (o.max.z - ct)) continue;
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
                    const top = bestH + pieceHeights[pIdx] + packingGap;
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
     * Async + abortable heightmap packing with multi-orientation gap filling.
     * Yields to the browser regularly to keep UI responsive and to allow cancellation.
     *
     * Supports multiple piece orientations: the primary geometry plus any number
     * of alternate orientations. At each placement step the algorithm evaluates
     * ALL orientations at ALL grid positions, picking the one with the best
     * packing score (lowest height, gap-filling bonus, wall alignment).
     *
     * @param {Object} params
     * @param {THREE.BufferGeometry} params.stlGeometry - primary orientation
     * @param {Array<{geometry:THREE.BufferGeometry}>} [params.alternateOrientations] - extra orientations to try
     * @param {number} [params.maxDraw=500]
     * @param {number} [params.packingGap=0]
     * @param {number} [params.colorCount]
     * @param {number} params.boxL
     * @param {number} params.boxW
     * @param {number} params.boxH
     * @param {boolean} [params.singleLayer=false] - When true, only pack the first layer (floor)
     * @param {boolean} [params.replicateFirstLayer=false] - Pack first layer greedily, then replicate pattern upward
     * @param {boolean} [params.dryRun=false]
     * @param {AbortSignal} [params.abortSignal]
     * @param {(p:{placed:number,maxTry:number})=>void} [params.onProgress]
     * @param {number} [params.cellSizeOverride] - If provided, use this cell size instead of computing from geometry
     */
    async addPackedSTLHeightMapAsync({
        stlGeometry,
        alternateOrientations = [],
        maxDraw = 500,
        maxTry = null,
        packingGap = 0,
        colorCount = null,
        boxL = null,
        boxW = null,
        boxH = null,
        singleLayer = false,
        replicateFirstLayer = false,
        dryRun = false,
        abortSignal = null,
        onProgress = null,
        cellSizeOverride = null
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

        if (!dryRun) {
            this.clearPieces();
        }

        if (boxL === null || boxW === null || boxH === null) {
            return this.addPackedSTLPieces({
                stlGeometry,
                pieceL: 0, pieceW: 0, pieceH: 0,
                nx: 0, ny: 0, nz: 0,
                maxDraw, packingGap, colorCount,
                boxL, boxW, boxH,
                strictGeometryCheck: true
            });
        }

        const numColors = colorCount || this.colorCount;

        // --- Build orientation data for primary + alternates ---
        // Use cellSizeOverride if provided (ensures dry-run and final pack use
        // the same grid resolution). Otherwise compute from primary geometry.
        stlGeometry.computeBoundingBox();
        const primBbox = stlGeometry.boundingBox;
        const primSX = primBbox.max.x - primBbox.min.x;
        const primSZ = primBbox.max.z - primBbox.min.z;
        const cellSize = (typeof cellSizeOverride === 'number' && Number.isFinite(cellSizeOverride))
            ? cellSizeOverride
            : Math.max(1, Math.min(4, Math.min(primSX, primSZ) / 20));

        // Build orientation data array
        const allSrcGeometries = [stlGeometry, ...alternateOrientations.map(a => a.geometry).filter(Boolean)];
        const orientData = [];
        for (const src of allSrcGeometries) {
            const od = await _buildOrientData(src, cellSize, boxL, boxW, boxH, maybeYield);
            if (od) orientData.push(od);
        }

        if (orientData.length === 0) return { count: 0 };
        console.log(`[HeightMapAsync] ${orientData.length} orientation(s) prepared (cell=${cellSize.toFixed(1)}mm)`);

        // Use primary orientation for volume estimate
        const primary = orientData[0];
        const heightEps = Math.max(0.1, packingGap * 0.1);

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
        const pieceDataOut = dryRun ? null : []; // per-piece orientation metadata
        let placed = 0;

        // AABB collision array: stores every placed piece's world bounding box
        // so the scan loop can reject candidates that physically overlap.
        const placedAABBs = [];  // { minX, minY, minZ, maxX, maxY, maxZ }
        const aabbCT = 0.05;     // contact tolerance — allow face-touching

        let consecutiveSkips = 0;
        const maxConsecutiveSkips = Math.max(500, gridNX * gridNZ * 2);

        // --- Replicate-first-layer state ---
        // When replicateFirstLayer is active, we run the normal greedy scan for
        // the ground layer only, then stamp the same pattern at each subsequent
        // layer height until the box is full or maxDraw is reached.
        const firstLayerPlacements = [];  // { gx, gz, orientIdx }
        let replicatePhase = false;       // true once we start replicating

        // --- Rendering: one InstancedMesh per orientation ---
        const instancedMeshes = [];
        const orientCounts = new Array(orientData.length).fill(0);
        const tmpObj = new THREE.Object3D();
        if (!dryRun) {
            for (const od of orientData) {
                const im = new THREE.InstancedMesh(od.geometry, material.clone(), maxDraw);
                im.castShadow = true;
                im.receiveShadow = true;
                instancedMeshes.push(im);
            }
        }

        // ===== MAIN PLACEMENT LOOP (capped by maxDraw = weight limit) =====
        while (placed < maxDraw) {
            if (abortSignal?.aborted) throw abortError();
            await maybeYield();

            // ---------------------------------------------------------------
            // REPLICATE-FIRST-LAYER PHASE
            // Once the first layer is complete, stamp the same pattern at
            // successive heights until the box is full or maxDraw is reached.
            // ---------------------------------------------------------------
            if (replicatePhase) {
                let layerPlaced = 0;
                for (const fp of firstLayerPlacements) {
                    if (placed >= maxDraw) break;
                    if (abortSignal?.aborted) throw abortError();
                    await maybeYield();

                    const od = orientData[fp.orientIdx];
                    const { sizeX, sizeY, sizeZ, pieceNX, pieceNZ, pieceHeights } = od;

                    // Find base height at this XZ position
                    let baseH = 0;
                    for (let pz = 0; pz < pieceNZ; pz++) {
                        for (let px = 0; px < pieceNX; px++) {
                            const hIdx = (fp.gz + pz) * gridNX + (fp.gx + px);
                            if (heightMap[hIdx] > baseH) baseH = heightMap[hIdx];
                        }
                    }

                    // Height fit check
                    if (baseH + sizeY > boxH + heightEps) continue;

                    // AABB collision check
                    let collides = false;
                    const cMinX = fp.gx * cellSize + aabbCT;
                    const cMaxX = fp.gx * cellSize + sizeX - aabbCT;
                    const cMinY = baseH + aabbCT;
                    const cMaxY = baseH + sizeY - aabbCT;
                    const cMinZ = fp.gz * cellSize + aabbCT;
                    const cMaxZ = fp.gz * cellSize + sizeZ - aabbCT;
                    for (let pi = 0; pi < placedAABBs.length; pi++) {
                        const p = placedAABBs[pi];
                        if (cMaxX <= p.minX || cMinX >= p.maxX ||
                            cMaxY <= p.minY || cMinY >= p.maxY ||
                            cMaxZ <= p.minZ || cMinZ >= p.maxZ) continue;
                        collides = true;
                        break;
                    }
                    if (collides) continue;

                    // Place the piece
                    const posX = fp.gx * cellSize + sizeX / 2;
                    const posZ = fp.gz * cellSize + sizeZ / 2;
                    const posY = baseH;

                    if (!dryRun) {
                        const im = instancedMeshes[fp.orientIdx];
                        const idx = orientCounts[fp.orientIdx];
                        tmpObj.position.set(posX, posY, posZ);
                        tmpObj.rotation.set(0, 0, 0);
                        tmpObj.updateMatrix();
                        im.setMatrixAt(idx, tmpObj.matrix);
                        const colorIndex = placed % numColors;
                        const color = new THREE.Color(this.pieceColors[colorIndex]);
                        im.setColorAt(idx, color);
                        positionsOut.push(new THREE.Vector3(posX, posY, posZ));
                        pieceDataOut.push({ orientIdx: fp.orientIdx });
                    }
                    orientCounts[fp.orientIdx]++;

                    placedAABBs.push({
                        minX: fp.gx * cellSize,
                        maxX: fp.gx * cellSize + sizeX,
                        minY: baseH,
                        maxY: baseH + sizeY,
                        minZ: fp.gz * cellSize,
                        maxZ: fp.gz * cellSize + sizeZ
                    });

                    const top = baseH + sizeY + packingGap;
                    for (let pz = 0; pz < pieceNZ; pz++) {
                        for (let px = 0; px < pieceNX; px++) {
                            const hIdx = (fp.gz + pz) * gridNX + (fp.gx + px);
                            if (top > heightMap[hIdx]) heightMap[hIdx] = top;
                        }
                    }

                    placed++;
                    layerPlaced++;
                    if (onProgress && (placed % 5 === 0 || placed === maxDraw)) {
                        onProgress({ placed, maxTry: maxDraw });
                    }
                }

                // If no pieces could be placed this layer, we're done
                if (layerPlaced === 0) {
                    console.log(`[HeightMapAsync] Replicate phase complete: no more layers fit after ${placed} piece(s)`);
                    break;
                }
                // Otherwise continue the while loop to try the next layer
                continue;
            }

            // ---------------------------------------------------------------
            // GREEDY SCAN PHASE (first layer, or all layers if not replicating)
            // ---------------------------------------------------------------
            let bestScore = Infinity;
            let bestGX = -1;
            let bestGZ = -1;
            let bestBaseH = Infinity;
            let bestOrientIdx = -1;

            // Scan all orientations × all grid positions
            for (let oi = 0; oi < orientData.length; oi++) {
                const od = orientData[oi];
                const { pieceNX, pieceNZ, pieceMask, pieceHeights, sizeX, sizeY, sizeZ } = od;

                for (let gz = 0; gz <= gridNZ - pieceNZ; gz++) {
                    for (let gx = 0; gx <= gridNX - pieceNX; gx++) {
                        if (((gx + gz) & 511) === 0) {
                            await maybeYield();
                            if (onProgress) {
                                onProgress({ placed, maxTry: maxDraw });
                            }
                        }

                        // Bounds check
                        const x0 = gx * cellSize;
                        const z0 = gz * cellSize;
                        if (x0 + sizeX > boxL + 0.01 || z0 + sizeZ > boxW + 0.01) continue;

                        // Compute base height under the piece's exact footprint.
                        // The AABB collision check is the real safety net;
                        // heightmap just needs to be accurate for good density.
                        let baseH = 0;
                        for (let pz = 0; pz < pieceNZ; pz++) {
                            for (let px = 0; px < pieceNX; px++) {
                                const hIdx = (gz + pz) * gridNX + (gx + px);
                                if (heightMap[hIdx] > baseH) baseH = heightMap[hIdx];
                            }
                        }

                        // Quick height fit check: piece (full sizeY) must fit in box
                        if (baseH + sizeY > boxH + heightEps) continue;

                        // In replicate mode, only allow ground-layer placements
                        // during the greedy phase (first layer only).
                        if (replicateFirstLayer && baseH > 0.5) continue;

                        // Compute placement score (lower = better)
                        const score = _packingScore(
                            baseH, gx, gz, od, heightMap, gridNX, gridNZ, placed, boxH
                        );
                        if (score >= bestScore) continue;

                        // AABB collision check: verify candidate doesn't overlap
                        // any already-placed piece's bounding box.  This catches
                        // any residual overlap the heightmap might miss (e.g.
                        // multi-orientation footprint mismatch or float rounding).
                        let collides = false;
                        const cMinX = gx * cellSize + aabbCT;
                        const cMaxX = gx * cellSize + sizeX - aabbCT;
                        const cMinY = baseH + aabbCT;
                        const cMaxY = baseH + sizeY - aabbCT;
                        const cMinZ = gz * cellSize + aabbCT;
                        const cMaxZ = gz * cellSize + sizeZ - aabbCT;
                        for (let pi = 0; pi < placedAABBs.length; pi++) {
                            const p = placedAABBs[pi];
                            if (cMaxX <= p.minX || cMinX >= p.maxX ||
                                cMaxY <= p.minY || cMinY >= p.maxY ||
                                cMaxZ <= p.minZ || cMinZ >= p.maxZ) continue;
                            collides = true;
                            break;
                        }
                        if (collides) continue;

                        bestScore = score;
                        bestGX = gx;
                        bestGZ = gz;
                        bestBaseH = baseH;
                        bestOrientIdx = oi;
                    }
                }
            }

            // No valid position found for any orientation → layer/box is full
            if (bestOrientIdx < 0 || bestGX < 0 || bestGZ < 0) {
                // If replicate mode: first layer is done → switch to replication phase
                if (replicateFirstLayer && firstLayerPlacements.length > 0) {
                    console.log(`[HeightMapAsync] First layer complete: ${firstLayerPlacements.length} piece(s). Starting replication...`);
                    replicatePhase = true;
                    continue;  // re-enter while loop in replicate phase
                }
                break;
            }

            // Single-layer mode: stop when floor is completely filled
            if (singleLayer && bestBaseH > 0.5) {
                console.log(`[HeightMapAsync] Single-layer complete: floor full after ${placed} piece(s)`);
                break;
            }

            const od = orientData[bestOrientIdx];
            const { sizeX, sizeY, sizeZ, pieceNX, pieceNZ, pieceMask, pieceHeights } = od;

            // Compute world position
            const posX = bestGX * cellSize + sizeX / 2;
            const posZ = bestGZ * cellSize + sizeZ / 2;
            const posY = bestBaseH;

            // --- Place piece ---
            if (!dryRun) {
                const im = instancedMeshes[bestOrientIdx];
                const idx = orientCounts[bestOrientIdx]; // Note: orientCounts incremented below with cache
                tmpObj.position.set(posX, posY, posZ);
                tmpObj.rotation.set(0, 0, 0);
                tmpObj.updateMatrix();
                im.setMatrixAt(idx, tmpObj.matrix);

                const colorIndex = placed % numColors;
                const color = new THREE.Color(this.pieceColors[colorIndex]);
                im.setColorAt(idx, color);
                positionsOut.push(new THREE.Vector3(posX, posY, posZ));
                pieceDataOut.push({ orientIdx: bestOrientIdx });
            }

            // Track orient counts (used for rendering instance index)
            orientCounts[bestOrientIdx]++;

            // Store AABB for collision checks by subsequent placements
            placedAABBs.push({
                minX: bestGX * cellSize,
                maxX: bestGX * cellSize + sizeX,
                minY: bestBaseH,
                maxY: bestBaseH + sizeY,
                minZ: bestGZ * cellSize,
                maxZ: bestGZ * cellSize + sizeZ
            });

            // Update height map for the piece's exact footprint.
            // No buffer — tight packing requires precise heightmap data.
            // The AABB collision check prevents any actual overlap.
            const top = bestBaseH + sizeY + packingGap;
            for (let pz = 0; pz < pieceNZ; pz++) {
                for (let px = 0; px < pieceNX; px++) {
                    const hIdx = (bestGZ + pz) * gridNX + (bestGX + px);
                    if (top > heightMap[hIdx]) heightMap[hIdx] = top;
                }
            }

            // Record first-layer placement for replication
            if (replicateFirstLayer && bestBaseH < 0.5) {
                firstLayerPlacements.push({ gx: bestGX, gz: bestGZ, orientIdx: bestOrientIdx });
            }

            placed++;
            consecutiveSkips = 0;
            if (onProgress && (placed === 1 || (placed % 5) === 0 || placed === maxDraw)) {
                onProgress({ placed, maxTry: maxDraw });
            }
        }

        // Log per-orientation breakdown
        const orientBreakdown = orientCounts.map((c, i) => `orient${i}=${c}`).join(', ');
        console.log(`[HeightMapAsync] placed=${placed} (${orientBreakdown}), maxDraw=${maxDraw}, skips=${consecutiveSkips}`);
        const hMapMin = Math.min(...heightMap);
        const hMapMax = Math.max(...heightMap);
        console.log(`[HeightMapAsync] heightMap range: [${hMapMin.toFixed(1)}, ${hMapMax.toFixed(1)}], boxH=${boxH}`);

        // --- Finalize rendering ---
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
                pieceData: pieceDataOut,
                orientations: orientData.map(od => ({
                    geometry: od.geometry,
                    vertices: od.positions ? new Float32Array(od.positions.array) : null,
                    sizeX: od.sizeX, sizeY: od.sizeY, sizeZ: od.sizeZ
                })),
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
