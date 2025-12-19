
/**
 * PackAssist Web - Server Storage
 * Handles server-side persistence via custom Python server API
 */

export class ServerStorage {
    constructor() {
        this.basePath = '/library/';
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
            const response = await fetch('/api/upload', {
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
            const response = await fetch('/api/library');
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
     */
    async getFile(filename) {
        try {
            const response = await fetch(`${this.basePath}${filename}`);
            if (!response.ok) throw new Error('File not found on server');
            
            const buffer = await response.arrayBuffer();
            
            // Retrieve metadata from list (optional, might need caching if critical)
            // For now, return basic structure with data
            return {
                data: buffer,
                name: filename
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
        console.warn('Delete not implemented on server yet');
        return Promise.resolve();
    }
    
    async getAllFiles() {
        // Re-use getRecentFiles as it returns everything from CSV
        return this.getRecentFiles(1000);
    }
}
