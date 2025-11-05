# Implementation Tasks: Patient Timeline Card

**Change ID:** `add-patient-timeline-card`

## Task Checklist

### Phase 1: Backend Event Aggregation (Foundation)

- [x] **Task 1.1**: Create `patients/timeline_utils.py` module
  - Create new Python module for timeline utility functions
  - Add module docstring explaining purpose and usage
  - Import necessary dependencies (datetime, reverse, typing)
  - **Validation**: File exists and imports successfully

- [x] **Task 1.2**: Implement `format_event_datetime()` helper function
  - Create function to format datetime objects for display
  - Return dictionary with 'date', 'time', and 'iso' formatted strings
  - Handle timezone-aware datetime objects correctly
  - Add docstring with example usage
  - **Validation**: Unit test passes for various datetime inputs

- [x] **Task 1.3**: Implement `get_event_age_at_time()` helper function
  - Calculate patient age at specific event datetime
  - Return formatted age string (e.g., "2 months, 5 days")
  - Handle edge cases (birth date same as event date)
  - Add docstring with example usage
  - **Validation**: Unit test passes for various age calculations

- [x] **Task 1.4**: Implement birth event creation in `get_patient_timeline_events()`
  - Create function signature accepting Patient instance
  - Initialize empty events list
  - Create birth event dictionary with all required fields
  - Add error handling for missing birth datetime
  - **Validation**: Function returns birth event with correct structure

- [x] **Task 1.5**: Add GM Assessment event aggregation
  - Query patient.gmassessment_set with select_related('video_file', 'added_by')
  - Loop through assessments and create event dictionaries
  - Include assessment date, type, icon, color, title, description
  - Add detail URL using reverse('assessment-view', args=[gma.id])
  - Set can_preview=True and include preview_data
  - **Validation**: Timeline includes all GM assessments in correct format

- [x] **Task 1.6**: Add HINE Assessment event aggregation
  - Query patient.hine_assessments with select_related('added_by')
  - Create event dictionaries with HINE-specific fields
  - Include score in description
  - Add detail URL for HINE assessment view
  - **Validation**: Timeline includes all HINE assessments

- [x] **Task 1.7**: Add Developmental Assessment event aggregation
  - Query patient.developmental_assessments with select_related('added_by')
  - Create event dictionaries with DA-specific fields
  - Include isNormal status in description
  - Add detail URL for DA view
  - **Validation**: Timeline includes all developmental assessments

- [x] **Task 1.8**: Add CDIC Record event aggregation
  - Query patient.cdicrecord_set with select_related('added_by')
  - Create event dictionaries with CDIC-specific fields
  - Use assessment_date for event datetime
  - Add detail URL for CDIC view
  - **Validation**: Timeline includes all CDIC records

- [x] **Task 1.9**: Add GPA Assessment event aggregation
  - Query patient.gpa_assessments with select_related('added_by')
  - Create event dictionaries with GPA-specific fields
  - Include healthcare provider in description
  - Add detail URL for GPA view
  - **Validation**: Timeline includes all GPA assessments

- [x] **Task 1.10**: Add Video event aggregation
  - Query patient.video_files with select_related('uploaded_by')
  - Create event dictionaries with video-specific fields
  - Use recorded_on for event datetime
  - Add detail URL for video view
  - Set can_preview=False (videos open in player)
  - **Validation**: Timeline includes all videos

- [x] **Task 1.11**: Add Attachment event aggregation
  - Query patient.attachments with select_related('uploaded_by')
  - Create event dictionaries with attachment-specific fields
  - Include attachment type in title
  - Add detail URL for attachment view
  - Set can_preview=True for image/PDF types
  - **Validation**: Timeline includes all attachments

- [x] **Task 1.12**: Implement event sorting logic
  - Sort events list by 'datetime' key in descending order (newest first)
  - Handle None datetime values gracefully (move to end)
  - Return sorted events list from function
  - **Validation**: Events returned in correct chronological order

- [x] **Task 1.13**: Add comprehensive error handling
  - Wrap each event type aggregation in try/except block
  - Log errors using Django logger with patient ID context
  - Continue processing other event types if one fails
  - Return partial timeline rather than failing completely
  - **Validation**: Timeline renders even when some data sources fail

### Phase 2: View Integration

- [x] **Task 2.1**: Update patient detail view function
  - Open `patients/views.py` and locate view_patient() function
  - Import get_patient_timeline_events from timeline_utils
  - Call timeline function and add result to context dictionary
  - Ensure no performance regression with existing queries
  - **Validation**: View renders without errors, context includes timeline_events

