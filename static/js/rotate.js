// Check if videoPlayer element exists before initializing
var videoPlayerElement = document.getElementById('videoPlayer');
var player = null;

// Only initialize if the video element exists and videojs is available
if (videoPlayerElement && typeof videojs !== 'undefined') {
    try {
        player = videojs('videoPlayer');
    } catch (error) {
        console.warn('Video.js player initialization failed:', error);
    }
}

function rotate(player) {
    // Guard clause to ensure player exists
    if (!player) {
        console.warn('Video player not available for rotate functionality');
        return;
    }

	var dimension = 0;

	var rotateLeftButton = createButton('&#8635;');
	var rotateRightButton = createButton('&#8634;');

	rotateLeftButton.onclick = function() {
		dimension += 90;
		dimension %= 360;
		player.zoomrotate({ rotate: dimension });
	};

	rotateRightButton.onclick = function() {
		dimension -= 90;
		if (Math.abs(dimension) == 360) {
			dimension = 0;
		}
		player.zoomrotate({ rotate: dimension });
	};

	var playbackRate = document.querySelector('.vjs-playback-rate');
    if (playbackRate) {
        insertAfter(rotateLeftButton, playbackRate);
        insertAfter(rotateRightButton, rotateLeftButton);
    }

	function createButton(icon) {
		var button = document.createElement('button');
		button.classList.add('vjs-menu-button');
		button.innerHTML = icon;
		button.style.fontSize = '1.8em';
		return button;
	};

	function insertAfter(newEl, element) {
		element.parentNode.insertBefore(newEl, element.nextSibling);
	};
};

// Only register plugin if player exists
if (player && typeof player.registerPlugin === 'function') {
    player.registerPlugin('rotate', rotate);
}