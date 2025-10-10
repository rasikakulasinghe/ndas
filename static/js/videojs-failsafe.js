/**
 * Video.js Failsafe Initialization Wrapper
 * Prevents initialization errors with silent fail mode for production
 * Version: 2.0 - Optimized (reduced console logging)
 */

(function() {
    'use strict';

    // Store original videojs function
    var originalVideojs = window.videojs;

    // Override videojs function with safety checks
    window.videojs = function(elementOrId, options, ready) {
        // Safety check: Ensure videojs library is loaded
        if (typeof originalVideojs !== 'function') {
            return null;
        }

        var element;
        var elementId;

        // Handle different input types
        if (typeof elementOrId === 'string') {
            elementId = elementOrId;
            element = document.getElementById(elementId);
        } else if (elementOrId && elementOrId.nodeType === 1) {
            element = elementOrId;
            elementId = element.id || 'unknown';
        } else {
            return null; // Invalid input
        }

        // Ensure element exists and is a video element
        if (!element || element.tagName.toLowerCase() !== 'video') {
            return null;
        }

        // Check if player already initialized
        if (element.player) {
            return element.player;
        }

        try {
            // Call original videojs function
            var player = originalVideojs.call(this, element, options, ready);
            return player;
        } catch (error) {
            // Silent fail in production
            return null;
        }
    };

    // Copy over properties from original videojs
    for (var prop in originalVideojs) {
        if (originalVideojs.hasOwnProperty(prop)) {
            window.videojs[prop] = originalVideojs[prop];
        }
    }

    // Expose original function for debugging
    window.videojs.original = originalVideojs;

})();
