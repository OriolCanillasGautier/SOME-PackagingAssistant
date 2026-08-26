const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 950 });
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
  page.on('pageerror', e => errs.push(String(e).slice(0, 160)));
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
  await sleep(2000);
  await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/tests/large_mesh.stl');
  // Heavy mesh: orientation is deferred; wait for status to settle (simplify btn or ok).
  await sleep(6000);
  const res = await page.evaluate(() => {
    const sm = window.__sceneManager;
    if (!sm) return { noSM: true };
    return {
      heavy: sm._heavy,
      pixelRatio: sm.renderer ? sm.renderer.getPixelRatio() : null,
      shadows: sm.renderer ? sm.renderer.shadowMap.enabled : null,
      pieces: sm.pieces.length,
      heavyMeshTris: sm.heavyMeshTris,
    };
  });
  console.log('SCENE STATE:', JSON.stringify(res, null, 2));
  console.log('CONSOLE ERRORS:', JSON.stringify(errs.slice(0, 3)));
  await browser.close();
  process.exit(errs.length ? 1 : 0);
})();
