/**
 * PackAssist Web - History Page
 * Displays and manages calculation history
 */

import { StorageManager } from './storage/storage-manager.js';

// State
const state = {
    storage: null,
    history: [],
    filteredHistory: [],
    selectedItem: null
};

// DOM Elements
const elements = {
    historyStats: document.getElementById('history-stats'),
    historyBody: document.getElementById('history-body'),
    historyTable: document.getElementById('history-table'),
    historyEmpty: document.getElementById('history-empty'),
    filterMode: document.getElementById('filter-mode'),
    filterDate: document.getElementById('filter-date'),
    filterSearch: document.getElementById('filter-search'),
    exportBtn: document.getElementById('export-btn'),
    clearBtn: document.getElementById('clear-btn'),
    // Modal
    detailModal: document.getElementById('detail-modal'),
    modalBody: document.getElementById('modal-body'),
    modalClose: document.getElementById('modal-close'),
    modalCancel: document.getElementById('modal-cancel'),
    modalLoad: document.getElementById('modal-load')
};

/**
 * Initialize the history page
 */
async function init() {
    // Initialize storage
    state.storage = new StorageManager();
    await state.storage.init();
    
    // Load history
    await loadHistory();
    
    // Setup event listeners
    setupEventListeners();
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Filters
    elements.filterMode?.addEventListener('change', applyFilters);
    elements.filterDate?.addEventListener('change', applyFilters);
    elements.filterSearch?.addEventListener('input', debounce(applyFilters, 300));
    
    // Actions
    elements.exportBtn?.addEventListener('click', exportToCSV);
    elements.clearBtn?.addEventListener('click', confirmClearHistory);
    
    // Modal
    elements.modalClose?.addEventListener('click', closeModal);
    elements.modalCancel?.addEventListener('click', closeModal);
    elements.modalLoad?.addEventListener('click', loadSelectedData);
    elements.detailModal?.addEventListener('click', (e) => {
        if (e.target === elements.detailModal) closeModal();
    });
}

/**
 * Load calculation history
 */
async function loadHistory() {
    try {
        state.history = await state.storage.getCalculationHistory(100);
        applyFilters();
        updateStats();
    } catch (error) {
        console.error('Error loading history:', error);
        showError('Error carregant l\'historial');
    }
}

/**
 * Apply filters to history
 */
function applyFilters() {
    const modeFilter = elements.filterMode?.value || 'all';
    const dateFilter = elements.filterDate?.value || 'all';
    const searchFilter = (elements.filterSearch?.value || '').toLowerCase();
    
    const now = Date.now();
    const dayMs = 24 * 60 * 60 * 1000;
    
    state.filteredHistory = state.history.filter(item => {
        // Mode filter
        if (modeFilter !== 'all' && item.mode !== modeFilter) return false;
        
        // Date filter
        if (dateFilter !== 'all') {
            const age = now - item.timestamp;
            if (dateFilter === 'today' && age > dayMs) return false;
            if (dateFilter === 'week' && age > 7 * dayMs) return false;
            if (dateFilter === 'month' && age > 30 * dayMs) return false;
        }
        
        // Search filter (STL name)
        if (searchFilter && item.stlFileName) {
            if (!item.stlFileName.toLowerCase().includes(searchFilter)) return false;
        } else if (searchFilter && !item.stlFileName) {
            return false;
        }
        
        return true;
    });
    
    renderTable();
}

/**
 * Render the history table
 */
