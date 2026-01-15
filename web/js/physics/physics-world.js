/**
 * PackAssist Web - Physics Engine (Rapier.js)
 * Handles physics simulation for bulk/gravity mode
 * FIXED: Proper physics loop integration with Three.js
 */

import * as THREE from 'three';

// Rapier will be loaded dynamically
let RAPIER = null;

/**
 * Initialize Rapier physics engine
 * @returns {Promise<boolean>}
 */
export async function initRapier() {
    if (RAPIER) return true;
    
    try {
        RAPIER = await import('@dimforge/rapier3d-compat');
        await RAPIER.init();
        console.log('✅ Rapier physics engine initialized');
        return true;
    } catch (error) {
        console.error('❌ Failed to initialize Rapier:', error);
        return false;
    }
}

/**
 * Physics world manager for bulk simulation
 */
export class PhysicsWorld {
    constructor() {
        this.world = null;
        this.bodies = [];
        this.meshBodies = []; // Array of {body, mesh} pairs for easier sync
        this.wallBodies = []; // Floor and walls for vibration
        this.wallOriginalPositions = []; // Original positions of walls
        this.isRunning = false;
        this.settledCount = 0;
        this.onSettled = null;
        this.boxDims = null;
        
        // Physics settings - scaled for mm units
        this.gravity = -9810; // mm/s² (9.81 m/s² * 1000)
        
        // Solver iterations for more accurate collision (reduces interpenetration)
        // Higher values = less interpenetration but slower
        // Solver iterations for more accurate collision (reduces interpenetration)
        // Higher values = less interpenetration but slower
        this.numSolverIterations = 64; // Increased from 16 for stability
        this.numAdditionalFrictionIterations = 32; // Increased from 8
        this.numVelocitySolverIterations = 32; // Increased from 8
        
        // Vibration settings
        this.isVibrating = false;
        this.vibrationTime = 0;
        this.vibrationDuration = 5000; // 5 seconds of vibration
        this.vibrationFrequency = 20; // Hz - reduced from 25
        this.vibrationAmplitude = 4.5; // mm - increased to intermediate value (2 was too weak, 8 too strong)

        
        // Lid Press settings
        this.lidBody = null;
        this.lidState = 'idle'; // idle, descending, holding, ascending, finished
        this.lidTargetY = 0;
        this.lidStartTime = 0;
        this.lidHoldTime = 0;
        this.onLidFinished = null;
    }

    /**
     * Initialize the physics world
     * @param {Object} boxDims - {length, width, height} in mm
     */
    async init(boxDims) {
        if (!RAPIER) {
            const success = await initRapier();
            if (!success) throw new Error('Failed to initialize physics engine');
        }

        this.boxDims = boxDims;

        // Create world with gravity (Y is up in Three.js)
        const gravity = { x: 0.0, y: this.gravity, z: 0.0 };
        this.world = new RAPIER.World(gravity);
        
        // Configure solver for more accurate collisions (reduces interpenetration)
        this.world.numSolverIterations = this.numSolverIterations;
        this.world.numAdditionalFrictionIterations = this.numAdditionalFrictionIterations;
        this.world.numVelocitySolverIterations = this.numVelocitySolverIterations;
        
        // Reset arrays
        this.bodies = [];
        this.meshBodies = [];
        this.settledCount = 0;

        // Create box container (floor + walls)
        this.createBoxContainer(boxDims);
        
        console.log(`Physics world created with gravity: ${this.gravity} mm/s²`);
    }

    /**
     * Create the box container with floor and walls
     */
    createBoxContainer({ length, width, height }) {
        // THICK walls positioned OUTSIDE the box visualization
        // The visual box goes from (0,0,0) to (length, height, width)
        // Walls are placed OUTSIDE these bounds so pieces can't escape
        const wallThickness = 100;
        this.wallBodies = [];
        this.wallOriginalPositions = [];
        
        // FLOOR at y=0 (slightly below)
        const floor = this.createKinematicBox(
            length / 2, -wallThickness / 2, width / 2,
            length / 2 + wallThickness, wallThickness / 2, width / 2 + wallThickness
        );
        this.wallBodies.push(floor);
        this.wallOriginalPositions.push({ x: length / 2, y: -wallThickness / 2, z: width / 2 });
        
        // BACK WALL at z=0 (positioned at z = -thickness/2, so inner face is at z=0)
        const back = this.createKinematicBox(
            length / 2, height / 2, -wallThickness / 2,
            length / 2 + wallThickness, height / 2 + wallThickness, wallThickness / 2
        );
        this.wallBodies.push(back);
        this.wallOriginalPositions.push({ x: length / 2, y: height / 2, z: -wallThickness / 2 });
        
        // FRONT WALL at z=width (positioned so inner face is at z=width)
        const front = this.createKinematicBox(
            length / 2, height / 2, width + wallThickness / 2,
            length / 2 + wallThickness, height / 2 + wallThickness, wallThickness / 2
        );
        this.wallBodies.push(front);
        this.wallOriginalPositions.push({ x: length / 2, y: height / 2, z: width + wallThickness / 2 });
        
        // LEFT WALL at x=0 (positioned so inner face is at x=0)
        const left = this.createKinematicBox(
            -wallThickness / 2, height / 2, width / 2,
            wallThickness / 2, height / 2 + wallThickness, width / 2 + wallThickness
        );
        this.wallBodies.push(left);
        this.wallOriginalPositions.push({ x: -wallThickness / 2, y: height / 2, z: width / 2 });
        
        // RIGHT WALL at x=length (positioned so inner face is at x=length)
        const right = this.createKinematicBox(
            length + wallThickness / 2, height / 2, width / 2,
            wallThickness / 2, height / 2 + wallThickness, width / 2 + wallThickness
        );
        this.wallBodies.push(right);
        this.wallOriginalPositions.push({ x: length + wallThickness / 2, y: height / 2, z: width / 2 });
        
        console.log(`Box container created: ${length}×${width}×${height} mm`);
    }

