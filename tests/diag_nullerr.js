const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
    const browser = await puppeteer.launch({ headless: 'new', args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 950 });
    page.on('console', m => {
        if (m.type() === 'error') {
            // location() gives URL:line for console errors
            const loc = m.location();
            console.log('[console.error]', m.text().slice(0, 120), '@', loc.url.replace('http://127.0.0.1:8787', ''), ':' + loc.lineNumber);
        }
    });
    page.on('pageerror', e => console.log('[pageerror]', String(e.stack || e).slice(0, 500)));
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(3000);
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
    for (let w = 0; w < 90; w++) { await sleep(1000); if (await page.evaluate(() => !!window.PackAssist.state.lastResults)) break; }
    await sleep(1500);
    console.log('-- section on --');
    await page.evaluate(() => document.getElementById('section-btn').click());
    await sleep(500);
    console.log('-- axis y --');
    await page.evaluate(() => document.querySelector('.section-axis-btn[data-saxis="y"]').click());
    await sleep(500);
    console.log('-- slider 30 --');
    await page.evaluate(() => { const s = document.getElementById('section-slider'); s.value = '30'; s.dispatchEvent(new Event('input', { bubbles: true })); });
    await sleep(500);
    console.log('-- axis z --');
    await page.evaluate(() => document.querySelector('.section-axis-btn[data-saxis="z"]').click());
    await sleep(500);
    console.log('-- section off --');
    await page.evaluate(() => document.getElementById('section-btn').click());
    await sleep(500);
    console.log('DONE');
    await browser.close();
})();
