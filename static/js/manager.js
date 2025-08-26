/**
 * Manager.js - JavaScript functionality for patient manager pages
 * Part of NDAS (Neonatal Development Assessment System)
 */

// Initialize patient manager functionality
document.addEventListener('DOMContentLoaded', function() {
    if (typeof $ === 'undefined') {
        console.error('❌ jQuery not available in patient manager');
        return;
    }
    
    $(document).ready(function() {
        try {
            // jQuery code for patient manager functionality
        
            //////////////////////// Prevent closing from click inside dropdown
            $(document).on('click', '.dropdown-menu', function (e) {
                e.stopPropagation();
            });

            // Enhanced submenu handling for both desktop and mobile
            $('.dropdown-item.dropdown-toggle').on('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                const $submenu = $(this).next('.submenu');
                const $parentDropdown = $(this).closest('.dropdown-menu');
                
                // Close other submenus in the same parent dropdown
                $parentDropdown.find('.submenu').not($submenu).removeClass('show').hide();
                
                // Toggle current submenu
                if ($(window).width() < 992) {
                    // Mobile behavior - simple toggle
                    $submenu.toggle();
                } else {
                    // Desktop behavior - ensure it shows and stays visible
                    if ($submenu.hasClass('show')) {
                        $submenu.removeClass('show').hide();
                    } else {
                        $submenu.addClass('show').show();
                        // Keep it visible even without hover for a moment
                        $submenu.data('clickOpened', true);
                        setTimeout(function() {
                            $submenu.removeData('clickOpened');
                        }, 2000);
                    }
                }
            });

            // Handle submenu positioning on desktop
            $('.dropdown').on('shown.bs.dropdown', function() {
                if ($(window).width() >= 992) {
                    const $dropdown = $(this);
                    const $menu = $dropdown.find('.dropdown-menu');
                    
                    // Position submenus correctly
                    $menu.find('.submenu').each(function() {
                        const $submenu = $(this);
                        const $toggle = $submenu.prev('.dropdown-toggle');
                        
                        if ($toggle.length) {
                            const toggleOffset = $toggle.position();
                            $submenu.css({
                                'position': 'absolute',
                                'left': '100%',
                                'top': toggleOffset.top + 'px'
                            });
                        }
                    });
                }
            });

            // Clean up submenus when main dropdown closes
            $('.dropdown').on('hide.bs.dropdown', function () {
                $(this).find('.submenu').removeClass('show').hide();
            });

            // Handle hover effects on desktop with improved behavior
            if ($(window).width() >= 992) {
                // Improved hover handling for dropdown toggles
                $('.dropdown-item.dropdown-toggle').hover(
                    function() {
                        // Mouse enter
                        const $this = $(this);
                        const $submenu = $this.next('.submenu');
                        const $parentDropdown = $this.closest('.dropdown-menu');
                        
                        // Clear any existing timeouts
                        clearTimeout($submenu.data('hideTimeout'));
                        clearTimeout($this.data('hideTimeout'));
                        
                        // Hide other submenus
                        $parentDropdown.find('.submenu').not($submenu).removeClass('show').hide();
                        
                        // Show current submenu
                        $submenu.addClass('show').show();
                    },
                    function() {
                        // Mouse leave - set a timeout to hide submenu
                        const $this = $(this);
                        const $submenu = $this.next('.submenu');
                        
                        const hideTimeout = setTimeout(function() {
                            // Don't hide if submenu was opened by click and still within timeout
                            if (!$submenu.is(':hover') && !$this.is(':hover') && !$submenu.data('clickOpened')) {
                                $submenu.removeClass('show').hide();
                            }
                        }, 200); // Reduced timeout for better responsiveness
                        
                        $submenu.data('hideTimeout', hideTimeout);
                        $this.data('hideTimeout', hideTimeout);
                    }
                );

                // Improved hover handling for submenus
                $('.submenu').hover(
                    function() {
                        // Mouse enter submenu
                        const $submenu = $(this);
                        const $parentToggle = $submenu.prev('.dropdown-toggle');
                        
                        // Clear timeouts
                        clearTimeout($submenu.data('hideTimeout'));
                        clearTimeout($parentToggle.data('hideTimeout'));
                        
                        // Ensure submenu stays visible
                        $submenu.addClass('show').show();
                    },
                    function() {
                        // Mouse leave submenu
                        const $submenu = $(this);
                        const $parentToggle = $submenu.prev('.dropdown-toggle');
                        
                        const hideTimeout = setTimeout(function() {
                            if (!$submenu.is(':hover') && !$parentToggle.is(':hover') && !$submenu.data('clickOpened')) {
                                $submenu.removeClass('show').hide();
                            }
                        }, 200);
                        
                        $submenu.data('hideTimeout', hideTimeout);
                    }
                );
                
                // Additional safety: handle mouse leave from entire dropdown area
                $('.dropdown-menu').on('mouseleave', function() {
                    const $menu = $(this);
                    setTimeout(function() {
                        if (!$menu.is(':hover')) {
                            $menu.find('.submenu').removeClass('show').hide();
                        }
                    }, 300);
                });
            }
            
            console.log('✅ Patient manager navigation initialized');
        } catch (error) {
            console.error('❌ Patient manager navigation failed:', error);
        }
    }); // jquery end
});