    /**
     * Create a kinematic box collider (can be moved for vibration)
     */
    createKinematicBox(px, py, pz, hx, hy, hz) {
        const bodyDesc = RAPIER.RigidBodyDesc.kinematicPositionBased()
            .setTranslation(px, py, pz);
        const body = this.world.createRigidBody(bodyDesc);
        
        const colliderDesc = RAPIER.ColliderDesc.cuboid(hx, hy, hz)
            .setFriction(0.8) // Increased friction
            .setRestitution(0.05)
            .setContactForceEventThreshold(0.1);
        this.world.createCollider(colliderDesc, body);
        
        return body;
    }
    
    /**
     * Start vibrating the box
     */
    startVibration(duration = 3000) {
        this.isVibrating = true;
        this.vibrationTime = 0;
        this.vibrationDuration = duration;
        console.log(`Starting box vibration for ${duration}ms`);
    }
    
    /**
     * Stop vibration and reset walls to original positions
     */
    stopVibration() {
        this.isVibrating = false;
        // Reset walls to original positions
        for (let i = 0; i < this.wallBodies.length; i++) {
            const body = this.wallBodies[i];
            const orig = this.wallOriginalPositions[i];
            if (body.isValid()) {
                body.setNextKinematicTranslation({ x: orig.x, y: orig.y, z: orig.z });
            }
        }
        console.log('Box vibration stopped');
    }
    
    /**
     * Update vibration - call this each physics step
     */
    updateVibration(deltaMs) {
        if (!this.isVibrating) return false;
        
        this.vibrationTime += deltaMs;
        
        if (this.vibrationTime >= this.vibrationDuration) {
            this.stopVibration();
            return false; // Vibration finished
        }
        
        // Calculate vibration offset using sine waves
        const t = this.vibrationTime / 1000; // seconds
        const progress = this.vibrationTime / this.vibrationDuration; // 0 to 1
        const freq = this.vibrationFrequency;
        const amp = this.vibrationAmplitude;
        
        // Decreasing amplitude over time (starts strong, ends gentle)
        const ampFactor = 1.0 - progress * 0.5;
        
        // Multi-frequency vibration with stronger vertical component
        // Phase 1: Strong lateral shaking (first half)
        // Phase 2: More vertical settling (second half)
        const lateralFactor = progress < 0.5 ? 1.0 : 0.5;
        const verticalFactor = progress < 0.5 ? 0.8 : 1.2;
        
        const offsetX = amp * ampFactor * lateralFactor * (
            Math.sin(2 * Math.PI * freq * t) + 
            0.5 * Math.sin(2 * Math.PI * freq * 2.3 * t)
        );
        const offsetY = amp * ampFactor * verticalFactor * (
            Math.sin(2 * Math.PI * freq * 1.5 * t + 0.5) +
            0.3 * Math.sin(2 * Math.PI * freq * 3.7 * t)
        );
        const offsetZ = amp * ampFactor * lateralFactor * (
            Math.sin(2 * Math.PI * freq * 1.1 * t + 1.0) +
            0.5 * Math.sin(2 * Math.PI * freq * 2.7 * t + 0.3)
        );
        
        // Apply offset to all walls
        for (let i = 0; i < this.wallBodies.length; i++) {
            const body = this.wallBodies[i];
            const orig = this.wallOriginalPositions[i];
            if (body.isValid()) {
                body.setNextKinematicTranslation({
                    x: orig.x + offsetX,
                    y: orig.y + offsetY,
                    z: orig.z + offsetZ
                });
            }
        }
        
        return true; // Still vibrating
    }

    /**
     * Add a dynamic cuboid piece
     * @param {Object} dims - {l, w, h} dimensions in mm
     * @param {THREE.Vector3} position - Initial position
     * @param {THREE.Euler} rotation - Initial rotation (optional)
     * @param {THREE.Mesh} mesh - Three.js mesh to sync
     * @returns {Object} The rigid body
     */
    addCuboid(dims, position, rotation = null, mesh = null) {
        const { l, w, h } = dims;
        
        // Create dynamic rigid body
        const bodyDesc = RAPIER.RigidBodyDesc.dynamic()
            .setTranslation(position.x, position.y, position.z)
            .setLinearDamping(0.5) // Increased damping for stability
            .setAngularDamping(0.8) // Increased angular damping
            .setCcdEnabled(true); // Continuous collision detection
        
        // Apply rotation if provided
        if (rotation) {
            const quat = new THREE.Quaternion().setFromEuler(rotation);
            bodyDesc.setRotation({ x: quat.x, y: quat.y, z: quat.z, w: quat.w });
        }

        const body = this.world.createRigidBody(bodyDesc);
        
        // Create cuboid collider (half-extents)
        // Use nearly exact collider (0.999 scale) for accurate physics
        const colliderDesc = RAPIER.ColliderDesc.cuboid(l / 2 * 0.999, h / 2 * 0.999, w / 2 * 0.999)
            .setDensity(2.0) // Moderate density
            .setFriction(0.8) // High friction for stable stacking
            .setRestitution(0.0) // No bounce
            .setContactForceEventThreshold(0.01);
        
        this.world.createCollider(colliderDesc, body);
        
        this.bodies.push(body);
        
        if (mesh) {
            this.meshBodies.push({ body, mesh });
        }

        return body;
    }

