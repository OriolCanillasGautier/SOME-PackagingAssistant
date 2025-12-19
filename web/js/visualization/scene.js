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
     * Prepara la geometria STL: centra i posa la base a Y=0
     * NO aplica cap rotació - respecta l'orientació que vingui del calculador
     */
    orientGeometryToMatch(geometry, originalDims, optimalDims) {
        // Només centrar i posar a Y=0, sense rotar
        geometry.computeBoundingBox();
        geometry.center();
        geometry.computeBoundingBox();
        geometry.translate(0, -geometry.boundingBox.min.y, 0);
        
        // Retornar dimensions reals de la geometria
        geometry.computeBoundingBox();
        const bbox = geometry.boundingBox;
        return {
            geometry,
            dims: [
                bbox.max.x - bbox.min.x,
                bbox.max.y - bbox.min.y,
                bbox.max.z - bbox.min.z
            ]
        };
    }
    
    /**
     * Orienta la geometria sense rotació específica, només centra i posa a Y=0
     */
    orientGeometryFlat(geometry) {
        geometry.computeBoundingBox();
        geometry.center();
        geometry.computeBoundingBox();
        geometry.translate(0, -geometry.boundingBox.min.y, 0);
        
        geometry.computeBoundingBox();
        const bbox = geometry.boundingBox;
        return {
            geometry,
            dims: [
                bbox.max.x - bbox.min.x,
                bbox.max.y - bbox.min.y,
                bbox.max.z - bbox.min.z
            ]
        };
    }

    /**
     * Aplica rotació a la geometria segons l'orientació del calculador
     * El calculador permuta [L, W, H] en diferents ordres
     * Hem de rotar la geometria per coincidir amb la permutació
     * 
     * STL original té: X=length, Y=height, Z=width
     * Orientacions del calculador:
     *   Original (L×W×H) -> Cap rotació
     *   Rotació Y (L×H×W) -> W i H intercanviats -> Rotar X 90°
     *   Rotació Z (W×L×H) -> L i W intercanviats -> Rotar Y 90°
     *   Rotació XY (W×H×L) -> W→L, H→W, L→H -> Rotar Y 90° + X 90°
     *   Rotació XZ (H×L×W) -> H→L, L→W, W→H -> Rotar Z 90° 
     *   Rotació YZ (H×W×L) -> H→L -> Rotar Z -90°
     */
    applyOrientationRotation(geometry, orientationName, originalDims) {
        const rotMatrix = new THREE.Matrix4();
        
        // Netejar el nom de possibles sufixos
        const cleanName = orientationName.split(' (')[0].trim();
        
        console.log(`📐 Aplicant rotació per: "${cleanName}"`);
        
        switch(cleanName) {
            case 'Original':
            case 'Sense rotació':
                // Cap rotació
                break;
                
            case 'Rotació Y':
                // L×H×W: W i H intercanviats
                // Rotar 90° al voltant de X per posar W a Y i H a Z
                rotMatrix.makeRotationX(Math.PI / 2);
                geometry.applyMatrix4(rotMatrix);
                break;
                
            case 'Rotació Z':
                // W×L×H: L i W intercanviats
                // Rotar 90° al voltant de Y per intercanviar X i Z
                rotMatrix.makeRotationY(Math.PI / 2);
                geometry.applyMatrix4(rotMatrix);
                break;
                
            case 'Rotació XY':
                // W×H×L: W→X, H→Y, L→Z
                // Rotar 90° Y després 90° X
                rotMatrix.makeRotationY(Math.PI / 2);
                geometry.applyMatrix4(rotMatrix);
                rotMatrix.makeRotationX(Math.PI / 2);
                geometry.applyMatrix4(rotMatrix);
                break;
                
            case 'Rotació XZ':
                // H×L×W: H→X, L→Y, W→Z
                // Rotar 90° al voltant de Z
                rotMatrix.makeRotationZ(Math.PI / 2);
                geometry.applyMatrix4(rotMatrix);
                break;
                
            case 'Rotació YZ':
                // H×W×L: H→X, W→Y, L→Z
                // Rotar -90° al voltant de Z
                rotMatrix.makeRotationZ(-Math.PI / 2);
                geometry.applyMatrix4(rotMatrix);
                break;
                
            default:
                console.warn(`⚠️ Orientació desconeguda: ${orientationName}`);
        }
        
        // Centrar després de la rotació
        geometry.center();
    }

    /**
     * Add packed pieces in organized grid layout
     * MODE OPTIMITZAT: Col·loca peces STL en graella ordenada
     * SIMPLE: Agafem l'STL tal qual (com al mode gravetat) i el posicionem en graella
     */
    addPackedPieces({ pieceL, pieceW, pieceH, nx, ny, nz, maxDraw = 500, stlGeometry = null, addSeparators = false, separatorThickness = 2, originalDims = null, optimalDims = null, orientationName = 'Original', densityFactor = 1.0, boxDims = null }) {
        this.clearPieces();

        // COLORS MOLT VIUS! 🎨
        const pieceColors = [
            0xFF6B6B, 0x4ECDC4, 0xFFE66D, 0x95E1D3, 0xF38181,
            0xAA96DA, 0xFCBAD3, 0xA8D8EA, 0xFF9F43, 0x6C5CE7,
            0x00CEC9, 0xFD79A8, 0x55EFC4, 0x74B9FF, 0xE17055,
            0x81ECEC, 0xFAB1A0, 0xA29BFE, 0x00B894, 0xFDCB6E
        ];

        let geometry;
        // Dimensions for spacing - will be updated after STL rotation
        let spacingX, spacingZ, spacingY;
        
        if (stlGeometry) {
            geometry = stlGeometry.clone();
            geometry.computeVertexNormals();
            geometry.center();
            geometry.computeBoundingBox();
            
            // Get original STL dimensions
            let bbox = geometry.boundingBox;
            const stlX = bbox.max.x - bbox.min.x;
            const stlY = bbox.max.y - bbox.min.y;
            const stlZ = bbox.max.z - bbox.min.z;
            
            console.log(`📦 Original STL: ${stlX.toFixed(1)} x ${stlY.toFixed(1)} x ${stlZ.toFixed(1)}`);
            console.log(`📦 Target dims (L×W×H): ${pieceL.toFixed(1)} x ${pieceW.toFixed(1)} x ${pieceH.toFixed(1)}`);
            console.log(`📦 Orientation: ${orientationName}`);
            
            // Map orientation name to the rotation defined in ORIENTATIONS
            // Original STL assumes: X=length, Y=height, Z=width (Three.js convention)
            // The rotations will permute these to match the calculator's expected orientation
            const orientationRotations = {
                'Original (L×W×H)': { x: 0, y: 0, z: 0 },
                'Rotació Y (L×H×W)': { x: Math.PI / 2, y: 0, z: 0 },
                'Rotació Z (W×L×H)': { x: 0, y: 0, z: Math.PI / 2 },
                'Rotació XY (W×H×L)': { x: Math.PI / 2, y: 0, z: Math.PI / 2 },
                'Rotació XZ (H×L×W)': { x: 0, y: Math.PI / 2, z: 0 },
                'Rotació YZ (H×W×L)': { x: 0, y: Math.PI / 2, z: Math.PI / 2 },
            };
            
            // Find matching rotation
            let rot = { x: 0, y: 0, z: 0 };
            for (const [name, r] of Object.entries(orientationRotations)) {
                if (orientationName.includes(name) || name.includes(orientationName.split(' ')[0])) {
                    rot = r;
                    break;
                }
            }
            
            // Apply rotation
            if (rot.x !== 0) geometry.rotateX(rot.x);
            if (rot.y !== 0) geometry.rotateY(rot.y);
            if (rot.z !== 0) geometry.rotateZ(rot.z);
            
            console.log(`📦 Applied rotation: X=${(rot.x * 180/Math.PI).toFixed(0)}°, Y=${(rot.y * 180/Math.PI).toFixed(0)}°, Z=${(rot.z * 180/Math.PI).toFixed(0)}°`);
            
            // Recompute bounding box after rotation
            geometry.computeBoundingBox();
            bbox = geometry.boundingBox;
            
            const newX = bbox.max.x - bbox.min.x;
            const newY = bbox.max.y - bbox.min.y;
            const newZ = bbox.max.z - bbox.min.z;
            
            console.log(`📦 After rotation: ${newX.toFixed(1)} x ${newY.toFixed(1)} x ${newZ.toFixed(1)}`);
            
            // Move geometry so its CORNER is at origin (not center!)
            // This way when we position at (x, y, z), the piece occupies from there to (x+w, y+h, z+d)
            geometry.translate(-bbox.min.x, -bbox.min.y, -bbox.min.z);
            
            // USE ACTUAL STL DIMENSIONS after rotation for spacing!
            spacingX = newX * densityFactor;
            spacingZ = newZ * densityFactor;
            spacingY = newY;
            
            console.log(`📦 Spacing from STL: X=${spacingX.toFixed(1)}, Y=${spacingY.toFixed(1)}, Z=${spacingZ.toFixed(1)}`);
            
        } else {
            // Simple box geometry - use pieceL/W/H
            spacingX = pieceL * densityFactor;
            spacingZ = pieceW * densityFactor;
            spacingY = pieceH;
            
            geometry = new THREE.BoxGeometry(pieceL, pieceH, pieceW);
            geometry.translate(0, pieceH / 2, 0);
        }

        // Add gaps if separators
        const gapX = addSeparators ? separatorThickness : 0;
        const gapZ = addSeparators ? separatorThickness : 0;
        const gapY = addSeparators ? separatorThickness : 0;
        
        spacingX += gapX;
        spacingZ += gapZ;
        spacingY += gapY;

        // 🔒 IMPORTANT: Recalculate nx/ny/nz based on ACTUAL box dimensions and STL spacing
        // This ensures pieces NEVER exceed the box bounds
        if (boxDims) {
            const boxL = boxDims.l || boxDims.length;
            const boxW = boxDims.w || boxDims.width;
            const boxH = boxDims.h || boxDims.height;
            
            const maxNx = Math.floor(boxL / spacingX);
            const maxNy = Math.floor(boxW / spacingZ);  // ny corresponds to Z (width)
            const maxNz = Math.floor(boxH / spacingY);  // nz corresponds to Y (height)
            
            console.log(`📦 Box dims: L=${boxL}, W=${boxW}, H=${boxH}`);
            console.log(`📦 Requested grid: ${nx}×${ny}×${nz}`);
            console.log(`📦 Max fit in box: ${maxNx}×${maxNy}×${maxNz}`);
            
            // Limit to what actually fits
            nx = Math.min(nx, maxNx);
            ny = Math.min(ny, maxNy);
            nz = Math.min(nz, maxNz);
            
            console.log(`📦 Adjusted grid: ${nx}×${ny}×${nz}`);
        }

        // Ensure at least 0 pieces if nothing fits
        nx = Math.max(0, nx);
        ny = Math.max(0, ny);
        nz = Math.max(0, nz);
        
        if (nx === 0 || ny === 0 || nz === 0) {
            console.warn('⚠️ No pieces fit in the box with current dimensions!');
            return 0;
        }

        console.log(`Grid: ${nx} x ${ny} x ${nz} = ${nx*ny*nz} pieces`);
        console.log(`Spacing: X=${spacingX.toFixed(1)}, Z=${spacingZ.toFixed(1)}, Y=${spacingY.toFixed(1)}`);

        const totalPieces = Math.min(nx * ny * nz, maxDraw);
        let index = 0;

        // No offset needed - geometry corner is at origin
        // nz = vertical layers (Y), ny = rows (Z), nx = columns (X)
        for (let iz = 0; iz < nz && index < totalPieces; iz++) {
            for (let iy = 0; iy < ny && index < totalPieces; iy++) {
                for (let ix = 0; ix < nx && index < totalPieces; ix++) {
                    const colorIndex = index % pieceColors.length;
                    const material = new THREE.MeshPhongMaterial({
                        color: pieceColors[colorIndex],
                        flatShading: false,
                        shininess: 80,
                        side: THREE.DoubleSide
                    });

                    const mesh = new THREE.Mesh(geometry.clone(), material);
                    
                    const posX = ix * spacingX;
                    const posY = iz * spacingY;
                    const posZ = iy * spacingZ;
                    
                    mesh.position.set(posX, posY, posZ);
                    
                    mesh.castShadow = true;
                    mesh.receiveShadow = true;
                    
                    this.scene.add(mesh);
                    this.pieces.push(mesh);
                    
                    index++;
                }
            }
        }
        
        // Separadors horitzontals entre capes
        if (addSeparators && separatorThickness > 0 && nz > 1) {
            this.addHorizontalSeparators({
                pieceL: spacingX - gapX, 
                pieceW: spacingZ - gapZ,
                nx, ny, nz,
                separatorThickness,
                spacingX, spacingZ, spacingY,
                offsetX: 0, 
                offsetZ: 0
            });
        }

        console.log(`✅ Rendered ${index} pieces`);
        return index;
    }
    
    /**
     * Afegeix separadors horitzontals (cartons) entre capes
     */
    addHorizontalSeparators({ pieceL, pieceW, nx, ny, nz, separatorThickness, spacingX, spacingZ, spacingY, offsetX = 0, offsetZ = 0 }) {
        const cardboardColor = 0xD4A574;
        const cardboardMaterial = new THREE.MeshPhongMaterial({
            color: cardboardColor,
            flatShading: true,
            side: THREE.DoubleSide
        });
        
        const totalWidth = nx * spacingX;
        const totalDepth = ny * spacingZ;
        
        // Un separador horitzontal entre cada capa
        for (let layer = 1; layer < nz; layer++) {
            const separatorGeom = new THREE.BoxGeometry(
                totalWidth,
                separatorThickness,
                totalDepth
            );
            const separator = new THREE.Mesh(separatorGeom, cardboardMaterial.clone());
            separator.position.set(
                offsetX + totalWidth / 2,
                layer * spacingY - separatorThickness / 2,
                offsetZ + totalDepth / 2
            );
            this.scene.add(separator);
            this.pieces.push(separator);
        }
    }
    
    /**
     * Add cardboard L-separators between pieces
     */
    addCardboardSeparators({ pieceL, pieceW, pieceH, nx, ny, nz, separatorThickness, spacingX, spacingY, spacingZ }) {
        const cardboardColor = 0xC4A574; // Color cartró
        const cardboardMaterial = new THREE.MeshPhongMaterial({
            color: cardboardColor,
            transparent: false,
            flatShading: true,
            side: THREE.DoubleSide
        });
        
        // Vertical separators between columns (YZ plane)
        for (let ix = 1; ix < nx; ix++) {
            for (let iy = 0; iy < ny; iy++) {
                const height = nz * spacingZ;
                const separatorGeom = new THREE.BoxGeometry(
                    separatorThickness,
                    height,
                    pieceW
                );
                const separator = new THREE.Mesh(separatorGeom, cardboardMaterial.clone());
                separator.position.set(
                    ix * spacingX - separatorThickness / 2,
                    height / 2,
                    iy * spacingY + pieceW / 2
                );
                this.scene.add(separator);
                this.pieces.push(separator);
            }
        }
        
        // Horizontal separators between rows (XZ plane)
        for (let iy = 1; iy < ny; iy++) {
            for (let ix = 0; ix < nx; ix++) {
                const height = nz * spacingZ;
                const separatorGeom = new THREE.BoxGeometry(
                    pieceL,
                    height,
                    separatorThickness
                );
                const separator = new THREE.Mesh(separatorGeom, cardboardMaterial.clone());
                separator.position.set(
                    ix * spacingX + pieceL / 2,
                    height / 2,
                    iy * spacingY - separatorThickness / 2
                );
                this.scene.add(separator);
                this.pieces.push(separator);
            }
        }
        
        // Horizontal layer separators (XY plane) between vertical layers
        for (let iz = 1; iz < nz; iz++) {
            const separatorGeom = new THREE.BoxGeometry(
                nx * spacingX - separatorThickness,
                separatorThickness,
                ny * spacingY - separatorThickness
            );
            const separator = new THREE.Mesh(separatorGeom, cardboardMaterial.clone());
            separator.position.set(
                (nx * spacingX - separatorThickness) / 2,
                iz * spacingZ - separatorThickness / 2,
                (ny * spacingY - separatorThickness) / 2
            );
            this.scene.add(separator);
            this.pieces.push(separator);
        }
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
