/**
 * PackAssist Web - Physics Engine (Rapier.js)
 * Handles physics simulation for bulk/gravity mode
 * FIXED: Proper physics loop integration with Three.js
 */

import * as THREE from 'three';

// Rapier will be loaded dynamically
let RAPIER = null;

// ── Concave collider budget ──
// Real nesting (cone into cone, parts sliding inside hollow shells) needs the
// exact triangle surface as collider. That is far heavier than a convex hull,
// so it is enabled per piece up to MAX_CONCAVE_TRIS triangles and for a whole
// simulation up to MAX_CONCAVE_TOTAL_TRIS; anything above falls back to the
// convex hull (no nesting, but stable and fast).
export const MAX_CONCAVE_TRIS = 2500;
// Total budget is deliberately modest: the user's GPU driver is currently
// dead, so the browser falls back to software GL — a huge trimesh world both
// slows physics and can crash the tab (observed in headless testing).
export const MAX_CONCAVE_TOTAL_TRIS = 200000;

// ── Concave colliders: DISABLED ──
// Rapier's trimesh collider on a DYNAMIC body derives its mass properties from
// the mesh, and for an open shell (our hollow parts) the inertia/COM come out
// unreliable: A/B testing in the real app showed a lone cone sometimes resting
// fine (y=5.1) and sometimes being ejected to y=91 with nothing else in the
// world. Flaky explosions are worse than no nesting, so the stable convex hull
// is used until the collider becomes a COMPOUND OF CONVEX PARTS (e.g. a small
// set of boxes from the server's voxel model, which keeps the cavity and has
// exact mass properties). See HANDOFF.md §4.12.
export const USE_CONCAVE_COLLIDERS = false;

// ── Compound of convex boxes: the nesting collider ──
// A hollow part can only nest if the collider has the cavity. Raw trimesh does
// (but is flaky + slow on dynamic bodies); a convex hull does not. So the
// collider is a COMPOUND: the mesh surface is voxelised into a thin shell and
// the shell cells are merged into a handful of axis-aligned boxes. Boxes are
// convex (exact mass properties, fast narrow-phase) while the union still has
// the cavity, so cones slide into cones.
// DISABLED after measurement: a compound of boxes preserves the cavity, but
// shell-on-shell contact in Rapier 0.12 blows up — two cones stacked as 50-box
// compounds swapped positions (lower body launched 5 -> 28.7mm) and a coarse
// 10-box version sank the upper cone THROUGH the lower (rise -0.77mm). The
// solver's contact parameters are not exposed in this build (integrationParameters
// only exposes a wasm `raw` pointer), so there is nothing to soften. Gravity
// mode therefore uses the stable convex hull; real nesting lives in the
// stacking engine (Apilat), and a hybrid (seed the physics with the stacking
// layout, then vibrate) is the planned route. See HANDOFF.md §4.13.
export const USE_COMPOUND_COLLIDERS = false;
export const COMPOUND_TARGET_CELLS = 14;  // cells across the largest dimension
export const COMPOUND_MAX_BOXES = 96;     // above this the build bails to the hull

/**
 * Voxelise a geometry's SURFACE and merge the cells into convex boxes.
 * Returns [{ c: [x,y,z], h: [hx,hy,hz] }] in the geometry's local coordinates
 * (not centred — the caller shifts by the same offset it uses for the mesh),
 * or null when the mesh is unusable / needs too many boxes.
 */
/**
 * Enclosed volume of a triangle mesh (divergence theorem). For a hollow shell
 * this is the space the part occupies — exactly what packing cares about.
 */
export function meshVolume(geometry) {
    if (!geometry || !geometry.getAttribute) return 0;
    const pos = geometry.getAttribute('position');
    if (!pos || pos.count < 3) return 0;
    const idx = geometry.index;
    const tri = Math.floor((idx ? idx.count : pos.count) / 3);
    const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
    const cross = new THREE.Vector3();
    let v = 0;
    for (let t = 0; t < tri; t++) {
        a.fromBufferAttribute(pos, idx ? idx.getX(t * 3) : t * 3);
        b.fromBufferAttribute(pos, idx ? idx.getX(t * 3 + 1) : t * 3 + 1);
        c.fromBufferAttribute(pos, idx ? idx.getX(t * 3 + 2) : t * 3 + 2);
        cross.crossVectors(b, c);
        v += a.dot(cross);
    }
    return Math.abs(v) / 6;
}

if (typeof window !== 'undefined') {
    // dev/test hook: lets the harness rebuild compounds at other resolutions
    window.__buildVoxelBoxCompound = (geo, opts) => buildVoxelBoxCompound(geo, opts);
}

export function buildVoxelBoxCompound(geometry, { targetCells = COMPOUND_TARGET_CELLS, maxBoxes = COMPOUND_MAX_BOXES } = {}) {
    // A thin shell fragments badly at fine resolution, so try progressively
    // coarser grids until the box count fits the budget instead of giving up.
    for (const cells of [targetCells, 10, 7, 5]) {
        const boxes = buildVoxelBoxCompoundOnce(geometry, cells, maxBoxes);
        if (boxes) {
            console.log(`[Bulk] compound: ${boxes.length} boxes at ${cells} cells`);
            return boxes;
        }
    }
    return null;
}

