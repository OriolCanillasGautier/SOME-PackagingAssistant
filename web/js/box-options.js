/**
 * box-options.js — Ranked Box Options + Cost per Part ("Comparar caixes")
 *
 * Packs the current STL into MULTIPLE box sizes (4 presets + the user's custom
 * box) via the backend /api/boxes endpoint, then ranks them by cost per part.
 *
 * Flow: button click → cost config modal → POST /api/boxes → poll job →
 * render a ranking table (best first, best highlighted).
 */

import { t as localeText } from './i18n.js?v=force_update_43';

const BOX_PRESETS = [
    [160, 160, 160],
    [200, 200, 200],
    [300, 200, 200],
    [385, 285, 150],
];

const CONTAINER_ID = 'box-options-container';
const BUTTON_ID = 'compare-boxes-btn';
const COST_MODAL_ID = 'box-cost-modal';

function appState() {
    return (typeof window !== 'undefined' && window.PackAssist) ? window.PackAssist.state : null;
}

function text(path, fallback) {
    const st = appState();
    if (st && st.locale) {
        return localeText(st.locale, `main.${path}`, {}, fallback);
    }
    return fallback;
}

function textV(path, fallback, variables) {
    const st = appState();
    if (st && st.locale) {
        return localeText(st.locale, `main.${path}`, variables, fallback);
    }
    return fallback;
}

function container() {
    return document.getElementById(CONTAINER_ID);
}

function currency() {
    return text('boxOptions.currency', '€');
}

function fmt(n, digits = 2) {
    if (n == null || !isFinite(n)) return '—';
    return n.toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
    });
}

/**
 * The button is only relevant for Planar ('fast') and Optimitzat ('gpu') modes.
 * Reads state.mode directly because the Optimitzat variant is reached via the
 * Bulk button (active class stays on data-mode="bulk") while state.mode is 'gpu'.
 */
function updateButtonVisibility() {
    const btn = document.getElementById(BUTTON_ID);
    if (!btn) return;
    const st = appState();
    const mode = st ? st.mode : 'fast';
    btn.style.display = (mode === 'fast' || mode === 'gpu') ? 'flex' : 'none';
}

function setupVisibilityWatcher() {
    const targets = document.querySelectorAll('.mode-btn, .variant-btn');
    // Deferred so it runs AFTER main.js's switchMode listener has updated state.mode.
    targets.forEach(b => b.addEventListener('click', () => setTimeout(updateButtonVisibility, 0)));
    // Class toggles catch programmatic switches too (state.mode changes come with
    // active-class mutations on the mode/variant buttons).
    if (typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver(updateButtonVisibility);
        targets.forEach(b => observer.observe(b, { attributes: true, attributeFilter: ['class'] }));
    }
}

function buildBoxList() {
    const list = BOX_PRESETS.map(([l, w, h]) => [l, w, h]);
    const read = (id) => parseFloat(document.getElementById(id)?.value) || 0;
    const custom = [read('box-length'), read('box-width'), read('box-height')];
    if (custom.every(v => v > 0)) {
        const dup = list.some(([l, w, h]) =>
            Math.abs(l - custom[0]) < 0.5 && Math.abs(w - custom[1]) < 0.5 && Math.abs(h - custom[2]) < 0.5);
        if (!dup) list.push(custom);
    }
    return list;
}

function renderMessage(html) {
    const el = container();
    if (!el) return;
    el.innerHTML = `<div class="box-options-panel box-options-msg">${html}</div>`;
}

function renderError(message) {
    renderMessage(`<p class="error-text">${text('boxOptions.error', 'Error comparing boxes')}: ${message}</p>`);
}

function renderBoxOptionsLoading(current, total) {
    const el = container();
    if (!el) return;
    const label = total > 0
        ? textV('boxOptions.loadingProgress', 'Comparing boxes ({current}/{total})...', { current, total })
        : text('boxOptions.loading', 'Comparing boxes...');
    el.innerHTML = `
        <div class="box-options-panel box-options-loading">
            <div class="box-options-spinner"></div>
            <span>${label}</span>
        </div>`;
}

