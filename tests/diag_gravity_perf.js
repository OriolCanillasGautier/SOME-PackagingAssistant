// Where does the bulk sim's time go, and where do the pieces actually go?
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
        document.getElementById('box-length').value = '25';
        document.getElementById('box-width').value = '25';
        document.getElementById('box-height').value = '25';
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
        const res = {};
        res.boxDims = sim.boxDims;
        res.pieceDims = sim.pieceDims;
        res.dropHeight = sim.dropHeight;
        res.physicsBox = sim.physics.boxDims || sim.physics.box || null;
        // install driver
        window.__drive = { sim, t: performance.now(), steps: 0, vib: false, lid: false,
                           realNow: performance.now.bind(performance), realRaf: window.requestAnimationFrame };
        window.requestAnimationFrame = () => 0;
        performance.now = () => window.__drive.t;

        const t = (fn, n = 5) => {
            const a = performance.now();
            for (let i = 0; i < n; i++) fn();
            return ((performance.now() - a) / n).toFixed(2);
        };
        // 1) cost of a bare physics step (no drop, no UI)
        res.msPerPhysicsStep = t(() => sim.physics.step(), 8);
        // 2) cost of a full update()
        res.msPerUpdate = t(() => sim.update(), 8);
        // 3) drop + measure
        const t2 = performance.now();
        for (let i = 0; i < 20; i++) { window.__drive.t += 33; sim.dropPiece(); }
        res.msPer20Drops = (performance.now() - t2).toFixed(1);
        // 4) run 120 steps so pieces fall, then report where they are
        for (let i = 0; i < 120; i++) { window.__drive.t += 33; sim.update(); }
        const bodies = sim.physics.meshBodies;
        const ys = [], xs = [], zs = [];
        for (const { body } of bodies) {
            if (!body.isValid || !body.isValid()) continue;
            const p = body.translation();
            xs.push(p.x); ys.push(p.y); zs.push(p.z);
        }
        const rng = (a) => a.length ? [Math.min(...a).toFixed(1), Math.max(...a).toFixed(1)] : null;
        res.bodies = bodies.length;
        res.xRange = rng(xs); res.yRange = rng(ys); res.zRange = rng(zs);
        res.countInBox = sim.physics.countPiecesInBox();
        res.dropped = sim.droppedCount;
        res.firstPositions = bodies.slice(0, 4).map(({ body }) => {
            const p = body.translation(); return [+p.x.toFixed(1), +p.y.toFixed(1), +p.z.toFixed(1)];
        });
        performance.now = window.__drive.realNow;
        window.requestAnimationFrame = window.__drive.realRaf;
        return res;
    });
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
})();