    /**
     * Add a convex hull piece for STL
     */
    addConvexHull(vertices, position, rotation = null, mesh = null) {
        const bodyDesc = RAPIER.RigidBodyDesc.dynamic()
            .setTranslation(position.x, position.y, position.z)
            .setLinearDamping(0.5) // Increased damping
            .setAngularDamping(0.8) // Increased damping
            .setCcdEnabled(true);
        
        if (rotation) {
            const quat = new THREE.Quaternion().setFromEuler(rotation);
            bodyDesc.setRotation({ x: quat.x, y: quat.y, z: quat.z, w: quat.w });
        }

        const body = this.world.createRigidBody(bodyDesc);
        
        // Try convex hull, fallback to bounding box
        let colliderDesc = null;
        try {
            colliderDesc = RAPIER.ColliderDesc.convexHull(vertices);
        } catch (e) {
            console.warn('Convex hull failed, using bounding box');
        }
        
        if (!colliderDesc) {
            // Calculate bounding box from vertices
            let minX = Infinity, maxX = -Infinity;
            let minY = Infinity, maxY = -Infinity;
            let minZ = Infinity, maxZ = -Infinity;
            
            for (let i = 0; i < vertices.length; i += 3) {
                minX = Math.min(minX, vertices[i]);
                maxX = Math.max(maxX, vertices[i]);
                minY = Math.min(minY, vertices[i + 1]);
                maxY = Math.max(maxY, vertices[i + 1]);
                minZ = Math.min(minZ, vertices[i + 2]);
                maxZ = Math.max(maxZ, vertices[i + 2]);
            }
            
            colliderDesc = RAPIER.ColliderDesc.cuboid(
                (maxX - minX) / 2 * 0.999,
                (maxY - minY) / 2 * 0.999,
                (maxZ - minZ) / 2 * 0.999
            );
        }
        
        colliderDesc.setDensity(2.0).setFriction(0.8).setRestitution(0.0);
        this.world.createCollider(colliderDesc, body);
        
        this.bodies.push(body);
        
        if (mesh) {
            this.meshBodies.push({ body, mesh });
        }

        return body;
    }

    /**
     * Step the physics simulation and sync meshes
     */
    step() {
        if (!this.world || !this.isRunning) return false;
        
        // Step physics with sub-stepping for higher stability
        // Run 2 steps of 1/120s per frame (total 1/60s)
        this.world.timestep = 1 / 120; 
        this.world.step();
        this.world.step();
        this.world.step();
        
        // Update Lid animation if active
        if (this.lidState !== 'idle' && this.lidState !== 'finished') {
            this.updateLid(1000/60); // approx 16ms
        }
        
        // Sync Three.js meshes with physics bodies
        for (const { body, mesh } of this.meshBodies) {
            if (!body.isValid()) continue; // Skip removed bodies
            
            const pos = body.translation();
            const rot = body.rotation();
            
            mesh.position.set(pos.x, pos.y, pos.z);
            mesh.quaternion.set(rot.x, rot.y, rot.z, rot.w);
        }
        
        // Check for settled state
        return this.checkSettled();
    }

    /**
     * Check if all objects have settled
     * @returns {boolean} True if all settled
     */
    checkSettled() {
        if (this.meshBodies.length === 0) return false;
        
        const velocityThreshold = 5.0; // mm/s
        const angularThreshold = 0.5;
        let allSettled = true;
        
        for (const { body } of this.meshBodies) {
            const linVel = body.linvel();
            const angVel = body.angvel();
            const speed = Math.sqrt(linVel.x ** 2 + linVel.y ** 2 + linVel.z ** 2);
            const angSpeed = Math.sqrt(angVel.x ** 2 + angVel.y ** 2 + angVel.z ** 2);
            
            if (speed > velocityThreshold || angSpeed > angularThreshold) {
                allSettled = false;
                break;
            }
        }

        if (allSettled) {
            this.settledCount++;
            if (this.settledCount > 60 && this.onSettled) { // ~1 second of stability
                const count = this.countPiecesInBox();
                this.onSettled(count);
                return true;
            }
        } else {
            this.settledCount = 0;
        }
        
        return false;
    }

    /**
     * Count pieces that are inside the box
     */
    countPiecesInBox() {
        if (!this.boxDims) return 0;
        
        let count = 0;
        const { length, width, height } = this.boxDims;
        const margin = 10; // tolerance
        
        for (const { body } of this.meshBodies) {
            if (!body.isValid()) continue;
            const pos = body.translation();
            // Check if mostly inside box
            if (pos.x > -margin && pos.x < length + margin &&
                pos.z > -margin && pos.z < width + margin &&
                pos.y > -margin && pos.y < height + margin * 5) {
                count++;
            }
        }
        
        return count;
    }
    
