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
            
            // Add status indicators animation
            $('.fas.fa-circle').each(function() {
                const $icon = $(this);
                if ($icon.hasClass('text-success')) {
                    $icon.addClass('pulse');
                }
            });
            
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
});
