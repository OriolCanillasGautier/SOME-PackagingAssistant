/**
 * PackAssist Benchmark Runner
 * 
 * Runs the benchmark.html tests headlessly via Puppeteer.
 * Requires XAMPP Apache running on port 80.
 * 
 * Usage:
 *   node test/run-benchmark.mjs [--timeout 180] [--verbose]
 */
import puppeteer from 'puppeteer';

const args = process.argv.slice(2);
const verbose = args.includes('--verbose');
const timeoutIdx = args.indexOf('--timeout');
const timeoutSec = timeoutIdx >= 0 ? parseInt(args[timeoutIdx + 1]) || 180 : 180;

const BENCHMARK_URL = 'http://localhost/GitHub/SOME-PackagingAssistant/web/benchmark.html?auto=1';

async function main() {
    console.log(`\n=== PackAssist Benchmark Runner ===`);
    console.log(`URL: ${BENCHMARK_URL}`);
    console.log(`Timeout: ${timeoutSec}s\n`);

    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--use-gl=angle',
            '--use-angle=swiftshader-webgl',
            '--enable-webgl',
        ]
    });

    const page = await browser.newPage();

    // Capture console logs
    const consoleLogs = [];
    const timingLogs = [];
    page.on('console', msg => {
        const text = msg.text();
        consoleLogs.push(text);
        if (text.includes('[Timing]') || text.includes('[HeightMapAsync]')) {
            timingLogs.push(text);
            if (verbose) console.log(`  [browser] ${text}`);
        }
    });

    page.on('pageerror', err => {
        console.error(`  [page error] ${err.message}`);
    });

    try {
        await page.goto(BENCHMARK_URL, { waitUntil: 'networkidle2', timeout: 30000 });
        console.log('Page loaded. Waiting for benchmark results...\n');

        // Wait for the __BENCHMARK_RESULTS_END__ marker in console
        const resultJSON = await new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error(`Benchmark timed out after ${timeoutSec}s`)), timeoutSec * 1000);

            let capturing = false;
            let buffer = '';

            const checkExisting = () => {
                const fullLog = consoleLogs.join('\n');
                const startIdx = fullLog.indexOf('__BENCHMARK_RESULTS_START__');
                const endIdx = fullLog.indexOf('__BENCHMARK_RESULTS_END__');
                if (startIdx >= 0 && endIdx >= 0) {
                    clearTimeout(timer);
                    const json = fullLog.slice(startIdx + '__BENCHMARK_RESULTS_START__'.length, endIdx).trim();
                    resolve(json);
                    return true;
                }
                return false;
            };

            // Check periodically
            const interval = setInterval(() => {
                if (checkExisting()) clearInterval(interval);
            }, 1000);

            // Also clear interval on timeout
            setTimeout(() => clearInterval(interval), timeoutSec * 1000);
        });

        const results = JSON.parse(resultJSON);

        // Print results table
        console.log('┌─────┬─────────────────────────────────────────────┬──────────────────┬────────┬──────────────────────┬─────────┐');
        console.log('│  #  │ Test                                        │ Piece dims       │ Result │ Counts               │ Time    │');
        console.log('├─────┼─────────────────────────────────────────────┼──────────────────┼────────┼──────────────────────┼─────────┤');
        for (const r of results) {
            const id = String(r.id).padStart(3);
            const name = r.name.substring(0, 43).padEnd(43);
            const dims = (r.dims || '-').substring(0, 16).padEnd(16);
            const result = r.result.padEnd(6);
            const counts = r.counts.substring(0, 20).padEnd(20);
            const ms = `${(r.ms / 1000).toFixed(1)}s`.padStart(7);
            console.log(`│ ${id} │ ${name} │ ${dims} │ ${result} │ ${counts} │ ${ms} │`);
        }
        console.log('└─────┴─────────────────────────────────────────────┴──────────────────┴────────┴──────────────────────┴─────────┘');

        // Summary
        const passed = results.filter(r => r.result === 'PASS').length;
        const failed = results.filter(r => r.result === 'FAIL').length;
        const warned = results.filter(r => r.result === 'WARN').length;
        const errors = results.filter(r => r.result === 'ERROR').length;
        const totalMs = results.reduce((s, r) => s + r.ms, 0);
        console.log(`\n${passed} PASS / ${warned} WARN / ${failed} FAIL / ${errors} ERROR — Total: ${(totalMs / 1000).toFixed(1)}s\n`);

        // Print timing logs
        if (timingLogs.length > 0) {
            console.log('--- Phase Timing ---');
            for (const line of timingLogs) console.log(`  ${line}`);
            console.log('');
        }

        const exitCode = failed + errors > 0 ? 1 : 0;
        await browser.close();
        process.exit(exitCode);

    } catch (err) {
        console.error(`\nBenchmark failed: ${err.message}`);
        await browser.close();
        process.exit(2);
    }
}

main();
