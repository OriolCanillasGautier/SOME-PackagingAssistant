const puppeteer = require('puppeteer');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--use-angle=swiftshader', '--no-sandbox', '--disable-background-timer-throttling'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 950 });
  const errs=[]; page.on('pageerror', e=>errs.push(String(e).slice(0,150)));
  await page.goto('http://127.0.0.1:8787/', { waitUntil: 'domcontentloaded' });
  await sleep(2000);
  // box: <50k verts -> orientation analysis runs immediately on upload
  await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/tests/box.stl');
  for (let w=0;w<40;w++){ await sleep(500); if (await page.evaluate(()=>document.getElementById('orientation-modal').style.display==='flex')) break; }
  const res = await page.evaluate(() => {
    const modal = document.getElementById('orientation-modal');
    const cards = [...document.querySelectorAll('#orientation-options .orient-card')];
    const boxes = cards.map(c => ({ i: c.dataset.index, sel: c.classList.contains('selected'), rec: c.classList.contains('recommended'), act: c.classList.contains('active'), fit: c.querySelector('.orient-fit')?.textContent }));
    return { count: cards.length, boxes, boxL: document.getElementById('box-length').value, boxW: document.getElementById('box-width').value, boxH: document.getElementById('box-height').value };
  });
  console.log('cards:', res.count, '| box', res.boxL+'x'+res.boxW+'x'+res.boxH);
  res.boxes.forEach(b => console.log('  idx', b.i, 'selected='+b.sel, 'active='+b.act, 'recommended='+b.rec, '->', b.fit));
  const autoSelIsRec = res.boxes.filter(b=>b.sel).every(b=>b.rec && b.act);
  console.log('AUTO-SELECT matches recommended:', autoSelIsRec);
  console.log('pageerrors:', errs.slice(0,3));
  await browser.close();
  process.exit((autoSelIsRec && res.count>=2) ? 0 : 2);
})();
