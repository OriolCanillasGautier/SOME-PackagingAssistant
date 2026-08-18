const puppeteer = require('puppeteer');
const APP_URL = 'http://127.0.0.1:8787/';
const STL_PATH = '/var/www/SOME-PackagingAssistant/physics-engine/stl/part.stl';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function waitFor(fn, timeout = 60000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) { try { const v = await fn(); if (v) return v; } catch {} await sleep(400); }
    throw new Error('timeout');
}
(async () => {
    const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader','--use-gl=swiftshader','--ignore-gpu-blocklist'] });
    const page = await browser.newPage();
    await page.goto(APP_URL, { waitUntil: 'networkidle2' });
    await (await page.$('#stl-upload')).uploadFile(STL_PATH);
    await waitFor(() => page.evaluate(() => {
        const s = document.getElementById('stl-status');
        return s && s.textContent.includes('Dimensions');
    }), 90000);
    const hasOrient = await page.evaluate(() => { const m = document.getElementById('orientation-modal'); return m && m.style.display !== 'none'; });
    if (hasOrient) { await page.evaluate(() => document.getElementById('orientation-confirm').click()); await sleep(800); }
    await page.evaluate(() => document.getElementById('calculate-btn').click());
    await waitFor(() => page.evaluate(() => { const rb = document.getElementById('report-buttons'); return rb && rb.style.display === 'block'; }), 120000);

    // Inject cost data like a cost agent would, then open modal
    await page.evaluate(() => {
        if (!window.PackAssist?.state) throw new Error('no state');
        window.PackAssist.state.lastResults.cost = {
            boxCost: 0.85,
            packagingCost: 0.22,
            freightCost: 1.2,
            costPerPart: 0.0287,
        };
    });
    await page.evaluate(() => document.getElementById('report-preview-btn').click());
    await sleep(1500);
    await waitFor(() => page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        const d = f && f.contentDocument;
        return d && d.querySelector('.cost-section');
    }), 30000);

    const info = await page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        const d = f.contentDocument;
        return {
            costTitle: d.querySelector('.cost-title')?.textContent,
            costValues: Array.from(d.querySelectorAll('.cost-value')).map(e => e.textContent),
            costLabels: Array.from(d.querySelectorAll('.cost-label')).map(e => e.textContent),
            highlight: d.querySelector('.cost-item-highlight')?.textContent || null,
        };
    });
    console.log('cost section:', JSON.stringify(info, null, 2));

    const out = await page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        const sheet = f.contentDocument.querySelector('.sheet');
        return { sheetHeight: sheet.getBoundingClientRect().height };
    });
    await page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        f.style.height = '1123px';
        f.contentDocument.querySelector('.sheet').style.transform = 'none';
    });
    await page.screenshot({ path: '/tmp/opencode/report-cost.png' });
    console.log('cost screenshot saved', JSON.stringify(out));

    await browser.close();
    console.log('COST TEST DONE');
})().catch(e => { console.error('FAIL', e); process.exit(1); });
