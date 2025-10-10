/**
 * NDAS Main Application JavaScript
 * Consolidated initialization and coordination of all components
 * Version: 2.0 - Optimized and Deduplicated
 */

(function() {
    'use strict';

    // Single centralized initialization manager
    const NDASApp = {
        initialized: false,

        /**
         * Initialize all NDAS application components in correct order
         */
        init: function() {
            if (this.initialized) {
                console.warn('NDASApp already initialized, skipping duplicate initialization');
                return;
            }

            console.log('🚀 Initializing NDAS Application...');

            // Check critical dependencies
            if (!this.checkDependencies()) {
                console.error('❌ Critical dependencies missing, initialization aborted');
                return;
            }

            // Initialize components in dependency order
            this.initBootstrapComponents();
            this.initAdminLTE();
            this.initHTMXIntegration();

            this.initialized = true;
            console.log('✅ NDAS Application initialized successfully');
        },

        /**
         * Check if all required dependencies are loaded
         */
        checkDependencies: function() {
            const deps = {
                'jQuery': typeof $ !== 'undefined',
                'Bootstrap': typeof $.fn !== 'undefined' && typeof $.fn.modal !== 'undefined',
                'AdminLTE': typeof $.AdminLTE !== 'undefined',
                'HTMX': typeof htmx !== 'undefined'
            };

            const missing = Object.entries(deps)
                .filter(([name, loaded]) => !loaded)
                .map(([name]) => name);

            if (missing.length > 0) {
                console.error('❌ Missing dependencies:', missing.join(', '));
                return false;
            }

            console.log('✅ All dependencies loaded');
            return true;
        },

        /**
         * Initialize Bootstrap components (single source of truth)
         */
        initBootstrapComponents: function() {
            try {
                // Initialize tooltips
                if (typeof $.fn.tooltip === 'function') {
                    $('[data-toggle="tooltip"]').tooltip({
                        boundary: 'window',
                        trigger: 'hover'
                    });
                }

                // Initialize popovers
                if (typeof $.fn.popover === 'function') {
                    $('[data-toggle="popover"]').popover();
                }

                // Initialize Select2
                if (typeof $.fn.select2 === 'function') {
                    $('.select2').select2();
                }

                console.log('✅ Bootstrap components initialized');
            } catch (error) {
                console.error('❌ Bootstrap initialization error:', error);
            }
        },

        /**
         * Initialize AdminLTE sidebar navigation
         */
        initAdminLTE: function() {
            try {
                // Standard AdminLTE menu highlighting
                const currentPath = window.location.pathname;

                // Remove existing active states
                $('.nav-sidebar .nav-link').removeClass('active');
                $('.nav-sidebar .nav-item').removeClass('menu-open');

                // Find and highlight active menu item
                $('.nav-sidebar .nav-link[href]').each(function() {
                    const linkHref = $(this).attr('href');

                    if (!linkHref || linkHref === '#') return;

                    // Check for exact match or path contains link
                    if (currentPath === linkHref ||
                        (linkHref !== '/' && currentPath.includes(linkHref))) {

                        $(this).addClass('active');

                        // Open parent menu if submenu item
                        const $parentNavItem = $(this).closest('.nav-treeview').closest('.nav-item');
                        if ($parentNavItem.length) {
                            $parentNavItem.addClass('menu-open');
                            $parentNavItem.find('> .nav-link').addClass('active');
                        }

                        return false;
                    }
                });

                console.log('✅ AdminLTE sidebar initialized');
            } catch (error) {
                console.error('❌ AdminLTE initialization error:', error);
            }
        },

        /**
         * Setup HTMX integration for dynamic content
         */
        initHTMXIntegration: function() {
            if (typeof htmx === 'undefined') return;

            // Re-initialize components after HTMX content swap
            document.addEventListener('htmx:afterSwap', () => {
                this.initBootstrapComponents();

                // Re-highlight sidebar if navigation occurred
                this.initAdminLTE();

                console.log('✅ Components re-initialized after HTMX swap');
            });

            console.log('✅ HTMX integration configured');
        },

        /**
         * Reinitialize components (for dynamic content)
         */
        reinit: function() {
            this.initBootstrapComponents();
        }
    };

    // Expose globally for access from other scripts
    window.NDASApp = NDASApp;

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => NDASApp.init());
    } else {
        // DOM already loaded
        NDASApp.init();
    }

})();
