// Ensure this script runs after DOM is ready and Video.js is loaded
// This script provides rotate functionality but doesn't initialize players
(function() {
    'use strict';
    
    // Wait for DOM and Video.js to be ready before defining the rotate function
    function defineRotateFunction() {
        // Global rotate function that can be called by video player initialization
        window.rotate = function(player) {
            // Guard clause to ensure player exists and is valid
            if (!player) {
                console.warn('No player object passed to rotate function');
                return;
            }
            
            if (typeof player !== 'object') {
                console.warn('Invalid player object type passed to rotate function:', typeof player);
                return;
            }
            
            if (typeof player.ready !== 'function') {
                console.warn('Player object does not have ready method, skipping rotate functionality');
                return;
            }

            // Wait for player to be ready before adding rotation controls
            player.ready(function() {
                try {
                    // Check if zoomrotate plugin is available
                    if (typeof player.zoomrotate !== 'function') {
                        console.log('zoomrotate plugin not available for this video player, skipping rotate controls');
                        return;
                    }

                    console.log('✅ zoomrotate plugin available, adding rotate controls');
                    var dimension = 0;

                    var rotateLeftButton = createButton('&#8635;');
                    var rotateRightButton = createButton('&#8634;');

                    rotateLeftButton.onclick = function() {
                        dimension += 90;
                        dimension %= 360;
                        try {
                            player.zoomrotate({ rotate: dimension });
                        } catch (error) {
                            console.warn('Rotate left failed:', error);
                        }
                    };

                    rotateRightButton.onclick = function() {
                        dimension -= 90;
                        if (Math.abs(dimension) == 360) {
                            dimension = 0;
                        }
                        try {
                            player.zoomrotate({ rotate: dimension });
                        } catch (error) {
                            console.warn('Rotate right failed:', error);
                        }
                    };

                    // Add buttons to the control bar
                    var playbackRate = document.querySelector('.vjs-playback-rate');
                    if (playbackRate) {
                        insertAfter(rotateLeftButton, playbackRate);
                        insertAfter(rotateRightButton, rotateLeftButton);
                    } else {
                        // Fallback: add to control bar if playback rate button not found
                        var controlBar = document.querySelector('.vjs-control-bar');
                        if (controlBar) {
                            controlBar.appendChild(rotateLeftButton);
                            controlBar.appendChild(rotateRightButton);
                        }
                    }
                } catch (error) {
                    console.warn('Failed to add rotate functionality to player:', error);
                }
            });

            function createButton(icon) {
                var button = document.createElement('button');
                button.classList.add('vjs-menu-button');
                button.innerHTML = icon;
                button.style.fontSize = '1.8em';
                return button;
            }

            function insertAfter(newEl, element) {
                if (element && element.parentNode) {
                    element.parentNode.insertBefore(newEl, element.nextSibling);
                }
            }
        };
    }
    
    // Define the function immediately or wait for Video.js
    if (typeof videojs !== 'undefined') {
        defineRotateFunction();
    } else {
        // Wait for Video.js to load
        document.addEventListener('DOMContentLoaded', function() {
            if (typeof videojs !== 'undefined') {
                defineRotateFunction();
            } else {
                console.log('Video.js not available, rotate functionality will not be available');
            }
        });
    }
    
})();