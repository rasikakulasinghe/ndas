// Main JavaScript file for NDAS application

// Tool Tip initialization
$(function () {
    $('[data-toggle="tooltip"]').tooltip()
});

// VideoJs initialization
$(document).ready(function() {
    // Check if videojs exists and if there's a video player element
    if (typeof videojs !== 'undefined' && document.getElementById('videoPlayer')) {
        try {
            var player = videojs('videoPlayer', {
                controlBar: {
                    'volumePanel': false,
                }
            }); 

            player.muted(true);
            
            // Check if rotate function exists before calling it
            if (player.rotate && typeof player.rotate === 'function') {
                player.rotate(player);
            }
        } catch (error) {
            console.warn('VideoJS initialization failed:', error);
        }
    }
});
