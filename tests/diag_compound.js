// Why do compound-collider pieces sink through the floor?
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
        window.requestAnimationFrame = () => 0;
        if (sim.dropInterval) { clearInterval(sim.dropInterval); sim.dropInterval = null; }
        if (sim.refillInterval) { clearInterval(sim.refillInterval); sim.refillInterval = null; }
        for (const { body } of ph.meshBodies.slice()) if (body && body.isValid()) ph.world.removeRigidBody(body);
        ph.meshBodies.length = 0;
        sim.isRunning = true; ph.isRunning = true;
        const step = (n) => { for (let i = 0; i < n; i++) { window.__drive.t += 33; sim.update(); } };

        // boxes (centred like dropPiece does)
        const geo = sim.stlGeometry.clone();
        geo.computeBoundingBox();
        const bb = geo.boundingBox;
        const cx = (bb.min.x + bb.max.x) / 2, cy = (bb.min.y + bb.max.y) / 2, cz = (bb.min.z + bb.max.z) / 2;
        const boxes = (sim._colliderBoxes || []).map(b => ({ c: [b.c[0] - cx, b.c[1] - cy, b.c[2] - cz], h: b.h }));
        res.nBoxes = boxes.length;
        res.sampleBoxes = boxes.slice(0, 3).map(b => ({ c: b.c.map(v => +v.toFixed(2)), h: b.h.map(v => +v.toFixed(2)) }));
        // box extent sanity
        let maxH = 0, minH = Infinity, maxC = 0;
        for (const b of boxes) {
            maxH = Math.max(maxH, ...b.h); minH = Math.min(minH, ...b.h);
            maxC = Math.max(maxC, ...b.c.map(Math.abs));
        }
        res.halfExtents = { min: +minH.toFixed(3), max: +maxH.toFixed(3) };
        res.maxAbsCenter = +maxC.toFixed(2);
        res.geoBBox = { min: [+bb.min.x.toFixed(1), +bb.min.y.toFixed(1), +bb.min.z.toFixed(1)],
                        max: [+bb.max.x.toFixed(1), +bb.max.y.toFixed(1), +bb.max.z.toFixed(1)] };

        // one compound body
        const b1 = ph.addCompoundBoxes(boxes, { x: 25, y: 20, z: 25 }, null, null);
        res.mass = b1 ? +b1.mass().toFixed(3) : null;
        res.nColliders = b1 ? b1.numColliders() : null;
        // where are its colliders in world space?
        if (b1 && b1.numColliders) {
            const cs = [];
            for (let i = 0; i < Math.min(3, b1.numColliders()); i++) {
                const col = b1.collider(i);
                const t = col.translation();
                cs.push([+t.x.toFixed(2), +t.y.toFixed(2), +t.z.toFixed(2)]);
            }
            res.colliderWorldPos = cs;
        }
        step(60);
        const p1 = b1.translation();
        res.after60 = [+p1.x.toFixed(1), +p1.y.toFixed(1), +p1.z.toFixed(1)];
        const v1 = b1.linvel();
        res.vel = [+v1.x.toFixed(0), +v1.y.toFixed(0), +v1.z.toFixed(0)];
        // control: hull body elsewhere
        const posAttr = geo.getAttribute('position');
        const b2 = ph.addConvexHull(new Float32Array(posAttr.array), { x: 45, y: 20, z: 45 }, null, null);
        step(60);
        const p2 = b2.translation();
        res.hullAfter60 = [+p2.x.toFixed(1), +p2.y.toFixed(1), +p2.z.toFixed(1)];
        performance.now = window.__drive.realNow;
        return res;
    });
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
})();
