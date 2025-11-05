# patient-timeline-visualization Specification

## Purpose
TBD - created by archiving change add-patient-timeline-card. Update Purpose after archive.
## Requirements
### Requirement: Aggregate patient events from all data sources

The system MUST aggregate patient events from all existing data sources (Patient birth, GMAssessment, HINEAssessment, DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment, Video, Attachment models) into a unified chronological timeline.

#### Scenario: Patient with multiple assessment types
```
GIVEN a patient with:
  - Birth date: 2024-01-15 10:30 AM
  - 2 GM Assessments (2024-02-01, 2024-03-15)
  - 1 HINE Assessment (2024-02-20)
  - 1 Video (2024-03-01)
  - 1 Attachment (2024-03-10)
WHEN the patient timeline is requested
THEN the timeline MUST include exactly 6 events
AND events MUST be sorted by datetime in descending order (newest first)
AND the birth event MUST appear last in the list
```

#### Scenario: Patient with no assessments
```
GIVEN a patient with only birth information
WHEN the patient timeline is requested
THEN the timeline MUST include exactly 1 event (birth)
AND the timeline MUST display "No additional timeline events yet" message
```

#### Scenario: Patient with orphaned references
```
GIVEN a patient with a deleted related assessment
WHEN the patient timeline is requested
THEN the timeline MUST NOT include the orphaned event
AND the timeline MUST NOT crash or raise exceptions
AND other valid events MUST still be displayed
```

### Requirement: Standardize timeline event metadata

Each timeline event MUST include standardized metadata with datetime, type, icon, color, title, description, detail_url, can_preview, and preview_data fields for consistent display and interaction.

#### Scenario: GM Assessment event metadata
```
GIVEN a GM Assessment dated 2024-03-15 14:30 with diagnosis "Normal" and assessor "Dr. Smith"
WHEN converted to timeline event
THEN event MUST have:
  - datetime: 2024-03-15 14:30:00
  - type: "assessment_gma"
  - icon: "fa-video fa-eye"
  - color: "info"
  - title: "GM Assessment"
  - description: "Normal - Dr. Smith"
  - detail_url: "/assessment/view/{id}/"
  - can_preview: true
```

#### Scenario: Video event metadata
```
GIVEN a Video uploaded on 2024-04-10 09:15 with caption "Follow-up assessment"
WHEN converted to timeline event
THEN event MUST have:
  - datetime: 2024-04-10 09:15:00
  - type: "media_video"
  - icon: "fa-video"
  - color: "success"
  - title: "Video Recorded"
  - description: "Follow-up assessment"
  - detail_url: "/video/view/{id}/"
  - can_preview: false
```

### Requirement: Display timeline as separate card in patient view

The timeline component MUST display as a card-success card-outline below the assessments section and above the media card in the patient detail view.

#### Scenario: Timeline card positioning
```
GIVEN a user viewing patient detail page
WHEN the page loads
THEN the timeline card MUST appear after the "Assessments Card" (GMA/HINE/DA/CDIC/GPA tabs) and before the "Media Card" (Videos/Attachments tabs) as a full-width card
```

### Requirement: Use vertical timeline layout with visual markers

The timeline MUST use a vertical layout with a connecting line on the left, circular icon markers, event content cards, and chronological flow from top (newest) to bottom (oldest).

#### Scenario: Timeline visual structure
```
GIVEN a timeline with 3 events
WHEN rendered in the browser
THEN the display MUST show a continuous vertical line connecting all events, circular markers at each event position, event content cards aligned consistently, and clear visual hierarchy from newest to oldest
```

### Requirement: Format event datetime and descriptions consistently

The timeline MUST display event datetime in "MMM DD, YYYY" and "HH:MM AM/PM" format, with event title in bold 1.1rem font and description in regular 0.9rem font truncated if exceeding 100 characters.

#### Scenario: Event datetime formatting
```
GIVEN an event with datetime 2024-03-15 14:30:00
WHEN displayed in timeline
THEN datetime MUST show as "Mar 15, 2024" for date and "02:30 PM" for time
AND datetime MUST be right-aligned in the event header
```

### Requirement: Provide client-side event category filtering

The timeline MUST provide client-side filtering with three buttons: "All Events" (default, shows all), "Assessments" (shows GMA/HINE/DA/CDIC/GPA only), and "Media" (shows Videos/Attachments only).

