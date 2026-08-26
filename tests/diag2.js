const puppeteer = require('puppeteer');
const sleep = (ms)=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const browser = await puppeteer.launch({headless:'new', args:['--use-angle=swiftshader','--no-sandbox','--disable-background-timer-throttling']});
  const page = await browser.newPage();
  const logs=[]; page.on('console', m=>{ const t=m.text(); if(t.includes('OptimalGrid')||t.includes('Càlcul total')||t.includes('handleCalculate')||t.includes('handleGPUCalculate')||t.includes('Graella Optima')) logs.push(t.slice(0,90)); });
  await page.goto('http://127.0.0.1:8787/', {waitUntil:'domcontentloaded'});
  await sleep(2000);
  await (await page.$('#stl-upload')).uploadFile('/var/www/SOME-PackagingAssistant/physics-engine/stl/cone.stl');
  for (let w=0;w<40;w++){ await sleep(500); if(await page.evaluate(()=>document.getElementById('orientation-modal').style.display==='flex')) break; }
  await page.evaluate(()=>{ [...document.querySelectorAll('#orientation-options .orient-card')][0].click(); document.getElementById('orientation-confirm').click(); });
  await sleep(300);
  await page.evaluate(()=>{ document.getElementById('box-length').value='50'; document.getElementById('box-width').value='50'; document.getElementById('box-height').value='50';
    [...document.querySelectorAll('.variant-btn')].find(b=>b.dataset.variant==='grid')?.click(); document.getElementById('calculate-btn').click(); });
  await sleep(6000);
  console.log('count:', await page.evaluate(()=>window.PackAssist?.state?.lastResults?.pieceCount));
  console.log('LOGS:\n'+logs.join('\n'));
  await browser.close();
})();
