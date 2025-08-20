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
        
        // Check if zoomrotate plugin is available
        if (typeof videojs.getPlugin === 'function') {
            var zoomrotatePlugin = videojs.getPlugin('zoomrotate');
            if (zoomrotatePlugin) {
                console.log('✅ zoomrotate plugin registered successfully');
            } else {
                console.warn('⚠️ zoomrotate plugin not registered');
            }
        } else {
            console.log('ℹ️ videojs.getPlugin method not available (older Video.js version)');
        }
    } else {
        console.error('❌ Video.js not loaded');
    }
    
    // Check for video elements
    const videoElements = document.querySelectorAll('video');
    const videoJsElements = document.querySelectorAll('video.video-js');
    console.log(`Found ${videoElements.length} video elements total, ${videoJsElements.length} with video-js class`);
    
    // Check for canvas elements (for Chart.js)
    const canvasElements = document.querySelectorAll('canvas');
    console.log(`Found ${canvasElements.length} canvas elements:`, canvasElements);
    
    // Check if jQuery is loaded
    if (typeof $ !== 'undefined') {
        console.log('✅ jQuery loaded successfully - Version:', $.fn.jquery);
    } else {
        console.error('❌ jQuery not loaded');
    }
    
    // Check for specific video player elements by ID
    const commonVideoIds = ['videoPlayer', 'video-player', 'mainVideo'];
    commonVideoIds.forEach(function(id) {
        const element = document.getElementById(id);
        if (element) {
            console.log(`✅ Video element found with ID "${id}":`, element);
            
            // Check if player is initialized
            setTimeout(function() {
                if (element.player) {
                    console.log(`✅ Video.js player initialized for "${id}"`);
                } else {
                    console.warn(`⚠️ Video.js player not initialized for "${id}"`);
                }
            }, 1000);
        }
    });
    
    // Check for rotate function
    if (typeof window.rotate === 'function') {
        console.log('✅ Rotate function available');
    } else {
        console.warn('⚠️ Rotate function not available');
    }
    
    // Test Chart.js functionality
    setTimeout(function() {
        if (typeof Chart !== 'undefined') {
            try {
                // Try to create a simple chart test
                const testCanvas = document.createElement('canvas');
                testCanvas.id = 'debugChart';
                testCanvas.style.display = 'none';
                document.body.appendChild(testCanvas);
                
                const testChart = new Chart(testCanvas, {
                    type: 'bar',
                    data: {
                        labels: ['Test'],
                        datasets: [{
                            label: 'Debug Test',
                            data: [1]
                        }]
                    },
                    options: {
                        responsive: false,
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
                
                console.log('✅ Chart.js functionality test passed');
                testChart.destroy();
                document.body.removeChild(testCanvas);
            } catch (chartError) {
                console.error('❌ Chart.js functionality test failed:', chartError);
            }
        }
    }, 1500);
    
    console.log('=== End Debug Info ===');
});
