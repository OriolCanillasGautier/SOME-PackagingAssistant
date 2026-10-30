const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
    const browser = await puppeteer.launch({ headless: 'new', args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 950 });
    page.on('console', m => console.log('[' + m.type() + ']', m.text().slice(0, 300)));
    page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 400)));
    page.on('response', async r => {
        const u = r.url();
        if (u.includes('/api/pack') && !u.includes('png') && !u.includes('stl')) {
            try {
                const j = await r.json();
                console.log('[api]', r.status(), u.replace('http://127.0.0.1:8787', ''), JSON.stringify(j).slice(0, 220));
            } catch (e) { console.log('[api]', r.status(), u.slice(-60)); }
        }
    });
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
    for (let w = 0; w < 60; w++) { await sleep(1000); if (await page.evaluate(() => !!window.PackAssist.state.lastResults)) break; }
    const res = await page.evaluate(() => window.PackAssist.state.lastResults ? { count: window.PackAssist.state.lastResults.pieceCount } : null);
    console.log('RESULT:', JSON.stringify(res));
    await browser.close();
})();
