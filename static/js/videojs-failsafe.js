// Failsafe Video.js initialization wrapper
// This script prevents the "element or ID supplied is not valid" error

(function() {
    'use strict';
    
    // Store original videojs function
    var originalVideojs = window.videojs;
    
    // Override videojs function with safety checks
    window.videojs = function(elementOrId, options, ready) {
        // Safety check 1: Ensure videojs library is actually loaded
        if (typeof originalVideojs !== 'function') {
            console.error('[NDAS Failsafe] Video.js library not loaded');
            return null;
        }
        
        var element;
        var elementId;
        
        // Safety check 2: Handle different input types
        if (typeof elementOrId === 'string') {
            elementId = elementOrId;
            element = document.getElementById(elementId);
        } else if (elementOrId && elementOrId.nodeType === 1) {
            element = elementOrId;
            elementId = element.id || 'unknown';
        } else {
            console.error('[NDAS Failsafe] Invalid element or ID supplied to videojs:', elementOrId);
            return null;
        }
        
        // Safety check 3: Ensure element exists
        if (!element) {
            console.warn('[NDAS Failsafe] Element with ID "' + elementId + '" not found. Skipping video initialization.');
            return null;
        }
        
        // Safety check 4: Ensure element is a video element
        if (element.tagName.toLowerCase() !== 'video') {
            console.error('[NDAS Failsafe] Element "' + elementId + '" is not a video element, it is:', element.tagName);
            return null;
        }
        
        // Safety check 5: Check if player is already initialized
        if (element.player) {
            console.log('[NDAS Failsafe] Player already initialized for element:', elementId);
            return element.player;
        }
        
        try {
            // Call original videojs function with safety checks passed
            console.log('[NDAS Failsafe] Initializing video player for:', elementId);
            var player = originalVideojs.call(this, element, options, ready);
            
            if (player) {
                console.log('[NDAS Failsafe] Successfully initialized player for:', elementId);
            }
            
            return player;
        } catch (error) {
            console.error('[NDAS Failsafe] Failed to initialize video player for "' + elementId + '":', error);
            return null;
        }
    };
    
    // Copy over any properties from the original videojs
    for (var prop in originalVideojs) {
        if (originalVideojs.hasOwnProperty(prop)) {
            window.videojs[prop] = originalVideojs[prop];
        }
    }
    
    // Expose original function for debugging
    window.videojs.original = originalVideojs;
    
    console.log('[NDAS Failsafe] Video.js failsafe wrapper initialized');
    
})();
