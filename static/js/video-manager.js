/**
 * NDAS Video Manager - Consolidated Video.js Management
 * Replaces multiple video-related scripts with unified approach
 */

(function() {
    'use strict';
    
    // Video Manager Configuration
    const VideoManager = {
        defaultOptions: {
            controlBar: {
                'volumePanel': false,
            },
            fluid: true,
            responsive: true,
            muted: true
        },
        
        initialized: new Set(),
        players: new Map(),
        
        /**
         * Initialize Video.js with error handling and plugins
         * @param {string} elementId - Video element ID
         * @param {Object} options - Video.js options
         * @returns {Promise} Promise resolving to player instance
         */
        init: function(elementId, options = {}) {
            return new Promise((resolve, reject) => {
                // Check if Video.js is loaded
                if (typeof videojs === 'undefined') {
                    reject(new Error('Video.js library not loaded'));
                    return;
                }
                
                // Check if already initialized
                if (this.initialized.has(elementId)) {
                    const existingPlayer = this.players.get(elementId);
                    if (existingPlayer) {
                        resolve(existingPlayer);
                        return;
                    }
                }
                
                // Check if video element exists
                const videoElement = document.getElementById(elementId);
                if (!videoElement) {
                    reject(new Error(`Video element with ID "${elementId}" not found`));
                    return;
                }
                
                // Merge options with defaults
                const mergedOptions = { ...this.defaultOptions, ...options };
                
                try {
                    // Initialize video player
                    const player = videojs(elementId, mergedOptions);
                    
                    // Set as initialized
                    this.initialized.add(elementId);
                    this.players.set(elementId, player);
                    
                    // Apply default settings
                    player.muted(true);
                    
                    // Load plugins when ready
                    player.ready(() => {
                        this.loadPlugins(player, elementId);
                        resolve(player);
                    });
                    
                    // Handle player errors
                    player.on('error', () => {
                        const error = player.error();
                        console.warn(`Video.js player error for ${elementId}:`, error);
                    });
                    
                } catch (error) {
                    reject(new Error(`Video.js player initialization failed for ${elementId}: ${error.message}`));
                }
            });
        },
        
        /**
         * Load video plugins (rotate, zoom, etc.)
         * @param {Object} player - Video.js player instance
         * @param {string} elementId - Video element ID
         */
        loadPlugins: function(player, elementId) {
            // Load rotate functionality if available
            if (typeof window.rotate === 'function') {
                try {
                    window.rotate(player);
                    console.log(`Rotate functionality loaded for: ${elementId}`);
                } catch (error) {
                    console.warn(`Failed to load rotate functionality for ${elementId}:`, error);
                }
            }
            
            // Load zoom/rotate plugin if available
            if (typeof window.zoomRotate === 'function') {
                try {
                    window.zoomRotate(player);
                    console.log(`Zoom/rotate plugin loaded for: ${elementId}`);
                } catch (error) {
                    console.warn(`Failed to load zoom/rotate plugin for ${elementId}:`, error);
                }
            }
        },
        
        /**
         * Auto-initialize all video elements on page
         */
        autoInit: function() {
            const videoElements = document.querySelectorAll('video.video-js');
            
            if (videoElements.length === 0) {
                console.log('No video elements found on this page');
                return;
            }
            
            videoElements.forEach(videoElement => {
                if (!videoElement.id) {
                    console.warn('Video element missing ID, skipping initialization');
                    return;
                }
                
                this.init(videoElement.id).catch(error => {
                    console.error(`Auto-initialization failed for ${videoElement.id}:`, error);
                });
            });
        },
        
        /**
         * Get player instance by element ID
         * @param {string} elementId - Video element ID
         * @returns {Object|null} Video.js player instance or null
         */
        getPlayer: function(elementId) {
            return this.players.get(elementId) || null;
        },
        
        /**
         * Dispose of player and cleanup
         * @param {string} elementId - Video element ID
         */
        dispose: function(elementId) {
            const player = this.players.get(elementId);
            if (player) {
                try {
                    player.dispose();
                    this.players.delete(elementId);
                    this.initialized.delete(elementId);
                    console.log(`Player disposed: ${elementId}`);
                } catch (error) {
                    console.error(`Error disposing player ${elementId}:`, error);
                }
            }
        }
    };
    
    // Expose VideoManager globally
    window.NDASVideoManager = VideoManager;
    
    // Auto-initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        // Small delay to ensure all scripts are loaded
        setTimeout(() => {
            VideoManager.autoInit();
        }, 100);
    });
    
    // Re-initialize after HTMX content swaps
    if (typeof window.htmx !== 'undefined') {
        document.addEventListener('htmx:afterSwap', function() {
            setTimeout(() => {
                VideoManager.autoInit();
            }, 100);
        });
    }
    
})();
