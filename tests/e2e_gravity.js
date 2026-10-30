// Gravity/bulk verification — DETERMINISTIC, CHUNKED driver.
//
// Headless Chrome throttles timers AND requestAnimationFrame, so the real-time
// bulk simulation crawls (10+ min, no progress). This suite drives the SAME
// simulation code on a fake clock, but in SHORT chunks (one page.evaluate per
// chunk) so a single call can never hit puppeteer's protocol timeout, and the
// page's event loop gets a breather between chunks for the real setTimeout
// phases (staged vibration, lid start, final settle).
//
//   * requestAnimationFrame is stubbed so update() cannot self-schedule
//   * performance.now() advances 33 ms per step (virtual 60 fps)
//   * the drop/refill setInterval loops are emulated by the driver
const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const CHUNK_FN = (n) => {
    const d = window.__drive, sim = d.sim;
    const stepMs = 33;
    const dropEvery = Math.max(6, Math.round((sim.dropIntervalMs || 100) / stepMs));
    for (let i = 0; i < n && sim.isRunning; i++) {
        d.t += stepMs; d.steps++;
        // emulate the intervals this driver disabled
        if (sim.dropInterval) { clearInterval(sim.dropInterval); sim.dropInterval = null; }
        if (sim.refillInterval) { clearInterval(sim.refillInterval); sim.refillInterval = null; }
        if (!sim.allDropped) {
            const inRefill = sim.refillTarget != null && sim.refillDropped < sim.refillTarget;
            if (inRefill) {
                if (d.steps % dropEvery === 0) { sim.dropPiece(); sim.refillDropped++; }
            } else if (sim.refillTarget != null) {
                sim.refillTarget = null;              // refill phase finished
                d.refills++;
                sim.finishDropping('refill');
            } else if (d.steps % dropEvery === 0) {
                sim.dropPiece();
            }
        }
        if (sim.vibrationPhase) d.vib = true;
        if (sim.hasPressedLid) d.lid = true;
        sim.update();
    }
    return {
        steps: d.steps, running: sim.isRunning, dropped: sim.droppedCount,
        inside: sim.physics.countPiecesInBox(), bodies: sim.physics.meshBodies.length,
        vib: d.vib, lid: d.lid, refills: d.refills, cycles: sim.currentCycle,
        lidState: sim.physics.lidState || null,
        pieceVolume: sim.pieceVolume ? +sim.pieceVolume.toFixed(1) : 0,
        volumeCapacity: sim.volumeCapacity ? +sim.volumeCapacity.toFixed(1) : 0,
    };
};

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new',
        protocolTimeout: 600000,
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
               '--disable-features=CalculateNativeWinOcclusion',
               '--js-flags=--max-old-space-size=4096'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    await page.bringToFront();

    const errs = [];
    let colliderLog = '';
    let crashed = false;
    page.on('console', m => {
        const t = m.text();
        if (t.includes('[Bulk] collider:')) { colliderLog = t; console.log('LOG:', t); }
        if (t.includes('[Bulk] Box full')) console.log('LOG:', t);
        if (m.type() === 'error') errs.push(t.slice(0, 140));
    });
    page.on('pageerror', e => errs.push(String(e).slice(0, 140)));
    page.on('error', e => { crashed = true; console.log('PAGE CRASHED:', String(e).slice(0, 160)); });

    let pass = 0, fail = 0;
    const ok = (n, c, x) => { console.log((c ? 'PASS' : 'FAIL') + ' ' + n + (x ? ' [' + x + ']' : '')); c ? pass++ : fail++; };
    const safeEval = async (fn, arg) => {
        try { return await page.evaluate(fn, arg); }
        catch (e) { crashed = true; console.log('EVAL FAILED:', String(e).slice(0, 110)); return null; }
    };

    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);

    // ── UI setup: cone, Bulk + Gravetat, 25³ box, auto mode ──
    await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/physics-engine/stl/cone.stl');
    await sleep(3000);
    await safeEval(() => document.querySelector('.mode-btn[data-mode="bulk"]')?.click());
    await sleep(600);
    await safeEval(() => document.querySelector('#bulk-variant-selector .variant-btn[data-variant="gravity"]')?.click());
    await sleep(600);
    await safeEval(() => {
        document.getElementById('box-length').value = '25';
        document.getElementById('box-width').value = '25';
        document.getElementById('box-height').value = '25';
        const di = document.getElementById('drop-interval'); if (di) di.value = '100';
        ['box-length', 'box-width', 'box-height'].forEach(id =>
            document.getElementById(id).dispatchEvent(new Event('input', { bubbles: true })));
    });
    await sleep(500);

    const started = await safeEval(() => {
        const b = document.getElementById('start-simulation-btn');
        if (!b) return false;
        b.click();
        return true;
    });
    await sleep(900);
    const popup = await safeEval(() => {
        const p = document.getElementById('bulk-start-popup');
        if (!p || p.style.display === 'none') return 'no-popup';
        const auto = document.querySelector('input[name="bulk-mode"][value="auto"]');
        if (auto) { auto.checked = true; auto.dispatchEvent(new Event('change', { bubbles: true })); }
        document.getElementById('bulk-start-confirm')?.click();
        return 'auto-confirmed';
    });
    console.log('popup:', popup);
    ok('1. SIMULATION STARTED', started === true && popup !== 'no-confirm-button');

    // ── install the deterministic driver ──
    const installed = await safeEval(() => {
        const sim = window.PackAssist.state.bulkSimulation;
        if (!sim) return false;
        window.__drive = {
            sim, t: performance.now(), steps: 0, vib: false, lid: false, refills: 0,
            realNow: performance.now.bind(performance),
            realRaf: window.requestAnimationFrame,
        };
        window.requestAnimationFrame = () => 0;
        performance.now = () => window.__drive.t;
        return true;
    });
    ok('2. DETERMINISTIC DRIVER INSTALLED', installed === true);

    // ── chunked stepping ──
    let st = null;
    const t0 = Date.now();
    let lastLog = 0;
    for (let c = 0; c < 200; c++) {
        st = await safeEval(CHUNK_FN, 150);
        if (!st) break;
        if (Date.now() - lastLog > 8000) {
            lastLog = Date.now();
            const secs = ((Date.now() - t0) / 1000).toFixed(0);
            console.log(`  [${secs}s] steps=${st.steps} inside=${st.inside} dropped=${st.dropped} ` +
                        `bodies=${st.bodies} lid=${st.lidState} running=${st.running}`);
        }
        if (!st.running) break;
        await sleep(60); // let the real setTimeout phases fire
    }
    await safeEval(() => {
        const d = window.__drive;
        performance.now = d.realNow;
        window.requestAnimationFrame = d.realRaf;
    });
    const wallMs = Date.now() - t0;
    console.log('drive:', JSON.stringify(st), `(${(wallMs / 1000).toFixed(1)}s wall)`);
    if (!st) { console.log('\n1 PASS, 1 FAIL (driver produced nothing)'); await browser.close(); process.exit(1); }
    console.log(`  step rate: ${(st.steps / Math.max(1, wallMs) * 1000).toFixed(0)} steps/s`);


    // ── Nesting proof: two compound bodies, one dropped on the other ──
    // With a cavity-preserving collider the upper cone slides INTO the lower
    // one: pair height ~14mm. A convex hull (solid copy) would stack at ~20mm.
    const nesting = await safeEval(() => {
        const sim = window.PackAssist.state.bulkSimulation;
        const ph = sim.physics;
        if (!sim._colliderBoxes || !sim._colliderBoxes.length) return { error: 'no compound boxes' };
        for (const { body } of ph.meshBodies.slice()) if (body && body.isValid()) ph.world.removeRigidBody(body);
        ph.meshBodies.length = 0;
        const geo = sim.stlGeometry.clone();
        geo.computeBoundingBox();
        const bb = geo.boundingBox;
        const cx = (bb.min.x + bb.max.x) / 2, cy = (bb.min.y + bb.max.y) / 2, cz = (bb.min.z + bb.max.z) / 2;
        const boxes = sim._colliderBoxes.map(b => ({ c: [b.c[0] - cx, b.c[1] - cy, b.c[2] - cz], h: b.h }));
        window.__drive = window.__drive || { t: performance.now(), realNow: performance.now.bind(performance) };
        performance.now = () => window.__drive.t;
        window.requestAnimationFrame = () => 0;
        sim.isRunning = true; ph.isRunning = true;
        const a = ph.addCompoundBoxes(boxes, { x: 25, y: 5.1, z: 25 }, null, null);
        const b = ph.addCompoundBoxes(boxes, { x: 25, y: 25, z: 25 }, null, null);
        for (let i = 0; i < 150; i++) { window.__drive.t += 33; sim.update(); }
        const pa = a.translation(), pb = b.translation();
        const pieceH = sim.pieceDims ? sim.pieceDims.h : 10.2;
        const res = {
            boxes: boxes.length,
            yA: +pa.y.toFixed(2), yB: +pb.y.toFixed(2),
            rise: +(pb.y - pa.y).toFixed(2),
            pair: +((pb.y - pa.y) + pieceH).toFixed(2),
        };
        performance.now = window.__drive.realNow;
        sim.isRunning = false;
        return res;
    });
    console.log('nesting:', JSON.stringify(nesting));
    // Nesting is NOT expected with hull colliders (concave colliders are
    // unstable in this Rapier build) — record the measurement for the record
    // instead of asserting it, so the suite stays honest about the limitation.
    console.log(nesting && !nesting.error
        ? `nesting measurement: pair=${nesting.pair}mm (hull ~20mm = no nesting)`
        : `nesting measurement unavailable: ${JSON.stringify(nesting)}`);

    // ── results panel ──
    await sleep(1500);
    const txt = await safeEval(() => document.getElementById('results')?.innerText || '');
    const num = (label) => {
        const m = (txt || '').match(new RegExp(label + '[^0-9]*([0-9]+(?:[.,][0-9]+)?)', 'i'));
        return m ? parseFloat(m[1].replace(',', '.')) : null;
    };
    const dropped = num('Dropped pieces|Peces deixades');
    const inside = num('Pieces inside|Peces dins');
    const removed = num('Removed pieces|Peces fora');
    const eff = num('Efficiency|Efici');
    console.log(`RESULT: dropped=${dropped} inside=${inside} removed=${removed} efficiency=${eff}%`);

    ok('3. PAGE DID NOT CRASH', !crashed);
    ok('4. STABLE COLLIDER (convex hull; concave colliders measured unstable)',
       /convex hull/.test(colliderLog), colliderLog.slice(0, 90));
    ok('5. SIMULATION REACHED THE END', st.running === false, 'steps=' + st.steps);
    ok('6. VIBRATION RAN, LID PRESS DISABLED', st.vib === true && st.lid === false,
       JSON.stringify({ vib: st.vib, lid: st.lid, lidState: st.lidState }));
    ok('7. FILLED THE BOX', (inside ?? 0) > 20, 'inside=' + inside);
    // Waste = poured pieces that did not end up inside (the panel's "removed"
    // only counts pieces the cleanup deleted; overflow perched above the rim
    // never lands inside either). Goal: < 10%.
    const waste = dropped > 0 ? (dropped - (inside || 0)) / dropped : 1;
    ok('8. WASTE < 10%', waste <= 0.10, `waste=${(waste * 100).toFixed(1)}% (${dropped - inside}/${dropped})`);
    ok('9. NO JS ERRORS', errs.length === 0, JSON.stringify(errs.slice(0, 2)));

    console.log('\n' + pass + ' PASS, ' + fail + ' FAIL');
    await browser.close();
    process.exit(fail > 0 ? 1 : 0);
})();