    /**
     * Remove pieces that are outside the box and update scene
     * @param {Object} scene - SceneManager to remove meshes from
     * @param {Object} pieceDims - Dimensions of pieces {l, w, h} for accurate bounds check
     * @returns {number} Number of pieces removed
     */
    /**
     * Remove pieces that are outside the box or sticking out
     * @param {Object} scene - SceneManager (optional)
     * @param {Object} pieceDims - Dimensions (optional)
     * @param {number} strictness - 0: Relaxed (fallouts), 1: Semi (>50% out), 2: Strict (>height)
     */
    removePiecesOutsideBox(scene, pieceDims = null, strictness = 0) {
        if (!this.boxDims) return 0;
        
        const { length, width, height } = this.boxDims;
        const toRemove = [];
        
        for (let i = 0; i < this.meshBodies.length; i++) {
            const { body, mesh } = this.meshBodies[i];
            if (!body.isValid()) {
                toRemove.push(i);
                continue;
            }
            
            const pos = body.translation();
            
            // Get mesh bounding box for accurate check
            let minY = 0, maxY = 0, minX = 0, maxX = 0, minZ = 0, maxZ = 0;
            if (mesh && mesh.geometry) {
                mesh.geometry.computeBoundingBox();
                const bb = mesh.geometry.boundingBox;
                if (bb) {
                    // Transform bounding box to world coordinates
                    const worldBB = bb.clone().applyMatrix4(mesh.matrixWorld);
                    minX = worldBB.min.x;
                    maxX = worldBB.max.x;
                    minY = worldBB.min.y;
                    maxY = worldBB.max.y;
                    minZ = worldBB.min.z;
                    maxZ = worldBB.max.z;
                }
            } else {
                // Fallback to position-based check with piece dims
                const halfL = pieceDims ? pieceDims.l / 2 : 25;
                const halfW = pieceDims ? pieceDims.w / 2 : 25;
                const halfH = pieceDims ? pieceDims.h / 2 : 25;
                minX = pos.x - halfL; maxX = pos.x + halfL;
                minY = pos.y - halfH; maxY = pos.y + halfH;
                minZ = pos.z - halfW; maxZ = pos.z + halfW;
            }
            
            // ONLY remove pieces that have fallen out of the box limits (e.g. fallen off floor)
            // Do NOT remove pieces just because they stick out the top during Simulation
            // because they might settle down.
            // Removal logic based on strictness
            let shouldRemove = false;
            
            // Level 0: ONLY remove completely outside (fallen off floor etc)
            const completelyOutside = maxY < -50 || pos.y > height + 1000 || 
                                    pos.x < -200 || pos.x > length + 200 || 
                                    pos.z < -200 || pos.z > width + 200;
            
            if (strictness === 0) {
                shouldRemove = completelyOutside;
            } 
            // Level 1: Remove pieces sticking out more than 50% (center above height)
            else if (strictness === 1) {
                shouldRemove = completelyOutside || pos.y > height;
            }
            // Level 2: Strict - Remove ANY piece protruding above height
            else if (strictness === 2) {
                shouldRemove = completelyOutside || maxY > height;
            }

            if (shouldRemove) {
                toRemove.push(i);
            }
        }
        
        // Remove in reverse order to maintain indices
        for (let i = toRemove.length - 1; i >= 0; i--) {
            const idx = toRemove[i];
            const { body, mesh } = this.meshBodies[idx];
            
            // Remove from physics
            if (body.isValid()) {
                this.world.removeRigidBody(body);
            }
            
            // Remove from scene
            if (mesh && scene) {
                scene.scene.remove(mesh);
                if (mesh.geometry) mesh.geometry.dispose();
                if (mesh.material) mesh.material.dispose();
                // Also remove from scene's pieces array
                const pieceIdx = scene.pieces.indexOf(mesh);
                if (pieceIdx > -1) scene.pieces.splice(pieceIdx, 1);
            }
            
            // Remove from tracking arrays
            this.meshBodies.splice(idx, 1);
            this.bodies.splice(idx, 1);
        }
        
        return toRemove.length;
    }
    
    /**
     * Create kinetic Lid
     */
    createLid(sceneManager) {
        if (this.lidBody) return;
        if (!this.boxDims) return;
        
        const { length, width, height } = this.boxDims;
        const thickness = 50;
        
        // Start high up
        const startY = height + 200;
        
        // Kinematic body
        const bodyDesc = RAPIER.RigidBodyDesc.kinematicPositionBased()
            .setTranslation(length/2, startY, width/2);
        this.lidBody = this.world.createRigidBody(bodyDesc);
        
        // Collider (slightly smaller than box to fit inside walls)
        const margin = 5;
        const colliderDesc = RAPIER.ColliderDesc.cuboid(
            (length/2 - margin), 
            thickness/2, 
            (width/2 - margin)
        )
        .setFriction(0.2)
        .setRestitution(0.0);
        
        this.world.createCollider(colliderDesc, this.lidBody);
        
        // VISUAL MESH
        if (sceneManager) {
            const geometry = new THREE.BoxGeometry(length - margin*2, thickness, width - margin*2);
            const material = new THREE.MeshPhongMaterial({
                color: 0x00ff00, // Bright Green Lid
                transparent: true,
                opacity: 0.5,
                side: THREE.DoubleSide
            });
            this.lidMesh = new THREE.Mesh(geometry, material);
            this.lidMesh.position.set(length/2, startY, width/2);
            sceneManager.scene.add(this.lidMesh);
        }
        
        console.log('Lid created and added to scene');
    }
    
