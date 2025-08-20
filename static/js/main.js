// Main JavaScript file for NDAS application

// Tool Tip initialization
$(function () {
    $('[data-toggle="tooltip"]').tooltip()
});

// Prevent duplicate Video.js initialization - this is handled in the base template
// This file only contains fallback initialization if base template fails
$(document).ready(function() {
    // Only initialize if not already done by base template
    var videoElement = document.getElementById('videoPlayer');
    if (videoElement && typeof videojs !== 'undefined' && !videoElement.player) {
        // Small delay to ensure base template script has run
        setTimeout(function() {
            if (!videoElement.player) {
                try {
                    console.log('Fallback Video.js initialization from main.js');
                    var player = videojs('videoPlayer', {
                        controlBar: {
                            'volumePanel': false,
                        },
                        fluid: true,
                        responsive: true
                    }); 

                    player.muted(true);
                    
                    // Check if rotate function exists before calling it
                    if (typeof window.rotate === 'function') {
                        player.ready(function() {
                            window.rotate(player);
                        });
                    }
                } catch (error) {
                    console.warn('Fallback VideoJS initialization in main.js failed:', error);
                }
            }
        }, 100);
    }
});
