/**
 * Manager.js - JavaScript functionality for patient manager pages
 * Part of NDAS (Neonatal Development Assessment System)
 */

// Fallback for utility functions if lodash not available
if (typeof _ === 'undefined') {
    window._ = {
        debounce: function(func, wait) {
            let timeout;
            return function() {
                const context = this, args = arguments;
                clearTimeout(timeout);
                timeout = setTimeout(function() {
                    func.apply(context, args);
                }, wait);
            };
        },
        throttle: function(func, wait) {
            let timeout;
            return function() {
                const context = this, args = arguments;
                if (!timeout) {
                    timeout = setTimeout(function() {
                        timeout = null;
                        func.apply(context, args);
                    }, wait);
                }
            };
        }
    };
}

// Initialize patient manager functionality
document.addEventListener('DOMContentLoaded', function() {
    if (typeof $ === 'undefined') {
        console.error('❌ jQuery not available in patient manager');
        return;
    }
    
    $(document).ready(function() {
        try {
            // Initialize tooltips for better user experience
            $('[data-toggle="tooltip"]').tooltip({
                boundary: 'window',
                trigger: 'hover',
                html: true
            });

            // Initialize search functionality
            function initializeSearch() {
                const searchInput = document.getElementById('searchInput');
                if (!searchInput) return;

                const searchTable = _.debounce(function(query) {
                    const rows = document.querySelectorAll('#patientsTable tbody tr');
                    const searchTerm = query.toLowerCase().trim();

                    rows.forEach(function(row) {
                        if (!searchTerm) {
                            row.style.display = '';
                            return;
                        }

                        const cells = row.querySelectorAll('td');
                        let found = false;

                        cells.forEach(function(cell) {
                            const text = cell.textContent.toLowerCase();
                            if (text.includes(searchTerm)) {
                                found = true;
                            }
                        });

                        row.style.display = found ? '' : 'none';
                    });

                    // Update showing/hiding empty state
                    updateTableVisibility();
                }, 300);

                searchInput.addEventListener('input', function(e) {
                    searchTable(e.target.value);
                });

                searchInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Escape') {
                        e.target.value = '';
                        searchTable('');
                    }
                });

                console.log('✅ Search functionality initialized');
            }

            function updateTableVisibility() {
                const visibleRows = document.querySelectorAll('#patientsTable tbody tr[style=""]');
                const allRows = document.querySelectorAll('#patientsTable tbody tr');
                const tableContainer = document.querySelector('.table-responsive');
                const emptyState = document.querySelector('.empty-state');

                if (visibleRows.length === 0 && allRows.length > 0) {
                    if (tableContainer) tableContainer.style.display = 'none';
                    if (!document.querySelector('.search-empty-state')) {
                        const searchEmpty = document.createElement('div');
                        searchEmpty.className = 'text-center py-5 search-empty-state';
                        searchEmpty.innerHTML = `
                            <div class="empty-state">
                                <i class="fas fa-search fa-3x text-muted mb-4"></i>
                                <h4 class="text-muted mb-3">No Results Found</h4>
                                <p class="text-muted mb-4">Try adjusting your search terms or clear the search to see all patients.</p>
                                <button class="btn btn-primary" onclick="document.getElementById('searchInput').value=''; document.querySelector('.search-empty-state').remove(); document.querySelector('.table-responsive').style.display=''; document.querySelectorAll('#patientsTable tbody tr').forEach(r => r.style.display='');">
                                    <i class="fas fa-times mr-2"></i>Clear Search
                                </button>
                            </div>
                        `;
                        if (tableContainer) {
                            tableContainer.parentNode.insertBefore(searchEmpty, tableContainer.nextSibling);
                        }
                    }
                } else {
                    if (tableContainer) tableContainer.style.display = '';
                    const searchEmptyState = document.querySelector('.search-empty-state');
                    if (searchEmptyState) searchEmptyState.remove();
                }
            }

            // Initialize search
            initializeSearch();

            // Initialize AdminLTE pagination functionality
            function initializeAdminLTEPagination() {
                // Add smooth loading animations to pagination links
                $('.dataTables_paginate .page-link').on('click', function(e) {
                    if ($(this).parent().hasClass('disabled') || $(this).attr('href') === '#') {
                        e.preventDefault();
                        return false;
                    }

                    const $link = $(this);
                    const originalContent = $link.html();

                    // Show loading state
                    $link.html('<i class="fas fa-spinner fa-spin"></i>');

                    // Restore if navigation fails (fallback)
                    setTimeout(() => {
                        $link.html(originalContent);
                    }, 3000);
                });

                // Prevent clicks on disabled pagination items
                $('.dataTables_paginate .page-item.disabled .page-link').on('click', function(e) {
                    e.preventDefault();
                    return false;
                });

                console.log('✅ AdminLTE pagination functionality initialized');
            }

            initializeAdminLTEPagination();
            
            // Enhanced mobile responsiveness for table
            function handleTableResponsiveness() {
                const $table = $('.table-responsive table');
                if ($(window).width() < 768) {
                    $table.addClass('table-sm');
                } else {
                    $table.removeClass('table-sm');
                }
            }
            
            // Run on load and resize
            handleTableResponsiveness();
            $(window).on('resize', _.debounce(handleTableResponsiveness, 250));
            
            // Initialize Select2 for patient action dropdowns
            function initializePatientActions() {
                console.log('🔧 Initializing Select2 patient actions');
                
                // Check if Select2 is available
                if (typeof $.fn.select2 === 'undefined') {
                    console.error('❌ Select2 library not loaded');
                    return;
                }
                
                // Initialize all patient action selects
                $('.patient-actions-select').each(function() {
                    const $select = $(this);
                    const patientId = $select.data('patient-id');
                    const patientName = $select.data('patient-name') || 'Unknown';
                    
                    console.log('🔧 Initializing Select2 for patient:', patientId, patientName);
                    
                    $select.select2({
                        placeholder: 'More Actions...',
                        allowClear: true,
                        width: '160px',
                        dropdownAutoWidth: true,
                        templateResult: function(option) {
                            if (!option.id) return option.text;
                            return $('<span>' + option.text + '</span>');
                        },
                        templateSelection: function(option) {
                            return 'More Actions...';
                        }
                    });
                    
                    // Handle selection changes
                    $select.on('select2:select', function(e) {
                        const selectedValue = e.params.data.id;
                        const selectedText = e.params.data.text;
                        
                        console.log('🔧 Action selected:', selectedValue, 'for patient:', patientId);
                        
                        // Reset the select to show placeholder
                        setTimeout(() => {
                            $select.val('').trigger('change');
                        }, 100);
                        
                        // Handle the action
                        handlePatientAction(selectedValue, patientId, patientName);
                    });
                });
                
                console.log('✅ Select2 patient actions initialized');
            }
            
            // Handle patient actions
            function handlePatientAction(action, patientId, patientName) {
                let url = '';
                
                console.log('🔧 Handling action:', action, 'for patient:', patientId);
                
                // Build URL based on action type
                switch(action) {
                    case 'view':
                        url = `/patients/view/${patientId}/`;
                        break;
                    case 'edit':
                        url = `/patients/edit/${patientId}/`;
                        break;
                    case 'delete':
                        if (confirm(`Are you sure you want to delete ${patientName}? This action cannot be undone.`)) {
                            url = `/patients/delete/confirm/${patientId}/`;
                        }
                        break;
                    case 'add-video':
                        url = `/video/add/${patientId}/`;
                        break;
                    case 'add-cdic':
                        url = `/assessment/cdic/add/${patientId}/`;
                        break;
                    case 'add-da':
                        url = `/assessment/da/add/${patientId}/`;
                        break;
                    case 'add-hine':
                        url = `/assessment/hine/add/${patientId}/`;
                        break;
                    case 'add-attachment':
                        url = `/attachment/add/${patientId}/`;
                        break;
                    case 'view-videos':
                        url = `/video/manager/patient/${patientId}/`;
                        break;
                    case 'view-assessments':
                        url = `/assessment/manager/patient/${patientId}/`;
                        break;
                    case 'view-da':
                        url = `/assessment/da/manager/patient/${patientId}/`;
                        break;
                    case 'view-cdic':
                        url = `/assessment/cdic/manager/patient/${patientId}/`;
                        break;
                    case 'view-attachments':
                        url = `/attachment/manager/patient/${patientId}/`;
                        break;
                    case 'bookmark':
                        url = `/bookmark/add/${patientId}/Patient/`;
                        break;
                    case 'view-created-user':
                        // This would need the user ID - skip for now
                        console.log('📍 View created user action - needs user ID');
                        return;
                }
                
                if (url) {
                    console.log('🔗 Navigating to:', url);
                    window.location.href = url;
                } else {
                    console.log('⚠️ No URL generated for action:', action);
                }
            }
            
            // Initialize Select2 when DOM is ready
            initializePatientActions();
            
            // Add loading states to direct action buttons
            $('.btn[href]').on('click', function() {
                const $btn = $(this);
                const originalText = $btn.html();
                
                if ($btn.attr('href').includes('delete') || 
                    $btn.attr('href').includes('confirm')) {
                    return;
                }
                
                $btn.html('<i class="fas fa-spinner fa-spin"></i>');
                $btn.prop('disabled', true);
                
                setTimeout(function() {
                    $btn.html(originalText);
                    $btn.prop('disabled', false);
                }, 3000);
            });
            
            // Initialize compact pagination functionality
            function initializeCompactPagination() {
                // Add smooth animations to pagination buttons
                $('.pagination .page-link').on('click', function(e) {
                    if ($(this).parent().hasClass('disabled')) {
                        e.preventDefault();
                        return false;
                    }

                    const $link = $(this);
                    const originalContent = $link.html();

                    // Show loading state for navigation
                    if (!$link.find('i').hasClass('fa-angle')) {
                        $link.html('<i class="fas fa-spinner fa-spin"></i>');
                    }

                    // Restore if navigation fails (fallback)
                    setTimeout(() => {
                        $link.html(originalContent);
                    }, 3000);
                });

                // Add keyboard navigation for page jump
                const pageJumpInput = document.getElementById('pageJump');
                if (pageJumpInput) {
                    pageJumpInput.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            jumpToPage();
                        }
                    });
                }

                console.log('✅ Compact pagination functionality initialized');
            }

            // Add status indicators animation
            $('.fas.fa-circle').each(function() {
                const $icon = $(this);
                if ($icon.hasClass('text-success')) {
                    $icon.addClass('pulse');
                }
            });
            
            // Initialize compact pagination functionality
            initializeCompactPagination();

            console.log('✅ Patient manager system initialized successfully');
            
        } catch (error) {
            console.error('❌ Patient manager initialization failed:', error);
        }
    });
    
    // Add CSS animations and critical dropdown fixes via JavaScript
    const style = document.createElement('style');
    style.textContent = `
        .pulse {
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        
        .table-responsive {
            transition: all 0.3s ease;
            overflow: visible !important;
        }
        
        .btn:disabled {
            opacity: 0.6;
        }
        
        .dropdown-item:hover {
            transition: background-color 0.2s ease;
        }
        
        .empty-state {
            padding: 2rem;
        }
        
        .badge-sm {
            font-size: 0.7em;
            padding: 0.2em 0.4em;
        }
        
        /* Select2 mobile adjustments */
        @media (max-width: 767px) {
            .select2-container {
                width: 100% !important;
            }
            
            .select2-dropdown {
                max-width: 90vw !important;
            }
        }
    `;
    document.head.appendChild(style);
    
    // Reinitialize Select2 after any dynamic content changes
    $(document).on('DOMNodeInserted', '.table-responsive', function() {
        setTimeout(function() {
            $('.patient-actions-select:not(.select2-hidden-accessible)').each(function() {
                $(this).select2({
                    placeholder: 'More Actions...',
                    allowClear: true,
                    width: '160px',
                    dropdownAutoWidth: true
                });
            });
        }, 100);
    });

    // Enhanced dropdown positioning for table containers
    // Extracted from inline template JavaScript for better maintainability
    class DropdownManager {
        constructor() {
            this.DROPDOWN_WIDTH = 280;
            this.VIEWPORT_MARGIN = 10;
            this.DROPDOWN_HEIGHT_ESTIMATE = 400;
            this.initializeDropdowns();
        }

        initializeDropdowns() {
            console.log('🔧 Initializing professional dropdown positioning');

            // Fix dropdown positioning to escape table clipping
            $('.table .dropdown-toggle').on('show.bs.dropdown', (event) => {
                this.positionDropdown(event);
            });

            // Reset positioning when dropdown hides
            $('.table .dropdown-toggle').on('hide.bs.dropdown', (event) => {
                this.resetDropdownPosition(event);
            });

            // Add loading states to dropdown items
            $('.dropdown-item[href]').on('click', (event) => {
                this.handleDropdownItemClick(event);
            });

            console.log('✅ Professional dropdown positioning initialized');
        }

        positionDropdown(event) {
            const $toggle = $(event.target);
            const $dropdown = $toggle.siblings('.dropdown-menu');
            const toggleRect = event.target.getBoundingClientRect();

            // Calculate optimal positioning
            const position = this.calculateOptimalPosition(toggleRect);

            console.log('🔧 Positioning dropdown at:', position);

            // Apply fixed positioning to escape table overflow
            $dropdown.css({
                'position': 'fixed',
                'top': position.top + 'px',
                'left': position.left + 'px',
                'z-index': '9999',
                'display': 'block'
            });
        }

        calculateOptimalPosition(toggleRect) {
            // Calculate base position
            let top = toggleRect.bottom + window.scrollY + 5;
            let left = toggleRect.right - this.DROPDOWN_WIDTH;

            // Adjust if dropdown would go off the left edge
            if (left < this.VIEWPORT_MARGIN) {
                left = toggleRect.left + window.scrollX;
            }

            // Adjust if dropdown would go off the right edge
            if (left + this.DROPDOWN_WIDTH > window.innerWidth) {
                left = window.innerWidth - this.DROPDOWN_WIDTH - this.VIEWPORT_MARGIN;
            }

            // Adjust if dropdown would go below viewport
            if (top + this.DROPDOWN_HEIGHT_ESTIMATE > window.innerHeight + window.scrollY) {
                top = toggleRect.top + window.scrollY - this.DROPDOWN_HEIGHT_ESTIMATE;
            }

            return { top, left };
        }

        resetDropdownPosition(event) {
            const $dropdown = $(event.target).siblings('.dropdown-menu');
            $dropdown.css({
                'position': '',
                'top': '',
                'left': '',
                'display': ''
            });
        }

        handleDropdownItemClick(event) {
            const $item = $(event.target);
            const originalText = $item.html();

            // Skip confirmation dialogs
            if ($item.attr('onclick') && $item.attr('onclick').includes('confirm')) {
                return;
            }

            // Add loading state
            $item.html('<i class="fas fa-spinner fa-spin mr-2"></i>Loading...');

            // Restore after timeout (fallback)
            setTimeout(() => {
                $item.html(originalText);
            }, 3000);
        }
    }

    // Initialize dropdown manager
    new DropdownManager();
});

// Global function for page jumping (called from template)
function jumpToPage() {
    const pageInput = document.getElementById('pageJump');
    if (!pageInput) return;

    const pageNumber = parseInt(pageInput.value);
    const maxPages = parseInt(pageInput.getAttribute('max'));

    if (isNaN(pageNumber) || pageNumber < 1 || pageNumber > maxPages) {
        // Show error feedback
        pageInput.classList.add('is-invalid');
        setTimeout(() => {
            pageInput.classList.remove('is-invalid');
        }, 2000);
        return;
    }

    // Navigate to the page
    const currentUrl = new URL(window.location);
    currentUrl.searchParams.set('page', pageNumber);
    window.location.href = currentUrl.toString();
}

// Export for potential external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        DropdownManager,
        jumpToPage
    };
}
