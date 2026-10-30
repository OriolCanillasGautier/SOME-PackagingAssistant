const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
    const browser = await puppeteer.launch({ headless: 'new', args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 950 });
    const errs = [];
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 150)); });
    page.on('pageerror', e => errs.push(String(e).slice(0, 150)));
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);
    let pass = 0, fail = 0;
    const ok = (n, c, x) => { console.log((c ? 'PASS' : 'FAIL') + ' ' + n + (x ? ' [' + x + ']' : '')); c ? pass++ : fail++; };

    // Upload cone + confirm orientation + run stacking
    await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/physics-engine/stl/cone.stl');
    for (let w = 0; w < 60; w++) { await sleep(500); if (await page.evaluate(() => document.getElementById('orientation-modal').style.display === 'flex')) break; }
    await page.evaluate(() => { [...document.querySelectorAll('#orientation-options .orient-card')][0].click(); document.getElementById('orientation-confirm').click(); });
    await sleep(200);
    await page.evaluate(() => {
        document.getElementById('box-length').value = '50';
        document.getElementById('box-width').value = '50';
        document.getElementById('box-height').value = '50';
        [...document.querySelectorAll('.variant-btn')].find(b => b.dataset.variant === 'stacking')?.click();
        document.getElementById('calculate-btn').click();
    });
    for (let w = 0; w < 90; w++) { await sleep(1000); if (await page.evaluate(() => !!document.getElementById('report-preview-btn') && document.getElementById('report-preview-btn').offsetParent !== null)) break; }
    const n = await page.evaluate(() => window.PackAssist.state.lastResults?.pieceCount);
    ok('1. STACKING DONE (~363)', n >= 300, n + ' pieces');

    // Enable section
    await page.evaluate(() => document.getElementById('section-btn').click());
    await sleep(400);
    const s1 = await page.evaluate(() => {
        const sm = window.__sceneManager || window.PackAssist.state.sceneManager;
        const ctr = document.getElementById('section-controls');
        const p = sm.renderer.clippingPlanes && sm.renderer.clippingPlanes[0];
        const attrs = sm.renderer.getContext().getContextAttributes();
        return {
            visible: ctr && ctr.style.display !== 'none',
            hasPlane: !!p,
            normal: p ? [p.normal.x, p.normal.y, p.normal.z].map(v => Math.round(v)) : null,
            planeMesh: !!sm._sectionMesh,
            // The cut must be FILLED (solid look), not a hollow shell:
            capMesh: !!sm._capMesh,
            capOpacity: sm._capMesh ? sm._capMesh.material.opacity : null,
            // 517 = THREE.NotEqualStencilFunc (THREE is a module import, not a
            // page global, so compare the numeric constant).
            capStencilTest: sm._capMesh ? sm._capMesh.material.stencilFunc === 517 : null,
            capStencilWrite: sm._capMesh ? sm._capMesh.material.stencilWrite === true : null,
            stencilBuffer: !!attrs.stencil,
        };
    });
    ok('2. SECTION ON (panel + clip plane)', s1.visible && s1.hasPlane && s1.planeMesh, JSON.stringify(s1));
    ok('3. DEFAULT AXIS X (normal -1,0,0)', s1.normal && s1.normal.join(',') === '-1,0,0', JSON.stringify(s1.normal));
    ok('3b. CUT IS FILLED (stencil cap, translucent)',
       s1.capMesh && s1.capOpacity > 0.5 && s1.capOpacity < 1 && s1.capStencilTest && s1.capStencilWrite && s1.stencilBuffer,
       JSON.stringify({ cap: s1.capMesh, op: s1.capOpacity, test: s1.capStencilTest, sw: s1.capStencilWrite, sb: s1.stencilBuffer }));

    // Switch to Y axis
    await page.evaluate(() => document.querySelector('.section-axis-btn[data-saxis="y"]').click());
    await sleep(300);
    const s2 = await page.evaluate(() => {
        const sm = window.__sceneManager || window.PackAssist.state.sceneManager;
        const p = sm.renderer.clippingPlanes[0];
        const active = document.querySelector('.section-axis-btn.active')?.dataset.saxis;
        return { normal: [p.normal.x, p.normal.y, p.normal.z].map(v => Math.round(v)).join(','), active };
    });
    ok('4. AXIS SWITCH Y', s2.normal === '0,-1,0' && s2.active === 'y', JSON.stringify(s2));

    // Slider moves the plane (set to 30%, Y axis, box height 50 -> constant 15)
    await page.evaluate(() => {
        const s = document.getElementById('section-slider');
        s.value = '30';
        s.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await sleep(300);
    const s3 = await page.evaluate(() => {
        const sm = window.__sceneManager || window.PackAssist.state.sceneManager;
        return { constant: Math.round(sm.renderer.clippingPlanes[0].constant * 100) / 100 };
    });
    ok('5. SLIDER MOVES PLANE (30% of 50mm = 15)', Math.abs(s3.constant - 15) < 0.6, JSON.stringify(s3));

    // Toggle off -> cleared
    await page.evaluate(() => document.getElementById('section-btn').click());
    await sleep(300);
    const s4 = await page.evaluate(() => {
        const sm = window.__sceneManager || window.PackAssist.state.sceneManager;
        return {
            planes: sm.renderer.clippingPlanes ? sm.renderer.clippingPlanes.length : 0,
            panelHidden: document.getElementById('section-controls').style.display === 'none',
            meshGone: !sm._sectionMesh,
            capGone: !sm._capMesh,
        };
    });
    ok('6. SECTION OFF (clip + marker + cap cleared)',
       s4.planes === 0 && s4.panelHidden && s4.meshGone && s4.capGone, JSON.stringify(s4));

    ok('7. NO JS ERRORS', errs.length === 0, JSON.stringify(errs.slice(0, 3)));
    console.log('\n' + pass + ' PASS, ' + fail + ' FAIL');
    await browser.close();
    process.exit(fail > 0 ? 1 : 0);
})();
