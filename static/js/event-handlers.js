/**
 * NDAS Event Handlers Module
 * File: static/js/event-handlers.js
 * Part of CSP compliance refactoring
 *
 * Provides centralized event handling for common patterns across NDAS application.
 * Replaces inline event handlers (onclick, onchange, etc.) with data-attribute driven handlers.
 *
 * Handler Types:
 * - Navigation: back, reload, navigate
 * - Pagination: jump-page
 * - Confirmations: data-confirm dialogs
 * - Password Toggle: show/hide password fields
 * - Logout: integrate with logout-modal.js
 * - Error Handling: CDN/image fallbacks
 */
(function() {
    'use strict';

    /**
     * NDASEventHandlers - Singleton module for common event handling patterns
     * @namespace
     */
    window.NDASEventHandlers = {
        /**
         * Initialize all event handlers
         * Called automatically on DOMContentLoaded
         */
        init: function() {
            console.log('NDASEventHandlers: Initializing event handlers');

            this.initNavigationHandlers();
            this.initPaginationHandlers();
            this.initConfirmationHandlers();
            this.initPasswordToggleHandlers();
            this.initLogoutHandlers();
            this.initErrorHandlers();

            console.log('NDASEventHandlers: All handlers initialized successfully');
        },

        /**
         * Navigation Handlers
         * Handles: data-action="back", "reload", "navigate"
         */
        initNavigationHandlers: function() {
            // Event delegation for all navigation actions
            $(document).on('click', '[data-action="back"]', function(e) {
                e.preventDefault();
                console.log('NDASEventHandlers: Navigating back');
                window.history.back();
                return false;
            });

            $(document).on('click', '[data-action="reload"]', function(e) {
                e.preventDefault();
                console.log('NDASEventHandlers: Reloading page');
                window.location.reload();
                return false;
            });

            $(document).on('click', '[data-action="navigate"]', function(e) {
                e.preventDefault();
                var targetUrl = $(this).data('url');

                if (!targetUrl) {
                    console.error('NDASEventHandlers: No URL specified for navigation');
                    return false;
                }

                console.log('NDASEventHandlers: Navigating to:', targetUrl);
                window.location.href = targetUrl;
                return false;
            });
        },

        /**
         * Pagination Handlers
         * Handles: data-action="jump-page" with optional data-search-query
         */
        initPaginationHandlers: function() {
            $(document).on('click', '[data-action="jump-page"]', function(e) {
                e.preventDefault();
                var searchQuery = $(this).data('search-query') || '';
                NDASEventHandlers.jumpToPage(searchQuery);
                return false;
            });
        },

        /**
         * Universal jump-to-page implementation
         * @param {string} searchQuery - Optional search query to preserve in URL
         */
        jumpToPage: function(searchQuery) {
            var pageInput = document.getElementById('jumpToPageInput');

            if (!pageInput) {
                console.error('NDASEventHandlers: Page input field not found');
                return;
            }

            var page = parseInt(pageInput.value, 10);

            if (isNaN(page) || page < 1) {
                alert('Please enter a valid page number');
                return;
            }

            var currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('page', page);

            // Preserve search query if provided
            if (searchQuery) {
                currentUrl.searchParams.set('q', searchQuery);
            }

            console.log('NDASEventHandlers: Jumping to page:', page);
            window.location.href = currentUrl.toString();
        },

        /**
         * Confirmation Handlers
         * Handles: data-confirm="message" on buttons/links/forms
         */
        initConfirmationHandlers: function() {
            // Handle confirmations on buttons and links
            $(document).on('click', '[data-confirm]', function(e) {
                var confirmMessage = $(this).data('confirm');

                if (!confirmMessage) {
                    return true; // No message, allow default
                }

                if (!confirm(confirmMessage)) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('NDASEventHandlers: User cancelled confirmation');
                    return false;
                }

                console.log('NDASEventHandlers: User confirmed action');
                return true;
            });

            // Handle confirmations on form submissions
            $(document).on('submit', 'form[data-confirm]', function(e) {
                var confirmMessage = $(this).data('confirm');

                if (!confirmMessage) {
                    return true;
                }

                if (!confirm(confirmMessage)) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('NDASEventHandlers: User cancelled form submission');
                    return false;
                }

                console.log('NDASEventHandlers: User confirmed form submission');
                return true;
            });
        },

        /**
         * Password Toggle Handlers
         * Handles: data-action="toggle-password" with data-target="field-id"
         */
        initPasswordToggleHandlers: function() {
            $(document).on('click', '[data-action="toggle-password"]', function(e) {
                e.preventDefault();

                var targetFieldId = $(this).data('target');

                if (!targetFieldId) {
                    console.error('NDASEventHandlers: No target field specified for password toggle');
                    return false;
                }

                var targetField = $('#' + targetFieldId);

                if (targetField.length === 0) {
                    console.error('NDASEventHandlers: Target field not found:', targetFieldId);
                    return false;
                }

                // Toggle input type
                var currentType = targetField.attr('type');
                var newType = currentType === 'password' ? 'text' : 'password';
                targetField.attr('type', newType);

                // Toggle icon
                var icon = $(this).find('i');
                if (icon.length > 0) {
                    if (newType === 'text') {
                        icon.removeClass('fa-eye').addClass('fa-eye-slash');
                    } else {
                        icon.removeClass('fa-eye-slash').addClass('fa-eye');
                    }
                }

                console.log('NDASEventHandlers: Toggled password visibility for:', targetFieldId);
                return false;
            });
        },

        /**
         * Logout Handlers
         * Integrates with existing logout-modal.js
         * Handles: data-action="logout"
         */
        initLogoutHandlers: function() {
            $(document).on('click', '[data-action="logout"]', function(e) {
                e.preventDefault();

                // Use existing logout confirmation modal if available
                if (typeof window.showLogoutConfirmation === 'function') {
                    console.log('NDASEventHandlers: Showing logout confirmation modal');
                    window.showLogoutConfirmation();
                } else {
                    // Fallback to confirm dialog
                    console.warn('NDASEventHandlers: Logout modal not available, using fallback');
                    if (confirm('Are you sure you want to logout?')) {
                        window.location.href = '/users/logout/';
                    }
                }

                return false;
            });
        },

        /**
         * Error Handlers for CDN Fallbacks and Image Loading
         * Handles: data-fallback-url on <link> and <img> tags
         */
        initErrorHandlers: function() {
            // CDN CSS fallback handler
            $(document).on('error', 'link[rel="stylesheet"][data-fallback-url]', function() {
                var link = $(this);
                var fallbackUrl = link.data('fallback-url');

                if (!fallbackUrl) {
                    console.error('NDASEventHandlers: No fallback URL specified for CSS');
                    return;
                }

                // Prevent infinite loop
                if (link.data('fallback-attempted')) {
                    console.error('NDASEventHandlers: CDN fallback failed, both primary and fallback URLs unavailable');
                    return;
                }

                console.warn('NDASEventHandlers: Primary CDN failed, switching to fallback:', fallbackUrl);
                link.data('fallback-attempted', true);
                link.attr('href', fallbackUrl);
            });

            // Image fallback handler
            $(document).on('error', 'img[data-fallback-html]', function() {
                var img = $(this);
                var fallbackHtml = img.data('fallback-html');

                if (!fallbackHtml) {
                    console.error('NDASEventHandlers: No fallback HTML specified for image');
                    return;
                }

                // Prevent infinite loop
                if (img.data('fallback-attempted')) {
                    return;
                }

                console.warn('NDASEventHandlers: Image load failed, using fallback HTML');
                img.data('fallback-attempted', true);

                // Hide image and insert fallback HTML
                img.hide();
                img.parent().html(fallbackHtml);
            });

            // Image fallback with alternative URL
            $(document).on('error', 'img[data-fallback-url]', function() {
                var img = $(this);
                var fallbackUrl = img.data('fallback-url');

                if (!fallbackUrl) {
                    console.error('NDASEventHandlers: No fallback URL specified for image');
                    return;
                }

                // Prevent infinite loop
                if (img.data('fallback-attempted')) {
                    console.error('NDASEventHandlers: Image fallback failed');
                    return;
                }

                console.warn('NDASEventHandlers: Image load failed, using fallback:', fallbackUrl);
                img.data('fallback-attempted', true);
                img.attr('src', fallbackUrl);
            });
        },

        /**
         * Utility: Re-initialize handlers after dynamic content load
         * Useful for HTMX swaps or dynamically loaded content
         */
        reinit: function() {
            console.log('NDASEventHandlers: Re-initializing handlers for dynamic content');
            // Event delegation handles this automatically, but this method
            // is available for future expansion if needed
        }
    };

    /**
     * Initialize when DOM is ready
     */
    function initEventHandlers() {
        // Check for jQuery
        if (typeof $ === 'undefined') {
            console.error('NDASEventHandlers: jQuery not loaded, retrying...');
            setTimeout(initEventHandlers, 100);
            return;
        }

        // Initialize handlers
        window.NDASEventHandlers.init();

        // Integrate with HTMX if available
        if (typeof htmx !== 'undefined') {
            document.body.addEventListener('htmx:afterSwap', function() {
                console.log('NDASEventHandlers: HTMX swap detected, handlers remain active via delegation');
            });
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEventHandlers);
    } else {
        initEventHandlers();
    }

})();
