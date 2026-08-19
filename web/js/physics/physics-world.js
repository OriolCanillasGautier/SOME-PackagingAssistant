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
        console.log('Rapier physics engine initialized');
        return true;
    } catch (error) {
        console.error('Failed to initialize Rapier:', error);
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
        this.numSolverIterations = 32;
        this.numAdditionalFrictionIterations = 16;
        this.numVelocitySolverIterations = 16;
        
        // Vibration settings
        this.isVibrating = false;
        this.vibrationTime = 0;
        this.vibrationDuration = 5000; // 5 seconds of vibration
        this.vibrationFrequency = 8.0; // Hz
        this.vibrationAmplitude = 0.5; // mm
        this.vibrationPhaseOffsets = [];
        this.vibrationFrequencyJitter = 0.25; // +/- 25%
        this.vibrationAmplitudeJitter = 0.35; // +/- 35%
        this.vibrationNoise = 0.15; // mm random jitter per step

        // Settle detection thresholds (configurable per-mode)
        this.settleVelocityThreshold = 5.0; // mm/s
        this.settleAngularThreshold = 0.5;  // rad/s
        this.settleFramesRequired = 60;     // ~1s at 60fps
        
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
     * Add a ceiling to close the container (useful for gravity verification)
     * Keeps pieces from escaping above the visual box.
     * `height` is the Y position of the ceiling top surface.
     * Also raises the 4 side walls up to the ceiling: pieces are dropped from
     * well above the box, and without tall walls they drift/tumble outside
     * the box footprint before reaching the short visual walls.
     */
    addCeiling({ length, width, height }, thickness = 100) {
        if (!this.world) return;
        const t = thickness;
        const wallTop = height + t / 2;
        const wallPlanes = [
            { x: length / 2, z: -t / 2, hx: length / 2 + t, hz: t / 2 },          // back
            { x: length / 2, z: width + t / 2, hx: length / 2 + t, hz: t / 2 },  // front
            { x: -t / 2, z: width / 2, hx: t / 2, hz: width / 2 + t },           // left
            { x: length + t / 2, z: width / 2, hx: t / 2, hz: width / 2 + t },   // right
        ];
        for (let i = 0; i < 4; i++) {
            const old = this.wallBodies[1 + i];
            if (old && typeof old.isValid === 'function' && old.isValid()) {
                this.world.removeRigidBody(old);
            }
            const p = wallPlanes[i];
            const body = this.createKinematicBox(
                p.x, wallTop / 2, p.z,
                p.hx, wallTop / 2 + t, p.hz
            );
            this.wallBodies[1 + i] = body;
            this.wallOriginalPositions[1 + i] = { x: p.x, y: wallTop / 2, z: p.z };
        }

        const ceiling = this.createKinematicBox(
            length / 2,
            height - t / 2,
            width / 2,
            length / 2 + t,
            t / 2,
            width / 2 + t
        );
        this.wallBodies.push(ceiling);
        this.wallOriginalPositions.push({ x: length / 2, y: height - t / 2, z: width / 2 });
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
            .setRestitution(0.0)
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
        // Randomize phase per wall to avoid coherent motion
        this.vibrationPhaseOffsets = this.wallBodies.map(() => ({
            px: Math.random() * Math.PI * 2,
            py: Math.random() * Math.PI * 2,
            pz: Math.random() * Math.PI * 2,
            freqScale: 1 + (Math.random() * 2 - 1) * this.vibrationFrequencyJitter,
            ampScale: 1 + (Math.random() * 2 - 1) * this.vibrationAmplitudeJitter
        }));
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
        
        // Calculate vibration offset using MULTI-FREQUENCY sine waves:
        //  - a LOW-frequency, higher-amplitude "jostle" wave that knocks pieces
        //    out of arches and into the low spots
        //  - a HIGH-frequency, lower-amplitude "settle" wave that keeps the top
        //    layer fluid so it slides into gaps
        //  - a slow "thump" pulse that periodically punches the whole box to
        //    break up any arch that forms mid-cycle
        const t = this.vibrationTime / 1000; // seconds
        const progress = this.vibrationTime / this.vibrationDuration; // 0 to 1
        const baseFreq = this.vibrationFrequency;
        const baseAmp = this.vibrationAmplitude;
        
        // PROGRESSIVE AMPLITUDE ENVELOPE:
        // Strong at the start (breaks arches), decaying smoothly to near zero
        // so pieces settle into the low spots without being re-jostled at the end.
        const env = Math.pow(1 - progress, 1.15);
        
        // Slow ~0.5 Hz thump that periodically punches the box to break arches.
        const thump = 0.6 + 0.4 * Math.sin(2 * Math.PI * 0.5 * t + Math.sin(2 * Math.PI * 0.5 * t + 1.7));
        
        // Apply offset to all walls
        for (let i = 0; i < this.wallBodies.length; i++) {
            const body = this.wallBodies[i];
            const orig = this.wallOriginalPositions[i];
            const phase = this.vibrationPhaseOffsets[i] || { px: 0, py: 0, pz: 0, freqScale: 1, ampScale: 1 };
            
            const fLow = baseFreq * phase.freqScale;
            const fHigh = fLow * 3.7; // high-frequency settle component
            const amp = baseAmp * phase.ampScale * env;
            const noise = (Math.random() * 2 - 1) * this.vibrationNoise * env;

            // Horizontal (X): full multi-frequency + thump
            const jx = Math.sin(2 * Math.PI * fLow * t + phase.px) +
                       0.5 * Math.sin(2 * Math.PI * fHigh * t + phase.px * 0.7) +
                       thump * 0.6 * Math.sin(2 * Math.PI * fLow * 0.5 * t + phase.px * 1.3);
            // Vertical (Y): softer so pieces lift-and-drop instead of launching;
            // floor (index 0) only gets a light nudge (never enough to eject pieces)
            const jy = Math.sin(2 * Math.PI * fLow * 1.3 * t + phase.py + 0.5) +
                       0.4 * Math.sin(2 * Math.PI * fHigh * 0.9 * t + phase.py * 0.9) +
                       thump * 0.4 * Math.sin(2 * Math.PI * fLow * 0.7 * t + phase.py * 1.1 + 0.5);
            // Horizontal (Z): full multi-frequency + thump
            const jz = Math.sin(2 * Math.PI * fLow * 1.1 * t + phase.pz + 1.0) +
                       0.5 * Math.sin(2 * Math.PI * fHigh * t + phase.pz * 0.6) +
                       thump * 0.6 * Math.sin(2 * Math.PI * fLow * 0.5 * t + phase.pz * 1.3 + 1.0);

            const offsetX = amp * jx + noise;
            const offsetZ = amp * jz + noise;
            let offsetY = amp * jy + noise * 0.5;
            if (i === 0) offsetY = amp * 0.35 * jy; // Floor: light vertical only

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
    addCuboid(dims, position, rotation = null, mesh = null, meshOffset = null) {
        const { l, w, h } = dims;
        
        // Create dynamic rigid body
        const bodyDesc = RAPIER.RigidBodyDesc.dynamic()
            .setTranslation(position.x, position.y, position.z)
            .setLinearDamping(0.1)
            .setAngularDamping(0.3)
            .setCcdEnabled(true); // Continuous collision detection
        
        // Apply rotation if provided
        if (rotation) {
            const quat = new THREE.Quaternion().setFromEuler(rotation);
            bodyDesc.setRotation({ x: quat.x, y: quat.y, z: quat.z, w: quat.w });
        }

        const body = this.world.createRigidBody(bodyDesc);
        
        // SYNC MESH IMMEDIATELY to prevent (0,0,0) flicker
        if (mesh) {
            // Initial sync (offset handled in step)
            mesh.position.set(position.x, position.y, position.z);
            if (rotation) {
                const quat = new THREE.Quaternion().setFromEuler(rotation);
                mesh.quaternion.set(quat.x, quat.y, quat.z, quat.w);
            }
            this.meshBodies.push({ body, mesh, offset: meshOffset });
        }
        
        // Create cuboid collider (half-extents)
        // Use slightly smaller collider to reduce interpenetration
        const colliderDesc = RAPIER.ColliderDesc.cuboid(l / 2 * 0.95, h / 2 * 0.95, w / 2 * 0.95)
            .setDensity(2.0)
            .setFriction(0.5)
            .setRestitution(0.0)
            .setContactForceEventThreshold(0.01);

        this.world.createCollider(colliderDesc, body);
        this.bodies.push(body);

        return body;
    }

    /**
     * Add a convex hull piece for STL
     */
    addConvexHull(vertices, position, rotation = null, mesh = null, meshOffset = null, options = {}) {
        const hullScale = (typeof options?.hullScale === 'number' && Number.isFinite(options.hullScale))
            ? options.hullScale
            : 1.0;

        const bodyDesc = RAPIER.RigidBodyDesc.dynamic()
            .setTranslation(position.x, position.y, position.z)
            .setLinearDamping(0.2)
            .setAngularDamping(0.5)
            .setCcdEnabled(true);
        
        if (rotation) {
            const quat = new THREE.Quaternion().setFromEuler(rotation);
            bodyDesc.setRotation({ x: quat.x, y: quat.y, z: quat.z, w: quat.w });
        }

        const body = this.world.createRigidBody(bodyDesc);
        
        // SYNC MESH IMMEDIATELY to prevent (0,0,0) flicker
        if (mesh) {
            // Initial sync (offset handled in step)
            mesh.position.set(position.x, position.y, position.z);
            if (rotation) {
                const quat = new THREE.Quaternion().setFromEuler(rotation);
                mesh.quaternion.set(quat.x, quat.y, quat.z, quat.w);
            }
            this.meshBodies.push({ body, mesh, offset: meshOffset });
        }
        
        // Optionally shrink hull slightly to prevent initial micro-interpenetration
        let hullVertices = vertices;
        if (hullScale !== 1.0) {
            hullVertices = new Float32Array(vertices.length);
            for (let i = 0; i < vertices.length; i += 3) {
                hullVertices[i] = vertices[i] * hullScale;
                hullVertices[i + 1] = vertices[i + 1] * hullScale;
                hullVertices[i + 2] = vertices[i + 2] * hullScale;
            }
        }

        // Try convex hull, fallback to bounding box
        let colliderDesc = null;
        try {
            colliderDesc = RAPIER.ColliderDesc.convexHull(hullVertices);
        } catch (e) {
            console.warn('Convex hull failed, using bounding box');
        }
        
        if (!colliderDesc) {
            // Calculate bounding box from vertices
            let minX = Infinity, maxX = -Infinity;
            let minY = Infinity, maxY = -Infinity;
            let minZ = Infinity, maxZ = -Infinity;
            
            for (let i = 0; i < hullVertices.length; i += 3) {
                minX = Math.min(minX, hullVertices[i]);
                maxX = Math.max(maxX, hullVertices[i]);
                minY = Math.min(minY, hullVertices[i + 1]);
                maxY = Math.max(maxY, hullVertices[i + 1]);
                minZ = Math.min(minZ, hullVertices[i + 2]);
                maxZ = Math.max(maxZ, hullVertices[i + 2]);
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
        
        return body;
    }

    /**
     * Step the physics simulation and sync meshes
     */
    step() {
        if (!this.world || !this.isRunning) return false;
        
        const subSteps = 4;
        const dt = 1/240;
        this.world.timestep = dt;
        
        for (let i = 0; i < subSteps; i++) {
            // Update vibration PER SUBSTEP for perfect smoothness
            if (this.isVibrating) {
                this.updateVibration(dt * 1000);
            }
            
            // Update Lid animation PER SUBSTEP if active
            if (this.lidState !== 'idle' && this.lidState !== 'finished') {
                this.updateLid(dt * 1000);
            }
            
            this.world.step();
        }
        
        // Sync Three.js meshes with physics bodies once per frame (after all substeps)
        for (const { body, mesh, offset } of this.meshBodies) {
            if (!body.isValid()) continue; // Skip removed bodies
            
            const pos = body.translation();
            const rot = body.rotation();

            mesh.quaternion.set(rot.x, rot.y, rot.z, rot.w);

            if (offset && typeof offset.x === 'number') {
                // Body translation is at COM; mesh origin may be offset (e.g. base-aligned STL)
                const q = new THREE.Quaternion(rot.x, rot.y, rot.z, rot.w);
                const off = new THREE.Vector3(offset.x, offset.y, offset.z).applyQuaternion(q);
                mesh.position.set(pos.x - off.x, pos.y - off.y, pos.z - off.z);
            } else {
                mesh.position.set(pos.x, pos.y, pos.z);
            }
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
        
        const vThresh = this.settleVelocityThreshold;
        const aThresh = this.settleAngularThreshold;
        let allSettled = true;
        
        for (const { body } of this.meshBodies) {
            const linVel = body.linvel();
            const angVel = body.angvel();
            const speed = Math.sqrt(linVel.x ** 2 + linVel.y ** 2 + linVel.z ** 2);
            const angSpeed = Math.sqrt(angVel.x ** 2 + angVel.y ** 2 + angVel.z ** 2);
            
            if (speed > vThresh || angSpeed > aThresh) {
                allSettled = false;
                break;
            }
        }

        if (allSettled) {
            this.settledCount++;
            if (this.settledCount > this.settleFramesRequired && this.onSettled) {
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
                pos.y > -margin && pos.y < height + margin * 2) {
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
        const completelyOutside = maxY < -20 || pos.y > height + 1000 || 
                                maxX < -10 || minX > length + 10 || 
                                maxZ < -10 || minZ > width + 10;
        
        if (strictness === 0) {
            shouldRemove = completelyOutside;
        } 
        // Level 1: Semi - SLACKER logic for intermediate cycles
        // Only remove if center is SIGNIFICANTLY above height or horizontally outside
        else if (strictness === 1) {
            const horizOutside = maxX < -5 || minX > length + 5 || maxZ < -5 || minZ > width + 5;
            const significantlyAbove = pos.y > height + 20; 
            shouldRemove = completelyOutside || horizOutside || significantlyAbove;
        }
        // Level 2: Strict - Final report cleanup (with small wall tolerance so
        // pieces resting against the walls aren't over-removed)
        else if (strictness === 2) {
            const wallTol = 5;
            const horizOutside = maxX < -wallTol || minX > length + wallTol || maxZ < -wallTol || minZ > width + wallTol;
            const heightTolerance = pieceDims ? Math.min(20, pieceDims.h * 0.3) : 20;
            shouldRemove = completelyOutside || horizOutside || maxY > height + heightTolerance;
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
        // Cleanup old lid if it somehow exists
        if (this.lidBody) {
            if (this.lidBody.isValid()) this.world.removeRigidBody(this.lidBody);
            this.lidBody = null;
        }
        
        if (this.lidMesh) {
            if (this.lidMesh.parent) this.lidMesh.parent.remove(this.lidMesh);
            if (this.lidMesh.geometry) this.lidMesh.geometry.dispose();
            if (this.lidMesh.material) this.lidMesh.material.dispose();
            this.lidMesh = null;
        }

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
        
        // Start vibration to help settlement while pressing (only if not already vibrating)
        if (!this.isVibrating) this.startVibration(6000);
        
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
        
        const speed = 0.1 * dtMs;
        
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
                
            case 'holding': {
                this.lidHoldTime += dtMs;
                // MICRO-VIBRATION (shake-and-press): while the lid is pressing,
                // give it small high-frequency lateral motions so the top layer
                // vibrates into the gaps below instead of just being crushed.
                // The shake tapers off over the hold so pieces settle in place.
                const holdProgress = Math.min(1, this.lidHoldTime / 3000);
                const shakeAmp = 1.6 * Math.max(0.25, 1 - holdProgress);
                const shakeFreq = 16;
                const sx = shakeAmp * Math.sin(2 * Math.PI * shakeFreq * this.lidHoldTime / 1000 + 0.7);
                const sz = shakeAmp * Math.cos(2 * Math.PI * shakeFreq * 0.9 * this.lidHoldTime / 1000);
                this.lidBody.setNextKinematicTranslation({
                    x: this.boxDims.length / 2 + sx,
                    y: pos.y,
                    z: this.boxDims.width / 2 + sz
                });
                if (this.lidHoldTime > 3000) { // Hold 3 seconds
                    this.lidState = 'ascending';
                    this.stopVibration(); // Stop vibration when we start lifting
                    console.log('Lid ascending...');
                }
                break;
            }
                
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

    setGravity(value) {
        this.gravity = value;
        if (this.world) {
            this.world.gravity = { x: 0.0, y: value, z: 0.0 };
        }
    }

    lockAllRotations(lock = true) {
        const bodies = this.meshBodies.map(m => m.body).concat(this.bodies);
        for (const body of bodies) {
            if (!body || !body.isValid?.()) continue;
            if (typeof body.lockRotations === 'function') {
                body.lockRotations(lock, true);
            } else if (typeof body.setEnabledRotations === 'function') {
                const enable = !lock;
                body.setEnabledRotations(enable, enable, enable, true);
            }
        }
    }

    /**
     * Change friction coefficient on all piece colliders at runtime.
     */
    setAllFriction(friction) {
        for (const { body } of this.meshBodies) {
            if (!body || !body.isValid?.()) continue;
            const numC = body.numColliders();
            for (let c = 0; c < numC; c++) {
                const col = body.collider(c);
                if (col && col.isValid()) col.setFriction(friction);
            }
        }
    }

    /**
     * Apply a small random horizontal impulse to every piece.
     * Rotations stay locked; pieces only slide laterally.
     * @param {number} strength — impulse magnitude in mm·kg/s
     */
    applyLateralJitter(strength = 50) {
        for (const { body } of this.meshBodies) {
            if (!body || !body.isValid?.()) continue;
            const ix = (Math.random() * 2 - 1) * strength;
            const iz = (Math.random() * 2 - 1) * strength;
            body.applyImpulse({ x: ix, y: 0, z: iz }, true);
        }
    }

    /**
     * Run N physics substeps without rendering — resolves interpenetration.
     * @param {number} steps — number of world.step() calls
     */
    warmUp(steps = 100) {
        if (!this.world) return;
        const dt = 1 / 240;
        this.world.timestep = dt;
        for (let i = 0; i < steps; i++) {
            this.world.step();
        }
        // Sync meshes after warm-up so visuals reflect resolved positions
        for (const { body, mesh, offset } of this.meshBodies) {
            if (!body.isValid()) continue;
            const pos = body.translation();
            const rot = body.rotation();
            mesh.quaternion.set(rot.x, rot.y, rot.z, rot.w);
            if (offset && typeof offset.x === 'number') {
                const q = new THREE.Quaternion(rot.x, rot.y, rot.z, rot.w);
                const off = new THREE.Vector3(offset.x, offset.y, offset.z).applyQuaternion(q);
                mesh.position.set(pos.x - off.x, pos.y - off.y, pos.z - off.z);
            } else {
                mesh.position.set(pos.x, pos.y, pos.z);
            }
        }
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
        
        // Reset lid state
        if (this.lidMesh && this.lidMesh.parent) {
            this.lidMesh.parent.remove(this.lidMesh);
        }
        this.lidMesh = null;
        this.lidBody = null;
        this.lidState = 'idle';
        
        if (this.world && this.boxDims) {
            // Recreate world to clear all bodies
            const gravity = { x: 0.0, y: this.gravity, z: 0.0 };
            this.world = new RAPIER.World(gravity);
            this.createBoxContainer(this.boxDims);
        }
    }

    dispose() {
        this.isRunning = false;
        this.isVibrating = false;
        this.onSettled = null;
        this.settledCount = 0;
        this.meshBodies = [];
        this.bodies = [];
        this.wallBodies = [];
        this.wallOriginalPositions = [];
        // Free the Rapier world to release WASM memory
        if (this.world) {
            try { this.world.free(); } catch (_) { /* already freed */ }
            this.world = null;
        }
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
        this.maxStagnantDrops = 8; // Stop after 8 consecutive checks without increase
        this.checkInterval = 30; // Check every 30 drops
        
        // Track pieces above box to detect overflow faster
        this.piecesAboveBox = 0;
        this.maxPiecesAboveBox = 12; // If 12+ pieces are stuck above, box is full
        
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
        
        this.vibrationPhase = false;
        this.lastUpdateTime = 0;
        
        // Refill cycles tracking
        this.currentCycle = 1;
        this.maxRefillCycles = 1; // Single refill, single final lid press

        // Enable lid press for compaction between cycles
        this.enableLidPress = true;
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
            vibrationFrequency = null,
            vibrationAmplitude = null,
            vibrationNoise = null,
            pieceWeight = 0,
            maxWeight = 0
        } = options;

        this.boxDims = boxDims;
        this.pieceDims = pieceDims;
        this.stlGeometry = stlGeometry;
        this.maxPieces = autoMode ? 20000 : maxPieces; // High limit in auto mode (safety cap)
        this.dropHeight = dropHeight;
        this.dropIntervalMs = dropIntervalMs;
        this.randomRotation = randomRotation;
        this.droppedCount = 0;
        this.autoMode = autoMode;
        this.maxOverflow = autoMode ? 12 : 20; // Stop soon after pieces start falling out
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

        // Invisible ceiling above the drop point: pieces fall from well above
        // the box walls and small/light pieces can bounce over them. The
        // ceiling keeps everything inside so nothing is lost even with
        // vibration disabled. Clearance includes the piece's own height so
        // spawned pieces never overlap the ceiling.
        this.physics.addCeiling({
            length: boxDims.length,
            width: boxDims.width,
            height: boxDims.height + this.dropHeight + 200 + Math.max(0, this.pieceDims?.h || 0),
        }, 100);

        // Apply vibration tuning if provided
        if (Number.isFinite(vibrationFrequency)) {
            this.physics.vibrationFrequency = vibrationFrequency;
        }
        if (Number.isFinite(vibrationAmplitude)) {
            this.physics.vibrationAmplitude = vibrationAmplitude;
        }
        if (Number.isFinite(vibrationNoise)) {
            this.physics.vibrationNoise = vibrationNoise;
        }

        // Setup settled callback (FINAL completion only)
        // Setup settled callback (FINAL completion only)
        this.physics.onSettled = (count) => {
            // Guard: only finish once the lid press is done and we are in the
            // final settle phase — otherwise pieces settling briefly between
            // drops (or during the compaction vibration) would end the sim early.
            if (this.allDropped && this.hasPressedLid && this.physics.lidState === 'finished') {
                this.finishSimulation();
            }
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
        this.hasRefilled = false;
        this.hasPressedLid = false;
        this.currentCycle = 1;
        
        // Clear any existing timeout
        if (this.settlingTimeout) {
            clearTimeout(this.settlingTimeout);
            this.settlingTimeout = null;
        }
        
        // Start dropping pieces at intervals
        this.dropInterval = setInterval(() => this.dropPiece(), this.dropIntervalMs);
        
        // Apply constant vibration during dropping to help pieces settle
        // The vibration should stop when the drop phase ends (managed in stop/reset)
        this.physics.startVibration(3600000); // 1 hour (effectively until stopped)
        
        // Start physics update loop
        this.update();

        if (this.onStatusUpdate) {
            const modeText = this.autoMode ? '(mode automàtic)' : '';
            this.onStatusUpdate({
                status: 'running',
                dropped: 0,
                message: `Simulació iniciada... ${modeText}`
            });
        }
    }

    /**
     * Main update loop - called every frame
     */
    update() {
        if (!this.isRunning) return;
        
        // Calculate delta time (still needed for refill and dropping)
        const now = performance.now();
        const deltaMs = this.lastUpdateTime ? (now - this.lastUpdateTime) : 16.67;
        this.lastUpdateTime = now;
        
        // Vibration check - now handled solely by flags and finishSimulation
        // The lid sequence initiation is now in finishDropping or startRefill
        
        // Step physics (sub-stepping is handled inside physics.step)
        const settled = this.physics.step();
        
        // Check if everything is truly settled (only after lid is finished)
        if (settled && !this.vibrationPhase && (this.hasPressedLid && this.physics.lidState === 'finished')) {
            this.isRunning = false;
            return;
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
        // TIGHTER MARGIN to prevent falling outside
        const safeMargin = Math.max(l, w) * 0.8; 
        const validLength = Math.max(10, length - safeMargin * 2);
        const validWidth = Math.max(10, width - safeMargin * 2);
        
        const x = safeMargin + Math.random() * validLength;
        const z = safeMargin + Math.random() * validWidth;
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
            
            // Set initial position/rotation BEFORE adding to scene
            mesh.position.copy(position);
            if (rotation) mesh.quaternion.setFromEuler(rotation);
            
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
                    progressText = `Mode automàtic: ${this.droppedCount} peces | ${weightStr}/${this.maxWeight} kg`;
                } else {
                    progressText = `Mode automàtic: ${this.droppedCount} peces (fins que la caixa es plenarà)`;
                }
            } else {
                progressText = `Deixant caure peces: ${this.droppedCount}/${this.maxPieces}`;
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
        clearInterval(this.refillInterval);
        this.refillInterval = null;
        
        const reasonText = reason === 'overflow' 
            ? `(caixa plena - ${this.maxOverflow} peces han caigut fora)`
            : reason === 'saturated'
            ? `(saturació detectada - cap peça nova entra a la caixa)`
            : reason === 'weight'
            ? `(pes màxim assolit: ${this.currentTotalWeight.toFixed(2)} kg)`
            : '';

        // 1. PRE-CLEANUP (Level 0: only completely outside)
        const removed = this.physics.removePiecesOutsideBox(this.scene, this.pieceDims, 0);
        
        // 2. START VIBRATION (more aggressive for better compaction)
        this.vibrationPhase = true;
        this.physics.vibrationAmplitude = 1.0; // Stronger vibration between cycles
        this.physics.startVibration(8000); // 8 seconds of vibration
        
        if (this.onStatusUpdate) {
            this.onStatusUpdate({
                status: 'vibrating',
                dropped: this.droppedCount,
                message: `${removed} peces fora. Vibrant i encaixant peces... ${reasonText}`
            });
        }
        
        // 3. Vibrate and press CONCURRENTLY — but press only on the FINAL
        //    cycle so there is exactly one lid compression.
        const isFinalCycle = this.currentCycle > this.maxRefillCycles;
        if (this.enableLidPress && isFinalCycle) {
            setTimeout(() => {
                if (!this.isRunning) return;
                this.hasPressedLid = true;
                
                if (this.onStatusUpdate) {
                    this.onStatusUpdate({
                        status: 'compacting',
                        message: `Vibració activa + Premsatge amb tapa...`
                    });
                }
                
                this.physics.startLidSequence(this.scene, () => {
                    this.vibrationPhase = false; // Ensure vibration phase flag is cleared
                    this.physics.stopVibration(); // Stop shaking immediately to speed up cycle
                    this.finalSettle();
                });
            }, 1000); // 1 second headstart for vibration
        } else {
            // Non-final cycle: vibrate only, then refill
            setTimeout(() => {
                if (!this.isRunning) return;
                this.vibrationPhase = false;
                this.physics.stopVibration();
                this.finishSimulation();
            }, 6000);
        }
        
        // Start settling timeout (safety)
        this.settlingTimeout = setTimeout(() => {
            if (this.isRunning) this.forceFinish();
        }, this.settlingTimeoutMs);
    }
    
    /**
     * Force finish after timeout
     */
    /**
     * Finalize simulation after Lid Press
     */
    /**
     * Post-lid settle phase: a short, gentle vibration to let the compacted
     * pieces settle fully, then finish once everything is at rest.
     * If the pieces never settle within the safety window we force-finish.
     */
    finalSettle(settleTimeoutMs = 10000) {
        this.physics.settledCount = 0;
        // Gentle tail: keep a modest amplitude so the top layer still has some
        // freedom to settle, but drop the noise so it goes quiet at the end.
        this.physics.vibrationAmplitude = Math.max(0.5, this.physics.vibrationAmplitude * 0.6);
        this.physics.vibrationNoise = Math.min(this.physics.vibrationNoise, 0.05);
        this.physics.startVibration(2000); // 2s gentle vibration
        
        // Wait for the pieces to reach equilibrium before finishing.
        this.physics.onSettled = () => {
            this.physics.stopVibration();
            if (this.settlingTimeout) { clearTimeout(this.settlingTimeout); this.settlingTimeout = null; }
            this.finishSimulation();
        };
        
        // Safety: never block completion on a stuck pile.
        this.settlingTimeout = setTimeout(() => {
            if (this.isRunning) {
                this.physics.stopVibration();
                this.finishSimulation();
            }
        }, settleTimeoutMs);
        
        if (this.onStatusUpdate) {
            this.onStatusUpdate({
                status: 'settling',
                message: 'Premsat finalitzat. Deixant assentir les peces...'
            });
        }
    }

    /**
     * Force finish after timeout
     */
    finishSimulation() {
        // Final Cleanup for this cycle (Relaxed Level 0)
        const semiRemoved = this.physics.removePiecesOutsideBox(this.scene, this.pieceDims, 0);
        const currentCount = this.physics.countPiecesInBox();
        
        // DECIDE IF WE NEED ANOTHER CYCLE
        // We refill if: we haven't reached max cycles AND (we removed many pieces OR there's a lot of space)
        const shouldRefill = this.currentCycle <= this.maxRefillCycles;
        
        if (shouldRefill) {
            this.currentCycle++;
            
            // Calculate proactive refill amount
            // Estimate space for at least 80% of maxPieces or at least 50 pieces
            const proactiveAmount = Math.max(50, Math.floor(this.maxPieces * 0.8));
            let refillCount = Math.max(proactiveAmount, semiRemoved + 20);
            // In auto mode maxPieces is a huge safety cap (20000) — cap the refill
            // to a sane multiple of the box's real volumetric capacity instead,
            // so we don't try to "add 16000 pieces" to a near-full box.
            if (this.autoMode && this.pieceDims) {
                const pieceVol = Math.max(1, this.pieceDims.l * this.pieceDims.w * this.pieceDims.h);
                const boxVol = Math.max(1, this.boxDims.length * this.boxDims.width * this.boxDims.height);
                const approxCapacity = Math.max(1, Math.floor(boxVol / pieceVol));
                refillCount = Math.min(refillCount, Math.max(50, approxCapacity * 2));
            }
            
            if (this.onStatusUpdate) {
                this.onStatusUpdate({
                    status: 'refilling',
                    message: `Cicle ${this.currentCycle-1} completat. Afegint ${refillCount} peces més per omplir buits...`
                });
            }
            
            this.startRefill(refillCount);
            return;
        }

        // COMPLETELY FINISHED
        const finalRemoved = this.physics.removePiecesOutsideBox(this.scene, this.pieceDims, 2);
        const finalCount = this.physics.countPiecesInBox();
        this.stop();
        
        if (this.onStatusUpdate) {
            this.onStatusUpdate({
                status: 'settled',
                dropped: this.droppedCount,
                inside: finalCount,
                removed: finalRemoved,
                message: `Finalitzat: ${finalCount} peces dins la caixa (compactat en ${this.currentCycle} cicles)`
            });
        }
    }

    /**
     * Start the refill phase
     */
    startRefill(count) {
        this.refillTarget = count;
        this.refillDropped = 0;
        
        // Reset flags for the new drop phase
        this.allDropped = false; 
        this.hasPressedLid = false;
        this.vibrationPhase = false;
        
        this.isRunning = true;
        this.physics.isRunning = true;
        this.lastUpdateTime = performance.now();
        
        // Reset physics world slightly if needed? No, just keep going.
        
        // Drop loop for refill
        this.refillInterval = setInterval(() => {
            if (this.refillDropped >= this.refillTarget) {
                clearInterval(this.refillInterval);
                this.refillInterval = null;
                
                // After refill drops, finish cycle (which triggers vibration -> lid)
                this.finishDropping('refill');
                return;
            }
            this.dropPiece();
            this.refillDropped++;
        }, this.dropIntervalMs);
        
        // Ensure update loop is running (only if not already)
        // Note: we don't call this.update() directly here anymore to avoid double loops
        if (!this.isRunning) this.update();
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
        this.physics.stopVibration(); // Stop any active vibration

        // Remove the lid if it's still around (e.g. force-finished mid-press)
        if (this.physics.lidBody) {
            if (this.physics.lidBody.isValid()) this.physics.world.removeRigidBody(this.physics.lidBody);
            this.physics.lidBody = null;
        }
        if (this.physics.lidMesh) {
            if (this.physics.lidMesh.parent) this.physics.lidMesh.parent.remove(this.physics.lidMesh);
            if (this.physics.lidMesh.geometry) this.physics.lidMesh.geometry.dispose();
            if (this.physics.lidMesh.material) this.physics.lidMesh.material.dispose();
            this.physics.lidMesh = null;
        }
        this.physics.lidState = 'idle';
        
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
        
        // Reset state
        this.hasPressedLid = false;
        this.vibrationPhase = false;
        
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
                message: 'Simulació reiniciada'
            });
        }
    }

    dispose() {
        this.stop();
        this.physics.dispose();
    }
}

export default { initRapier, PhysicsWorld, BulkSimulation };
