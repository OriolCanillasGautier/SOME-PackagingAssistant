/**
 * PackAssist Web - 3D Scene Manager
 * Handles Three.js scene setup, rendering, and camera controls
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

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
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.position.set(length / 2, 0.1, width / 2);
        floor.name = 'boxFloor';
        this.scene.add(floor);

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

        for (let iz = 0; iz < nz && index < totalPieces; iz++) {
            for (let iy = 0; iy < ny && index < totalPieces; iy++) {
                for (let ix = 0; ix < nx && index < totalPieces; ix++) {
                    // Calculate position with gap spacing
                    const posX = ix * (pieceL + packingGap) + pieceL / 2;
                    const posY = iz * (pieceH + packingGap) + pieceH / 2;
                    const posZ = iy * (pieceW + packingGap) + pieceW / 2;
                    
                    // Skip pieces that would overflow the box (with relaxed tolerance)
                    const tolerance = 1.0;
                    if (boxL !== null && posX + pieceL / 2 > boxL + tolerance) continue;
                    if (boxW !== null && posZ + pieceW / 2 > boxW + tolerance) continue;
                    if (boxH !== null && posY + pieceH / 2 > boxH + tolerance) continue;
                    
                    dummy.position.set(posX, posY, posZ);
                    dummy.updateMatrix();
                    instancedMesh.setMatrixAt(index, dummy.matrix);
                    
                    // Use colors from pieceColors array
                    const colorIndex = index % numColors;
                    const color = new THREE.Color(this.pieceColors[colorIndex]);
                    instancedMesh.setColorAt(index, color);
                    
                    index++;
                }
            }
        }

        instancedMesh.instanceMatrix.needsUpdate = true;
        if (instancedMesh.instanceColor) {
            instancedMesh.instanceColor.needsUpdate = true;
        }

        this.scene.add(instancedMesh);
        this.pieces.push(instancedMesh);

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
    addPackedSTLPieces({ stlGeometry, pieceL, pieceW, pieceH, nx, ny, nz, maxDraw = 500, packingGap = 0, colorCount = null, boxL = null, boxW = null, boxH = null }) {
        this.clearPieces();
        
        // Use provided colorCount or default
        const numColors = colorCount || this.colorCount;

        // Clone and prepare geometry
        const geometry = stlGeometry.clone();
        geometry.computeVertexNormals();

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

        for (let iz = 0; iz < nz && index < totalPieces; iz++) {
            for (let iy = 0; iy < ny && index < totalPieces; iy++) {
                for (let ix = 0; ix < nx && index < totalPieces; ix++) {
                    // Calculate position with gap spacing
                    const posX = ix * (pieceL + packingGap) + pieceL / 2;
                    const posY = iz * (pieceH + packingGap) + pieceH / 2;
                    const posZ = iy * (pieceW + packingGap) + pieceW / 2;
                    
                    // Skip pieces that would overflow the box (with relaxed tolerance)
                    const tolerance = 1.0;
                    if (boxL !== null && posX + pieceL / 2 > boxL + tolerance) continue;
                    if (boxW !== null && posZ + pieceW / 2 > boxW + tolerance) continue;
                    if (boxH !== null && posY + pieceH / 2 > boxH + tolerance) continue;
                    
                    dummy.position.set(posX, posY, posZ);
                    dummy.updateMatrix();
                    instancedMesh.setMatrixAt(index, dummy.matrix);
                    
                    // Use colors from pieceColors array
                    const colorIndex = index % numColors;
                    const color = new THREE.Color(this.pieceColors[colorIndex]);
                    instancedMesh.setColorAt(index, color);
                    
                    index++;
                }
            }
        }

        instancedMesh.instanceMatrix.needsUpdate = true;
        if (instancedMesh.instanceColor) {
            instancedMesh.instanceColor.needsUpdate = true;
        }

        this.scene.add(instancedMesh);
        this.pieces.push(instancedMesh);

        return index; // Return actual count drawn (may be less if pieces were skipped)
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
