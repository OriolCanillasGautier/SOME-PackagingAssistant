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

    // Upload cone, confirm orientation, run stacking (363 pieces in 50^3)
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
    await sleep(2500);
    const n = await page.evaluate(() => window.PackAssist.state.lastResults?.pieceCount);
    console.log('pieces:', n);

    // Section on (axis X, middle)
    await page.evaluate(() => document.getElementById('section-btn').click());
    await sleep(1200);

    const canvasBox = await page.evaluate(() => {
        const c = document.querySelector('#three-canvas canvas');
        const r = c.getBoundingClientRect();
        return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) };
    });

    // Isometric-ish camera so the cut is clearly visible
    await page.evaluate(() => window.PackAssist.state.sceneManager.setView('iso'));
    await sleep(1200);
    await page.screenshot({ path: '/var/www/SOME-PackagingAssistant/tests/renders/section_filled.png', clip: canvasBox });
    console.log('saved section_filled.png');

    // Same shot with the cap hidden = the old hollow look
    await page.evaluate(() => { window.PackAssist.state.sceneManager._capMesh.visible = false; window.PackAssist.state.sceneManager.requestRender(); });
    await sleep(1000);
    await page.screenshot({ path: '/var/www/SOME-PackagingAssistant/tests/renders/section_hollow_before.png', clip: canvasBox });
    console.log('saved section_hollow_before.png');

    await browser.close();
})();
