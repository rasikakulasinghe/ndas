// Ensure this script runs after DOM is ready and Video.js is loaded
// This script provides rotate functionality but doesn't initialize players
(function() {
    'use strict';
    
    // Global rotate function that can be called by video player initialization
    window.rotate = function(player) {
        // Guard clause to ensure player exists
        if (!player || typeof player.ready !== 'function') {
            console.warn('Invalid player object passed to rotate function');
            return;
        }

        // Wait for player to be ready before adding rotation controls
        player.ready(function() {
            // Check if zoomrotate plugin is available
            if (typeof player.zoomrotate !== 'function') {
                console.warn('zoomrotate plugin not available for video player');
                return;
            }

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
        });

        function createButton(icon) {
            var button = document.createElement('button');
            button.classList.add('vjs-menu-button');
            button.innerHTML = icon;
            button.style.fontSize = '1.8em';
            return button;
        }

        function insertAfter(newEl, element) {
            element.parentNode.insertBefore(newEl, element.nextSibling);
        }
    };
    
})();
window.rotate = rotate;