    /**
     * Start the Lid Press sequence
     */
    startLidSequence(sceneManager, callback) {
        if (!this.boxDims) {
            if (callback) callback();
            return;
        }
        
        this.createLid(sceneManager);
        
        // Wake up all bodies to ensure they react to the lid
        for (const { body } of this.meshBodies) {
            if (body && body.isValid()) body.wakeUp();
        }
        
        this.lidState = 'descending';
        
        // Target: Bottom of lid should be at Box Height
        // Lid center = Box Height + Lid Half-Height (25mm)
        this.lidTargetY = this.boxDims.height + 25; 
        
        this.onLidFinished = callback;
        this.lidHoldTime = 0;
        
        // Start vibration to help settlement while pressing
        // Vibrate for enough time to cover descent + hold
        this.startVibration(8000); 
        
        console.log('Starting Lid Sequence with Vibration...');
    }
    
    /**
     * Update Lid position/state
     */
    updateLid(dtMs) {
        if (!this.lidBody || !this.lidBody.isValid()) return;
        
        const pos = this.lidBody.translation();
        
        // Sync Visual Mesh
        if (this.lidMesh) {
            this.lidMesh.position.set(pos.x, pos.y, pos.z);
        }
        
        const speed = 0.1 * dtMs; // Increased speed (was 0.05)
        
        switch (this.lidState) {
            case 'descending':
                if (pos.y > this.lidTargetY) {
                    this.lidBody.setNextKinematicTranslation({
                        x: pos.x,
                        y: Math.max(this.lidTargetY, pos.y - speed),
                        z: pos.z
                    });
                } else {
                    this.lidState = 'holding';
                    this.lidHoldTime = 0;
                    console.log('Lid holding (compacting)...');
                }
                break;
                
            case 'holding':
                this.lidHoldTime += dtMs;
                if (this.lidHoldTime > 3000) { // Hold 3 seconds
                    this.lidState = 'ascending';
                    this.stopVibration(); // Stop vibration when we start lifting
                    console.log('Lid ascending...');
                }
                break;
                
            case 'ascending':
                const startY = this.boxDims.height + 200;
                if (pos.y < startY) {
                    this.lidBody.setNextKinematicTranslation({
                        x: pos.x,
                        y: Math.min(startY, pos.y + speed * 4), // Go up fast
                        z: pos.z
                    });
                } else {
                    this.lidState = 'finished';
                    // Remove lid body and mesh
                    this.world.removeRigidBody(this.lidBody);
                    this.lidBody = null;
                    if (this.lidMesh) {
                        if (this.lidMesh.parent) this.lidMesh.parent.remove(this.lidMesh);
                        if (this.lidMesh.geometry) this.lidMesh.geometry.dispose();
                        if (this.lidMesh.material) this.lidMesh.material.dispose();
                        this.lidMesh = null;
                    }
                    console.log('Lid finished');
                    
                    if (this.onLidFinished) {
                        this.onLidFinished();
                        this.onLidFinished = null;
                    }
                }
                break;
        }
    }

    start() {
        this.isRunning = true;
        console.log('Physics simulation started');
    }

    pause() {
        this.isRunning = false;
    }

    reset() {
        this.isRunning = false;
        this.isVibrating = false;
        this.meshBodies = [];
        this.bodies = [];
        this.wallBodies = [];
        this.wallOriginalPositions = [];
        this.settledCount = 0;
        
        if (this.world && this.boxDims) {
            // Recreate world to clear all bodies
            const gravity = { x: 0.0, y: this.gravity, z: 0.0 };
            this.world = new RAPIER.World(gravity);
            this.createBoxContainer(this.boxDims);
        }
    }

    dispose() {
        this.isRunning = false;
        this.meshBodies = [];
        this.bodies = [];
        this.world = null;
    }
}

/**
 * Bulk simulation controller - integrates physics with Three.js scene
 */
export class BulkSimulation {
    constructor(sceneManager) {
        this.scene = sceneManager;
        this.physics = new PhysicsWorld();
        this.boxDims = null;
        this.pieceDims = null;
        this.stlGeometry = null;
        this.stlVertices = null;
        this.dropInterval = null;
        this.droppedCount = 0;
        this.maxPieces = 50;
        this.dropHeight = 300;
        this.dropIntervalMs = 200;
        this.randomRotation = true;
        this.onStatusUpdate = null;
        this.isRunning = false;
        
        // Retry mechanism for removed pieces
        this.hasRetried = false;
        this.retryCount = 0;
        
        // Auto-capacity mode
        this.autoMode = false;
        this.overflowCount = 0;
        this.maxOverflow = 5; // Stop after 5 pieces fall outside
        
        // Weight control in auto mode
        this.pieceWeight = 0; // Weight per piece in kg
        this.maxWeight = 0; // Maximum total weight in kg
        this.currentTotalWeight = 0; // Current weight of pieces in box
        
        // Saturation detection - stop if no new pieces enter box after X drops
        this.lastInsideCount = 0;
        this.stagnantDrops = 0;
        this.maxStagnantDrops = 5; // Stop after 5 consecutive checks without increase
        this.checkInterval = 2; // Check every 2 drops (more responsive)
        
        // Track pieces above box to detect overflow faster
        this.piecesAboveBox = 0;
        this.maxPiecesAboveBox = 3; // If 3+ pieces are stuck above, box is full
        
        // 20 distinct colors for pieces - configurable
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
        
        // Number of colors to use (can be limited)
        this.colorCount = 10;
        
        // Timeout for settling
        this.settlingTimeout = null;
        this.settlingTimeoutMs = 30000; // 30 seconds
        this.allDropped = false;
        
        // Vibration phase
        this.vibrationPhase = false;
        this.lastUpdateTime = 0;
    }

