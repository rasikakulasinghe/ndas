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
                    // Mobile behavior
                    $submenu.toggle();
                } else {
                    // Desktop behavior
                    $submenu.toggleClass('show');
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

            // Handle hover effects on desktop
            if ($(window).width() >= 992) {
                $('.dropdown-item.dropdown-toggle').hover(
                    function() {
                        // Mouse enter
                        const $submenu = $(this).next('.submenu');
                        clearTimeout($submenu.data('hideTimeout'));
                        $submenu.addClass('show');
                    },
                    function() {
                        // Mouse leave
                        const $submenu = $(this).next('.submenu');
                        const hideTimeout = setTimeout(function() {
                            $submenu.removeClass('show');
                        }, 300);
                        $submenu.data('hideTimeout', hideTimeout);
                    }
                );

                $('.submenu').hover(
                    function() {
                        // Mouse enter submenu
                        clearTimeout($(this).data('hideTimeout'));
                    },
                    function() {
                        // Mouse leave submenu
                        const $submenu = $(this);
                        const hideTimeout = setTimeout(function() {
                            $submenu.removeClass('show');
                        }, 300);
                        $submenu.data('hideTimeout', hideTimeout);
                    }
                );
            }
            
            console.log('✅ Patient manager navigation initialized');
        } catch (error) {
            console.error('❌ Patient manager navigation failed:', error);
        }
    }); // jquery end
});
