// Sidebar Menu Accordion Functionality
// This script ensures only one menu group is open at a time

$(document).ready(function() {
    console.log('🔧 Initializing sidebar accordion menu...');
    
    // Function to close all menu items except the target
    function closeOtherMenuItems(targetItem) {
        $('.nav-sidebar .nav-item').each(function() {
            const $item = $(this);
            if ($item[0] !== targetItem[0] && $item.hasClass('menu-open')) {
                $item.removeClass('menu-open').addClass('menu-close');
                $item.find('.nav-treeview').slideUp(300);
                $item.find('.nav-link .fas.fa-angle-left').removeClass('rotate-270');
            }
        });
    }
    
    // Function to toggle menu item
    function toggleMenuItem($item) {
        const $treeview = $item.find('.nav-treeview');
        const $arrow = $item.find('.nav-link .fas.fa-angle-left');
        
        if ($item.hasClass('menu-open')) {
            // Close this menu
            $item.removeClass('menu-open').addClass('menu-close');
            $treeview.slideUp(300);
            $arrow.removeClass('rotate-270');
        } else {
            // Close other menus first
            closeOtherMenuItems($item);
            
            // Open this menu
            $item.removeClass('menu-close').addClass('menu-open');
            $treeview.slideDown(300);
            $arrow.addClass('rotate-270');
        }
    }
    
    // Handle click events on menu items with submenus
    $('.nav-sidebar .nav-item').each(function() {
        const $item = $(this);
        const $link = $item.find('> .nav-link');
        const $treeview = $item.find('.nav-treeview');
        
        // Only add click handler if item has a treeview (submenu)
        if ($treeview.length > 0) {
            $link.on('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                console.log('📝 Menu item clicked:', $item.find('p').first().text().trim());
                toggleMenuItem($item);
                
                return false;
            });
        }
    });
    
    // Initialize menu state - close all except the first one by default
    $('.nav-sidebar .nav-item').each(function(index) {
        const $item = $(this);
        const $treeview = $item.find('.nav-treeview');
        const $arrow = $item.find('.nav-link .fas.fa-angle-left');
        
        if ($treeview.length > 0) {
            if (index === 0) {
                // Keep first menu open
                $item.removeClass('menu-close').addClass('menu-open');
                $treeview.show();
                $arrow.addClass('rotate-270');
            } else {
                // Close other menus
                $item.removeClass('menu-open').addClass('menu-close');
                $treeview.hide();
                $arrow.removeClass('rotate-270');
            }
        }
    });
    
    console.log('✅ Sidebar accordion menu initialized successfully');
});

// CSS for arrow rotation animation
if (!document.getElementById('sidebar-menu-styles')) {
    const style = document.createElement('style');
    style.id = 'sidebar-menu-styles';
    style.textContent = `
        .nav-sidebar .nav-link .fas.fa-angle-left {
            transition: transform 0.3s ease;
        }
        
        .nav-sidebar .nav-link .fas.fa-angle-left.rotate-270 {
            transform: rotate(-90deg);
        }
        
        .nav-treeview {
            overflow: hidden;
        }
    `;
    document.head.appendChild(style);
}