function renderTable() {
    if (state.filteredHistory.length === 0) {
        elements.historyTable.style.display = 'none';
        elements.historyEmpty.style.display = 'block';
        return;
    }
    
    elements.historyTable.style.display = 'table';
    elements.historyEmpty.style.display = 'none';
    
    elements.historyBody.innerHTML = state.filteredHistory.map(item => {
        const date = new Date(item.timestamp);
        const dateStr = date.toLocaleDateString('ca-ES', { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const modeClass = item.mode === 'optimized' ? 'optimized' : 'bulk';
        const modeIcon = item.mode === 'optimized' ? '🎯' : '🌊';
        const modeName = item.mode === 'optimized' ? 'Optimitzat' : 'A Granel';
        
        const pieceDims = item.pieceDims ? 
            `${item.pieceDims.l?.toFixed(1) || '?'}×${item.pieceDims.w?.toFixed(1) || '?'}×${item.pieceDims.h?.toFixed(1) || '?'}` : 
            '-';
        
        const boxDims = item.boxDims ?
            `${item.boxDims.length?.toFixed(0) || '?'}×${item.boxDims.width?.toFixed(0) || '?'}×${item.boxDims.height?.toFixed(0) || '?'}` :
            '-';
        
        const weight = item.pieceWeight ? `${item.pieceWeight} kg/u` : '-';
        const stlName = item.stlFileName ? 
            `<span class="stl-name" title="${item.stlFileName}">${item.stlFileName}</span>` : 
            '<span class="no-stl">—</span>';
        
        return `
            <tr data-id="${item.id}">
                <td>${dateStr}</td>
                <td><span class="mode-badge ${modeClass}">${modeIcon} ${modeName}</span></td>
                <td class="dims-text">${pieceDims}</td>
                <td class="dims-text">${boxDims}</td>
                <td class="piece-count">${item.pieceCount || '-'}</td>
                <td class="weight-text">${weight}</td>
                <td>${stlName}</td>
                <td>
                    <div class="action-btns">
                        <button class="action-btn view" data-id="${item.id}" title="Veure detalls">👁️</button>
                        <button class="action-btn delete" data-id="${item.id}" title="Eliminar">🗑️</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    
    // Add event listeners to action buttons
    elements.historyBody.querySelectorAll('.action-btn.view').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const id = parseInt(e.target.dataset.id);
            showDetailModal(id);
        });
    });
    
    elements.historyBody.querySelectorAll('.action-btn.delete').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = parseInt(e.target.dataset.id);
            await deleteItem(id);
        });
    });
    
    // Row click to view details
    elements.historyBody.querySelectorAll('tr').forEach(row => {
        row.addEventListener('click', (e) => {
            if (!e.target.closest('.action-btn')) {
                const id = parseInt(row.dataset.id);
                showDetailModal(id);
            }
        });
    });
}

/**
 * Update statistics
 */
function updateStats() {
    const total = state.history.length;
    const optimized = state.history.filter(h => h.mode === 'optimized').length;
    const bulk = state.history.filter(h => h.mode === 'bulk').length;
    
    elements.historyStats.innerHTML = `
        <span class="stat">📊 Total: <span class="stat-value">${total}</span></span>
        <span class="stat">🎯 Optimitzat: <span class="stat-value">${optimized}</span></span>
        <span class="stat">🌊 A Granel: <span class="stat-value">${bulk}</span></span>
    `;
}

/**
 * Show detail modal
 */
function showDetailModal(id) {
    const item = state.history.find(h => h.id === id);
    if (!item) return;
    
    state.selectedItem = item;
    
    const date = new Date(item.timestamp);
    const dateStr = date.toLocaleDateString('ca-ES', { 
        weekday: 'long',
        day: 'numeric', 
        month: 'long', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
    
    const modeIcon = item.mode === 'optimized' ? '🎯' : '🌊';
    const modeName = item.mode === 'optimized' ? 'Mode Optimitzat' : 'Mode a Granel';
    
    elements.modalBody.innerHTML = `
        <div class="detail-header">
            <p style="color: var(--text-muted); margin-bottom: 20px;">📅 ${dateStr}</p>
        </div>
        
        <div class="detail-grid">
            <div class="detail-section">
                <h3>📏 Dimensions de la Peça</h3>
                <div class="detail-row">
                    <span class="detail-label">Llargada</span>
                    <span class="detail-value">${item.pieceDims?.l?.toFixed(2) || '-'} mm</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Amplada</span>
                    <span class="detail-value">${item.pieceDims?.w?.toFixed(2) || '-'} mm</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Alçada</span>
                    <span class="detail-value">${item.pieceDims?.h?.toFixed(2) || '-'} mm</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Pes</span>
                    <span class="detail-value">${item.pieceWeight || '-'} kg</span>
                </div>
            </div>
            
            <div class="detail-section">
                <h3>📦 Dimensions de la Caixa</h3>
                <div class="detail-row">
                    <span class="detail-label">Llargada</span>
                    <span class="detail-value">${item.boxDims?.length?.toFixed(0) || '-'} mm</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Amplada</span>
                    <span class="detail-value">${item.boxDims?.width?.toFixed(0) || '-'} mm</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Alçada</span>
                    <span class="detail-value">${item.boxDims?.height?.toFixed(0) || '-'} mm</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Pes màxim</span>
                    <span class="detail-value">${item.maxWeight || '-'} kg</span>
                </div>
            </div>
            
            <div class="detail-section">
                <h3>📊 Resultat</h3>
                <div class="detail-row">
                    <span class="detail-label">Mode</span>
                    <span class="detail-value">${modeIcon} ${modeName}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Peces</span>
                    <span class="detail-value" style="color: var(--accent-green); font-size: 1.2rem;">${item.pieceCount || '-'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Factor seguretat</span>
                    <span class="detail-value">${item.safetyFactor ? (item.safetyFactor * 100).toFixed(0) + '%' : '-'}</span>
                </div>
            </div>
            
            <div class="detail-section">
                <h3>📁 Fitxer STL</h3>
                <div class="detail-row">
                    <span class="detail-label">Nom</span>
                    <span class="detail-value">${item.stlFileName || 'Cap STL associat'}</span>
                </div>
            </div>
        </div>
    `;
    
    elements.detailModal.style.display = 'flex';
}

/**
 * Close modal
 */
function closeModal() {
    elements.detailModal.style.display = 'none';
    state.selectedItem = null;
}

/**
 * Load selected data into calculator
 */
function loadSelectedData() {
    if (!state.selectedItem) return;
    
    const item = state.selectedItem;
    
    // Build URL with query parameters
    const params = new URLSearchParams({
        objL: item.pieceDims?.l || '',
        objW: item.pieceDims?.w || '',
        objH: item.pieceDims?.h || '',
        objWeight: item.pieceWeight || '',
        boxL: item.boxDims?.length || '',
        boxW: item.boxDims?.width || '',
        boxH: item.boxDims?.height || '',
        maxWeight: item.maxWeight || '',
        mode: item.mode || 'optimized'
    });
    
    // Redirect to calculator with pre-filled data
    window.location.href = `index.html?${params.toString()}`;
}

/**
 * Delete item
 */
async function deleteItem(id) {
    if (!confirm('Segur que vols eliminar aquest càlcul de l\'historial?')) return;
    
    try {
        await state.storage.deleteCalculation(id);
        await loadHistory();
    } catch (error) {
        console.error('Error deleting item:', error);
        alert('Error eliminant el càlcul');
    }
}

/**
 * Export to CSV
 */
function exportToCSV() {
    if (state.filteredHistory.length === 0) {
        alert('No hi ha dades per exportar');
        return;
    }
    
    const headers = [
        'Data',
        'Mode',
        'Peça Llargada (mm)',
        'Peça Amplada (mm)',
        'Peça Alçada (mm)',
        'Pes Peça (kg)',
        'Caixa Llargada (mm)',
        'Caixa Amplada (mm)',
        'Caixa Alçada (mm)',
        'Pes Màxim (kg)',
        'Peces',
        'Factor Seguretat',
        'STL'
    ];
    
    const rows = state.filteredHistory.map(item => {
        const date = new Date(item.timestamp).toISOString();
        return [
            date,
            item.mode,
            item.pieceDims?.l || '',
            item.pieceDims?.w || '',
            item.pieceDims?.h || '',
            item.pieceWeight || '',
            item.boxDims?.length || '',
            item.boxDims?.width || '',
            item.boxDims?.height || '',
            item.maxWeight || '',
            item.pieceCount || '',
            item.safetyFactor || '',
            item.stlFileName || ''
        ].map(v => `"${v}"`).join(',');
    });
    
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `packassist_historial_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    
    URL.revokeObjectURL(url);
}

/**
 * Confirm clear history
 */
async function confirmClearHistory() {
    if (!confirm('⚠️ Segur que vols esborrar TOT l\'historial?\n\nAquesta acció no es pot desfer.')) return;
    if (!confirm('🔴 ÚLTIMA OPORTUNITAT: S\'esborraran tots els càlculs. Continuar?')) return;
    
    try {
        await state.storage.clearHistory();
        await loadHistory();
    } catch (error) {
        console.error('Error clearing history:', error);
        alert('Error esborrant l\'historial');
    }
}

/**
 * Show error message
 */
function showError(message) {
    elements.historyBody.innerHTML = `
        <tr>
            <td colspan="8" class="loading-cell" style="color: var(--accent-red);">
                ❌ ${message}
            </td>
        </tr>
    `;
}

/**
 * Debounce helper
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', init);
