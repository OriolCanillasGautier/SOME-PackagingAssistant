// Orientation detection: how many stable poses does the UI actually offer?
// Fixtures live in tests/fixtures/ (cube, plate, ring, L-bracket, cone).
const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const FIXTURES = [
    { file: 'tests/fixtures/cube10.stl', name: 'cube 10³', minCards: 3 },
    { file: 'tests/fixtures/plate.stl', name: 'plate 40×30×3', minCards: 2 },
    { file: 'tests/fixtures/ring.stl', name: 'ring Ø10×4', minCards: 2 },
    { file: 'tests/fixtures/lbracket.stl', name: 'L-bracket', minCards: 3 },
    { file: 'physics-engine/stl/cone.stl', name: 'hollow cone', minCards: 1 },
];

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new', protocolTimeout: 600000,
        args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling',
               '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1300, height: 900 });
    await page.bringToFront();
    const errs = [];
    page.on('pageerror', e => errs.push(String(e).slice(0, 140)));
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });

    await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
    await sleep(2500);

    let pass = 0, fail = 0;
    const ok = (n, c, x) => { console.log((c ? 'PASS' : 'FAIL') + ' ' + n + (x ? ' [' + x + ']' : '')); c ? pass++ : fail++; };

    for (const fx of FIXTURES) {
        const path = '/var/www/SOME-PackagingAssistant/' + fx.file;
        await (await page.$('#stl-upload')).uploadFile(path);
        // wait for the modal (it opens once poses are computed)
        let opened = false;
        for (let w = 0; w < 120; w++) {
            await sleep(500);
            opened = await page.evaluate(() => document.getElementById('orientation-modal')?.style.display === 'flex');
            if (opened) break;
        }
        await sleep(2000);
        const info = await page.evaluate(() => {
            const cards = [...document.querySelectorAll('#orientation-options .orient-card')];
            return {
                n: cards.length,
                texts: cards.map(c => (c.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60)),
            };
        });
        console.log(`  ${fx.name}: modal=${opened} cards=${info.n}`);
        info.texts.forEach(t => console.log(`      · ${t}`));
        ok(`${fx.name}: >= ${fx.minCards} pose card(s)`, info.n >= fx.minCards, `cards=${info.n}`);
        // close the modal so the next upload starts clean
        await page.evaluate(() => { document.getElementById('orientation-modal').style.display = 'none'; });
        await sleep(300);
    }

    ok('NO JS ERRORS', errs.length === 0, JSON.stringify(errs.slice(0, 2)));
    console.log('\n' + pass + ' PASS, ' + fail + ' FAIL');
    await browser.close();
    process.exit(fail > 0 ? 1 : 0);
})();
