/**
 * Patient Timeline Interactive Component
 *
 * Description: Provides filtering and preview functionality for patient timeline events
 * Designed for NDAS (Neurodevelopmental Assessment System)
 * Dependencies: jQuery 3.6+, Bootstrap 4.6+
 *
 * Author: NDAS Development Team
 * @module PatientTimeline
 */

(function ($) {
    'use strict';

    /**
     * Patient Timeline Module
     * Handles all timeline interactivity including filtering and previews
     */
    const PatientTimeline = {
        /**
         * Configuration object
         */
        config: {
            filterButtons: '[data-filter]',
            timelineItems: '.timeline-item',
            previewButtons: '.timeline-preview-btn',
            previewModal: '#timelinePreviewModal',
            previewContent: '#timelinePreviewContent',
            hiddenClass: 'hidden',
            activeClass: 'active'
        },

        /**
         * Current filter state
         */
        currentFilter: 'all',

        /**
         * Initialize the timeline component
         * Sets up all event listeners and initial state
         */
        init: function () {
            if (!this.hasTimeline()) {
                console.log('Timeline component not found on page');
                return;
            }

            console.log('Initializing Patient Timeline...');
            this.initFilters();
            this.initPreviews();
            this.initKeyboardNavigation();
            console.log('Patient Timeline initialized successfully');
        },

        /**
         * Check if timeline exists on current page
         * @returns {boolean} True if timeline card exists
         */
        hasTimeline: function () {
            return $('.timeline').length > 0;
        },

        /**
         * Initialize filter button functionality
         * Adds click handlers to filter buttons
         */
        initFilters: function () {
            const self = this;
            const $filterButtons = $(this.config.filterButtons);

            $filterButtons.on('click', function (e) {
                e.preventDefault();
                const $btn = $(this);
                const filterValue = $btn.data('filter');

                // Update button states
                $filterButtons.removeClass(self.config.activeClass).attr('aria-pressed', 'false');
                $btn.addClass(self.config.activeClass).attr('aria-pressed', 'true');

                // Apply filter
                self.applyFilter(filterValue);
            });

            console.log('Timeline filters initialized');
        },

        /**
         * Apply filter to timeline items
         * Shows/hides items based on filter type
         * @param {string} filterType - Filter type: 'all', 'assessment', or 'media'
         */
        applyFilter: function (filterType) {
            const self = this;
            const $items = $(this.config.timelineItems);

            this.currentFilter = filterType;

            if (filterType === 'all') {
                // Show all items
                $items.removeClass(this.config.hiddenClass);
            } else {
                // Filter items
                $items.each(function () {
                    const $item = $(this);
                    const itemType = $item.data('event-type');

                    if (itemType === filterType) {
                        $item.removeClass(self.config.hiddenClass);
                    } else {
                        $item.addClass(self.config.hiddenClass);
                    }
                });
            }

            // Announce to screen readers
            this.announceFilterChange(filterType);
        },

        /**
         * Announce filter change to screen readers
         * @param {string} filterType - Current filter type
         */
        announceFilterChange: function (filterType) {
            const $items = $(this.config.timelineItems).not('.' + this.config.hiddenClass);
            const count = $items.length;
            const message = `Showing ${count} ${filterType} event${count !== 1 ? 's' : ''}`;

            // Create or update aria-live region
            let $announcer = $('#timeline-filter-announcer');
            if ($announcer.length === 0) {
                $announcer = $('<div>', {
                    id: 'timeline-filter-announcer',
                    'aria-live': 'polite',
                    'aria-atomic': 'true',
                    'class': 'sr-only'
                }).appendTo('body');
            }
            $announcer.text(message);
        },

        /**
         * Initialize preview modal functionality
         * Adds click handlers to preview buttons
         */
        initPreviews: function () {
            const self = this;
            const $previewButtons = $(this.config.previewButtons);

            $previewButtons.on('click', function (e) {
                e.preventDefault();
                const $btn = $(this);

                // Show loading state
                self.setPreviewLoading($btn, true);

                // Get preview data
                const eventType = $btn.data('event-type');
                const previewData = $btn.data('preview');

                // Display preview
                self.showPreview(eventType, previewData);

                // Remove loading state
                self.setPreviewLoading($btn, false);
            });

            console.log('Timeline previews initialized');
        },

        /**
         * Set loading state on preview button
         * @param {jQuery} $btn - Button element
         * @param {boolean} isLoading - Loading state
         */
        setPreviewLoading: function ($btn, isLoading) {
            if (isLoading) {
                $btn.prop('disabled', true)
                    .data('original-html', $btn.html())
                    .html('<i class="fas fa-spinner fa-spin"></i> Loading...');
            } else {
                const originalHtml = $btn.data('original-html');
                $btn.prop('disabled', false)
                    .html(originalHtml || '<i class="fas fa-eye"></i> Quick Preview');
            }
        },

        /**
         * Show preview modal with event data
         * @param {string} eventType - Type of event (gma, hine, etc.)
         * @param {Object} previewData - Preview data object
         */
        showPreview: function (eventType, previewData) {
            const $modal = $(this.config.previewModal);
            const $content = $(this.config.previewContent);

            // Build preview HTML based on event type
            const previewHtml = this.buildPreviewHtml(eventType, previewData);

            // Update modal content
            $content.html(previewHtml);

            // Show modal
            $modal.modal('show');
        },

        /**
         * Build preview HTML based on event type
         * @param {string} eventType - Type of event
         * @param {Object} data - Event preview data
         * @returns {string} HTML string for preview
         */
        buildPreviewHtml: function (eventType, data) {
            let html = '<div class="preview-content">';

            switch (eventType) {
                case 'gma':
                    html += `
                        <h5><i class="fas fa-video text-success"></i> GM Assessment Preview</h5>
                        <hr>
                        <dl class="row">
                            <dt class="col-sm-3">Assessor:</dt>
                            <dd class="col-sm-9">${this.escapeHtml(data.assessor || 'Unknown')}</dd>
                            ${data.observation ? `
                                <dt class="col-sm-3">Observation:</dt>
                                <dd class="col-sm-9">${this.escapeHtml(data.observation)}</dd>
                            ` : ''}
                            ${data.diagnosis ? `
                                <dt class="col-sm-3">Diagnosis:</dt>
                                <dd class="col-sm-9"><span class="badge badge-info">${this.escapeHtml(data.diagnosis)}</span></dd>
                            ` : ''}
                            ${data.video ? `
                                <dt class="col-sm-3">Video:</dt>
                                <dd class="col-sm-9">${this.escapeHtml(data.video)}</dd>
                            ` : ''}
                        </dl>
                    `;
                    break;

                case 'hine':
                    html += `
                        <h5><i class="fas fa-brain text-info"></i> HINE Assessment Preview</h5>
                        <hr>
                        <dl class="row">
                            <dt class="col-sm-3">Total Score:</dt>
                            <dd class="col-sm-9"><strong>${this.escapeHtml(String(data.score || 'N/A'))}</strong></dd>
                            <dt class="col-sm-3">Assessor:</dt>
                            <dd class="col-sm-9">${this.escapeHtml(data.assessor || 'Unknown')}</dd>
                        </dl>
                    `;
                    break;

                case 'developmental':
                    html += `
                        <h5><i class="fas fa-child text-success"></i> Developmental Assessment Preview</h5>
                        <hr>
                        <dl class="row">
                            <dt class="col-sm-3">Status:</dt>
                            <dd class="col-sm-9"><span class="badge ${data.status.includes('Normal') ? 'badge-success' : 'badge-warning'}">${this.escapeHtml(data.status || 'Unknown')}</span></dd>
                            <dt class="col-sm-3">Assessor:</dt>
                            <dd class="col-sm-9">${this.escapeHtml(data.assessor || 'Unknown')}</dd>
                        </dl>
                    `;
                    break;

                case 'cdic':
                    html += `
                        <h5><i class="fas fa-hands-helping text-info"></i> CDIC Record Preview</h5>
                        <hr>
                        <dl class="row">
                            <dt class="col-sm-3">Assessor:</dt>
                            <dd class="col-sm-9">${this.escapeHtml(data.assessor || 'Unknown')}</dd>
                        </dl>
                    `;
                    break;

                case 'gpa':
                    html += `
                        <h5><i class="fas fa-stethoscope text-primary"></i> General Paediatric Assessment Preview</h5>
                        <hr>
                        <dl class="row">
                            <dt class="col-sm-3">Healthcare Provider:</dt>
                            <dd class="col-sm-9">${this.escapeHtml(data.provider || 'Unknown')}</dd>
                            <dt class="col-sm-3">Added By:</dt>
                            <dd class="col-sm-9">${this.escapeHtml(data.added_by || 'Unknown')}</dd>
                        </dl>
                    `;
                    break;

                case 'attachment':
                    html += `
                        <h5><i class="fas fa-paperclip text-secondary"></i> Attachment Preview</h5>
                        <hr>
                        <dl class="row">
                            <dt class="col-sm-3">Filename:</dt>
                            <dd class="col-sm-9">${this.escapeHtml(data.filename || 'Unknown')}</dd>
                            <dt class="col-sm-3">Type:</dt>
                            <dd class="col-sm-9"><span class="badge badge-secondary">${this.escapeHtml(data.type || 'File')}</span></dd>
                        </dl>
                    `;
                    break;

                default:
                    html += `<p class="text-muted">Preview not available for this event type.</p>`;
            }

            html += '</div>';
            return html;
        },

        /**
         * Escape HTML to prevent XSS
         * @param {string} text - Text to escape
         * @returns {string} Escaped text
         */
        escapeHtml: function (text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        /**
         * Initialize keyboard navigation
         * Adds keyboard shortcuts for accessibility
         */
        initKeyboardNavigation: function () {
            const self = this;

            // Escape key closes modal
            $(document).on('keydown', function (e) {
                if (e.key === 'Escape' && $(self.config.previewModal).hasClass('show')) {
                    $(self.config.previewModal).modal('hide');
                }
            });

            // Number keys 1-3 for filters
            $(document).on('keydown', function (e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    return; // Don't interfere with form inputs
                }

                const $filterButtons = $(self.config.filterButtons);

                switch (e.key) {
                    case '1':
                        $filterButtons.filter('[data-filter="all"]').trigger('click');
                        break;
                    case '2':
                        $filterButtons.filter('[data-filter="assessment"]').trigger('click');
                        break;
                    case '3':
                        $filterButtons.filter('[data-filter="media"]').trigger('click');
                        break;
                }
            });

            console.log('Keyboard navigation initialized');
        }
    };

    // Initialize on document ready
    $(document).ready(function () {
        PatientTimeline.init();
    });

    // Expose to global scope for debugging
    window.PatientTimeline = PatientTimeline;

})(jQuery);