#### Scenario: Filter to assessments only
```
GIVEN a timeline with 1 Birth, 2 GM Assessments, 1 Video, 1 Attachment
WHEN user clicks "Assessments" filter button
THEN the timeline MUST show 2 GM Assessment events visible, hide Birth/Video/Attachment events, visually activate "Assessments" button, and filter without page reload
```

#### Scenario: Filter to media only
```
GIVEN a timeline with 1 Birth, 2 GM Assessments, 1 Video, 1 Attachment
WHEN user clicks "Media" filter button
THEN the timeline MUST show Video and Attachment events visible, hide Birth/Assessment events, and visually activate "Media" button
```

#### Scenario: Reset filter to all events
```
GIVEN a timeline currently filtered to "Assessments"
WHEN user clicks "All Events" filter button
THEN the timeline MUST show all events and visually activate "All Events" button
```

### Requirement: Animate filter transitions smoothly

Filter transitions MUST fade out over 300ms, keep items in DOM with display:none, not cause layout shift, and fade in newly visible items over 300ms.

#### Scenario: Filter transition animation
```
GIVEN a timeline with applied filter
WHEN user changes filter selection
THEN filtered items MUST fade out over 300ms without layout shift
AND newly visible items MUST fade in over 300ms
```

### Requirement: Open event details in new window

Each timeline event MUST provide a "View Details" link that opens the event's detail page in a new browser window with rel="noopener noreferrer" and maintains scroll position.

#### Scenario: Open assessment detail in new window
```
GIVEN a GM Assessment event in the timeline
WHEN user clicks "View Details" button
THEN the system MUST open assessment detail view in new browser tab, keep current patient timeline page open, include rel="noopener noreferrer", and maintain user's scroll position
```

### Requirement: Display inline preview for capable events

Timeline events with can_preview=true (GM, HINE, DA, CDIC, GPA assessments, Image/PDF attachments) MUST display an inline preview modal showing key details, with "View Full Details" link, closable via X button or ESC key, and proper keyboard focus management.

#### Scenario: Preview GM Assessment inline
```
GIVEN a GM Assessment event with can_preview=true
WHEN user clicks "Quick Preview" button
THEN the system MUST display modal overlay showing diagnosis, assessor, date, include "View Full Details" link, allow closing with X button or ESC key, and maintain keyboard focus
```

#### Scenario: Video without preview
```
GIVEN a Video event with can_preview=false
WHEN user views the event in timeline
THEN the event MUST NOT show "Quick Preview" button and MUST only show "View Details" button
```

### Requirement: Adapt layout for responsive breakpoints

The timeline MUST adapt layout for desktop (≥992px) with full timeline, tablet (768px-991px) with simplified timeline, and mobile (<768px) with compact stacked elements.

#### Scenario: Desktop layout at 1920px width
```
GIVEN a user viewing timeline on desktop at 1920px
THEN the timeline MUST display 60px circular markers, 15px padding on event cards, horizontal filter buttons, and two-column event header layout
```

#### Scenario: Mobile layout at 375px width
```
GIVEN a user viewing timeline on mobile at 375px
THEN the timeline MUST display 40px circular markers, reduced padding, stacked event header, full-width action buttons, and touch-friendly tap targets (min 44px height)
```

### Requirement: Maintain readability across screen sizes

The timeline MUST maintain minimum 14px body text, 16px event titles, no horizontal scrolling, and content fitting within viewport width on all screen sizes.

#### Scenario: Font scaling on mobile
```
GIVEN a user viewing timeline on mobile device
THEN text MUST use minimum 14px for body and 16px for titles
AND no horizontal scrolling required
AND all content fits within viewport width
```

### Requirement: Load all patient events without pagination

The timeline component MUST load all patient events in a single request with performance targets: <50ms for 10 events, <200ms for 50 events, <500ms for 100 events.

#### Scenario: Timeline with 50 events
```
GIVEN a patient with 50 timeline events
WHEN the patient detail page loads
THEN the timeline MUST load all 50 events in single request, render within 200ms, not block other sections, and use optimized queries
```

### Requirement: Optimize queries to prevent N+1 issues

The system MUST use select_related() for ForeignKey and prefetch_related() for ManyToMany relationships, executing maximum 8 queries (one per event source).