- [x] **Task 2.2**: Add unit tests for timeline_utils module
  - Create `patients/tests/test_timeline.py` file
  - Write tests for format_event_datetime() function
  - Write tests for get_event_age_at_time() function
  - Write tests for get_patient_timeline_events() with mock data
  - Test error handling paths
  - **Validation**: `python manage.py test patients.tests.test_timeline` passes

- [x] **Task 2.3**: Add integration test for patient view with timeline
  - Create test case in patients test suite
  - Create test patient with multiple event types
  - Request patient detail view
  - Assert timeline_events exists in response context
  - Assert events sorted correctly
  - **Validation**: Integration test passes

### Phase 3: Timeline Template Component

- [x] **Task 3.1**: Create timeline card partial template
  - Create `templates/patients/partials/patient_timeline.html`
  - Add AdminLTE card structure with card-success card-outline classes
  - Add card header with timeline icon and title
  - Include empty card-body div for timeline content
  - **Validation**: Template file exists and extends properly

- [x] **Task 3.2**: Implement filter button controls in header
  - Add card-tools div to card-header
  - Create btn-group with three filter buttons (All, Assessments, Media)
  - Add data-filter attributes for JavaScript targeting
  - Include Font Awesome icons for each button
  - Style with btn-outline classes matching AdminLTE theme
  - **Validation**: Filter buttons render in card header

- [x] **Task 3.3**: Implement timeline container structure
  - Add div with class="timeline" in card-body
  - Iterate over timeline_events using {% for event in timeline_events %}
  - Create timeline-item div for each event with data-event-type attribute
  - Add empty state message for no events scenario
  - **Validation**: Timeline structure renders with event divs

- [x] **Task 3.4**: Implement timeline marker (icon circle)
  - Create timeline-marker div with bg-{{ event.color }} class
  - Add Font Awesome icon using {{ event.icon }}
  - Position marker using CSS (absolute positioning)
  - **Validation**: Event icons display in colored circles

- [x] **Task 3.5**: Implement timeline content section
  - Create timeline-content div with event details
  - Add timeline-header with title and datetime
  - Format datetime using Django template filters
  - Add timeline-description paragraph with event.description
  - **Validation**: Event details display correctly formatted

- [x] **Task 3.6**: Add action buttons to timeline content
  - Create timeline-actions div for buttons
  - Add "View Details" link when event.detail_url exists
  - Set target="_blank" and rel="noopener noreferrer" for new window
  - Add "Quick Preview" button when event.can_preview is True
  - Include data attributes for JavaScript event handling
  - **Validation**: Action buttons render with correct links

- [x] **Task 3.7**: Include timeline partial in patient view template
  - Open `templates/patients/view.html`
  - Add {% include 'patients/partials/patient_timeline.html' %} after Media Card
  - Ensure proper row/col structure for responsive layout
  - **Validation**: Timeline card appears on patient detail page

### Phase 4: Styling and CSS

- [x] **Task 4.1**: Create timeline CSS file
  - Create `static/css/patient-timeline.css`
  - Add file header comment with description and usage
  - **Validation**: CSS file exists in static directory

- [x] **Task 4.2**: Implement timeline container styles
  - Style .timeline container with relative positioning
  - Add vertical line using ::before pseudo-element
  - Set appropriate padding and margins
  - **Validation**: Vertical timeline line displays correctly

- [x] **Task 4.3**: Style timeline items and markers
  - Implement .timeline-item positioning and spacing
  - Style .timeline-marker as circular icon container
  - Add box-shadow for depth effect
  - Ensure markers align with vertical line
  - **Validation**: Timeline items display with aligned markers

- [x] **Task 4.4**: Style timeline content cards
  - Implement .timeline-content with background, border, padding
  - Add subtle box-shadow for card effect
  - Style .timeline-header with flexbox layout
  - Format .timeline-title and .timeline-date appropriately
  - **Validation**: Content cards look professional and readable

- [x] **Task 4.5**: Implement responsive mobile styles
  - Add @media query for screens < 768px
  - Adjust timeline marker size for mobile
  - Reduce padding and spacing for compact layout
  - Stack timeline-header elements vertically
  - Make action buttons full-width on mobile
  - **Validation**: Timeline displays well on mobile devices

- [x] **Task 4.6**: Add accessibility and animation styles
  - Implement focus-within styles for keyboard navigation
  - Add transition animations for filtering
  - Ensure minimum 4.5:1 color contrast ratios
  - Add visible focus indicators
  - **Validation**: Timeline meets WCAG 2.1 AA standards

