const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 950 });
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
  await sleep(2000);
  await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/tests/large_mesh.stl');
  await sleep(6000); // let preview + any reveal settle
  const sample = () => page.evaluate(() => {
    const sm = window.__sceneManager;
    return sm && sm.renderer ? sm.renderer.info.render.frame : -1;
  });
  const a = await sample();
  await sleep(2000); // camera static, nothing moving
  const b = await sample();
  await sleep(2000);
  const c = await sample();
  console.log('render.frame samples (2s apart):', a, b, c, '-> idle delta:', (c - a));
  console.log(b === a && c === b ? 'IDLE-PAUSE OK (no renders while static)' : 'WARNING: still rendering while idle');
  await browser.close();
})();