function buildVoxelBoxCompoundOnce(geometry, targetCells, maxBoxes) {
    if (!geometry || !geometry.getAttribute) return null;
    const pos = geometry.getAttribute('position');
    if (!pos || pos.count < 3) return null;
    geometry.computeBoundingBox();
    const bb = geometry.boundingBox;
    if (!bb) return null;
    const size = new THREE.Vector3();
    bb.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    if (!(maxDim > 0) || !isFinite(maxDim)) return null;

    const N = 256;                                    // grid cap per axis
    const cell = Math.max(0.4, maxDim / targetCells, maxDim / N);
    const pack = (i, j, k) => i + N * j + N * N * k;
    const occupied = new Set();
    const va = new THREE.Vector3(), vb = new THREE.Vector3(), vc = new THREE.Vector3();
    const idx = geometry.index;
    const triCount = Math.floor((idx ? idx.count : pos.count) / 3);
    const step = cell * 0.45;

    for (let t = 0; t < triCount; t++) {
        const ia = idx ? idx.getX(t * 3) : t * 3;
        const ib = idx ? idx.getX(t * 3 + 1) : t * 3 + 1;
        const ic = idx ? idx.getX(t * 3 + 2) : t * 3 + 2;
        va.fromBufferAttribute(pos, ia);
        vb.fromBufferAttribute(pos, ib);
        vc.fromBufferAttribute(pos, ic);
        const e1x = vb.x - va.x, e1y = vb.y - va.y, e1z = vb.z - va.z;
        const e2x = vc.x - va.x, e2y = vc.y - va.y, e2z = vc.z - va.z;
        const nS = Math.max(1, Math.min(12, Math.ceil(Math.max(
            Math.hypot(e1x, e1y, e1z), Math.hypot(e2x, e2y, e2z)) / step)));
        for (let s1 = 0; s1 <= nS; s1++) {
            for (let s2 = 0; s2 <= nS - s1; s2++) {
                const w1 = s1 / nS, w2 = s2 / nS;
                const px = va.x + w1 * e1x + w2 * e2x;
                const py = va.y + w1 * e1y + w2 * e2y;
                const pz = va.z + w1 * e1z + w2 * e2z;
                const i = Math.floor((px - bb.min.x) / cell);
                const j = Math.floor((py - bb.min.y) / cell);
                const k = Math.floor((pz - bb.min.z) / cell);
                if (i < 0 || j < 0 || k < 0 || i >= N || j >= N || k >= N) continue;
                occupied.add(pack(i, j, k));
            }
        }
    }
    if (occupied.size === 0) return null;

    // Greedy merge: take the lowest cell, grow +X, then +Z, then +Y.
    const cells = Array.from(occupied).sort((a, b) => a - b);
    const boxes = [];
    for (const v of cells) {
        if (!occupied.has(v)) continue;
        const i0 = v % N, j0 = Math.floor(v / N) % N, k0 = Math.floor(v / (N * N));
        let ex = i0;
        while (occupied.has(pack(ex + 1, j0, k0))) ex++;
        let ez = k0;
        growZ: while (true) {
            for (let x = i0; x <= ex; x++) if (!occupied.has(pack(x, j0, ez + 1))) break growZ;
            ez++;
        }
        let ey = j0;
        growY: while (true) {
            for (let x = i0; x <= ex; x++) {
                for (let z = k0; z <= ez; z++) if (!occupied.has(pack(x, ey + 1, z))) break growY;
            }
            ey++;
        }
        for (let x = i0; x <= ex; x++) {
            for (let y = j0; y <= ey; y++) {
                for (let z = k0; z <= ez; z++) occupied.delete(pack(x, y, z));
            }
        }
        boxes.push({
            c: [
                bb.min.x + (i0 + ex + 1) / 2 * cell,
                bb.min.y + (j0 + ey + 1) / 2 * cell,
                bb.min.z + (k0 + ez + 1) / 2 * cell,
            ],
            h: [(ex - i0 + 1) / 2 * cell, (ey - j0 + 1) / 2 * cell, (ez - k0 + 1) / 2 * cell],
        });
        if (boxes.length > maxBoxes) return null;     // too fragmented → hull fallback
    }
    return boxes;
}

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
 * VERIFY a candidate resting pose with real gravity (no drop / no bounce):
 * place the piece on the floor at the proposed orientation and check whether it
 * stays put or tips/rolls away. The COM is handled by physics automatically —
 * an unstable pose tips over, a stable one does not. This is the honest check
 * for the "put it on the floor, then apply gravity" workflow.
 * @param {THREE.BufferGeometry} geometry - the piece (assumed centered at origin)
 * @param {THREE.Quaternion} quaternion - the proposed resting orientation
 * @param {{maxSteps?:number, tippedThresholdDeg?:number}} opts
 * @returns {Promise<{stable:boolean, tippedDeg?:number, error?:string}>}
 */
