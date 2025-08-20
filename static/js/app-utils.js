/**
 * NDAS Application Utilities
 * Consolidated utility functions for the NDAS project
 */

(function() {
    'use strict';
    
    // Main utility object
    window.NDASUtils = {
        
        /**
         * Safely initialize Chart.js
         * @param {string} canvasId - Canvas element ID
         * @param {Object} config - Chart.js configuration
         * @returns {Promise} Promise resolving to chart instance
         */
        initChart: function(canvasId, config) {
            return new Promise((resolve, reject) => {
                // Check if Chart.js is loaded
                if (typeof Chart === 'undefined') {
                    reject(new Error('Chart.js library not loaded'));
                    return;
                }
                
                // Check if canvas element exists
                const canvas = document.getElementById(canvasId);
                if (!canvas) {
                    reject(new Error(`Canvas element with ID "${canvasId}" not found`));
                    return;
                }
                
                try {
                    const chart = new Chart(canvas, config);
                    resolve(chart);
                } catch (error) {
                    reject(error);
                }
            });
        },
        
        /**
         * Initialize Bootstrap components
         */
        initBootstrap: function() {
            // Initialize tooltips
            $('[data-toggle="tooltip"]').tooltip();
            
            // Initialize popovers
            $('[data-toggle="popover"]').popover();
            
            // Initialize Select2
            $('.select2').select2();
            
            console.log('Bootstrap components initialized');
        },
        
        /**
         * Format phone number
         * @param {HTMLInputElement} input - Phone input element
         */
        formatPhoneNumber: function(input) {
            let value = input.value.replace(/\D/g, '');
            if (value.length > 0) {
                if (value.length <= 3) {
                    value = value;
                } else if (value.length <= 6) {
                    value = value.slice(0, 3) + '-' + value.slice(3);
                } else {
                    value = value.slice(0, 3) + '-' + value.slice(3, 6) + '-' + value.slice(6, 10);
                }
            }
            input.value = value;
        },
        
        /**
         * Show notification message
         * @param {string} message - Message text
         * @param {string} type - Message type (success, error, warning, info)
         * @param {number} duration - Display duration in milliseconds
         */
        showNotification: function(message, type = 'info', duration = 5000) {
            // Create notification element
            const notification = document.createElement('div');
            notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
            notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
            
            notification.innerHTML = `
                ${message}
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            `;
            
            // Add to page
            document.body.appendChild(notification);
            
            // Auto-remove after duration
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, duration);
        },
        
        /**
         * Validate form with Bootstrap validation classes
         * @param {HTMLFormElement} form - Form element to validate
         * @returns {boolean} True if form is valid
         */
        validateForm: function(form) {
            if (!form.checkValidity()) {
                form.classList.add('was-validated');
                return false;
            }
            return true;
        },
        
        /**
         * Setup form validation
         * @param {string} formSelector - CSS selector for forms
         */
        setupFormValidation: function(formSelector = '.needs-validation') {
            const forms = document.querySelectorAll(formSelector);
            
            Array.from(forms).forEach(form => {
                form.addEventListener('submit', event => {
                    if (!this.validateForm(form)) {
                        event.preventDefault();
                        event.stopPropagation();
                    }
                }, false);
            });
        },
        
        /**
         * Debounce function calls
         * @param {Function} func - Function to debounce
         * @param {number} wait - Wait time in milliseconds
         * @returns {Function} Debounced function
         */
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func.apply(this, args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },
        
        /**
         * Check if element is in viewport
         * @param {HTMLElement} element - Element to check
         * @returns {boolean} True if element is visible
         */
        isInViewport: function(element) {
            const rect = element.getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        },
        
        /**
         * Lazy load images
         * @param {string} selector - CSS selector for images to lazy load
         */
        lazyLoadImages: function(selector = 'img[data-src]') {
            const images = document.querySelectorAll(selector);
            
            if ('IntersectionObserver' in window) {
                const imageObserver = new IntersectionObserver((entries, observer) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const img = entry.target;
                            img.src = img.dataset.src;
                            img.classList.remove('lazy');
                            imageObserver.unobserve(img);
                        }
                    });
                });
                
                images.forEach(img => imageObserver.observe(img));
            } else {
                // Fallback for older browsers
                images.forEach(img => {
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                });
            }
        },
        
        /**
         * Get URL parameters
         * @param {string} param - Parameter name
         * @returns {string|null} Parameter value or null
         */
        getUrlParameter: function(param) {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get(param);
        },
        
        /**
         * Set URL parameter without page reload
         * @param {string} param - Parameter name
         * @param {string} value - Parameter value
         */
        setUrlParameter: function(param, value) {
            const url = new URL(window.location);
            url.searchParams.set(param, value);
            window.history.pushState({}, '', url);
        },
        
        /**
         * Initialize all NDAS utilities
         */
        init: function() {
            this.initBootstrap();
            this.setupFormValidation();
            this.lazyLoadImages();
            console.log('NDAS utilities initialized');
        }
    };
    
    // Auto-initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        window.NDASUtils.init();
    });
    
    // Re-initialize Bootstrap components after HTMX content swaps
    if (typeof window.htmx !== 'undefined') {
        document.addEventListener('htmx:afterSwap', function() {
            window.NDASUtils.initBootstrap();
        });
    }
    
})();
