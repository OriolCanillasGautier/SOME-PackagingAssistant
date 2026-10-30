// A/B: one CONCAVE (trimesh) piece vs one HULL piece, same world, no overlap.
const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new', protocolTimeout: 600000,
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 900, height: 650 });
    await page.bringToFront();
    page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 140)));
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);

    await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/physics-engine/stl/cone.stl');
    await sleep(3000);
    await page.evaluate(() => document.querySelector('.mode-btn[data-mode="bulk"]')?.click());
    await sleep(500);
    await page.evaluate(() => document.querySelector('#bulk-variant-selector .variant-btn[data-variant="gravity"]')?.click());
    await sleep(500);
    await page.evaluate(() => {
        document.getElementById('box-length').value = '50';
        document.getElementById('box-width').value = '50';
        document.getElementById('box-height').value = '50';
        ['box-length', 'box-width', 'box-height'].forEach(id =>
            document.getElementById(id).dispatchEvent(new Event('input', { bubbles: true })));
    });
    await sleep(400);
    await page.evaluate(() => document.getElementById('start-simulation-btn').click());
    await sleep(900);
    await page.evaluate(() => {
        const auto = document.querySelector('input[name="bulk-mode"][value="auto"]');
        if (auto) { auto.checked = true; auto.dispatchEvent(new Event('change', { bubbles: true })); }
        document.getElementById('bulk-start-confirm')?.click();
    });
    await sleep(1200);

    const out = await page.evaluate(() => {
        const sim = window.PackAssist.state.bulkSimulation;
        const ph = sim.physics;
        const res = {};
        window.__drive = { t: performance.now(), realNow: performance.now.bind(performance) };
        performance.now = () => window.__drive.t;
        const step = (n) => { for (let i = 0; i < n; i++) { window.__drive.t += 33; sim.update(); } };

        // stop automatic dropping and clear the world of pieces
        if (sim.dropInterval) { clearInterval(sim.dropInterval); sim.dropInterval = null; }
        if (sim.refillInterval) { clearInterval(sim.refillInterval); sim.refillInterval = null; }
        const removed = ph.meshBodies.length;
        for (const { body } of ph.meshBodies.slice()) {
            if (body && body.isValid()) ph.world.removeRigidBody(body);
        }
        ph.meshBodies.length = 0;
        res.clearedPieces = removed;

        // geometry of the cone, centered (same maths as dropPiece)
        const geo = sim.stlGeometry.clone();
        geo.computeBoundingBox();
        const bb = geo.boundingBox;
        const cx = (bb.min.x + bb.max.x) / 2, cy = (bb.min.y + bb.max.y) / 2, cz = (bb.min.z + bb.max.z) / 2;
        geo.translate(-cx, -cy, -cz);
        const posAttr = geo.getAttribute('position');
        const verts = new Float32Array(posAttr.array);
        const idx = geo.index ? new Uint32Array(geo.index.array)
                              : Uint32Array.from({ length: posAttr.count }, (_, i) => i);
        res.tris = posAttr.count / 3;
        res.hasNaN = (() => { for (let i = 0; i < verts.length; i++) if (!isFinite(verts[i])) return true; return false; })();

        const V = (x, y, z) => new (window.THREE ? window.THREE.Vector3 : Object)(x, y, z);

        // ── A) CONCAVE piece at (25, 25, 25) ──
        const bA = ph.addConcaveMesh(verts, idx, { x: 25, y: 25, z: 25 }, null, null);
        res.massConcave = bA ? +bA.mass().toFixed(4) : null;
        step(45);
        const pA = bA.translation();
        res.concaveAfter45 = [+pA.x.toFixed(1), +pA.y.toFixed(1), +pA.z.toFixed(1)];
        if (bA.isValid()) ph.world.removeRigidBody(bA);

        // ── B) HULL piece at (25, 25, 25) (control) ──
        const bB = ph.addConvexHull(verts, { x: 25, y: 25, z: 25 }, null, null);
        res.massHull = bB ? +bB.mass().toFixed(4) : null;
        step(45);
        const pB = bB.translation();
        res.hullAfter45 = [+pB.x.toFixed(1), +pB.y.toFixed(1), +pB.z.toFixed(1)];

        // ── C) CONCAVE + explicit mass properties (box-like inertia, COM at origin) ──
        const bC = ph.addConcaveMesh(verts, idx, { x: 25, y: 25, z: 25 }, null, null);
        if (bC && bC.isValid()) {
            // piece bbox: cone 8 x 10.2 x 8  ->  w, h, d
            const w = 8, h = 10.2, d = 8;
            const m = 340.83;                       // hull mass (kg-equivalent units)
            const Ix = m / 12 * (h * h + d * d);
            const Iy = m / 12 * (w * w + d * d);
            const Iz = m / 12 * (w * w + h * h);
            try {
                bC.setAdditionalMassProperties(
                    m, { x: 0, y: 0, z: 0 }, { x: Ix, y: Iy, z: Iz },
                    { x: 0, y: 0, z: 0, w: 1 }, true);
                res.massPropsApplied = true;
            } catch (e) {
                res.massPropsApplied = 'ERROR: ' + String(e).slice(0, 80);
            }
        }
        step(45);
        const pC = bC.translation();
        res.concaveMassPropsAfter45 = [+pC.x.toFixed(1), +pC.y.toFixed(1), +pC.z.toFixed(1)];
        res.massConcaveC = bC ? +bC.mass().toFixed(2) : null;
        if (bC.isValid()) ph.world.removeRigidBody(bC);

        res.gravity = ph.world.gravity ? ph.world.gravity.y : null;
        res.timestep = ph.world.timestep || null;
        performance.now = window.__drive.realNow;
        return res;
    });
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
})();
