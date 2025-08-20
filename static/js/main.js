// Main JavaScript file for NDAS application

// Ensure jQuery is loaded before running any jQuery code
if (typeof $ === 'undefined') {
    console.error('❌ jQuery not available in main.js');
} else {
    // Tool Tip initialization
    $(function () {
        $('[data-toggle="tooltip"]').tooltip()
    });
}

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
                    
                    // Check if rotate function exists and player is ready before calling it
                    if (typeof window.rotate === 'function') {
                        player.ready(function() {
                            try {
                                window.rotate(player);
                                console.log('Rotate functionality added to fallback player');
                            } catch (rotateError) {
                                console.warn('Failed to add rotate functionality:', rotateError);
                            }
                        });
                    }
                } catch (error) {
                    console.warn('Fallback VideoJS initialization in main.js failed:', error);
                }
            }
        }, 100);
    }
});
