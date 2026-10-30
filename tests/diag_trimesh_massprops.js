// Does a trimesh collider become STABLE when the body's mass properties are
// taken from the piece's convex hull instead of Rapier's mesh-derived ones?
// (Bad inertia on an open shell was the suspected cause of the ejections.)
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
        const res = { singles: [], nest: null };
        window.__drive = { t: performance.now(), realNow: performance.now.bind(performance) };
        performance.now = () => window.__drive.t;
        window.requestAnimationFrame = () => 0;
        if (sim.dropInterval) { clearInterval(sim.dropInterval); sim.dropInterval = null; }
        if (sim.refillInterval) { clearInterval(sim.refillInterval); sim.refillInterval = null; }
        sim.isRunning = true; ph.isRunning = true;
        const step = (n) => { for (let i = 0; i < n; i++) { window.__drive.t += 33; sim.update(); } };
        const clear = () => {
            for (const { body } of ph.meshBodies.slice()) if (body && body.isValid()) ph.world.removeRigidBody(body);
            ph.meshBodies.length = 0;
        };

        // geometry (centred, same maths as dropPiece)
        const geo = sim.stlGeometry.clone();
        geo.computeBoundingBox();
        const bb = geo.boundingBox;
        const cx = (bb.min.x + bb.max.x) / 2, cy = (bb.min.y + bb.max.y) / 2, cz = (bb.min.z + bb.max.z) / 2;
        geo.translate(-cx, -cy, -cz);
        const posAttr = geo.getAttribute('position');
        const verts = new Float32Array(posAttr.array);
        const idx = geo.index ? new Uint32Array(geo.index.array)
                              : Uint32Array.from({ length: posAttr.count }, (_, i) => i);

        // ── probe the HULL's mass properties ──
        let massProps = null;
        try {
            const cd = window.RAPIER ? null : null;
            // build a temp convex-hull body through the physics world helper
            const tmp = ph.addConvexHull(verts, { x: 0, y: -5000, z: 0 }, null, null);
            const m = tmp.mass();
            const com = tmp.centerOfMass ? tmp.centerOfMass() : null;
            const pin = tmp.principalInertia ? tmp.principalInertia() : null;
            massProps = {
                mass: +m.toFixed(4),
                com: com ? [+com.x.toFixed(3), +com.y.toFixed(3), +com.z.toFixed(3)] : null,
                principalInertia: pin ? [+pin.x.toFixed(2), +pin.y.toFixed(2), +pin.z.toFixed(2)] : null,
                hasPrincipalInertia: !!pin,
            };
            ph.world.removeRigidBody(tmp);
            ph.meshBodies.length = 0;
        } catch (e) {
            massProps = { error: String(e).slice(0, 120) };
        }
        res.hullMassProps = massProps;

        const applyMassProps = (body) => {
            if (!massProps || massProps.error) return false;
            const pin = massProps.principalInertia || [4760, 1813, 4760];
            try {
                body.setAdditionalMassProperties(
                    massProps.mass,
                    { x: 0, y: 0, z: 0 },                       // COM at the body origin
                    { x: pin[0], y: pin[1], z: pin[2] },
                    { x: 0, y: 0, z: 0, w: 1 }, true);
                return true;
            } catch (e) {
                return 'ERR ' + String(e).slice(0, 60);
            }
        };

        // ── A) five single trimesh pieces with explicit mass properties ──
        for (let i = 0; i < 5; i++) {
            clear();
            const b = ph.addConcaveMesh(verts, idx, { x: 25, y: 20, z: 25 }, null, null);
            const applied = applyMassProps(b);
            step(150);
            const p = b.translation();
            res.singles.push({ applied, y: +p.y.toFixed(2), x: +p.x.toFixed(1), z: +p.z.toFixed(1) });
        }

        // ── B) two trimesh pieces: does the upper one NEST into the lower? ──
        clear();
        const a = ph.addConcaveMesh(verts, idx, { x: 25, y: 5.1, z: 25 }, null, null);
        applyMassProps(a);
        const b2 = ph.addConcaveMesh(verts, idx, { x: 25, y: 25, z: 25 }, null, null);
        applyMassProps(b2);
        step(200);
        const pa = a.translation(), pb = b2.translation();
        res.nest = {
            yA: +pa.y.toFixed(2), yB: +pb.y.toFixed(2),
            rise: +(pb.y - pa.y).toFixed(2),
            pair: +((pb.y - pa.y) + 10.2).toFixed(2),
        };

        performance.now = window.__drive.realNow;
        return res;
    });
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
})();
