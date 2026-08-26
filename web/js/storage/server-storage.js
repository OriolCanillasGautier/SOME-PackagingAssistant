
/**
 * PackAssist Web - Server Storage
 * Handles server-side persistence via custom Python server API
 */

export class ServerStorage {
    constructor() {
        // Resolve from the page origin (was hardcoded to http://localhost:80,
        // which breaks from any other device). Not currently wired into the
        // app (storage-manager uses IndexedDB) but kept device-independent.
        this.apiBase = (typeof window !== 'undefined' && window.location && window.location.origin)
            ? window.location.origin
            : 'http://localhost:80';
        this.basePath = this.apiBase + '/library/';
    }

    /**
     * Initialize (Placeholder for interface compatibility)
     */
    async init() {
        return Promise.resolve();
    }

    /**
     * Save a file (Upload to server)
     * @param {string} name 
     * @param {ArrayBuffer} data 
     * @param {Object} dimensions 
     * @param {number} weight 
     */
    async saveFile(name, data, dimensions, weight) {
        const formData = new FormData();
        const blob = new Blob([data], { type: 'application/octet-stream' });
        
        // Ensure name is safe
        formData.append('file', blob, name);
        formData.append('dimensions', `${dimensions.length},${dimensions.width},${dimensions.height}`);
        formData.append('weight', weight.toString());

        try {
            const response = await fetch(`${this.apiBase}/api/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error(`Upload failed: ${response.statusText}`);
            
            const result = await response.json();
            return result.id;
        } catch (error) {
            console.error('Server upload error:', error);
            throw error;
        }
    }

    /**
     * Get recent files (Fetch from library CSV api)
     */
    async getRecentFiles(limit = 100) {
        try {
            const response = await fetch(`${this.apiBase}/api/library`);
            if (!response.ok) throw new Error('Failed to fetch library');
            
            const files = await response.json();
            
            // Map to expected format
            return files.map(f => {
                const [l, w, h] = f.Dimensions.split(',').map(Number);
                return {
                    id: f.Filename, // Use filename as ID for loading
                    dbId: f.ID,
                    name: f.Name,
                    weight: parseFloat(f.Weight),
                    dimensions: { length: l, width: w, height: h },
                    date: f.Date
                };
            }).slice(0, limit);
            
        } catch (error) {
            console.warn('Server library fetch error:', error);
            return [];
        }
    }

    /**
     * Get file data by ID (Filename)
     * Since the server doesn't directly serve library files, we need to handle this differently
     * For now, we'll return the metadata from the library list
     */
    async getFile(id) {
        try {
            // Fetch the library to find the file metadata
            const allFiles = await this.getAllFiles();
            const file = allFiles.find(f => f.dbId === id || f.name === id);

            if (!file) {
                throw new Error('File not found');
            }

            // Fetch the actual file content from the server
            // The server serves files from the web directory, so library files are at /library/filename.stl
            const response = await fetch(`${this.apiBase}/library/${file.name}`);
            if (!response.ok) {
                throw new Error(`Failed to download file: ${response.statusText}`);
            }

            const buffer = await response.arrayBuffer();
            return {
                data: buffer,
                name: file.name,
                dimensions: file.dimensions,
                weight: file.weight
            };
        } catch (error) {
            console.error('Download error:', error);
            throw error;
        }
    }
    
    /**
     * Update last used (No-op for server CSV currently)
     */
    async updateLastUsed(id) {
        // Implement server API for this if needed later
        return Promise.resolve();
    }

    /**
     * Delete file (Not implemented in basic server yet)
     */
    async deleteFile(id) {
        try {
            const response = await fetch(`${this.apiBase}/api/delete?id=${id}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Delete failed');
            return;
        } catch (error) {
            console.error('Delete error:', error);
            throw error;
        }
    }
    
    async getAllFiles() {
        // Re-use getRecentFiles as it returns everything from CSV
        return this.getRecentFiles(1000);
    }
}