function renderBoxOptionsResults(job) {
    const el = container();
    if (!el) return;
    const boxes = Array.isArray(job.boxes) ? job.boxes : [];
    const cfg = job.cost_config || {};
    const cur = currency();

    if (!boxes.length) {
        renderMessage(`<p class="placeholder-text">${text('boxOptions.noFit', 'No part fits')}</p>`);
        return;
    }

    const head = `
        <thead>
            <tr>
                <th>${text('boxOptions.colBox', 'Box')}</th>
                <th>${text('boxOptions.colPieces', 'Pieces')}</th>
                <th>${text('boxOptions.colFill', 'Fill %')}</th>
                <th>${text('boxOptions.colWeight', 'Total weight')}</th>
                <th>${text('boxOptions.colCostPart', 'Cost per part')}</th>
                <th>${text('boxOptions.colTotalCost', 'Total cost')}</th>
            </tr>
        </thead>`;

    let bestMarked = false;
    const rows = boxes.map(b => {
        if (b.skipped) {
            const reason = b.reason === 'too_small'
                ? text('boxOptions.tooSmall', 'Too small for the part')
                : text('boxOptions.noFit', 'No part fits');
            return `<tr class="skipped">
                <td class="box-name">${fmt(b.box_l, 0)}×${fmt(b.box_w, 0)}×${fmt(b.box_h, 0)} mm</td>
                <td colspan="5" class="box-skip-reason">${reason}</td>
            </tr>`;
        }
        const isBest = !bestMarked;
        if (isBest) bestMarked = true;
        return `<tr${isBest ? ' class="best"' : ''}>
            <td class="box-name">${fmt(b.box_l, 0)}×${fmt(b.box_w, 0)}×${fmt(b.box_h, 0)} mm</td>
            <td class="box-pieces" data-pieces="${b.pieces}">${b.pieces}</td>
            <td class="box-fill">${fmt(b.fill_pct, 1)}%</td>
            <td class="box-weight" data-weight="${b.weight_kg}">${fmt(b.weight_kg, 2)} kg</td>
            <td class="box-cost-part" data-cost="${b.cost_per_part}">${cur} ${fmt(b.cost_per_part, 4)}</td>
            <td class="box-total-cost" data-total="${b.total_cost}">${cur} ${fmt(b.total_cost, 2)}</td>
        </tr>`;
    });

    const costLine = [];
    if (cfg.box_cost != null) costLine.push(`${text('boxOptions.configBox', 'box')} ${cur}${fmt(cfg.box_cost, 2)}`);
    if (cfg.packaging_cost != null) costLine.push(`${text('boxOptions.configPackaging', 'packaging')} ${cur}${fmt(cfg.packaging_cost, 2)}`);
    if (cfg.freight_per_kg) costLine.push(`${text('boxOptions.configFreightKg', 'freight')} ${cur}${fmt(cfg.freight_per_kg, 2)}/kg`);
    if (cfg.freight_per_m3) costLine.push(`${text('boxOptions.configFreightKg', 'freight')} ${cur}${fmt(cfg.freight_per_m3, 2)}/m³`);
    const method = cfg.method || 'sparrow';

    el.innerHTML = `
        <div class="box-options-panel">
            <h3 class="box-options-title">${text('boxOptions.rankingTitle', 'Box ranking by cost per part')}</h3>
            <div class="box-options-table-wrap">
                <table class="box-options-table">
                    ${head}
                    <tbody>${rows.join('')}</tbody>
                </table>
            </div>
            <div class="box-options-meta">
                ${text('boxOptions.subtitle', 'Pack the part into several box sizes and rank them by cost per part.')}
                <span class="box-options-config">${method} · ${costLine.join(' · ')}</span>
            </div>
        </div>`;
}

function closeCostModal() {
    const modal = document.getElementById(COST_MODAL_ID);
    if (modal) modal.remove();
}

