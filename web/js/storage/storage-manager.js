/**
 * PackAssist Web - Storage Manager
 * Handles IndexedDB operations for persisting STL files and calculation history
 */

export class StorageManager {
    constructor() {
        this.dbName = 'PackAssistDB';
        this.dbVersion = 2; // Incremented for new store
        this.stlStoreName = 'stlFiles';
        this.historyStoreName = 'calculationHistory';
        this.db = null;
    }

    /**
     * Initialize the database
     */
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // STL Files store
                if (!db.objectStoreNames.contains(this.stlStoreName)) {
                    const store = db.createObjectStore(this.stlStoreName, { keyPath: 'id', autoIncrement: true });
                    store.createIndex('lastUsed', 'lastUsed', { unique: false });
                    store.createIndex('name', 'name', { unique: false });
                }
                
                // Calculation History store
                if (!db.objectStoreNames.contains(this.historyStoreName)) {
                    const historyStore = db.createObjectStore(this.historyStoreName, { keyPath: 'id', autoIncrement: true });
                    historyStore.createIndex('timestamp', 'timestamp', { unique: false });
                    historyStore.createIndex('mode', 'mode', { unique: false });
                }
            };

            request.onsuccess = (event) => {
                this.db = event.target.result;
                resolve(this.db);
            };

            request.onerror = (event) => {
                reject(new Error(`Database error: ${event.target.error}`));
            };
        });
    }

    /**
     * Save a file and its metadata
     * @param {string} name 
     * @param {ArrayBuffer} data 
     * @param {Object} dimensions {length, width, height}
     * @param {number} weight 
     * @returns {Promise<number>} ID of the saved file
     */
    async saveFile(name, data, dimensions, weight) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.stlStoreName], 'readwrite');
            const store = transaction.objectStore(this.stlStoreName);

            const item = {
                name,
                data, // Binary STL data
                dimensions,
                weight,
                lastUsed: Date.now()
            };

            const request = store.add(item);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(new Error(`Error saving file: ${request.error}`));
        });
    }

    /**
     * Update the lastUsed timestamp for a file
     * @param {number} id 
     */
    async updateLastUsed(id) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.stlStoreName], 'readwrite');
            const store = transaction.objectStore(this.stlStoreName);

            const getRequest = store.get(id);

            getRequest.onsuccess = () => {
                const data = getRequest.result;
                if (data) {
                    data.lastUsed = Date.now();
                    store.put(data);
                    resolve();
                } else {
                    reject(new Error('File not found'));
                }
            };

            getRequest.onerror = () => reject(new Error(`Error searching file: ${getRequest.error}`));
        });
    }

    /**
     * Get the most recently used files list (metadata only)
     * @param {number} limit 
     * @returns {Promise<Array>}
     */
    async getRecentFiles(limit = 10) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.stlStoreName], 'readonly');
            const store = transaction.objectStore(this.stlStoreName);
            const index = store.index('lastUsed');
            
            const results = [];
            const request = index.openCursor(null, 'prev'); // Most recent first

            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor && results.length < limit) {
                    // Don't include the large 'data' field in this list
                    const { data, ...metadata } = cursor.value;
                    results.push(metadata);
                    cursor.continue();
                } else {
                    resolve(results);
                }
            };

            request.onerror = () => reject(new Error(`Error listing files: ${request.error}`));
        });
    }

    /**
     * Get all files for export
     */
    async getAllFiles() {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.stlStoreName], 'readonly');
            const store = transaction.objectStore(this.stlStoreName);
            const request = store.getAll();

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(new Error(`Error getting all files: ${request.error}`));
        });
    }

    /**
     * Get file data by ID
     * @param {number} id 
     * @returns {Promise<Object>}
     */
    async getFile(id) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.stlStoreName], 'readonly');
            const store = transaction.objectStore(this.stlStoreName);
            const request = store.get(id);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(new Error(`Error getting file: ${request.error}`));
        });
    }

    /**
     * Delete a file from storage
     * @param {number} id 
     */
    async deleteFile(id) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.stlStoreName], 'readwrite');
            const store = transaction.objectStore(this.stlStoreName);
            const request = store.delete(id);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(new Error(`Error deleting file: ${request.error}`));
        });
    }

    /**
     * Update a file in storage (replace all fields)
     * @param {number} id 
     * @param {Object} fileData - Updated file data
     */
    async updateFile(id, fileData) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.stlStoreName], 'readwrite');
            const store = transaction.objectStore(this.stlStoreName);
            
            // Ensure id is preserved
            fileData.id = id;
            
            const request = store.put(fileData);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(new Error(`Error updating file: ${request.error}`));
        });
    }

    // ============================================
    // CALCULATION HISTORY METHODS
    // ============================================

    /**
     * Save a calculation to history
     * @param {Object} calculation - Calculation data
     * @returns {Promise<number>} ID of the saved calculation
     */
    async saveCalculation(calculation) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.historyStoreName], 'readwrite');
            const store = transaction.objectStore(this.historyStoreName);

            const item = {
                ...calculation,
                timestamp: Date.now()
            };

            const request = store.add(item);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(new Error(`Error saving calculation: ${request.error}`));
        });
    }

    /**
     * Get calculation history, most recent first
     * @param {number} limit - Max number of results
     * @returns {Promise<Array>}
     */
    async getCalculationHistory(limit = 50) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.historyStoreName], 'readonly');
            const store = transaction.objectStore(this.historyStoreName);
            const index = store.index('timestamp');
            
            const results = [];
            const request = index.openCursor(null, 'prev'); // Most recent first

            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor && results.length < limit) {
                    results.push(cursor.value);
                    cursor.continue();
                } else {
                    resolve(results);
                }
            };

            request.onerror = () => reject(new Error(`Error listing history: ${request.error}`));
        });
    }

    /**
     * Delete a calculation from history
     * @param {number} id 
     */
    async deleteCalculation(id) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.historyStoreName], 'readwrite');
            const store = transaction.objectStore(this.historyStoreName);
            const request = store.delete(id);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(new Error(`Error deleting calculation: ${request.error}`));
        });
    }

    /**
     * Clear all calculation history
     */
    async clearHistory() {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.historyStoreName], 'readwrite');
            const store = transaction.objectStore(this.historyStoreName);
            const request = store.clear();

            request.onsuccess = () => resolve();
            request.onerror = () => reject(new Error(`Error clearing history: ${request.error}`));
        });
    }
}
