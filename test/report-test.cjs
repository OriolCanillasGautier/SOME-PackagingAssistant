const puppeteer = require('puppeteer');

const APP_URL = process.env.APP_URL || 'http://127.0.0.1:8787/';
const STL_PATH = process.env.STL_PATH || '/var/www/SOME-PackagingAssistant/physics-engine/stl/part.stl';
const OUT = process.env.OUT || '/tmp/opencode';
const fs = require('fs');

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function waitFor(fn, timeout = 60000, step = 500) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
        try {
            const v = await fn();
            if (v) return v;
        } catch (e) { /* retry */ }
        await sleep(step);
    }
    throw new Error('timeout waiting for condition');
}

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--enable-unsafe-swiftshader',
            '--use-gl=swiftshader',
            '--ignore-gpu-blocklist',
        ],
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);
    page.on('console', (msg) => {
        const t = msg.type();
        if (t === 'error' || t === 'warn') console.log(`[console.${t}]`, msg.text().slice(0, 300));
    });
    page.on('pageerror', (err) => console.log('[pageerror]', String(err).slice(0, 400)));

    console.log('1. navigate');
    await page.goto(APP_URL, { waitUntil: 'networkidle2', timeout: 60000 });

    // Disable the WebGL context loss between captures: WebGLRenderer with preserveDrawingBuffer default false
    await page.evaluate(() => {
        // n/a
    });

    console.log('2. upload STL');
    const input = await page.$('#stl-upload');
    await input.uploadFile(STL_PATH);

    // Wait for orientation modal / STL status
    await waitFor(() => page.evaluate(() => {
        const s = document.getElementById('stl-status');
        return s && (s.textContent.includes('Dimensions') || s.textContent.includes('Simplificat'));
    }), 90000);

    const stlStatus = await page.evaluate(() => document.getElementById('stl-status').textContent);
    console.log('   stl-status:', stlStatus.trim().replace(/\n/g, ' | '));

    // If the orientation modal appears, confirm it
    const hasOrient = await page.evaluate(() => {
        const m = document.getElementById('orientation-modal');
        return m && m.style.display !== 'none';
    });
    if (hasOrient) {
        console.log('3. confirm orientation');
        await page.evaluate(() => document.getElementById('orientation-confirm').click());
        await sleep(800);
    }

    console.log('4. run Planar (fast) pack');
    // Ensure fast mode is active
    await page.evaluate(() => {
        const fast = document.querySelector('.mode-btn[data-mode="fast"]');
        if (fast && !fast.classList.contains('active')) fast.click();
    });
    await page.evaluate(() => document.getElementById('calculate-btn').click());

    // Wait for the report buttons to appear (means results ready)
    await waitFor(() => page.evaluate(() => {
        const rb = document.getElementById('report-buttons');
        return rb && rb.style.display === 'block';
    }), 120000);

    console.log('5. open report preview modal');
    await page.evaluate(() => document.getElementById('report-preview-btn').click());
    await sleep(500);

    // Wait for iframe inside preview frame with rendered content
    const iframe = await waitFor(() => page.evaluateHandle(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        if (!f) return null;
        const d = f.contentDocument;
        if (!d) return null;
        return d.readyState === 'complete' || d.querySelector('.sheet') ? f : null;
    }), 60000);

    // Give images time to load inside iframe
    await waitFor(() => page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        const d = f && f.contentDocument;
        if (!d) return false;
        const imgs = Array.from(d.querySelectorAll('img'));
        return imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0);
    }), 30000);

    const reportInfo = await page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        const d = f.contentDocument;
        const sheet = d.querySelector('.sheet');
        const metrics = Array.from(d.querySelectorAll('.metric-value')).map(e => e.textContent);
        const labels = Array.from(d.querySelectorAll('.metric-label')).map(e => e.textContent);
        const views = Array.from(d.querySelectorAll('.view img')).map(i => i.naturalWidth + 'x' + i.naturalHeight);
        const hero = d.querySelector('.hero img');
        const cost = d.querySelector('.cost-section');
        return {
            hasSheet: !!sheet,
            title: d.querySelector('.header-title')?.textContent,
            brand: d.querySelector('.brand')?.textContent,
            heroSize: hero ? hero.naturalWidth + 'x' + hero.naturalHeight : 'none',
            metrics: metrics.map((m, i) => m + ' = ' + labels[i]),
            views,
            costPresent: !!cost,
            sheetHeight: sheet ? sheet.getBoundingClientRect().height : 0,
            sheetScrollHeight: sheet ? sheet.scrollHeight : 0,
            bodyOverflow: sheet ? (sheet.scrollHeight > sheet.clientHeight + 2) : null,
        };
    });
    console.log('   report:', JSON.stringify(reportInfo, null, 2));

    // Screenshot: modal + full page report
    const modal = await page.$('#report-modal');
    await page.evaluate(() => {
        const m = document.getElementById('report-modal');
        m.style.width = '1080px';
        m.style.maxWidth = '95vw';
    });
    await page.screenshot({ path: `${OUT}/report-modal.png` });
    await modal.screenshot({ path: `${OUT}/report-modal-content.png` });

    // Screenshot of the iframe content directly (the A4 sheet)
    const frame = await iframe.asElement();
    await frame.screenshot({ path: `${OUT}/report-iframe.png` });

    // 6. Test EN language via radio
    await page.evaluate(() => {
        document.querySelector('input[name="report-lang"][value="en"]').checked = true;
        document.querySelector('input[name="report-lang"][value="en"]').dispatchEvent(new Event('change', { bubbles: true }));
    });
    await sleep(2500);
    const enInfo = await page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        const d = f.contentDocument;
        return {
            title: d.querySelector('.header-title')?.textContent,
            brand: d.querySelector('.brand')?.textContent,
            kicker: d.querySelector('.header-kicker')?.textContent,
            metricLabels: Array.from(d.querySelectorAll('.metric-label')).map(e => e.textContent),
        };
    });
    console.log('   EN report:', JSON.stringify(enInfo));
    await page.evaluate(() => {
        document.querySelector('input[name="report-lang"][value="en"]').dispatchEvent(new Event('change', { bubbles: true }));
    });
    await sleep(2500);
    await page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        const d = f.contentDocument;
        const sheet = d.querySelector('.sheet');
        sheet.style.transform = 'none';
        document.body.style.height = '1123px';
    });
    await page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        f.style.height = '1123px';
    });
    await page.screenshot({ path: `${OUT}/report-en.png` });

    // 7. Extract the report HTML to a standalone file for printing/PDF
    const reportHtml = await page.evaluate(() => {
        const f = document.querySelector('#report-preview-frame iframe');
        return '<!DOCTYPE html>\n' + f.contentDocument.documentElement.outerHTML;
    });
    fs.writeFileSync(`${OUT}/report.html`, reportHtml);
    console.log('   saved report.html');

    // 8. Verify one-page print via new page + pdf
    const printPage = await browser.newPage();
    await printPage.goto('file://' + OUT + '/report.html', { waitUntil: 'networkidle0' });
    const pdf = await printPage.pdf({
        format: 'A4',
        printBackground: true,
        margin: { top: '0', right: '0', bottom: '0', left: '0' },
        preferCSSPageSize: true,
    });
    fs.writeFileSync(`${OUT}/report.pdf`, pdf);
    console.log('   pdf bytes:', pdf.length);
    // count pages by looking for /Type /Page occurrences
    const n = pdf.toString('latin1').match(/\/Type\s*\/Page[^s]/g);
    console.log('   pdf pages (approx):', n ? n.length : 0);

    await browser.close();
    console.log('DONE');
})().catch((e) => { console.error('FAIL', e); process.exit(1); });