#### Scenario: Query optimization for multiple event types
```
GIVEN a patient with events from all 8 source types
WHEN timeline events are aggregated
THEN the system MUST execute maximum 8 database queries with select_related/prefetch_related and NOT execute additional queries during iteration
```

### Requirement: Support full keyboard navigation

The timeline MUST allow Tab navigation through filter and action buttons, Enter/Space to activate buttons, and Escape to close preview modals, with visible focus indicators on all elements.

#### Scenario: Keyboard navigation through timeline
```
GIVEN a user navigating with keyboard only
WHEN user presses Tab key repeatedly
THEN focus MUST move through filter buttons, then event action buttons in order
AND each focused element MUST have visible focus indicator
```

### Requirement: Comply with WCAG 2.1 Level AA standards

The timeline MUST meet minimum 4.5:1 text contrast, use semantic HTML5 elements, maintain proper heading hierarchy, include ARIA labels, and announce filter changes to screen readers.

#### Scenario: Screen reader announces filter change
```
GIVEN a screen reader user
WHEN user activates "Assessments" filter
THEN screen reader MUST announce "Assessments filter active", number of visible events, and first visible event title
```

#### Scenario: Color contrast validation
```
GIVEN timeline text on background colors
THEN body text MUST meet minimum 4.5:1 contrast ratio
AND large text (≥18px) MUST meet minimum 3:1 contrast ratio
AND interactive elements MUST meet minimum 3:1 contrast against background
```

### Requirement: Handle missing or invalid data gracefully

The timeline MUST log errors for invalid events, skip them, continue processing other events, and never crash the page.

#### Scenario: Event with missing datetime
```
GIVEN an assessment with null date_of_assessment
WHEN timeline is aggregated
THEN the system MUST log error with patient ID and event type, skip the invalid event, continue processing other events, and NOT raise exception
```

#### Scenario: Event with deleted related object
```
GIVEN a GM Assessment with deleted video_file
WHEN timeline is aggregated
THEN the system MUST detect missing relationship, skip orphaned event OR show "Details unavailable", log warning, and continue processing
```

### Requirement: Display user-friendly empty and error states

The timeline MUST show "No additional timeline events yet" for patients with only birth information, and "No media events to display" when filters result in empty view.

#### Scenario: No events available
```
GIVEN a patient with only birth information and no assessments, videos, or attachments
WHEN timeline is displayed
THEN the timeline MUST show birth event only and message "No additional timeline events yet" styled as info alert
```

#### Scenario: All events filtered out
```
GIVEN a timeline with only assessment events
WHEN user applies "Media" filter
THEN the timeline MUST show no visible events, message "No media events to display", and keep filter buttons active
```

### Requirement: Integrate with AdminLTE design system

The timeline component MUST use AdminLTE card classes, Bootstrap 4.6 grid, existing color palette, matching button styles, and Font Awesome 6.4 icons.

#### Scenario: Visual consistency with existing cards
```
GIVEN the patient detail page with existing cards
WHEN timeline card is added
THEN the timeline card MUST use same border radius, box-shadow, header styling, card-tools button styling, and consistent spacing as other cards
```

### Requirement: Preserve existing patient view functionality

The timeline MUST NOT interfere with existing patient view tabs, JavaScript, behaviors, or data loading.

#### Scenario: Existing tabs still functional
```
GIVEN the patient detail page with timeline added
WHEN user interacts with existing tabs (GMA, HINE, Videos, etc.)
THEN all existing tabs MUST function correctly, not be affected by timeline JavaScript, and maintain current behavior
```

### Requirement: Respect authentication and access control

The timeline MUST maintain @login_required decorator protection, redirect unauthenticated users to login, and never display patient data to unauthenticated users.

#### Scenario: Unauthenticated user
```
GIVEN an unauthenticated user
WHEN user attempts to access patient detail page
THEN the system MUST redirect to login page and NOT display timeline or any patient data
```

### Requirement: Prevent XSS attacks through content escaping

The timeline MUST escape all HTML entities in user-generated content using Django's auto-escaping to prevent script execution.

#### Scenario: Event description with HTML content
```
GIVEN an assessment description containing "<script>alert('XSS')</script>"
WHEN displayed in timeline
THEN the system MUST escape all HTML entities, display literal text, not execute scripts, and use Django's auto-escaping
```

