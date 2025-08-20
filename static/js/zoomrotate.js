console.log('zoomrotate: Start');

(function(){
    // Check if videojs is available
    if (typeof videojs === 'undefined') {
        console.warn('zoomrotate: Video.js not available, skipping plugin registration');
        return;
    }

    // Wait a moment for Video.js to be fully loaded
    function registerZoomRotatePlugin() {
        var defaults, extend;
        console.log('zoomrotate: Init defaults');
        defaults = {
          zoom: 1,
          rotate: 0,
          debug: true
        };
        extend = function() {
          var args, target, i, object, property;
          args = Array.prototype.slice.call(arguments);
          target = args.shift() || {};
          for (i in args) {
            object = args[i];
            for (property in object) {
              if (object.hasOwnProperty(property)) {
                if (typeof object[property] === 'object') {
                  target[property] = extend(target[property], object[property]);
                } else {
                  target[property] = object[property];
                }
              }
            }
          }
          return target;
        };

      /**
        * register the zoomrotate plugin - compatible with both old and new Video.js APIs
        */
        var pluginFunction = function(settings){
            if (defaults.debug) console.log('zoomrotate: Register init');

            var options, player, video, poster;
            options = extend(defaults, settings);

            /* Grab the necessary DOM elements */
            player = this.el();
            video = this.el().getElementsByTagName('video')[0];
            poster = this.el().getElementsByTagName('div')[1]; // div vjs-poster

            if (!video) {
                console.warn('zoomrotate: No video element found');
                return;
            }

            if (options.debug) console.log('zoomrotate: '+video.style);
            if (options.debug) console.log('zoomrotate: '+poster.style);
            if (options.debug) console.log('zoomrotate: '+options.rotate);
            if (options.debug) console.log('zoomrotate: '+options.zoom);

        /* Array of possible browser specific settings for transformation */
        var properties = ['transform', 'WebkitTransform', 'MozTransform',
                          'msTransform', 'OTransform'],
            prop = properties[0];

        /* Iterators */
        var i,j;

        /* Find out which CSS transform the browser supports */
        for(i=0,j=properties.length;i<j;i++){
          if(typeof player.style[properties[i]] !== 'undefined'){
            prop = properties[i];
            break;
          }
        }

        /* Let's do it */
        player.style.overflow = 'hidden';
        video.style[prop]='scale('+options.zoom+') rotate('+options.rotate+'deg)';
        poster.style[prop]='scale('+options.zoom+') rotate('+options.rotate+'deg)';
        if (options.debug) console.log('zoomrotate: Register end');
        };

        // Try new API first (Video.js 7+), then fall back to old API
        if (typeof videojs.registerPlugin === 'function') {
            console.log('zoomrotate: Using new registerPlugin API');
            videojs.registerPlugin('zoomrotate', pluginFunction);
        } else if (typeof videojs.plugin === 'function') {
            console.log('zoomrotate: Using legacy plugin API');
            videojs.plugin('zoomrotate', pluginFunction);
        } else {
            console.warn('zoomrotate: Neither registerPlugin nor plugin function available on videojs object');
            console.log('zoomrotate: Available videojs methods:', Object.keys(videojs));
        }
    }

    // Register immediately if videojs is ready, otherwise wait
    if (videojs && (typeof videojs.registerPlugin === 'function' || typeof videojs.plugin === 'function')) {
        registerZoomRotatePlugin();
    } else {
        // Wait for Video.js to be fully loaded
        var attempts = 0;
        var maxAttempts = 50; // Wait up to 5 seconds
        var checkInterval = setInterval(function() {
            attempts++;
            if (videojs && (typeof videojs.registerPlugin === 'function' || typeof videojs.plugin === 'function')) {
                clearInterval(checkInterval);
                registerZoomRotatePlugin();
            } else if (attempts >= maxAttempts) {
                clearInterval(checkInterval);
                console.error('zoomrotate: Timeout waiting for Video.js to be ready');
            }
        }, 100);
    }
})();

console.log('zoomrotate: End');

console.log('zoomrotate: End');