function showCostModal() {
    const st = appState();
    closeCostModal();
    const cfg = st?.costConfig || {};
    const modal = document.createElement('div');
    modal.id = COST_MODAL_ID;
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content box-cost-modal">
            <div class="modal-header">
                <h2>${text('boxOptions.title', 'Compare boxes')}</h2>
                <button type="button" class="modal-close" data-close aria-label="Close">×</button>
            </div>
            <div class="modal-body">
                <p class="modal-subtitle">${text('boxOptions.subtitle', 'Pack the part into several box sizes and rank them by cost per part.')}</p>
                <div class="input-group">
                    <label for="box-cost-input">${text('boxOptions.boxCost', 'Box cost (€/box)')}</label>
                    <input type="number" id="box-cost-input" min="0" step="0.01" value="${cfg.boxCost ?? 0.5}">
                </div>
                <div class="input-group">
                    <label for="packaging-cost-input">${text('boxOptions.packagingCost', 'Packaging cost (€/box, dunnage/tape)')}</label>
                    <input type="number" id="packaging-cost-input" min="0" step="0.01" value="${cfg.packagingCost ?? 0.15}">
                </div>
                <div class="input-group">
                    <label for="freight-kg-input">${text('boxOptions.freightPerKg', 'Freight per kg (€/kg)')}</label>
                    <input type="number" id="freight-kg-input" min="0" step="0.01" value="${cfg.freightPerKg ?? 0.8}">
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-secondary" data-close>${text('boxOptions.cancel', 'Cancel')}</button>
                <button type="button" class="btn-primary" data-run>${text('boxOptions.run', 'Compare')}</button>
            </div>
        </div>`;
    document.body.appendChild(modal);
    modal.style.display = 'flex';

    modal.querySelector('[data-run]').addEventListener('click', () => {
        const costConfig = {
            boxCost: parseFloat(modal.querySelector('#box-cost-input').value) || 0,
            packagingCost: parseFloat(modal.querySelector('#packaging-cost-input').value) || 0,
            freightPerKg: parseFloat(modal.querySelector('#freight-kg-input').value) || 0,
        };
        if (st) st.costConfig = costConfig;
        closeCostModal();
        runComparison(costConfig);
    });
    modal.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeCostModal));
    modal.addEventListener('click', (e) => { if (e.target === modal) closeCostModal(); });
}

async function runComparison(costConfig) {
    const st = appState();
    if (!st) return;
    if (!st.stlFileData) {
        renderMessage(`<p class="error-text">${text('boxOptions.needStl', 'Load an STL before comparing boxes')}</p>`);
        return;
    }

    const boxList = buildBoxList();
    const method = document.getElementById('gpu-method')?.value || 'sparrow';
    const pieceWeight = parseFloat(document.getElementById('obj-weight')?.value) || 0;

    renderBoxOptionsLoading(0, boxList.length);

    const formData = new FormData();
    formData.append('stl', new Blob([st.stlFileData], { type: 'application/octet-stream' }), st.stlFileName || 'piece.stl');
    formData.append('boxes', JSON.stringify(boxList.map(([l, w, h]) => ({ l, w, h }))));
    formData.append('method', method);
    formData.append('cell', '2.0');
    formData.append('piece_weight', String(pieceWeight));
    formData.append('box_cost', String(costConfig.boxCost));
    formData.append('packaging_cost', String(costConfig.packagingCost));
    formData.append('freight_per_kg', String(costConfig.freightPerKg));

    let resp;
    try {
        resp = await fetch('/api/boxes', { method: 'POST', body: formData, signal: AbortSignal.timeout(15000) });
    } catch (err) {
        renderError(err.message);
        return;
    }
    if (!resp.ok) {
        let msg = `HTTP ${resp.status}`;
        try { const d = await resp.json(); if (d.error) msg = d.error; } catch (_) { /* ignore */ }
        renderError(msg);
        return;
    }

    let submitData;
    try {
        submitData = await resp.json();
    } catch (err) {
        renderError(err.message);
        return;
    }
    await pollBoxJob(submitData.job_id);
}

async function pollBoxJob(jobId) {
    const started = Date.now();
    const MAX_WAIT = 10 * 60 * 1000; // mirror the server watchdog
    for (;;) {
        let job;
        try {
            const r = await fetch(`/api/boxes/${jobId}`, { signal: AbortSignal.timeout(10000) });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            job = await r.json();
        } catch (err) {
            renderError(err.message);
            return;
        }

        if (job.status === 'done') {
            renderBoxOptionsResults(job);
            return;
        }
        if (job.status === 'error') {
            renderError(job.error || text('boxOptions.error', 'Error comparing boxes'));
            return;
        }
        if (Date.now() - started > MAX_WAIT) {
            renderMessage(`<p class="error-text">${text('boxOptions.timeout', 'Timed out while comparing boxes')}</p>`);
            return;
        }

        const progress = job.progress || {};
        renderBoxOptionsLoading(progress.current || 0, progress.total || 0);
        await new Promise(r => setTimeout(r, 2500));
    }
}

function setupButton() {
    const btn = document.getElementById(BUTTON_ID);
    if (!btn) return;
    btn.addEventListener('click', () => {
        const st = appState();
        if (!st || !st.stlFileData) {
            renderMessage(`<p class="error-text">${text('boxOptions.needStl', 'Load an STL before comparing boxes')}</p>`);
            return;
        }
        showCostModal();
    });
}

export function initBoxOptions() {
    document.addEventListener('DOMContentLoaded', () => {
        setupButton();
        setupVisibilityWatcher();
        updateButtonVisibility();
    });
}

// Expose for debugging / Puppeteer tests
if (typeof window !== 'undefined') {
    window.CompareBoxes = { runComparison, renderBoxOptionsResults };
}
