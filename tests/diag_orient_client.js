// Why does the cube show 1 card when the server returns 3 poses?
// Dumps the client-side stability verdict for every pose it received.
const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new', protocolTimeout: 600000,
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.bringToFront();
    page.on('pageerror', e => console.log('[pageerror]', String(e).slice(0, 140)));
    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);

    const fixture = process.argv[2] || 'tests/fixtures/cube10.stl';
    await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/' + fixture);
    for (let w = 0; w < 120; w++) {
        await sleep(500);
        if (await page.evaluate(() => document.getElementById('orientation-modal')?.style.display === 'flex')) break;
    }
    await sleep(1500);

    const info = await page.evaluate(() => {
        const st = window.PackAssist.state;
        const ors = st.stlStableOrientations || [];
        return {
            cards: document.querySelectorAll('#orientation-options .orient-card').length,
            poses: ors.map((o, i) => ({
                i,
                stable: o.stability?.stable,
                physicsStable: o.stability?.physicsStable,
                tippedDeg: o.stability?.tippedDeg != null ? +Number(o.stability.tippedDeg).toFixed(1) : null,
                supportArea: o.stability?.supportArea != null ? +Number(o.stability.supportArea).toFixed(0) : null,
                hasQuat: !!o.quat,
            })),
        };
    });
    console.log(fixture);
    console.log(JSON.stringify(info, null, 1));
    await browser.close();
})();
