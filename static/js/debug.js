// Debug script to identify JavaScript loading issues
document.addEventListener('DOMContentLoaded', function() {
    console.log('=== NDAS JavaScript Debug Info ===');
    
    // Check if Chart.js is available
    if (typeof Chart !== 'undefined') {
        console.log('✅ Chart.js loaded successfully - Version:', Chart.version);
    } else {
        console.error('❌ Chart.js not loaded');
    }
    
    // Check if Video.js is available
    if (typeof videojs !== 'undefined') {
        console.log('✅ Video.js loaded successfully - Version:', videojs.VERSION);
    } else {
        console.error('❌ Video.js not loaded');
    }
    
    // Check for video elements
    const videoElements = document.querySelectorAll('video');
    console.log(`Found ${videoElements.length} video elements:`, videoElements);
    
    // Check for canvas elements (for Chart.js)
    const canvasElements = document.querySelectorAll('canvas');
    console.log(`Found ${canvasElements.length} canvas elements:`, canvasElements);
    
    // Check if jQuery is loaded
    if (typeof $ !== 'undefined') {
        console.log('✅ jQuery loaded successfully - Version:', $.fn.jquery);
    } else {
        console.error('❌ jQuery not loaded');
    }
    
    // Check for specific video player
    const videoPlayer = document.getElementById('videoPlayer');
    if (videoPlayer) {
        console.log('✅ Video player element found:', videoPlayer);
        
        // Check if player is initialized
        setTimeout(function() {
            if (videoPlayer.player) {
                console.log('✅ Video.js player initialized successfully');
            } else {
                console.warn('⚠️ Video.js player not initialized');
            }
        }, 1000);
    } else {
        console.log('ℹ️ No video player element on this page');
    }
    
    // Check for rotate function
    if (typeof window.rotate === 'function') {
        console.log('✅ Rotate function available');
    } else {
        console.warn('⚠️ Rotate function not available');
    }
    
    console.log('=== End Debug Info ===');
});