    /**
     * Initialize the simulation
     */
    async init(options) {
        const {
            boxDims,
            pieceDims,
            stlGeometry = null,
            maxPieces = 50,
            dropHeight = 300,
            dropIntervalMs = 200,
            randomRotation = true,
            autoMode = false,
            settlingTimeoutMs = 30000,
            colorCount = 10,
            pieceWeight = 0,
            maxWeight = 0
        } = options;

        this.boxDims = boxDims;
        this.pieceDims = pieceDims;
        this.stlGeometry = stlGeometry;
        this.maxPieces = autoMode ? 50000 : maxPieces; // Much higher limit in auto mode (50k)
        this.dropHeight = dropHeight;
        this.dropIntervalMs = dropIntervalMs;
        this.randomRotation = randomRotation;
        this.droppedCount = 0;
        this.autoMode = autoMode;
        this.maxOverflow = autoMode ? 50 : 20; // Allow more overflow in auto mode
        this.overflowCount = 0;
        this.lastInsideCount = 0;
        this.stagnantDrops = 0;
        this.allDropped = false;
        this.settlingTimeoutMs = settlingTimeoutMs;
        this.colorCount = Math.min(colorCount, this.pieceColors.length);
        
        // Weight control
        this.pieceWeight = pieceWeight;
        this.maxWeight = maxWeight;
        this.currentTotalWeight = 0;
        
        // Pre-compute STL vertices if available
        if (stlGeometry) {
            const positions = stlGeometry.getAttribute('position');
            this.stlVertices = new Float32Array(positions.array);
        }

        // Initialize physics world
        await this.physics.init(boxDims);

        // Setup settled callback (FINAL completion only)
        // Setup settled callback (FINAL completion only)
        this.physics.onSettled = (count) => {
            // This is now only called via the manual check in the Lid callback
            this.finishSimulation();
        };

        // Create box visualization
        this.scene.createBox(boxDims.length, boxDims.width, boxDims.height);
        
        console.log('Bulk simulation initialized');
    }

    /**
     * Start the simulation - uses requestAnimationFrame for smooth updates
     */
    start() {
        this.isRunning = true;
        this.physics.start();
        this.droppedCount = 0;
        this.overflowCount = 0;
        this.allDropped = false;
        this.vibrationPhase = false;
        this.lastUpdateTime = 0;
        this.hasRetried = false;
        this.retryCount = 0;
        this.hasRetried = false;
        this.hasRefilled = false;
        this.retryCount = 0;
        this.hasPressedLid = false;
        
        // Clear any existing timeout
        if (this.settlingTimeout) {
            clearTimeout(this.settlingTimeout);
            this.settlingTimeout = null;
        }
        
        // Start dropping pieces at intervals
        this.dropInterval = setInterval(() => this.dropPiece(), this.dropIntervalMs);
        
        // Start physics update loop
        this.update();

        if (this.onStatusUpdate) {
            const modeText = this.autoMode ? '(mode automàtic)' : '';
            this.onStatusUpdate({
                status: 'running',
                dropped: 0,
                message: `▶️ Simulació iniciada... ${modeText}`
            });
        }
    }

    /**
     * Main update loop - called every frame
     */
    update() {
        if (!this.isRunning) return;
        
        // Calculate delta time
        const now = performance.now();
        const deltaMs = this.lastUpdateTime ? (now - this.lastUpdateTime) : 16.67;
        this.lastUpdateTime = now;
        
        // Update vibration if active
        if (this.vibrationPhase) {
            const stillVibrating = this.physics.updateVibration(deltaMs);
            if (!stillVibrating) {
                this.vibrationPhase = false;
                
                // FORCE START LID SEQUENCE
                if (!this.hasPressedLid) {
                    this.hasPressedLid = true;
                    
                    // Pre-cleanup (optional but good)
                    const semiRemoved = this.physics.removePiecesOutsideBox(this.scene, this.pieceDims, 1);
                    
                    if (this.onStatusUpdate) {
                        this.onStatusUpdate({
                            status: 'compacting',
                            message: `🚜 Premsant amb tapa... (${semiRemoved} eliminades prèviament)`
                        });
                    }
                    
                    this.physics.startLidSequence(this.scene, () => {
                        // After lid finishes, we finish the simulation
                        this.finishSimulation();
                    });
                }
            }
        }
        
        // Step physics multiple times for stability (sub-stepping)
        // More substeps = better collision resolution but slower
        const substeps = 6; // Increased for better collision resolution
        for (let i = 0; i < substeps; i++) {
            const settled = this.physics.step();
            if (settled && !this.vibrationPhase) {
                this.isRunning = false;
                return;
            }
        }
        
        // Continue loop
        requestAnimationFrame(() => this.update());
    }

