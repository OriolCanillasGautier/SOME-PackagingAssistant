const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
    const browser = await puppeteer.launch({ headless: 'new', args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 950 });
    const errs = [];
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 120)); });
    page.on('pageerror', e => errs.push(String(e).slice(0, 120)));
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);
    let pass = 0, fail = 0;
    const ok = (n, c, x) => { console.log((c ? 'PASS' : 'FAIL') + ' ' + n + (x ? ' [' + x + ']' : '')); c ? pass++ : fail++; };
    await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/physics-engine/stl/cone.stl');
    for (let w = 0; w < 60; w++) { await sleep(500); if (await page.evaluate(() => document.getElementById('orientation-modal').style.display === 'flex')) break; }
    const cards = await page.evaluate(() => document.querySelectorAll('#orientation-options .orient-card').length);
    ok('1. ORIENTATION (1-2 cards)', cards >= 1 && cards <= 2, cards + ' cards');
    await page.evaluate(() => { [...document.querySelectorAll('#orientation-options .orient-card')][0].click(); document.getElementById('orientation-confirm').click(); });
    await sleep(300);
    await page.evaluate(() => {
        document.getElementById('box-length').value = '50';
        document.getElementById('box-width').value = '50';
        document.getElementById('box-height').value = '50';
        [...document.querySelectorAll('.variant-btn')].find(b => b.dataset.variant === 'stacking')?.click();
        document.getElementById('calculate-btn').click();
    });
    for (let w = 0; w < 90; w++) { await sleep(1000); if (await page.evaluate(() => !!document.getElementById('report-preview-btn') && document.getElementById('report-preview-btn').offsetParent !== null)) break; }
    const stk = await page.evaluate(() => window.PackAssist.state.lastResults?.pieceCount);
    ok('2. STACKING HOLLOW CONE 50^3 (~279)', stk >= 230 && stk <= 320, stk + ' pieces');
    await page.evaluate(() => { [...document.querySelectorAll('.variant-btn')].find(b => b.dataset.variant === 'grid')?.click(); document.getElementById('calculate-btn').click(); });
    for (let w = 0; w < 60; w++) { await sleep(500); if (await page.evaluate(() => !!document.getElementById('report-preview-btn') && document.getElementById('report-preview-btn').offsetParent !== null)) break; }
    const grid = await page.evaluate(() => window.PackAssist.state.lastResults?.pieceCount);
    ok('3. GRAELLA (144 = 6x6x4, 10.2mm tall)', grid === 144, grid + ' pieces');
    const hasSimp = await page.evaluate(() => !!document.getElementById('simplify-mesh-btn'));
    ok('4. SIMPLIFY BUTTON', hasSimp);
    console.log('\n' + pass + ' PASS, ' + fail + ' FAIL');
    console.log('ERRORS:', JSON.stringify(errs.slice(0, 3)));
    await browser.close();
    process.exit(fail > 0 ? 1 : 0);
})();
