/**
 * Box Options ("Comparar caixes") Puppeteer test
 *
 * Uploads the test STL, clicks "Comparar caixes", enters cost config, and
 * verifies the ranking table renders with the expected boxes, is sorted by
 * cost per part ascending, and the best box is highlighted. Also asserts zero
 * console errors.
 *
 * Usage:
 *   node test/box-options.test.mjs [--timeout 360] [--verbose]
 */
import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2);
const verbose = args.includes('--verbose');
const timeoutIdx = args.indexOf('--timeout');
const timeoutSec = timeoutIdx >= 0 ? parseInt(args[timeoutIdx + 1]) || 360 : 360;

const URL = 'http://127.0.0.1:8787/';
const STL = path.join(__dirname, '..', 'physics-engine', 'stl', 'part.stl');

async function main() {
    console.log(`\n=== Box Options Test ===`);
    console.log(`URL: ${URL}`);
    console.log(`STL: ${STL}`);
    console.log(`Timeout: ${timeoutSec}s\n`);

    const browser = await puppeteer.launch({
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--use-gl=angle',
            '--use-angle=swiftshader-webgl',
            '--enable-webgl',
            '--enable-unsafe-swiftshader'
        ]
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000 });

    const consoleErrors = [];
    page.on('console', msg => {
        if (msg.type() === 'error') {
            consoleErrors.push(msg.text());
        }
        if (verbose && msg.type() === 'error') console.log(`  [console.error] ${msg.text()}`);
    });
    page.on('pageerror', err => {
        consoleErrors.push(`pageerror: ${err.message}`);
    });

    try {
        console.log('Loading page...');
        await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });
        await new Promise(r => setTimeout(r, 1500));

        // --- 1. Upload the test STL ---
        console.log('Uploading STL...');
        await page.waitForSelector('#stl-upload', { timeout: 5000 });
        await page.$eval('#stl-upload', el => (el.style.display = 'block'));
        await page.$eval('#stl-upload', el => (el.style.visibility = 'visible'));
        const stlInput = await page.$('#stl-upload');
        await stlInput.uploadFile(STL);

        // Wait for the STL to finish loading (status shows dimensions)
        console.log('Waiting for STL to load...');
        await page.waitForFunction(() => {
            const st = document.getElementById('stl-status');
            return st && /mm/.test(st.textContent) && !/Preparant|Carregant/i.test(st.textContent);
        }, { timeout: 90000 });

        // Dismiss the orientation modal if present (Planar mode shows it)
        const modalVisible = await page.evaluate(() => {
            const m = document.getElementById('orientation-modal');
            return m && m.style.display !== 'none';
        });
        if (modalVisible) {
            console.log('Dismissing orientation modal...');
            await page.click('#orientation-confirm');
            await new Promise(r => setTimeout(r, 500));
        }

        // --- 2. Give the compare button a moment, then check it's visible ---
        const btnVisible = await page.evaluate(() => {
            const btn = document.getElementById('compare-boxes-btn');
            return btn && btn.style.display !== 'none';
        });
        console.log(`Compare button visible: ${btnVisible}`);
        if (!btnVisible) throw new Error('Compare button not visible in Planar mode');

        // Set a unique custom box so we get 5 rows (4 presets + custom)
        await page.evaluate(() => {
            document.getElementById('box-length').value = '250';
            document.getElementById('box-width').value = '250';
            document.getElementById('box-height').value = '250';
        });

        // --- 3. Open cost modal, enter costs, run ---
        console.log('Clicking "Comparar caixes"...');
        await page.click('#compare-boxes-btn');
        await page.waitForSelector('#box-cost-modal', { visible: true, timeout: 5000 });
        console.log('Cost modal opened. Entering costs...');

        await page.evaluate(() => {
            document.getElementById('box-cost-input').value = '0.60';
            document.getElementById('packaging-cost-input').value = '0.20';
            document.getElementById('freight-kg-input').value = '1.00';
        });

        // Store the config before running to compare with server echo later
        const expectedCosts = await page.evaluate(() => {
            return {
                boxCost: document.getElementById('box-cost-input').value,
                packagingCost: document.getElementById('packaging-cost-input').value,
                freightPerKg: document.getElementById('freight-kg-input').value
            };
        });

        await page.click('#box-cost-modal [data-run]');
        console.log('Comparison submitted. Waiting for ranking table...');

        // --- 4. Wait for the ranking table to render ---
        const started = Date.now();
        await page.waitForFunction(() => {
            return !!document.querySelector('#box-options-container .box-options-table tbody tr');
        }, { timeout: (timeoutSec - 30) * 1000 });
        const waitSec = ((Date.now() - started) / 1000).toFixed(1);
        console.log(`Ranking table rendered after ${waitSec}s`);

        // --- 5. Read and verify the ranking ---
        const data = await page.evaluate(() => {
            const rows = Array.from(document.querySelectorAll('#box-options-container .box-options-table tbody tr'));
            const rowsOut = rows.map(tr => {
                const cells = Array.from(tr.querySelectorAll('td'));
                const box = cells[0]?.textContent.trim() || '';
                const pieces = parseInt(cells[1]?.dataset.pieces || cells[1]?.textContent || '', 10);
                const fill = parseFloat((cells[2]?.textContent || '').replace('%', '')) || 0;
                const weight = parseFloat(cells[3]?.dataset.weight ?? 'NaN') || 0;
                const costPart = parseFloat(cells[4]?.dataset.cost ?? 'NaN');
                const totalCost = parseFloat(cells[5]?.dataset.total ?? 'NaN');
                const skipped = tr.classList.contains('skipped');
                const best = tr.classList.contains('best');
                return { box, pieces, fill, weight, costPart, totalCost, skipped, best };
            });
            const meta = document.querySelector('#box-options-container .box-options-meta')?.textContent || '';
            const title = document.querySelector('#box-options-container .box-options-title')?.textContent || '';
            const costConfig = window.PackAssist.state.costConfig;
            return { rows: rowsOut, meta, title, costConfig };
        });

        console.log('\n=== RANKING TABLE ===');
        data.rows.forEach(r => {
            const skip = r.skipped ? ` [SKIPPED]` : '';
            const best = r.best ? ` [BEST]` : '';
            console.log(`  ${r.box} | pcs=${r.pieces} | fill=${r.fill}% | wt=${r.weight}kg | cost/part=${r.costPart}€ | total=${r.totalCost}€${skip}${best}`);
        });
        console.log(`Title: "${data.title}"`);
        console.log(`Meta: "${data.meta.replace(/\s+/g, ' ').trim()}"`);
        console.log(`costConfig stored: ${JSON.stringify(data.costConfig)}`);

        // --- 6. Assertions ---
        const validRows = data.rows.filter(r => !r.skipped && !isNaN(r.costPart));
        const skippedRows = data.rows.filter(r => r.skipped);
        const totalRows = data.rows.length;

        console.log('\n=== ASSERTIONS ===');
        console.log(`Total rows: ${totalRows} (expected >= 5)`);
        console.log(`Valid (ranked) rows: ${validRows.length}, skipped: ${skippedRows.length}`);
        console.log(`Best row highlighted: ${validRows.length > 0 ? validRows[0].best : false}`);

        // N boxes renders (4 presets + custom box)
        const nOk = totalRows >= 5;
        console.log(`N boxes >= 5: ${nOk ? 'PASS' : 'FAIL'}`);

        // Sorted ascending by cost per part (valid rows only)
        let sorted = true;
        for (let i = 1; i < validRows.length; i++) {
            if (validRows[i].costPart < validRows[i - 1].costPart - 1e-9) {
                sorted = false;
                break;
            }
        }
        console.log(`Sorted ascending by cost/part: ${sorted ? 'PASS' : 'FAIL'}`);

        // Best (first valid) row highlighted
        const bestOk = validRows.length > 0 && validRows[0].best;
        console.log(`Best highlighted: ${bestOk ? 'PASS' : 'FAIL'}`);

        // Cost config persisted for the PDF agent
        const expBox = parseFloat(expectedCosts.boxCost);
        const expPack = parseFloat(expectedCosts.packagingCost);
        const expFreight = parseFloat(expectedCosts.freightPerKg);
        const cfgOk = data.costConfig &&
            Math.abs(data.costConfig.boxCost - expBox) < 1e-9 &&
            Math.abs(data.costConfig.packagingCost - expPack) < 1e-9 &&
            Math.abs(data.costConfig.freightPerKg - expFreight) < 1e-9;
        console.log(`costConfig persisted: ${cfgOk ? 'PASS' : 'FAIL'}`);

        // Zero console errors
        const errors = consoleErrors.filter(e => !/Failed to load resource/i.test(e));
        const consoleOk = errors.length === 0;
        console.log(`Zero console errors: ${consoleOk ? 'PASS' : 'FAIL'} (${errors.length})`);
        if (!consoleOk) errors.forEach(e => console.log(`    • ${e}`));

        await page.screenshot({ path: '/tmp/opencode/box-options-result.png', fullPage: true });

        await browser.close();
        const passed = nOk && sorted && bestOk && cfgOk && consoleOk;
        console.log(`\n${passed ? 'PASS' : 'FAIL'} — Box Options test\n`);
        process.exit(passed ? 0 : 1);
    } catch (err) {
        console.error(`\nERROR: ${err.message}`);
        try {
            await page.screenshot({ path: '/tmp/opencode/box-options-error.png' });
        } catch (_) { /* ignore */ }
        await browser.close();
        process.exit(1);
    }
}

main();