    /**
     * Drop a single piece from above the box
     */
    dropPiece() {
        if (!this.isRunning) return;
        
        // Check for weight limit in auto mode
        if (this.autoMode && this.pieceWeight > 0 && this.maxWeight > 0) {
            const insideCount = this.physics.countPiecesInBox();
            this.currentTotalWeight = insideCount * this.pieceWeight;
            
            if (this.currentTotalWeight >= this.maxWeight) {
                this.finishDropping('weight');
                return;
            }
        }
        
        // Check for overflow in auto mode
        if (this.autoMode) {
            const outsideCount = this.countPiecesOutside();
            if (outsideCount >= this.maxOverflow) {
                this.finishDropping('overflow');
                return;
            }
        }
        
        if (this.droppedCount >= this.maxPieces) {
            this.finishDropping('max');
            return;
        }

        const { length, width, height } = this.boxDims;
        const { l, w, h } = this.pieceDims;

        // Random position above the box center
        const margin = Math.max(l, w) * 0.5;
        const x = margin + Math.random() * (length - margin * 2);
        const z = margin + Math.random() * (width - margin * 2);
        const y = height + this.dropHeight + Math.random() * 100;

        const position = new THREE.Vector3(x, y, z);
        
        // Random rotation if enabled
        let rotation = null;
        if (this.randomRotation) {
            rotation = new THREE.Euler(
                Math.random() * Math.PI * 2,
                Math.random() * Math.PI * 2,
                Math.random() * Math.PI * 2
            );
        }

        // Create visual mesh
        // Pick a random color from the available colors (limited by colorCount)
        const colorIndex = Math.floor(Math.random() * this.colorCount);
        const pieceColor = this.pieceColors[colorIndex];
        
        let mesh;
        if (this.stlGeometry && this.stlVertices) {
            // Use STL geometry
            const geometry = this.stlGeometry.clone();
            const material = new THREE.MeshPhongMaterial({
                color: pieceColor,
                flatShading: true,
                transparent: true,
                opacity: 0.9
            });
            geometry.computeVertexNormals();
            mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            
            this.scene.scene.add(mesh);
            this.scene.pieces.push(mesh);
            
            // Add to physics as convex hull
            this.physics.addConvexHull(this.stlVertices, position, rotation, mesh);
        } else {
            // Use simple cuboid
            const geometry = new THREE.BoxGeometry(l, h, w);
            const material = new THREE.MeshPhongMaterial({
                color: pieceColor,
                flatShading: true
            });
            mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            
            this.scene.scene.add(mesh);
            this.scene.pieces.push(mesh);
            
            // Add to physics
            this.physics.addCuboid({ l, w, h }, position, rotation, mesh);
        }

        this.droppedCount++;
        
        // Check for saturation in auto mode (every checkInterval drops)
        if (this.autoMode && this.droppedCount % this.checkInterval === 0) {
            const currentInside = this.physics.countPiecesInBox();
            const piecesAbove = this.countPiecesAboveBox();
            
            // Fast detection: if pieces are piling above the box, it's full
            if (piecesAbove >= this.maxPiecesAboveBox) {
                console.log(`Box full: ${piecesAbove} pieces stuck above box`);
                this.finishDropping('overflow');
                return;
            }
            
            if (currentInside <= this.lastInsideCount) {
                // No new pieces entered the box
                this.stagnantDrops++;
                console.log(`Saturation check: ${currentInside} inside, stagnant: ${this.stagnantDrops}/${this.maxStagnantDrops}`);
                
                if (this.stagnantDrops >= this.maxStagnantDrops) {
                    this.finishDropping('saturated');
                    return;
                }
            } else {
                // Progress made, reset counter
                this.stagnantDrops = 0;
                this.lastInsideCount = currentInside;
            }
        }

        if (this.onStatusUpdate) {
            let progressText;
            if (this.autoMode) {
                if (this.pieceWeight > 0 && this.maxWeight > 0) {
                    const weightStr = this.currentTotalWeight.toFixed(2);
                    progressText = `🌊 Mode automàtic: ${this.droppedCount} peces | ⚖️ ${weightStr}/${this.maxWeight} kg`;
                } else {
                    progressText = `🌊 Mode automàtic: ${this.droppedCount} peces (fins que la caixa es plenarà)`;
                }
            } else {
                progressText = `🌊 Deixant caure peces: ${this.droppedCount}/${this.maxPieces}`;
            }
            this.onStatusUpdate({
                status: 'running',
                dropped: this.droppedCount,
                message: progressText
            });
        }
    }

    /**
     * Count pieces that have fallen outside the box
     */
    countPiecesOutside() {
        if (!this.boxDims) return 0;
        
        const { length, width, height } = this.boxDims;
        const margin = 50;
        let count = 0;
        
        for (const { body } of this.physics.meshBodies) {
            if (!body.isValid()) continue;
            const pos = body.translation();
            // Check if outside box bounds or fallen below
            // Relaxed check: Only count if fallen BELOW floor or FAR outside XY
            // Ignore pieces bouncing UP (y > 0)
            if (pos.y < -margin || 
                pos.x < -margin || pos.x > length + margin ||
                pos.z < -margin || pos.z > width + margin) {
                count++;
            }
        }
        
        return count;
    }
    
    /**
     * Count pieces that are stuck above the box (not falling into it)
     * These are pieces that have settled above the box height
     */
    countPiecesAboveBox() {
        if (!this.boxDims) return 0;
        
        const { length, width, height } = this.boxDims;
        let count = 0;
        
        for (const { body } of this.physics.meshBodies) {
            if (!body.isValid()) continue;
            const pos = body.translation();
            const vel = body.linvel();
            const speed = Math.sqrt(vel.x ** 2 + vel.y ** 2 + vel.z ** 2);
            
            // Piece is above box, within XZ bounds, and nearly stationary
            if (pos.y > height + 20 && 
                pos.x > -20 && pos.x < length + 20 &&
                pos.z > -20 && pos.z < width + 20 &&
                speed < 50) { // Slow enough to be considered "stuck"
                count++;
            }
        }
        
        return count;
    }
    
