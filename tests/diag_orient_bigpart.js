// Big real part: upload -> simplify modal -> "Usar la malla original" -> poses?
const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
    const browser = await puppeteer.launch({ headless: 'new', protocolTimeout: 600000,
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.bringToFront();
    page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 140)));
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);
    const fixture = process.argv[2];
    const t0 = Date.now();
    await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/' + fixture);
    // wait for the simplify modal's "use original" button
    let hasBtn = false;
    for (let w = 0; w < 60; w++) {
        await sleep(500);
        hasBtn = await page.evaluate(() => !!document.getElementById('use-original-btn'));
        if (hasBtn) break;
    }
    console.log('use-original button present:', hasBtn, `(${((Date.now()-t0)/1000).toFixed(0)}s)`);
    if (hasBtn) {
        await page.evaluate(() => document.getElementById('use-original-btn').click());
    }
    // wait for the orientation modal
    let opened = false;
    for (let w = 0; w < 180; w++) {
        await sleep(500);
        opened = await page.evaluate(() => document.getElementById('orientation-modal')?.style.display === 'flex');
        if (opened) break;
    }
    await sleep(2500);
    const info = await page.evaluate(() => {
        const ors = window.PackAssist.state.stlStableOrientations || [];
        return {
            cards: document.querySelectorAll('#orientation-options .orient-card').length,
            poses: ors.length,
            nVerts: window.PackAssist.state.stlGeometry?.getAttribute('position')?.count || 0,
            verdicts: ors.map(o => ({
                stable: o.stability?.stable,
                physicsStable: o.stability?.physicsStable,
                tippedDeg: o.stability?.tippedDeg != null ? +Number(o.stability.tippedDeg).toFixed(1) : null,
                supportArea: o.stability?.supportArea != null ? +Number(o.stability.supportArea).toFixed(0) : null,
            })),
            texts: [...document.querySelectorAll('#orientation-options .orient-card')]
                .map(c => (c.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 46)),
        };
    });
    console.log(`modal=${opened} after ${((Date.now()-t0)/1000).toFixed(0)}s`);
    console.log(JSON.stringify(info, null, 1));
    await browser.close();
})();
