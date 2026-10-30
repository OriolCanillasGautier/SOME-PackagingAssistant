// Two compound shells stacked: why do they blow up, and what fixes it?
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
        const res = { ip: {}, tests: [] };
        window.__drive = { t: performance.now(), realNow: performance.now.bind(performance) };
        performance.now = () => window.__drive.t;
        window.requestAnimationFrame = () => 0;
        if (sim.dropInterval) { clearInterval(sim.dropInterval); sim.dropInterval = null; }
        if (sim.refillInterval) { clearInterval(sim.refillInterval); sim.refillInterval = null; }
        sim.isRunning = true; ph.isRunning = true;

        const ip = ph.world.integrationParameters;
        if (ip) {
            for (const k of Object.keys(ip)) {
                const v = ip[k];
                if (typeof v === 'number') res.ip[k] = +v.toFixed(4);
            }
        }
        res.ipKeys = Object.keys(ip || {});

        const geo = sim.stlGeometry.clone();
        geo.computeBoundingBox();
        const bb = geo.boundingBox;
        const cx = (bb.min.x + bb.max.x) / 2, cy = (bb.min.y + bb.max.y) / 2, cz = (bb.min.z + bb.max.z) / 2;
        const centre = (list) => list.map(b => ({ c: [b.c[0] - cx, b.c[1] - cy, b.c[2] - cz], h: b.h }));
        const clear = () => {
            for (const { body } of ph.meshBodies.slice()) if (body && body.isValid()) ph.world.removeRigidBody(body);
            ph.meshBodies.length = 0;
        };
        const twoBody = (boxes, label, tweak) => {
            clear();
            if (tweak) tweak(ip);
            const a = ph.addCompoundBoxes(boxes, { x: 25, y: 5.1, z: 25 }, null, null);
            const b = ph.addCompoundBoxes(boxes, { x: 25, y: 25, z: 25 }, null, null);
            for (let i = 0; i < 150; i++) { window.__drive.t += 33; sim.update(); }
            const pa = a.translation(), pb = b.translation();
            const r = { label, boxes: boxes.length, yA: +pa.y.toFixed(2), yB: +pb.y.toFixed(2),
                        rise: +(pb.y - pa.y).toFixed(2) };
            if (tweak) tweak(null);   // restore
            res.tests.push(r);
        };

        const fine = centre(sim._colliderBoxes || []);
        const coarse = centre(window.__buildVoxelBoxCompound(geo, { targetCells: 5, maxBoxes: 96 }) || []);
        res.fineBoxes = fine.length;
        res.coarseBoxes = coarse.length;

        twoBody(fine, 'fine default');
        if (coarse.length) twoBody(coarse, 'coarse (5 cells)');

        // softer contacts: lower the natural frequency if the build exposes it
        const savedFreq = ip ? ip.contactNaturalFrequency : undefined;
        if (ip && 'contactNaturalFrequency' in ip) {
            twoBody(fine, 'fine + soft contacts', (p) => { if (p) p.contactNaturalFrequency = 20; else ip.contactNaturalFrequency = savedFreq; });
        } else {
            res.tests.push({ label: 'soft contacts not available', keys: res.ipKeys });
        }

        performance.now = window.__drive.realNow;
        return res;
    });
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
})();
