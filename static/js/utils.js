// JavaScript utilities for NDAS project
// Prevents common loading and initialization errors

(function() {
    'use strict';
    
    // Global utility object
    window.NDASUtils = {
        
        // Safely initialize Chart.js
        initChart: function(canvasId, config) {
            return new Promise(function(resolve, reject) {
                // Check if Chart.js is loaded
                if (typeof Chart === 'undefined') {
                    reject(new Error('Chart.js library not loaded'));
                    return;
                }
                
                // Check if canvas element exists
                var canvas = document.getElementById(canvasId);
                if (!canvas) {
                    reject(new Error('Canvas element with ID "' + canvasId + '" not found'));
                    return;
                }
                
                try {
                    var chart = new Chart(canvas, config);
                    resolve(chart);
                } catch (error) {
                    reject(error);
                }
            });
        },
        
        // Safely initialize Video.js
        initVideoPlayer: function(elementId, options) {
            return new Promise(function(resolve, reject) {
                // Check if Video.js is loaded
                if (typeof videojs === 'undefined') {
                    reject(new Error('Video.js library not loaded'));
                    return;
                }
                
                // Check if video element exists
                var videoElement = document.getElementById(elementId);
                if (!videoElement) {
                    reject(new Error('Video element with ID "' + elementId + '" not found'));
                    return;
                }
                
                // Check if player is already initialized
                if (videoElement.player) {
                    resolve(videoElement.player);
                    return;
                }
                
                try {
                    var player = videojs(elementId, options || {});
                    player.ready(function() {
                        resolve(player);
                    });
                } catch (error) {
                    reject(error);
                }
            });
        },
        
        // Wait for DOM and libraries to be ready
        ready: function(callback) {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', callback);
            } else {
                callback();
            }
        },
        
        // Load script dynamically with fallback
        loadScript: function(src, fallbackSrc) {
            return new Promise(function(resolve, reject) {
                var script = document.createElement('script');
                script.src = src;
                
                script.onload = function() {
                    resolve(script);
                };
                
                script.onerror = function() {
                    if (fallbackSrc) {
                        // Try fallback URL
                        var fallbackScript = document.createElement('script');
                        fallbackScript.src = fallbackSrc;
                        
                        fallbackScript.onload = function() {
                            resolve(fallbackScript);
                        };
                        
                        fallbackScript.onerror = function() {
                            reject(new Error('Failed to load script: ' + src + ' and fallback: ' + fallbackSrc));
                        };
                        
                        document.head.appendChild(fallbackScript);
                    } else {
                        reject(new Error('Failed to load script: ' + src));
                    }
                };
                
                document.head.appendChild(script);
            });
        },
        
        // Check if all required libraries are loaded
        checkLibraries: function() {
            var libraries = {
                'jQuery': typeof $ !== 'undefined',
                'Chart.js': typeof Chart !== 'undefined',
                'Video.js': typeof videojs !== 'undefined'
            };
            
            var missing = [];
            for (var lib in libraries) {
                if (!libraries[lib]) {
                    missing.push(lib);
                }
            }
            
            return {
                allLoaded: missing.length === 0,
                loaded: libraries,
                missing: missing
            };
        },
        
        // Safe console logging
        log: function(message, type) {
            if (typeof console !== 'undefined') {
                var logType = type || 'log';
                if (console[logType]) {
                    console[logType]('[NDAS]', message);
                }
            }
        }
    };
    
    // Auto-check libraries when script loads
    NDASUtils.ready(function() {
        var check = NDASUtils.checkLibraries();
        if (check.allLoaded) {
            NDASUtils.log('All required libraries loaded successfully', 'info');
        } else {
            NDASUtils.log('Missing libraries: ' + check.missing.join(', '), 'warn');
        }
    });
    
})();
