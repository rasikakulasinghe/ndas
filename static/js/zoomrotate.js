/**
 * Video.js Zoom Rotate Plugin
 * Optimized version with reduced console logging
 */

(function(){
    'use strict';

    // Check if videojs is available
    if (typeof videojs === 'undefined') {
        return; // Silent fail if Video.js not available
    }

    // Register the zoomrotate plugin
    function registerZoomRotatePlugin() {
        if (typeof videojs === 'undefined' || !videojs) {
            return;
        }

        var defaults, extend;
        defaults = {
          zoom: 1,
          rotate: 0,
          debug: false // Set to false for production
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
        try {
            if (videojs && typeof videojs.registerPlugin === 'function') {
                videojs.registerPlugin('zoomrotate', pluginFunction);
            } else if (videojs && typeof videojs.plugin === 'function') {
                videojs.plugin('zoomrotate', pluginFunction);
            }
        } catch (error) {
            // Silent fail - plugin registration failed
        }
    }

    // Register immediately if videojs is ready, otherwise wait
    if (typeof videojs !== 'undefined' && videojs && (typeof videojs.registerPlugin === 'function' || typeof videojs.plugin === 'function')) {
        registerZoomRotatePlugin();
    } else {
        // Wait for Video.js to be fully loaded (silent retry)
        var attempts = 0;
        var maxAttempts = 50; // Wait up to 5 seconds
        var checkInterval = setInterval(function() {
            attempts++;
            if (typeof videojs !== 'undefined' && videojs && (typeof videojs.registerPlugin === 'function' || typeof videojs.plugin === 'function')) {
                clearInterval(checkInterval);
                registerZoomRotatePlugin();
            } else if (attempts >= maxAttempts) {
                clearInterval(checkInterval);
                // Silent timeout - plugin not registered
            }
        }, 100);
    }
})();