    /**
     * Finish dropping and start vibration phase
     */
    finishDropping(reason) {
        if (this.allDropped) return;
        this.allDropped = true;
        
        clearInterval(this.dropInterval);
        this.dropInterval = null;
        
        const reasonText = reason === 'overflow' 
            ? `(caixa plena - ${this.maxOverflow} peces han caigut fora)`
            : reason === 'saturated'
            ? `(saturació detectada - cap peça nova entra a la caixa)`
            : reason === 'weight'
            ? `(pes màxim assolit: ${this.currentTotalWeight.toFixed(2)} kg)`
            : '';
        
        // Start vibration phase to settle pieces
        this.vibrationPhase = true;
        this.physics.startVibration(5000); // 5 seconds of vibration
        
        if (this.onStatusUpdate) {
            this.onStatusUpdate({
                status: 'vibrating',
                dropped: this.droppedCount,
                message: `📳 ${this.droppedCount} peces deixades caure ${reasonText}. Vibrant caixa per encaixar peces...`
            });
        }
        
        // Start settling timeout
        this.settlingTimeout = setTimeout(() => {
            this.forceFinish();
        }, this.settlingTimeoutMs);
    }
    
    /**
     * Force finish after timeout
     */
    /**
     * Finalize simulation after Lid Press
     */
    finishSimulation() {
         // Final Cleanup (Strict)
        const strictRemoved = this.physics.removePiecesOutsideBox(this.scene, this.pieceDims, 2);
        const finalCount = this.physics.countPiecesInBox();
        
        // SMART REFILL LOGIC
        // If we removed pieces, it means we might have created space during compaction.
        // Let's try to add back some of the pieces we just removed?
        // Or better: if we removed X pieces, maybe we can fit X/2 back in now that it's compacted?
        if (strictRemoved > 0 && !this.hasRefilled) {
            this.hasRefilled = true;
            this.hasPressedLid = false; // Reset lid flag so we can press again later
            
            // Calculate how many to try adding back
            // Let's be optimistic: try adding back 50% of what was removed
            const toRefill = Math.max(1, Math.floor(strictRemoved * 0.5));
            
            if (this.onStatusUpdate) {
                this.onStatusUpdate({
                    status: 'refilling',
                    message: `🔄 Compactació feta. ${strictRemoved} peces tretes. Intentant re-afegir ${toRefill} peces als forats...`
                });
            }
            
            // Start refill phase
            this.startRefill(toRefill);
            return;
        }

        this.stop();
        
        if (this.onStatusUpdate) {
            const removedText = strictRemoved > 0 ? ` (${strictRemoved} eliminades post-tapa)` : '';
            const refillText = this.hasRefilled ? ' (amb re-farcit automàtic)' : '';
            this.onStatusUpdate({
                status: 'settled',
                dropped: this.droppedCount,
                inside: finalCount,
                removed: strictRemoved,
                message: `✅ Finalitzat: ${finalCount} peces dins la caixa (compactat amb tapa${refillText})`
            });
        }
    }

    /**
     * Start the refill phase
     */
    startRefill(count) {
        this.refillTarget = count;
        this.refillDropped = 0;
        this.isRunning = true;
        this.physics.isRunning = true;
        this.lastUpdateTime = performance.now();
        
        // Drop loop for refill
        this.refillInterval = setInterval(() => {
            if (this.refillDropped >= this.refillTarget) {
                clearInterval(this.refillInterval);
                this.refillInterval = null;
                
                // After refill drops, vibrate briefly then Lid Press again
                this.vibrationPhase = true;
                this.physics.startVibration(3000); // Shorter vibration
                // The update loop will catch end of vibration and trigger Lid Press (since hasPressedLid is false)
                return;
            }
            this.dropPiece();
            this.refillDropped++;
        }, this.dropIntervalMs);
        
        // Ensure update loop is running
        this.update();
    }
    
    /**
     * Force finish after timeout
     */
    forceFinish() {
        // If timeout hits, just finish (maybe skip lid if it stuck?)
        // Or try to run lid if we haven't?
        // Let's just standard finish to be safe.
        this.finishSimulation();
    }

    /**
     * Stop the simulation
     */
    stop() {
        this.isRunning = false;
        this.physics.pause();
        
        if (this.dropInterval) {
            clearInterval(this.dropInterval);
            this.dropInterval = null;
        }
        
        if (this.refillInterval) {
            clearInterval(this.refillInterval);
            this.refillInterval = null;
        }
        
        if (this.settlingTimeout) {
            clearTimeout(this.settlingTimeout);
            this.settlingTimeout = null;
        }
    }

    /**
     * Reset everything
     */
    reset() {
        this.stop();
        this.physics.reset();
        this.scene.clearPieces();
        this.droppedCount = 0;
        this.overflowCount = 0;
        this.allDropped = false;
        this.vibrationPhase = false;
        this.lastUpdateTime = 0;
        this.lastInsideCount = 0;
        this.stagnantDrops = 0;
        this.hasRetried = false;
        this.retryCount = 0;
        this.currentTotalWeight = 0;
        
        if (this.onStatusUpdate) {
            this.onStatusUpdate({
                status: 'reset',
                dropped: 0,
                message: '🔄 Simulació reiniciada'
            });
        }
    }

    dispose() {
        this.stop();
        this.physics.dispose();
    }
}

export default { initRapier, PhysicsWorld, BulkSimulation };
