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
    await page.evaluate(() => { [...document.querySelectorAll('#orientation-options .orient-card')][0].click(); document.getElementById('orientation-confirm').click(); });
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

    // Force one frame, then read the framebuffer and count pixels by colour.
    const probe = async (capVisible) => page.evaluate((capVis) => {
        const sm = window.PackAssist.state.sceneManager;
        if (sm._capMesh) sm._capMesh.visible = capVis;
        sm._needsRender = true;
        sm._renderFrame();
        const gl = sm.renderer.getContext();
        const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
        const px = new Uint8Array(w * h * 4);
        gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
        let cap = 0, any = 0;
        for (let i = 0; i < px.length; i += 4) {
            const r = px[i], g = px[i + 1], b = px[i + 2];
            if (r > 4 || g > 4 || b > 4) any++;
            // cap colour 0xb9cfe6 = (185, 207, 230)
            if (Math.abs(r - 185) < 14 && Math.abs(g - 207) < 14 && Math.abs(b - 230) < 14) cap++;
        }
        return { w, h, capPixels: cap, anyPixels: any };
    }, capVisible);

    const withCap = await probe(true);
    const withoutCap = await probe(false);
    console.log('cap VISIBLE  :', JSON.stringify(withCap));
    console.log('cap HIDDEN   :', JSON.stringify(withoutCap));
    console.log('cap adds pixels:', withCap.capPixels - withoutCap.capPixels);
    await browser.close();
})();
