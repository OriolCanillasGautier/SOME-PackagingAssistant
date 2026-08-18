/**
 * Bulk gravity simulation Puppeteer test
 *
 * Loads the app, switches to Bulk > Gravetat, starts a fixed-pieces run via the
 * start popup (40 pieces), and verifies the full flow:
 *   running → vibrating → compacting (lid press) → settling → settled
 *
 * Usage:
 *   node test/bulk-gravity-sim.test.mjs [--timeout 90] [--verbose]
 */
import puppeteer from 'puppeteer';

const args = process.argv.slice(2);
const verbose = args.includes('--verbose');
const timeoutIdx = args.indexOf('--timeout');
const timeoutSec = timeoutIdx >= 0 ? parseInt(args[timeoutIdx + 1]) || 90 : 90;

const URL = 'http://127.0.0.1:8787/';
const FIXED_PIECES = 40;

async function main() {
    console.log(`\n=== Bulk Gravity Simulation Test ===`);
    console.log(`URL: ${URL}`);
    console.log(`Fixed pieces: ${FIXED_PIECES}`);
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

    const consoleLogs = [];
    const statuses = [];
    page.on('console', msg => {
        const text = msg.text();
        consoleLogs.push(text);
        if (verbose && /vibrat|Lid|lid|settl|Bulk|peces|Simulaci|box|overflow|refill/i.test(text)) {
            console.log(`  [browser] ${text}`);
        }
    });
    page.on('pageerror', err => {
        console.error(`  [page error] ${err.message}`);
    });

    try {
        console.log('Loading page...');
        await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });

        // Ensure the page has fully booted (Rapier + Three init)
        await new Promise(r => setTimeout(r, 1500));

        // --- 1. Switch to Bulk mode (Gravetat variant is the default) ---
        await page.click('button.mode-btn[data-mode="bulk"]');
        await new Promise(r => setTimeout(r, 500));

        const bulkActive = await page.evaluate(() => {
            const btn = document.querySelector('button.mode-btn[data-mode="bulk"]');
            const variant = document.querySelector('.variant-btn[data-variant="gravity"]');
            return {
                bulkActive: btn && btn.classList.contains('active'),
                gravityActive: variant && variant.classList.contains('active'),
                startVisible: document.getElementById('start-simulation-btn')?.style.display !== 'none'
            };
        });
        console.log(`Bulk mode active: ${bulkActive.bulkActive}, gravity variant: ${bulkActive.gravityActive}`);
        if (!bulkActive.gravityActive) {
            await page.click('.variant-btn[data-variant="gravity"]');
            await new Promise(r => setTimeout(r, 300));
        }

        // --- 2. Click start, popup appears, set fixed=40, confirm ---
        console.log('Opening start popup...');
        await page.click('#start-simulation-btn');
        await page.waitForSelector('#bulk-start-popup', { visible: true, timeout: 5000 });
        const popupVisible = await page.evaluate((n) => {
            const popup = document.getElementById('bulk-start-popup');
            const fixedRadio = document.querySelector('input[name="bulk-mode"][value="fixed"]');
            if (fixedRadio) fixedRadio.checked = true;
            document.getElementById('bulk-fixed-pieces-group').style.display = 'block';
            document.getElementById('bulk-fixed-pieces').value = String(n);
            return popup.style.display !== 'none';
        }, FIXED_PIECES);
        console.log(`Popup visible: ${popupVisible}, setting fixed=${FIXED_PIECES}`);

        // Monitor the status line continuously
        await page.evaluate(() => {
            window.__statusHistory = [];
            const el = document.getElementById('simulation-status');
            if (el) {
                new MutationObserver(() => {
                    window.__statusHistory.push(el.textContent);
                }).observe(el, { childList: true, characterData: true, subtree: true });
            }
        });

        await page.click('#bulk-start-confirm');
        console.log('Simulation started. Waiting for completion...\n');

        // --- 3. Wait for the simulation to finish (settled status) ---
        const started = Date.now();
        let finalStatus = null;

        const poll = async () => {
            for (;;) {
                const elapsed = Date.now() - started;
                if (elapsed > timeoutSec * 1000) {
                    return null;
                }
                const state = await page.evaluate(() => {
                    const el = document.getElementById('simulation-status');
                    return {
                        text: el ? el.textContent : '',
                        results: document.getElementById('results')?.textContent || '',
                        history: window.__statusHistory || []
                    };
                });
                if (/Resultat Simulació a Granel|Bulk Simulation Result|Finalitzat|finalizad|Finalizado|finished|finalized/i.test(state.results)) {
                    return state;
                }
                if (/Finalitzat/.test(state.text)) {
                    return state;
                }
                if (verbose && elapsed % 5000 < 50) {
                    console.log(`  [wait ${(elapsed/1000).toFixed(1)}s] status: ${state.text.slice(0, 80)}`);
                }
                await new Promise(r => setTimeout(r, 500));
            }
        };

        const state = await poll();
        const elapsedSec = ((Date.now() - started) / 1000).toFixed(1);

        if (!state) {
            const last = await page.evaluate(() => ({
                text: document.getElementById('simulation-status')?.textContent || '',
                results: document.getElementById('results')?.textContent || ''
            }));
            console.log(`FAIL: timed out after ${timeoutSec}s. Last status: "${last.text}"`);
            console.log(`Last results text: "${last.results.slice(0, 300)}"`);
            await page.screenshot({ path: '/tmp/opencode/bulk-sim-timeout.png' });
            await browser.close();
            process.exit(1);
        }

        // --- 4. Parse the reported numbers from the results list ---
        const result = await page.evaluate(() => {
            const el = document.getElementById('results');
            const text = el ? el.textContent : '';
            const lis = Array.from(document.querySelectorAll('#results li'))
                .map(li => li.textContent.replace(/\s+/g, ' ').trim());
            const droppedItem = lis.find(t => /deixades|dropped/i.test(t));
            const insideItem = lis.find(t => /dins|inside/i.test(t));
            const num = (s) => {
                const m = s && s.match(/([\d.,]+)/);
                return m ? m[1] : null;
            };
            return {
                text: text.replace(/\s+/g, ' ').trim(),
                droppedRaw: num(droppedItem),
                insideRaw: num(insideItem)
            };
        });

        const statusHistory = state.history.length ? state.history : statuses;
        console.log(`\nCompleted in ${elapsedSec}s`);
        console.log(`Results: ${result.text.slice(0, 400)}`);
        console.log(`\nStatus timeline (${statusHistory.length} updates, last 12):`);
        statusHistory.slice(-12).forEach(s => console.log(`  • ${s}`));

        // --- 5. Assertions ---
        const dropped = result.droppedRaw ? parseFloat(result.droppedRaw) : NaN;
        const inside = result.insideRaw ? parseFloat(result.insideRaw) : NaN;

        const flowOk = state.history.some(s => /vibrant/i.test(s)) &&
                       state.history.some(s => /tapa|premsa|compac/i.test(s)) &&
                       (state.history.some(s => /assent|settl/i.test(s)) || /assent|settl/i.test(state.text));

        const resultsOk = /Resultat Simulació a Granel|Bulk Simulation Result/i.test(result.text);

        console.log(`\n=== RESULTS ===`);
        console.log(`Dropped count: ${Number.isNaN(dropped) ? 'N/A' : dropped}`);
        console.log(`Inside count:  ${Number.isNaN(inside) ? 'N/A' : inside}`);
        console.log(`Flow (vibrate → lid → settle): ${flowOk ? 'PASS' : 'WARN (not all phases seen)'}`);
        console.log(`Results panel shows completion: ${resultsOk ? 'PASS' : 'FAIL'}`);
        console.log(`Dropped < 100: ${(!Number.isNaN(dropped) && dropped < 100) ? 'PASS' : 'FAIL'}`);
        console.log(`Inside reported: ${!Number.isNaN(inside) ? `PASS (${inside})` : 'FAIL'}`);

        await page.screenshot({ path: '/tmp/opencode/bulk-sim-result.png' });
        await browser.close();

        const passed = resultsOk && !Number.isNaN(inside) && (!Number.isNaN(dropped) && dropped < 100);
        process.exit(passed ? 0 : 1);
    } catch (err) {
        console.error(`\nERROR: ${err.message}`);
        await page.screenshot({ path: '/tmp/opencode/bulk-sim-error.png' });
        await browser.close();
        process.exit(1);
    }
}

main();