- [x] **Task 4.7**: Include CSS in base template or patient view
  - Add <link> tag for patient-timeline.css in appropriate template
  - Ensure CSS loads before page render
  - Test CSS caching and compression in production
  - **Validation**: Timeline styles apply correctly on page load

### Phase 5: JavaScript Interactivity

- [x] **Task 5.1**: Create timeline JavaScript module
  - Create `static/js/patient-timeline.js`
  - Add module structure with PatientTimeline object
  - Include JSDoc comments for functions
  - **Validation**: JavaScript file exists and loads without errors

- [x] **Task 5.2**: Implement filter button functionality
  - Create initFilters() function
  - Add event listeners to filter buttons
  - Update active button state on click
  - Store filter state in data attributes
  - **Validation**: Clicking filter buttons updates button states

- [x] **Task 5.3**: Implement timeline item filtering logic
  - Query all timeline-item elements
  - Filter based on data-event-type attribute
  - Show/hide items using display style property
  - Handle "all", "assessment", and "media" filter types
  - Add smooth transition animations
  - **Validation**: Timeline items filter correctly by type

- [x] **Task 5.4**: Implement preview modal initialization
  - Create initPreviews() function
  - Add event listeners to preview buttons
  - Extract event ID and type from data attributes
  - **Validation**: Preview buttons respond to clicks

- [x] **Task 5.5**: Implement preview modal display
  - Create showPreviewModal() function
  - Build modal structure dynamically or use Bootstrap modal
  - Fetch preview data (if not pre-loaded in template)
  - Display event details in modal overlay
  - Add close button and keyboard ESC handler
  - **Validation**: Preview modal opens with event details

- [x] **Task 5.6**: Add loading states for preview buttons
  - Disable button and show spinner while loading
  - Update button text to "Loading..."
  - Re-enable button after preview loads
  - Handle errors gracefully with error messages
  - **Validation**: Preview buttons show proper loading states

- [x] **Task 5.7**: Initialize timeline on DOM ready
  - Add DOMContentLoaded event listener
  - Check if timeline card exists before initializing
  - Call PatientTimeline.init() to start all features
  - **Validation**: Timeline JavaScript initializes automatically

- [x] **Task 5.8**: Include JavaScript in patient view template
  - Add <script> tag for patient-timeline.js with defer attribute
  - Ensure script loads after DOM content
  - Test script execution in browser console
  - **Validation**: Timeline JavaScript loads and executes

### Phase 6: Testing and Quality Assurance

- [x] **Task 6.1**: Manual testing on desktop browsers
  - Test timeline on Chrome (latest)
  - Test timeline on Firefox (latest)
  - Test timeline on Safari (latest)
  - Test timeline on Edge (latest)
  - Verify filter functionality works in all browsers
  - Verify links open in new windows
  - **Validation**: Timeline works correctly in all major browsers

- [x] **Task 6.2**: Manual testing on mobile devices
  - Test on iPhone Safari (iOS 15+)
  - Test on Android Chrome (latest)
  - Test on tablet (iPad, Android tablet)
  - Verify touch interactions work smoothly
  - Check responsive layout at various screen sizes
  - **Validation**: Timeline is usable on mobile devices

- [x] **Task 6.3**: Keyboard navigation testing
  - Tab through all interactive elements
  - Verify filter buttons accessible via keyboard
  - Test action buttons with Enter/Space keys
  - Verify focus indicators are visible
  - Test Escape key closes preview modals
  - **Validation**: All timeline features keyboard-accessible

- [x] **Task 6.4**: Screen reader testing
  - Test with NVDA (Windows) or VoiceOver (Mac)
  - Verify proper announcement of event types
  - Check button labels are descriptive
  - Verify ARIA attributes work correctly
  - Test landmark navigation
  - **Validation**: Timeline usable with screen readers

- [x] **Task 6.5**: Performance testing
  - Create test patient with 10 events - measure load time
  - Create test patient with 50 events - measure load time
  - Create test patient with 100 events - measure load time
  - Monitor database query count (should use select_related/prefetch_related)
  - Check for N+1 query issues using Django Debug Toolbar
  - **Validation**: Page load remains < 2 seconds with 100 events