export async function verifyRestPose(geometry, quaternion, opts = {}) {
    const maxSteps = opts.maxSteps || 150;
    const tippedThresholdDeg = opts.tippedThresholdDeg || 20.0;
    try {
        if (!RAPIER) { const ok = await initRapier(); if (!ok) return { stable: true, error: 'no-rapier' }; }
        const pos = geometry.getAttribute('position');
        if (!pos || pos.count < 12) return { stable: true, error: 'few-verts' };
        const verts = new Float32Array(pos.count * 3);
        for (let i = 0; i < pos.count; i++) {
            verts[i * 3] = pos.getX(i); verts[i * 3 + 1] = pos.getY(i); verts[i * 3 + 2] = pos.getZ(i);
        }
        // Triangle indices (support indexed + non-indexed geometries).
        const geoIndex = geometry.getIndex ? geometry.getIndex() : null;
        const indices = new Uint32Array(geoIndex ? geoIndex.count : pos.count);
        if (geoIndex) { for (let i = 0; i < geoIndex.count; i++) indices[i] = geoIndex.getX(i); }
        else { for (let i = 0; i < indices.length; i++) indices[i] = i; }
        // Rotated lowest point -> place the bottom just on the floor (no drop).
        const v = new THREE.Vector3(); let minY = Infinity;
        for (let i = 0; i < verts.length; i += 3) {
            v.set(verts[i], verts[i + 1], verts[i + 2]).applyQuaternion(quaternion);
            if (v.y < minY) minY = v.y;
        }
        const world = new RAPIER.World({ x: 0, y: -9810, z: 0 });
        world.timestep = 1 / 240;
        // Large floor only (no walls) — the piece is free to tip/roll.
        const floor = world.createRigidBody(
            RAPIER.RigidBodyDesc.fixed().setTranslation(0, -8, 0));
        world.createCollider(RAPIER.ColliderDesc.cuboid(4000, 8, 4000), floor);
        const body = world.createRigidBody(
            RAPIER.RigidBodyDesc.dynamic()
                .setTranslation(0, -minY, 0)
                .setRotation({ x: quaternion.x, y: quaternion.y, z: quaternion.z, w: quaternion.w }));
        // ACCURATE trimesh collider (exact shape) so tapering/concave parts tip
        // correctly — the convex hull over-stabilised them (its flat hull base
        // "rested" where the real piece falls). Fall back to convex hull only if
        // Rapier can't build the trimesh.
        let cdesc = null;
        try {
            cdesc = RAPIER.ColliderDesc.trimesh(verts, indices)
                .setDensity(2.0).setFriction(0.9).setRestitution(0.0);
        } catch (e) { cdesc = null; }
        if (!cdesc) {
            try {
                cdesc = RAPIER.ColliderDesc.convexHull(verts)
                    .setDensity(2.0).setFriction(0.9).setRestitution(0.0);
            } catch (e) { cdesc = null; }
        }
        if (!cdesc) return { stable: true, error: 'no-collider' };
        world.createCollider(cdesc, body);
        for (let i = 0; i < maxSteps; i++) world.step();
        // Compare the body's actual up-axis to the intended pose's up-axis.
        const rot = body.rotation();
        const up = new THREE.Vector3(0, 1, 0).applyQuaternion(
            new THREE.Quaternion(rot.x, rot.y, rot.z, rot.w));
        const intendedUp = new THREE.Vector3(0, 1, 0).applyQuaternion(quaternion);
        const tippedDeg = THREE.MathUtils.radToDeg(up.angleTo(intendedUp));
        return { stable: tippedDeg < tippedThresholdDeg, tippedDeg: +tippedDeg.toFixed(1) };
    } catch (e) {
        console.warn('[Orientation] gravity verify failed:', e?.message || e);
        return { stable: true, error: 'physics-error' }; // don't block; keep static label
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
        this.vibrationLateral = 0.25; // "wind": 1 = shake all axes, 0.25 = mostly vertical
        this.vibrationFade = 1.0;     // "fade": extra amplitude scale (falls as the box fills)

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
     * Concave (exact triangle-mesh) collider — REQUIRED for real nesting: a
     * hollow cone only slides into another hollow cone if the collider is the
     * actual surface. A convex hull is a SOLID copy of the part, so two hulls
     * can never interpenetrate and the pieces always sit on top of each other
     * (that is why "cones never fit together" in bulk mode).
     *
     * Rapier trimesh colliders on dynamic bodies are heavier and can tunnel
     * through thin walls, so they are used only for light meshes (see
     * MAX_CONCAVE_TRIS) with CCD enabled.
     */
    addConcaveMesh(vertices, indices, position, rotation = null, mesh = null, meshOffset = null, options = {}) {
        let colliderDesc = null;
        try {
            const flags = RAPIER.TriMeshFlags ? RAPIER.TriMeshFlags.FIX_INTERNAL_EDGES : undefined;
            colliderDesc = flags !== undefined
                ? RAPIER.ColliderDesc.trimesh(vertices, indices, flags)
                : RAPIER.ColliderDesc.trimesh(vertices, indices);
        } catch (e) {
            colliderDesc = null;
        }
        if (!colliderDesc) {
            // Rapier rejected the mesh — the hull path is always valid.
            return this.addConvexHull(vertices, position, rotation, mesh, meshOffset, options);
        }

        const bodyDesc = RAPIER.RigidBodyDesc.dynamic()
            .setTranslation(position.x, position.y, position.z)
            .setLinearDamping(0.2)
            .setAngularDamping(0.5)
            // NO CCD on triangle-mesh colliders: continuous collision detection
            // against a trimesh is extremely expensive in Rapier's solver and
            // was the bulk sim's dominant cost (thousands of steps took
            // minutes). Pieces spawn just above the pile now, so speeds are
            // low and tunnelling is unlikely.
            .setCcdEnabled(false);
        if (rotation) {
            const quat = new THREE.Quaternion().setFromEuler(rotation);
            bodyDesc.setRotation({ x: quat.x, y: quat.y, z: quat.z, w: quat.w });
        }
        const body = this.world.createRigidBody(bodyDesc);

        if (mesh) {
            mesh.position.set(position.x, position.y, position.z);
            if (rotation) {
                const quat = new THREE.Quaternion().setFromEuler(rotation);
                mesh.quaternion.set(quat.x, quat.y, quat.z, quat.w);
            }
            this.meshBodies.push({ body, mesh, offset: meshOffset });
        }

        colliderDesc.setDensity(2.0).setFriction(0.8).setRestitution(0.0);
        this.world.createCollider(colliderDesc, body);

        // Open shells have no well-defined volume, so the mass derived from
        // the density can come out 0/NaN (body then ignores gravity). Give it
        // an explicit mass in that case so it behaves like the hull fallback.
        try {
            const m = body.mass();
            if (!Number.isFinite(m) || m <= 0) {
                body.setAdditionalMass(Math.max(1e-4, options?.fallbackMass ?? 0.05), true);
            }
        } catch (e) { /* older rapier builds have no mass() */ }

        return body;
    }

    /**
     * One dynamic body carrying a COMPOUND of convex boxes (the nesting
     * collider). Unlike a trimesh collider the parts are convex, so Rapier
     * derives exact mass properties from them — no flaky ejections — while the
     * union of the boxes still has the part's cavity, so hollow parts nest.
     */
    addCompoundBoxes(boxes, position, rotation = null, mesh = null, meshOffset = null, options = {}) {
        if (!boxes || boxes.length === 0) return null;
        const bodyDesc = RAPIER.RigidBodyDesc.dynamic()
            .setTranslation(position.x, position.y, position.z)
            .setLinearDamping(0.2)
            .setAngularDamping(0.5)
            // Boxes are convex and pieces spawn just above the pile, so CCD
            // (expensive) is not needed here.
            .setCcdEnabled(false);
        if (rotation) {
            const quat = new THREE.Quaternion().setFromEuler(rotation);
            bodyDesc.setRotation({ x: quat.x, y: quat.y, z: quat.z, w: quat.w });
        }
        const body = this.world.createRigidBody(bodyDesc);

        if (mesh) {
            mesh.position.set(position.x, position.y, position.z);
            if (rotation) {
                const quat = new THREE.Quaternion().setFromEuler(rotation);
                mesh.quaternion.set(quat.x, quat.y, quat.z, quat.w);
            }
            this.meshBodies.push({ body, mesh, offset: meshOffset });
        }

        const density = options?.density ?? 2.0;
        for (const b of boxes) {
            const cd = RAPIER.ColliderDesc.cuboid(b.h[0], b.h[1], b.h[2])
                .setTranslation(b.c[0], b.c[1], b.c[2])
                .setDensity(density)
                .setFriction(0.8)
                .setRestitution(0.0);
            this.world.createCollider(cd, body);
        }
        return body;
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
            const amp = baseAmp * phase.ampScale * env * this.vibrationFade;
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

            // "Wind" (a trick borrowed from the square-packing lab): real
            // shaker tables shake mostly VERTICALLY — pieces lift and drop into
            // the cavities instead of skating sideways out of them. Lateral
            // components are damped (1 = shake every axis, 0 = vertical only).
            const lateral = this.vibrationLateral;
            const offsetX = (amp * jx + noise) * lateral;
            const offsetZ = (amp * jz + noise) * lateral;
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
        
        // Per-piece vibration personality: each piece shivers with its own
        // small random frequency/phase/scale instead of all pieces feeling
        // the identical box motion — the tiny differences make the settling
        // look organic (e.g. base 8Hz/1mm → pieces at 9Hz/1.1, 7.5Hz/0.9…).
        body._jitter = {
            freq: 8 + (Math.random() * 2 - 1) * 1.2,        // ~6.8..9.2 Hz
            phase: Math.random() * Math.PI * 2,
            scale: 0.5 + Math.random() * 0.5,               // 0.5..1.0 × base
            amp: 0.4 + Math.random() * 0.8,                 // 0.4..1.2 mm/s kick
            rate: 0.02 + Math.random() * 0.06,              // kick probability/step
            t: Math.random() * 10,
        };
        
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
                // Per-piece micro-jitter: each body shivers with its own
                // random frequency/phase/scale (stored at spawn) so the
                // settling is organic instead of all pieces moving with the
                // box in lock-step. Small kicks only — just enough to keep
                // the top layer fluid, never enough to launch pieces.
                for (const b of this.bodies) {
                    if (!b.isValid() || !b.isDynamic()) continue;
                    const j = b._jitter;
                    if (!j) continue;
                    j.t += dt;
                    if (Math.random() < j.rate) {
                        const kick = j.amp * j.scale * Math.sin(2 * Math.PI * j.freq * j.t + j.phase);
                        const lv = b.linvel();
                        b.setLinvel({
                            x: lv.x + (Math.random() * 2 - 1) * kick * 0.5,
                            y: lv.y + (Math.random() - 0.5) * kick * 0.3,
                            z: lv.z + (Math.random() * 2 - 1) * kick * 0.5,
                        }, true);
                    }
                }
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
     * Pieces still in flight (moving faster than a settled piece). Used to
     * pace the pour: dropping while several pieces are mid-air both stacks
     * them into unrealistic towers and makes the "box is full" count lag
     * behind reality, so the pour overshot (8 wasted pieces for 56 that fit).
     */
    piecesInFlight(threshold = 150) {
        let n = 0;
        for (const { body } of this.meshBodies) {
            if (!body || !body.isValid || !body.isValid()) continue;
            const v = body.linvel();
            if (Math.hypot(v.x, v.y, v.z) > threshold) n++;
        }
        return n;
    }

    /**
     * Count pieces that are inside the box
     */
    countPiecesInBox() {
        if (!this.boxDims) return 0;
        
        const { length, width, height } = this.boxDims;
        // A piece counts as INSIDE when its footprint is over the box AND its
        // centre is below the rim. Older rules were far too generous: the
        // centre with a +20mm vertical margin (80% of a 25mm box) counted
        // pieces perched well above the walls, and even "lowest point below
        // the rim" counted the whole overflow pile — reporting 108 cones in a
        // 25³ box, which is volumetrically impossible.
        const tol = 5;                                              // wall tolerance
        const halfH = this.pieceDims ? Math.max(1, this.pieceDims.h) / 2 : 5;
        let count = 0;
        
        for (const { body } of this.meshBodies) {
            if (!body.isValid()) continue;
            const pos = body.translation();
            if (pos.x > -tol && pos.x < length + tol &&
                pos.z > -tol && pos.z < width + tol &&
                pos.y < height + 1 &&                               // centre below the rim
                pos.y - halfH > -halfH) {                           // not below the floor
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
            // A filled box has its top layer AT (or just over) the rim — those
            // pieces are legitimately inside. Removing them by maxY (the old
            // rule, tolerance pieceDims.h*0.3) halved the reported fill: the
            // count peaked at 119 and the final cleanup left 60. Only pieces
            // whose LOWEST point is above the rim are actually floating outside.
            const floatingAbove = minY > height + 2;
            shouldRemove = completelyOutside || horizOutside || floatingAbove;
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
        this._recentInside = [];   // rolling inside-count window for the "full" test
        this.maxStagnantDrops = 1; // kept for the single-check path
        this.checkInterval = 2; // check every 2 drops: 6 x 15 = 90 wasted pours before
        
        // Track pieces above box to detect overflow faster
        this.piecesAboveBox = 0;
        this.maxPiecesAboveBox = 2; // 2+ pieces settled above the rim = the box is full
        
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
        // Lid press: DISABLED. It has no UI control (it was removed from the
        // panel while this flag stayed true) and the implementation is a
        // kinematic crush: the lid descends unconditionally to the box height,
        // squeezing pieces INTO each other. Measured in the deterministic
        // harness: the inside count jumped 61 -> 94 during the press, and 94
        // hull cones below the rim of a 25^3 box is ~98% volumetric fill —
        // impossible without nesting. The vibration + settle phases do the
        // real compaction; a lid can come back later as a force-limited press.
        this.enableLidPress = false;
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
        this._recentInside = [];   // fresh rolling window for this run
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

        // Concave colliders (real nesting) are per-piece and budgeted.
        this._concaveTris = 0;
        const pieceTris = this.stlVertices ? Math.floor(this.stlVertices.length / 9) : 0;
        this.concaveColliders = USE_CONCAVE_COLLIDERS
            && pieceTris > 0 && pieceTris <= MAX_CONCAVE_TRIS;

        // Nesting collider: a compound of convex boxes built ONCE from the
        // mesh surface (the cavity survives, so hollow parts can nest).
        this._colliderBoxes = null;
        if (USE_COMPOUND_COLLIDERS && stlGeometry) {
            try {
                const t0 = performance.now();
                this._colliderBoxes = buildVoxelBoxCompound(stlGeometry);
                if (this._colliderBoxes) {
                    console.log(`[Bulk] compound built in ${(performance.now() - t0).toFixed(0)}ms`);
                }
            } catch (e) {
                console.warn('[Bulk] compound build failed:', e?.message || e);
                this._colliderBoxes = null;
            }
        }
        // Random packing of rigid parts fills ~64% of the box volume (measured:
        // 59 cones x 170mm3 = 10,030mm3 in a 15,625mm3 box). Combined with the
        // plateau test this gives an honest "the box is full" signal that stops
        // the pour BEFORE a pile of rejects builds up.
        console.log(`[Bulk] collider: ${this._colliderBoxes
            ? `compound of ${this._colliderBoxes.length} convex boxes — nesting enabled`
            : 'convex hull — stable, no nesting'} (${pieceTris} tris/piece)`);

        // Initialize physics world
        await this.physics.init(boxDims);

        // ── Volume capacity (must run AFTER physics.init: the probe needs the
        // Rapier world) ──
        // Volume of the piece's CONVEX HULL, read straight from Rapier: a
        // temporary convex collider's mass at density 2.0 / 2.0 is its volume.
        // (meshVolume() is unreliable here — our hand-built shells have mixed
        // winding, so the signed volume cancels to ~0.) This drives the
        // "the box is full" stop, so it MUST actually run: it used to sit
        // before physics.init, threw on the missing world, and silently left
        // volumeCapacity at 0 — the pour then overshot every time (waste
        // swinging 6-14% run to run).
        this.pieceVolume = 0;
        if (stlGeometry) {
            try {
                const pos = stlGeometry.getAttribute('position');
                if (pos && pos.count >= 12) {
                    const probeDesc = RAPIER.ColliderDesc.convexHull(new Float32Array(pos.array));
                    if (probeDesc) {
                        probeDesc.setDensity(2.0);
                        const probeBody = this.physics.world.createRigidBody(RAPIER.RigidBodyDesc.dynamic());
                        this.physics.world.createCollider(probeDesc, probeBody);
                        const m = probeBody.mass();
                        this.physics.world.removeRigidBody(probeBody);
                        if (Number.isFinite(m) && m > 0) this.pieceVolume = m / 2.0;
                    }
                }
            } catch (e) {
                console.warn('[Bulk] hull volume probe failed:', e?.message || e);
            }
        }
        this.volumeCapacity = 0;
        if (this.pieceVolume > 0 && boxDims) {
            const boxVol = boxDims.length * boxDims.width * boxDims.height;
            this.volumeCapacity = (boxVol / this.pieceVolume) * 0.65;
            console.log(`[Bulk] capacity estimate: ${this.volumeCapacity.toFixed(0)} pieces ` +
                        `(piece ${this.pieceVolume.toFixed(0)}mm3, box ${boxVol.toFixed(0)}mm3, 65% fill)`);
        }

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

        // Cycle bookkeeping for the "is the box full?" yield test: how many
        // pieces were already inside / already dropped when this cycle began.
        this.cycleStartInside = this.physics.countPiecesInBox();
        this.cycleStartDropped = this.droppedCount;
        
        // Clear any existing timeout
        if (this.settlingTimeout) {
            clearTimeout(this.settlingTimeout);
            this.settlingTimeout = null;
        }
        
        // Start dropping pieces at intervals
        // Paced pour: skip a tick while too many pieces are still falling.
        // This is what an operator does (drop, wait, drop) and it keeps the
        // inside-count honest at the moment the full-box test runs.
        this.maxInFlight = 2;
        this.dropInterval = setInterval(() => {
            if (this.physics.piecesInFlight() >= this.maxInFlight) return;
            this.dropPiece();
        }, this.dropIntervalMs);
        
        // Apply constant vibration during dropping to help pieces settle
        // The vibration should stop when the drop phase ends (managed in stop/reset)
        // Gentle constant vibration while pouring (helps pieces slide into
        // place instead of pyramiding), then the staged burst+settle after the
        // drop phase (see finishDropping).
        this.physics.vibrationAmplitude = 0.35;
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
        
        // Keep the 3D view live while the physics runs. The SceneManager
        // render loop is on-demand (idle pause), so it must be told to redraw
        // each frame or the dropped pieces stay invisible until the result
        // renders at the end.
        if (this.scene && typeof this.scene.requestRender === 'function') this.scene.requestRender();
        
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

        // Spawn just above the SETTLED pile (or at the box rim while the box is
        // still mostly empty) instead of `dropHeight` above the walls. A long
        // free-fall makes pieces bounce straight back out — a big share of the
        // rejected pieces came from there — and they land too hard to slide
        // into the cavities below. A short, pile-following drop is both
        // realistic and far more efficient.
        // Spawn floor = the highest piece, settled OR still falling. Using
        // only SETTLED pieces (maxPieceY) let a new piece materialise inside
        // one that was still in the air — an immediate deep overlap that the
        // solver answers with an explosion (pieces flew to y=-967 in testing).
        let highestPieceY = -Infinity;
        for (const { body } of this.physics.meshBodies) {
            if (!body || !body.isValid || !body.isValid()) continue;
            const p = body.translation();
            if (p.y > highestPieceY) highestPieceY = p.y;
        }
        const pileRef = Number.isFinite(highestPieceY) ? Math.max(highestPieceY, 0) : 0;
        const spawnGap = Math.max(8, Math.max(l, w, h) * 1.2);
        const y = Math.min(
            Math.max(pileRef + spawnGap, height * 0.95),
            height + this.dropHeight
        ) + Math.random() * 6;

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
            // Use STL geometry. CRITICAL: center the geometry on its own
            // bounding-box center so the visual mesh and the RAPIER convex
            // hull (which sits at the hull's centre of mass) share the same
            // origin. Without this the collider rests on the pile while the
            // visual hovers up to ~half a piece away — "floating pieces".
            const geometry = this.stlGeometry.clone();
            geometry.computeBoundingBox();
            const bb = geometry.boundingBox;
            const cx = (bb.min.x + bb.max.x) / 2;
            const cy = (bb.min.y + bb.max.y) / 2;
            const cz = (bb.min.z + bb.max.z) / 2;
            geometry.translate(-cx, -cy, -cz);

            const centeredVerts = new Float32Array(this.stlVertices.length);
            for (let i = 0; i < this.stlVertices.length; i += 3) {
                centeredVerts[i] = this.stlVertices[i] - cx;
                centeredVerts[i + 1] = this.stlVertices[i + 1] - cy;
                centeredVerts[i + 2] = this.stlVertices[i + 2] - cz;
            }

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

            // Collider choice, best first:
            //  1. COMPOUND of convex boxes — has the cavity (nesting) and exact
            //     mass properties (stable). Built once in init().
            //  2. concave trimesh — same cavity, but flaky on dynamic bodies
            //     (gated off by default).
            //  3. convex hull — solid copy: stable and fast, but no nesting.
            const posAttr = geometry.getAttribute('position');
            const triCount = Math.floor(posAttr.count / 3);
            const concaveOk = USE_CONCAVE_COLLIDERS
                && triCount > 0
                && triCount <= MAX_CONCAVE_TRIS
                && ((this._concaveTris || 0) + triCount) <= MAX_CONCAVE_TOTAL_TRIS;
            if (this._colliderBoxes && this._colliderBoxes.length) {
                // Shift the boxes into the same centred frame as the visual
                // mesh (the geometry above was translated by -cx,-cy,-cz).
                const shifted = this._colliderBoxes.map(b => ({
                    c: [b.c[0] - cx, b.c[1] - cy, b.c[2] - cz],
                    h: b.h,
                }));
                this.physics.addCompoundBoxes(shifted, position, rotation, mesh);
            } else if (concaveOk) {
                const verts = new Float32Array(posAttr.array); // already centered
                const idx = geometry.index
                    ? new Uint32Array(geometry.index.array)
                    : Uint32Array.from({ length: posAttr.count }, (_, i) => i);
                this._concaveTris = (this._concaveTris || 0) + triCount;
                this.physics.addConcaveMesh(verts, idx, position, rotation, mesh);
            } else {
                // Convex hull (centered vertices) — stable fallback, no nesting.
                this.physics.addConvexHull(centeredVerts, position, rotation, mesh);
            }
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
        
        // Check for saturation / overflow in ALL modes (every checkInterval
        // drops). A full box stops accepting pieces; keep dropping and they pile
        // into an unrealistic tower above the walls. Detect "full":
        //  * pieces are piling up above the box (stuck on top of the pile), or
        //  * no new piece has entered the box for a while (saturation).
        // NOTE: we deliberately do NOT stop on a "pile reached the box top"
        // heuristic — for a large box with big pieces the pile touches the top
        // after only a couple of layers while the box is still mostly empty,
        // which stops the fill at ~15%. Saturation is the real signal.
        if (this.droppedCount % this.checkInterval === 0) {
            const currentInside = this.physics.countPiecesInBox();
            const piecesAbove = this.countPiecesAboveBox();

            // "Fade" (square-packing-lab trick): shake less as the box fills.
            // A nearly full box wants gentle settling, not agitation — strong
            // shaking at the end just bounces pieces back out.
            const capEst = Math.max(1, Math.floor(
                (length * width * height) / Math.max(1, l * w * h)));
            this.physics.vibrationFade = Math.max(0.35, 1 - (currentInside / capEst) * 0.65);

            // Fast detection: if pieces are piling above the box, it's full
            if (piecesAbove >= this.maxPiecesAboveBox) {
                console.log(`Box full: ${piecesAbove} pieces stuck above box`);
                this.finishDropping('overflow');
                return;
            }

            // ── Is the box full? ──
            // A single "no growth since the last check" test is not enough:
            // near the top the count creeps up one piece at a time (one lands,
            // one bounces out), so the counter keeps resetting and the pour
            // runs long (measured: 75 poured for 59 that fit = 21% waste).
            // Instead: a rolling window of the last few checks, and the pile
            // must ALSO have reached the rim — otherwise a transient
            // bounce-stall would end the fill early (the "pile touched the top
            // while the box is still empty" trap).
            this._recentInside.push(currentInside);
            if (this._recentInside.length > 3) this._recentInside.shift();
            const pileTop = this.maxPieceY();
            const pileAtRim = Number.isFinite(pileTop) && pileTop >= height * 0.85;
            const windowGain = this._recentInside.length >= 3
                ? this._recentInside[this._recentInside.length - 1] - this._recentInside[0]
                : Infinity;
            if (currentInside > this.lastInsideCount) this.lastInsideCount = currentInside;

            // Stop a little BELOW the estimated capacity: pieces already in
            // flight still land after the stop, so aiming at 90% of the
            // estimate overshot (measured waste 6.3% one run, 12.1% the next).
            // 85% keeps the waste under the 10% target run-to-run while giving
            // up at most a piece or two of fill.
            const volumeFull = this.volumeCapacity > 4
                && currentInside >= this.volumeCapacity * 0.85;
            if (volumeFull) {
                console.log(`Box full: ${currentInside} inside >= 95% of the volume capacity ` +
                            `(${this.volumeCapacity.toFixed(0)}) — stopping the pour`);
                this.finishDropping('saturated');
                return;
            }
            // NOTE: the old "pile reached the rim AND the count stopped
            // growing" stop is GONE. Cones pyramid: with only 21 pieces in a
            // 25^3 box the pile already touches the rim while the box is a
            // third full, so it stopped the pour far too early (measured 21 of
            // ~58). The honest signals are the volume capacity above and the
            // pieces-above-the-rim overflow test below.
            if (pileAtRim && windowGain <= 1 && this.volumeCapacity > 4
                    && currentInside >= this.volumeCapacity * 0.7) {
                console.log(`Box full: ${currentInside} inside, gain ${windowGain}, ` +
                            `pileTop=${pileTop.toFixed(1)} — stopping the pour`);
                this.finishDropping('saturated');
                return;
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

    /** Highest settled piece Y (the top of the pile). Used to detect that the
     *  box is full before pieces start stacking into an unrealistic tower. */
    maxPieceY() {
        let maxY = -Infinity;
        for (const { body } of this.physics.meshBodies) {
            if (!body.isValid || !body.isValid()) continue;
            const p = body.translation();
            const v = body.linvel();
            const speed = Math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2);
            if (speed > 50) continue; // ignore pieces still falling
            if (p.y > maxY) maxY = p.y;
        }
        return maxY;
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
        
        // 2. START VIBRATION — staged like a real shaker table: a strong burst
        //    breaks bridges and opens gaps, then a GENTLE phase lets the pieces
        //    settle down into the cavities. Constant strong shaking keeps them
        //    dancing on top of each other and they never nest.
        this.vibrationPhase = true;
        this.physics.vibrationAmplitude = 1.6;
        this.physics.vibrationFrequency = 11.0;
        this.physics.startVibration(3000); // strong burst
        setTimeout(() => {
            if (!this.isRunning || !this.vibrationPhase) return;
            this.physics.vibrationAmplitude = 0.45;
            this.physics.vibrationFrequency = 7.0;
            this.physics.startVibration(4000); // gentle settling
        }, 3000);
        
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

        // ── Is the box actually FULL? ──
        // A full box stops accepting pieces: whatever is poured on top ends up
        // outside. The honest signal is the YIELD of the cycle (how many pieces
        // actually stayed inside while it ran). Refilling a box that accepted
        // almost nothing only produces rejected pieces ("removed: 176").
        const insideAtCycleStart = this.cycleStartInside || 0;
        const droppedThisCycle = this.droppedCount - (this.cycleStartDropped || 0);
        const yieldThisCycle = currentCount - insideAtCycleStart;
        const acceptRate = droppedThisCycle > 0 ? yieldThisCycle / droppedThisCycle : 1;
        const boxFull = droppedThisCycle > 0
            && (yieldThisCycle < Math.max(3, Math.round(droppedThisCycle * 0.2)) || acceptRate < 0.35);
        if (boxFull) {
            console.log(`[Bulk] Box full: +${yieldThisCycle} inside of ${droppedThisCycle} dropped ` +
                        `(${(acceptRate * 100).toFixed(0)}% accepted) — no refill`);
        }

        // DECIDE IF WE NEED ANOTHER CYCLE
        // We refill if: we haven't reached max cycles AND the box still accepts
        // pieces (see boxFull above).
        const shouldRefill = this.currentCycle <= this.maxRefillCycles && !boxFull;

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
            // …and the bbox estimate still overestimates capacity 3-5x for
            // hollow/nesting parts. Top up with what the box actually accepted
            // this cycle (plus a margin): pouring 488 pieces into a box that
            // fits ~360 is what created the pile of rejected pieces.
            const topUp = Math.max(15, Math.ceil(yieldThisCycle * 1.35));
            refillCount = Math.min(refillCount, topUp);
            
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

        // Snapshot for the next cycle's yield test (see finishSimulation).
        this.cycleStartInside = this.physics.countPiecesInBox();
        this.cycleStartDropped = this.droppedCount;
        
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
            if (this.physics.piecesInFlight() >= (this.maxInFlight || 2)) return;  // paced
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
