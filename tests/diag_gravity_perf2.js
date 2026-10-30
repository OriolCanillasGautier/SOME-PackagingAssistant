// Isolate the bulk explosion: single piece (mass/floor) vs many (spawn overlap).
const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new', protocolTimeout: 600000,
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1000, height: 700 });
    await page.bringToFront();
    page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 120)));
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
        const di = document.getElementById('drop-interval'); if (di) di.value = '40';
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
    await sleep(1000);

    const out = await page.evaluate(() => {
        const sim = window.PackAssist.state.bulkSimulation;
        const res = { boxDims: sim.boxDims };
        window.__drive = { sim, t: performance.now(), realNow: performance.now.bind(performance),
                           realRaf: window.requestAnimationFrame };
        window.requestAnimationFrame = () => 0;
        performance.now = () => window.__drive.t;
        const step = (n) => { for (let i = 0; i < n; i++) { window.__drive.t += 33; sim.update(); } };

        // stop the automatic dropping so we control it
        if (sim.dropInterval) { clearInterval(sim.dropInterval); sim.dropInterval = null; }
        if (sim.refillInterval) { clearInterval(sim.refillInterval); sim.refillInterval = null; }

        const t0 = performance.now();
        sim.physics.step();
        res.msPerStep = +(performance.now() - t0).toFixed(2);

        // ── ONE piece ──
        sim.dropPiece();
        const b0 = sim.physics.meshBodies[0]?.body;
        res.mass_concave = b0 ? +b0.mass().toFixed(6) : null;
        res.bodyType = b0 ? b0.bodyType() : null;
        step(60);
        const p0 = b0?.translation();
        res.onePieceAfter60Steps = p0 ? [+p0.x.toFixed(1), +p0.y.toFixed(1), +p0.z.toFixed(1)] : null;

        // ── THREE more pieces, spaced ──
        for (let i = 0; i < 3; i++) { sim.dropPiece(); step(20); }
        res.after4Pieces = sim.physics.meshBodies.slice(0, 4).map(({ body }) => {
            const p = body.translation();
            return [+p.x.toFixed(0), +p.y.toFixed(0), +p.z.toFixed(0)];
        });

        // ── 15 more (likely overlap) ──
        for (let i = 0; i < 15; i++) { sim.dropPiece(); step(6); }
        step(120);
        const ps = sim.physics.meshBodies.map(({ body }) => body.translation());
        res.nBodies = ps.length;
        res.maxAbsCoord = Math.max(...ps.map(p => Math.max(Math.abs(p.x), Math.abs(p.y), Math.abs(p.z)))).toFixed(0);
        res.countInBox = sim.physics.countPiecesInBox();
        performance.now = window.__drive.realNow;
        window.requestAnimationFrame = window.__drive.realRaf;
        return res;
    });
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
})();
