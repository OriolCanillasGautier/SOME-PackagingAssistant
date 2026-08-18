/**
 * Protective Packaging (Pack Studio) Puppeteer test
 *
 * Uploads the test STL, runs a Planar → Compartment-style pack (the Planar
 * optimal-grid pack records compartment cell data), then verifies:
 *   - the "Protective packaging" section is visible in Planar mode
 *   - toggling "Separadors de cartró" renders brown cardboard divider meshes
 *   - toggling "Inserts d'escuma" renders grey foam pads
 *   - toggling "Safata motllurada" renders the grey slab + recessed cells
 *   - toggling off removes the overlays
 *   - the section is hidden in Bulk mode
 *   - zero console errors
 *
 * Usage:
 *   node test/protective-packaging.test.mjs [--timeout 300] [--verbose]
 */
import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2);
const verbose = args.includes('--verbose');
const timeoutIdx = args.indexOf('--timeout');
const timeoutSec = timeoutIdx >= 0 ? parseInt(args[timeoutIdx + 1]) || 300 : 300;

const URL = 'http://127.0.0.1:8787/';
const STL = path.join(__dirname, '..', 'physics-engine', 'stl', 'part.stl');

async function main() {
    console.log(`\n=== Protective Packaging Test ===`);
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

    const results = [];

    const check = (name, ok, extra = '') => {
        results.push({ name, ok });
        console.log(`  ${ok ? 'PASS' : 'FAIL'} — ${name}${extra ? ` (${extra})` : ''}`);
    };

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

        // --- 2. Section visible in Planar mode ---
        const sectionVisible = await page.evaluate(() => {
            const s = document.getElementById('protective-section');
            return !!s && s.style.display !== 'none';
        });
        check('Protective section visible in Planar mode', sectionVisible);

        // --- 3. Run the Planar (Compartiment-style) pack ---
        console.log('Running Planar calculation...');
        await page.click('#calculate-btn');

        // Wait for the pack to finish (scene has placements + compartment data)
        await page.waitForFunction(() => {
            const mgr = window.__sceneManager;
            return mgr && mgr.lastPlacement && mgr.lastPlacement.boxDims && mgr._compartmentData;
        }, { timeout: (timeoutSec - 30) * 1000 });
        await new Promise(r => setTimeout(r, 500));

        const grid = await page.evaluate(() => {
            const mgr = window.__sceneManager;
            return { ...mgr._compartmentData, placed: mgr.pieces.length };
        });
        console.log(`  Compartment grid: ${grid.boxL}×${grid.boxW}×${grid.boxH}mm, cell ${grid.cellL}×${grid.cellW}mm, piece groups=${grid.placed}`);

        // --- 4. Partitions checkbox becomes enabled after the compartment pack ---
        await page.waitForFunction(() => {
            const cb = document.getElementById('protective-partitions');
            return cb && !cb.disabled;
        }, { timeout: 10000 });
        check('Partitions checkbox enabled after compartment pack', true);

        // Count helper: meshes anywhere in the scene with a given hex color
        const countProtective = hex => page.evaluate(h => {
            const mgr = window.__sceneManager;
            if (!mgr) return 0;
            let n = 0;
            mgr.scene.traverse(o => {
                if (o.isMesh && o.material && o.material.color && o.material.color.getHex() === h) n++;
            });
            return n;
        }, hex);

        // --- 5. Toggle partitions ON → brown cardboard divider meshes ---
        console.log('Toggling "Separadors de cartró" ON...');
        await page.click('#protective-partitions');
        await new Promise(r => setTimeout(r, 300));
        let partitions = await countProtective(0xc8a86e);
        check('Partitions render cardboard divider meshes', partitions > 0, `${partitions} walls`);
        if (verbose) console.log(`    [scene] cardboard meshes = ${partitions}`);

        // --- 6. Toggle foam ON → grey pads ---
        console.log('Toggling "Inserts d\'escuma" ON...');
        await page.click('#protective-foam');
        await new Promise(r => setTimeout(r, 300));
        let foam = await countProtective(0xd1d5db);
        check('Foam renders grey pads', foam > 0, `${foam} pads`);
        if (verbose) console.log(`    [scene] foam pads = ${foam}`);

        // --- 7. Toggle tray ON → slab + recessed cells ---
        console.log('Toggling "Safata motllurada" ON...');
        await page.click('#protective-tray');
        await new Promise(r => setTimeout(r, 300));
        const slab = await countProtective(0xd1d5db);
        const recess = await countProtective(0x9ca3af);
        check('Tray renders grey slab + recessed cells', slab > 0 && recess > 0, `slab+${recess} cells`);
        if (verbose) console.log(`    [scene] tray slab=${slab}, recessed cells=${recess}`);

        // --- 8. Toggle everything OFF → overlays disappear ---
        console.log('Toggling all OFF...');
        await page.click('#protective-tray');
        await page.click('#protective-foam');
        await page.click('#protective-partitions');
        await new Promise(r => setTimeout(r, 300));
        const totalAfterOff = await countProtective(0xc8a86e) + await countProtective(0xd1d5db) + await countProtective(0x9ca3af);
        check('Overlays removed after toggling off', totalAfterOff === 0, `${totalAfterOff} meshes remain`);

        // --- 9. Section hidden in Bulk mode ---
        console.log('Switching to Bulk mode...');
        await page.click('.mode-btn[data-mode="bulk"]');
        await new Promise(r => setTimeout(r, 400));
        const hiddenInBulk = await page.evaluate(() => {
            const s = document.getElementById('protective-section');
            return !!s && s.style.display === 'none';
        });
        check('Protective section hidden in Bulk mode', hiddenInBulk);

        // --- 10. Zero console errors ---
        const errors = consoleErrors.filter(e => !/Failed to load resource/i.test(e));
        check('Zero console errors', errors.length === 0, `${errors.length}`);
        if (errors.length) errors.forEach(e => console.log(`    • ${e}`));

        await page.screenshot({ path: '/tmp/opencode/protective-packaging-result.png', fullPage: true });

        await browser.close();
        const passed = results.every(r => r.ok);
        console.log(`\n${passed ? 'PASS' : 'FAIL'} — Protective Packaging test (${results.filter(r => r.ok).length}/${results.length} passed)\n`);
        process.exit(passed ? 0 : 1);
    } catch (err) {
        console.error(`\nERROR: ${err.message}`);
        try {
            await page.screenshot({ path: '/tmp/opencode/protective-packaging-error.png' });
        } catch (_) { /* ignore */ }
        await browser.close();
        process.exit(1);
    }
}

main();
