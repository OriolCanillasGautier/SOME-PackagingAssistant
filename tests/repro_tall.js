// Reproduce the user's TALL view: Apilat (stacking) + test cone in the given
// box, then capture the viewport and report what is actually in the scene.
const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new', protocolTimeout: 600000,
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 950 });
    await page.bringToFront();
    page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 140)));
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);

    const box = process.argv[2] || '160';
    await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/physics-engine/stl/cone.stl');
    for (let w = 0; w < 60; w++) {
        await sleep(500);
        if (await page.evaluate(() => document.getElementById('orientation-modal')?.style.display === 'flex')) break;
    }
    await page.evaluate(() => {
        [...document.querySelectorAll('#orientation-options .orient-card')][0]?.click();
        document.getElementById('orientation-confirm')?.click();
    });
    await sleep(300);
    await page.evaluate((b) => {
        for (const id of ['box-length', 'box-width', 'box-height']) {
            document.getElementById(id).value = b;
            document.getElementById(id).dispatchEvent(new Event('input', { bubbles: true }));
        }
        [...document.querySelectorAll('.variant-btn')].find(x => x.dataset.variant === 'stacking')?.click();
        document.getElementById('calculate-btn').click();
    }, box);
    for (let w = 0; w < 120; w++) {
        await sleep(1000);
        const done = await page.evaluate(() => {
            const b = document.getElementById('report-preview-btn');
            return !!b && b.offsetParent !== null;
        });
        if (done) break;
    }
    // wait for the progressive reveal to finish (instance count stable)
    let prev = -1, stable = 0;
    for (let i = 0; i < 40; i++) {
        await sleep(1000);
        const n = await page.evaluate(() => {
            const sm = window.PackAssist?.state?.sceneManager;
            let t = 0;
            for (const p of (sm?.pieces || [])) t += p.isInstancedMesh ? (p.count || 1) : 1;
            return t;
        });
        if (n === prev && n > 0) { stable++; if (stable >= 3) break; } else { stable = 0; }
        prev = n;
    }
    console.log('revealed instances (settled):', prev);
    const info = await page.evaluate(() => {
        const st = window.PackAssist.state;
        const sm = st.sceneManager;
        const kinds = {};
        let instTotal = 0;
        for (const p of (sm?.pieces || [])) {
            const k = `${p.isInstancedMesh ? 'instanced' : 'mesh'}:${p.geometry?.type || '?'}`;
            const n = p.isInstancedMesh ? (p.count || 1) : 1;
            kinds[k] = (kinds[k] || 0) + n;
            instTotal += n;
        }
        return {
            pieceCount: st.lastResults?.pieceCount ?? null,
            piecesInScene: instTotal,
            kinds,
            dims: st.lastResults?.dims || null,
        };
    });
    console.log(`box=${box}`, JSON.stringify(info));

    // capture WITHOUT the section first (reference)
    const rect0 = await page.evaluate(() => {
        const el = window.PackAssist?.state?.sceneManager?.renderer?.domElement;
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.x, y: r.y, w: r.width, h: r.height };
    });
    if (rect0 && rect0.w > 10) {
        await page.screenshot({ path: `tests/renders/nosection_stacking_${box}.png`,
                                clip: { x: rect0.x, y: rect0.y, width: rect0.w, height: rect0.h } });
        console.log(`wrote tests/renders/nosection_stacking_${box}.png`);
    }
    await page.evaluate(() => document.getElementById('section-btn').click());
    await sleep(2500);
    const rect = await page.evaluate(() => {
        const el = window.PackAssist?.state?.sceneManager?.renderer?.domElement;
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.x, y: r.y, w: r.width, h: r.height };
    });
    if (rect && rect.w > 10) {
        await page.screenshot({ path: `tests/renders/tall_stacking_${box}.png`,
                                clip: { x: rect.x, y: rect.y, width: rect.w, height: rect.h } });
        console.log(`wrote tests/renders/tall_stacking_${box}.png`);

        // (a) pieces WITHOUT the cap
        await page.evaluate(() => {
            const sm = window.PackAssist.state.sceneManager;
            if (sm._capMesh) sm._capMesh.visible = false;
            sm.requestRender?.();
        });
        await sleep(1200);
        await page.screenshot({ path: `tests/renders/tall_nocap_${box}.png`,
                                clip: { x: rect.x, y: rect.y, width: rect.w, height: rect.h } });
        console.log(`wrote tests/renders/tall_nocap_${box}.png`);

        // (b) the cap ALONE
        await page.evaluate(() => {
            const sm = window.PackAssist.state.sceneManager;
            if (sm._capMesh) sm._capMesh.visible = true;
            (sm.pieces || []).forEach(p => p.visible = false);
            sm.requestRender?.();
        });
        await sleep(1200);
        await page.screenshot({ path: `tests/renders/tall_caponly_${box}.png`,
                                clip: { x: rect.x, y: rect.y, width: rect.w, height: rect.h } });
        console.log(`wrote tests/renders/tall_caponly_${box}.png`);
        await page.evaluate(() => {
            const sm = window.PackAssist.state.sceneManager;
            (sm.pieces || []).forEach(p => p.visible = true);
            sm.requestRender?.();
        });

        // (c) MASK DEBUG: cap forced opaque red, depth test off. A solid red
        // sheet means the stencil mask is solid (and the speckle is depth
        // related); speckled red means the mask itself is broken.
        await page.evaluate(() => {
            const sm = window.PackAssist.state.sceneManager;
            const m = sm._capMesh?.material;
            if (m) { m.color.set(0xff0000); m.opacity = 1; m.transparent = false; m.depthTest = false; m.needsUpdate = true; }
            sm.requestRender?.();
        });
        await sleep(1200);
        await page.screenshot({ path: `tests/renders/tall_maskdebug_${box}.png`,
                                clip: { x: rect.x, y: rect.y, width: rect.w, height: rect.h } });
        console.log(`wrote tests/renders/tall_maskdebug_${box}.png`);
    }
    await browser.close();
})();
