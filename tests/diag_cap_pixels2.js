const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
               '--disable-features=CalculateNativeWinOcclusion'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 950 });
    await page.bringToFront();
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);

    await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/physics-engine/stl/cone.stl');
    for (let w = 0; w < 60; w++) { await sleep(500); if (await page.evaluate(() => document.getElementById('orientation-modal').style.display === 'flex')) break; }
    const cardCount = await page.evaluate(() => document.querySelectorAll('#orientation-options .orient-card').length);
    console.log('orientation cards:', cardCount);
    await page.evaluate(() => { document.querySelector('#orientation-options .orient-card')?.click(); document.getElementById('orientation-confirm').click(); });
    await sleep(300);
    await page.evaluate(() => {
        document.getElementById('box-length').value = '50';
        document.getElementById('box-width').value = '50';
        document.getElementById('box-height').value = '50';
        [...document.querySelectorAll('.variant-btn')].find(b => b.dataset.variant === 'stacking')?.click();
        document.getElementById('calculate-btn').click();
    });
    for (let w = 0; w < 90; w++) { await sleep(1000); if (await page.evaluate(() => !!window.PackAssist.state.lastResults)) break; }
    await sleep(2000);
    await page.evaluate(() => document.getElementById('section-btn').click());
    await sleep(1000);

    const out = await page.evaluate(() => {
        const sm = window.PackAssist.state.sceneManager;
        const r = sm.renderer, gl = r.getContext();
        const W = gl.drawingBufferWidth, H = gl.drawingBufferHeight;
        const readCount = (test) => {
            const px = new Uint8Array(W * H * 4);
            gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, px);
            let n = 0;
            for (let i = 0; i < px.length; i += 4) if (test(px[i], px[i + 1], px[i + 2])) n++;
            return n;
        };
        const redish = (rr, gg, bb) => rr > 180 && gg < 60 && bb < 60;
        const capish = (rr, gg, bb) => Math.abs(rr - 185) < 20 && Math.abs(gg - 207) < 20 && Math.abs(bb - 230) < 20;
        const res = {};

        // --- A) does the stencil PASS draw at all? Paint it bright red. ---
        const sm2 = sm._stencilMat;
        const oldColorWrite = sm2.colorWrite, oldColor = sm2.color.getHex();
        sm2.colorWrite = true; sm2.color.setHex(0xff0000);
        r.autoClear = false;
        r.clear(true, true, true);
        const swapped = [];
        for (const p of sm.pieces) if (p.material) { swapped.push([p, p.material]); p.material = sm2; }
        r.render(sm.scene, sm.camera);
        res.redPixels_pass1 = readCount(redish);
        res.piecesCount = sm.pieces.length;
        for (const [p, m] of swapped) p.material = m;
        sm2.colorWrite = oldColorWrite; sm2.color.setHex(oldColor);

        // --- B) does the CAP plane draw with a trivial stencil test? ---
        const capMat = sm._capMesh.material;
        const oldFunc = capMat.stencilFunc;
        capMat.stencilFunc = 519; // AlwaysStencilFunc
        capMat.needsUpdate = true;
        r.autoClear = false;
        r.clear(true, true, true);
        r.render(sm._capScene, sm.camera);
        res.capPixels_always = readCount(capish);
        res.capInScene = sm._capScene.children.length;
        res.capGeoOk = !!(sm._capMesh.geometry && sm._capMesh.geometry.attributes.position.count > 0);
        res.capPos = [sm._capMesh.position.x, sm._capMesh.position.y, sm._capMesh.position.z].map(v => Math.round(v));
        res.capVisible = sm._capMesh.visible;
        res.stencilAttrs = !!gl.getContextAttributes().stencil;
        capMat.stencilFunc = oldFunc; capMat.needsUpdate = true;

        // --- C) full frame, cap colour with the real stencil test ---
        sm._needsRender = true;
        sm._renderFrame();
        const px = new Uint8Array(W * H * 4);
        gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, px);
        // background reference = bottom-left corner of the framebuffer
        const bi = ((H - 2) * W + 2) * 4;
        const bg = [px[bi], px[bi + 1], px[bi + 2]];
        let cap = 0, content = 0;
        for (let i = 0; i < px.length; i += 4) {
            if (capish(px[i], px[i + 1], px[i + 2])) cap++;
            if (Math.abs(px[i] - bg[0]) + Math.abs(px[i + 1] - bg[1]) + Math.abs(px[i + 2] - bg[2]) > 40) content++;
        }
        res.capPixels_final = cap;
        res.contentPixels_final = content;
        res.bg = bg;
        r.autoClear = true;
        return res;
    });
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
})();