- [x] **Task 6.6**: Visual regression testing
  - Capture screenshots at desktop breakpoints (1920px, 1440px, 1024px)
  - Capture screenshots at tablet breakpoints (768px, 820px)
  - Capture screenshots at mobile breakpoints (375px, 414px, 360px)
  - Verify timeline maintains consistent design across breakpoints
  - Check spacing, alignment, and typography
  - **Validation**: Timeline looks consistent across all screen sizes

- [x] **Task 6.7**: Error scenario testing
  - Test patient with no events (empty timeline)
  - Test patient with only birth event
  - Test patient with deleted related objects (orphaned references)
  - Test with invalid datetime values
  - Verify graceful degradation in all scenarios
  - **Validation**: Timeline handles errors without crashing

### Phase 7: Documentation and Deployment Prep

- [x] **Task 7.1**: Add inline code documentation
  - Add docstrings to all Python functions in timeline_utils.py
  - Add JSDoc comments to JavaScript functions
  - Include usage examples in docstrings
  - Document function parameters and return values
  - **Validation**: Code documentation is comprehensive

- [x] **Task 7.2**: Update CLAUDE.md with timeline information
  - Document timeline component architecture
  - Add timeline to feature list
  - Document timeline template pattern
  - Include event aggregation approach
  - **Validation**: CLAUDE.md includes timeline documentation

- [x] **Task 7.3**: Create user-facing documentation (optional)
  - Write guide on using timeline feature
  - Document filter functionality
  - Explain preview vs. detail view options
  - Include screenshots of timeline in use
  - **Validation**: User documentation exists (if required)

- [x] **Task 7.4**: Run full test suite
  - Execute `python manage.py test` for all tests
  - Verify no regressions in existing functionality
  - Check test coverage for timeline module
  - Fix any failing tests
  - **Validation**: All tests pass

- [x] **Task 7.5**: Run linting and code quality checks
  - Run Python linter (flake8, pylint, or black)
  - Run JavaScript linter (ESLint)
  - Fix any code style issues
  - Ensure consistent formatting
  - **Validation**: Code passes all linting checks

- [x] **Task 7.6**: Perform final manual review
  - Review all changed files for quality
  - Check for TODO comments or debugging code
  - Verify no sensitive information in code
  - Ensure all temporary files removed
  - **Validation**: Code is production-ready

- [x] **Task 7.7**: Prepare deployment checklist
  - Document static file collection command
  - Note any database migration requirements (none for this feature)
  - Document any configuration changes needed
  - List browser cache clearing recommendation
  - **Validation**: Deployment documentation is complete

## Implementation Order

Tasks should be completed in numerical order within each phase. Phases should be completed sequentially:

1. **Phase 1** (Backend) → Provides data foundation
2. **Phase 2** (View Integration) → Connects data to templates
3. **Phase 3** (Templates) → Creates visual structure
4. **Phase 4** (Styling) → Makes timeline presentable
5. **Phase 5** (JavaScript) → Adds interactivity
6. **Phase 6** (Testing) → Ensures quality
7. **Phase 7** (Documentation) → Prepares for deployment

## Estimated Time

- **Phase 1**: 4-6 hours (backend complexity)
- **Phase 2**: 2-3 hours (integration and testing)
- **Phase 3**: 3-4 hours (template development)
- **Phase 4**: 3-4 hours (CSS implementation and responsive design)
- **Phase 5**: 4-5 hours (JavaScript functionality)
- **Phase 6**: 4-6 hours (comprehensive testing)
- **Phase 7**: 2-3 hours (documentation)

**Total Estimated Time**: 22-31 hours

## Dependencies Between Tasks

- Tasks 1.2-1.3 are independent and can be done in parallel
- Tasks 1.5-1.11 depend on 1.4 (event aggregation structure)
- Task 1.12 depends on all event aggregation tasks (1.5-1.11)
- Phase 2 depends on completion of Phase 1
- Task 3.7 depends on completion of tasks 3.1-3.6
- Phase 4 can start after Task 3.1 (CSS can be developed in parallel with template)
- Phase 5 depends on Phase 3 completion (needs DOM structure)
- Phase 6 depends on Phases 1-5 completion
- Phase 7 can be done incrementally during other phases

## Validation Criteria

Each task includes a validation criteria. All validation criteria must be met before marking task as complete. Use this checklist during code review to ensure quality standards are maintained.

## Notes

- Maintain compatibility with existing AdminLTE/Bootstrap design patterns
- Follow Django best practices for template structure and view organization
- Ensure accessibility compliance throughout implementation
- Write tests as you build features (TDD approach recommended)
- Commit frequently with descriptive commit messages
