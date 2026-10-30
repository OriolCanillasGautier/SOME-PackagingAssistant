// LIVE gravity flow — uses the app's OWN timers and render loop (no fake
// clock, no manual stepping). This is the regression guard for the class of
// bug that shipped once: `this.piecesInFlight()` was called on BulkSimulation
// while it is defined on PhysicsWorld, so the drop interval threw on every
// tick and NO piece was ever poured — invisible to e2e_gravity.js, which
// clears the intervals and drives dropPiece() itself.
const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new', protocolTimeout: 600000,
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
               '--disable-features=CalculateNativeWinOcclusion'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    await page.bringToFront();

    const errs = [];
    page.on('pageerror', e => errs.push(String(e).slice(0, 160)));
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });

    let pass = 0, fail = 0;
    const ok = (n, c, x) => { console.log((c ? 'PASS' : 'FAIL') + ' ' + n + (x ? ' [' + x + ']' : '')); c ? pass++ : fail++; };

    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);
    // count render-loop frames + drop-interval ticks from the page itself
    await page.evaluate(() => {
        window.__raf = 0;
        const oRaf = window.requestAnimationFrame.bind(window);
        window.requestAnimationFrame = (cb) => { window.__raf++; return oRaf(cb); };
    });

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
        const di = document.getElementById('drop-interval'); if (di) di.value = '100';
        ['box-length', 'box-width', 'box-height'].forEach(id =>
            document.getElementById(id).dispatchEvent(new Event('input', { bubbles: true })));
    });
    await sleep(400);
    await page.evaluate(() => document.getElementById('start-simulation-btn').click());
    await sleep(900);
    const popup = await page.evaluate(() => {
        const p = document.getElementById('bulk-start-popup');
        if (!p || p.style.display === 'none') return 'no-popup';
        const auto = document.querySelector('input[name="bulk-mode"][value="auto"]');
        if (auto) { auto.checked = true; auto.dispatchEvent(new Event('change', { bubbles: true })); }
        document.getElementById('bulk-start-confirm')?.click();
        return 'auto-confirmed';
    });
    console.log('popup:', popup);

    // ── watch the REAL flow for up to 45s ──
    let saw = null;
    for (let i = 0; i < 15; i++) {
        await sleep(3000);
        saw = await page.evaluate(() => {
            const sim = window.PackAssist?.state?.bulkSimulation;
            return {
                dropped: sim?.droppedCount ?? -1,
                bodies: sim?.physics?.meshBodies?.length ?? -1,
                inside: sim?.physics?.countPiecesInBox ? sim.physics.countPiecesInBox() : -1,
                running: sim?.isRunning ?? null,
                raf: window.__raf,
                inFlight: sim?.physics?.piecesInFlight ? sim.physics.piecesInFlight() : -1,
                intervalAlive: !!sim?.dropInterval,
            };
        });
        console.log(`  +${(i + 1) * 3}s`, JSON.stringify(saw));
        if (saw.dropped > 0 && saw.bodies > 0) break;
    }

    ok('1. THE POUR ACTUALLY STARTS (pieces dropped)', saw && saw.dropped > 0, `dropped=${saw?.dropped}`);
    ok('2. PIECES EXIST IN THE SCENE', saw && saw.bodies > 0, `bodies=${saw?.bodies}`);
    ok('3. THE RENDER LOOP IS TICKING', saw && saw.raf > 10, `raf=${saw?.raf}`);
    ok('4. THE DROP INTERVAL IS ALIVE', saw && saw.intervalAlive === true);
    ok('5. NO JS ERRORS (no TypeError in the interval)', errs.length === 0, JSON.stringify(errs.slice(0, 2)));

    console.log('\n' + pass + ' PASS, ' + fail + ' FAIL');
    await browser.close();
    process.exit(fail > 0 ? 1 : 0);
})();
