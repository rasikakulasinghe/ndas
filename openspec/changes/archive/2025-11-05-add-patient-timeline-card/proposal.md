# Proposal: Add Patient Timeline Card

**Change ID:** `add-patient-timeline-card`
**Type:** Feature Addition
**Status:** Proposed
**Priority:** High

## Overview

Implement a comprehensive Patient Timeline Card component that visualizes a patient's complete medical history from birth to present in chronological order. The timeline will aggregate events from multiple sources (video assessments, written assessments, videos, and attachments) into a unified, filterable, and interactive visualization.

## Motivation

Currently, patient medical events are scattered across multiple tabs (GMA, HINE, Developmental, CDIC, GPA assessments, Videos, and Attachments). Medical professionals must navigate between tabs to understand the full chronological history of patient care, making it difficult to:

- Identify temporal patterns in patient development
- Understand the sequence of interventions and assessments
- Quickly review comprehensive patient history
- Correlate events across different assessment types

A unified timeline view addresses these challenges by providing a single, chronological visualization of all patient events.

## Goals

1. **Unified Visualization**: Present all patient events in a single chronological timeline
2. **Event Aggregation**: Automatically collect events from existing models (GMAssessment, HINEAssessment, DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment, Video, Attachment)
3. **Responsive Design**: Ensure usability across desktop, tablet, and mobile devices
4. **Interactive Filtering**: Allow users to filter timeline by event type
5. **Quick Access**: Provide inline previews and links to detailed views
6. **Accessibility**: Implement semantic HTML and keyboard navigation
7. **Performance**: Optimize for smooth rendering with large patient histories

## User Stories

**As a medical professional, I want to:**
- View a patient's complete medical history in chronological order
- Filter timeline events by type (assessments, videos, attachments)
- Click on timeline events to view full details in new windows
- See inline previews of event details without navigation
- Quickly identify when key assessments or interventions occurred
- Review the timeline on mobile devices during patient consultations

## Scope

### In Scope
- Timeline visualization component integrated into patient detail view
- Aggregation of events from all existing assessment models and media
- Event type filtering (show/hide categories)
- Inline preview modals for quick event details
- Links to open detailed views in new windows
- Responsive layout for desktop, tablet, and mobile
- Icon system for event categorization
- Birth date as initial timeline event
- Integration with AdminLTE design system

### Out of Scope
- Manual entry of clinical events (medications, injections, therapy)
- Pagination or virtual scrolling (using load-all approach)
- Date range filtering
- Export/print functionality
- Event editing from timeline (must use existing detail views)
- Predictive analytics or AI-based insights
- Real-time collaboration features

## Technical Approach

### Architecture
- **Frontend**: Server-rendered Django template with progressive enhancement
- **Backend**: Django view function to aggregate and sort events
- **Styling**: AdminLTE 3.2 + Bootstrap 4.6 components
- **Interactivity**: Vanilla JavaScript with optional HTMX for previews
- **Icons**: Font Awesome 6.4 for event type indicators

### Data Model Impact
- **No new models required**: Timeline aggregates data from existing models
- **View-level aggregation**: Django view collects events from related querysets
- **Queryset optimization**: Use `select_related` and `prefetch_related` for performance

### Event Sources
1. **Birth Event**: Patient.dob_tob (initial event)
2. **GM Assessments**: GMAssessment.date_of_assessment
3. **HINE Assessments**: HINEAssessment.date_of_assessment
4. **Developmental Assessments**: DevelopmentalAssessment.date_of_assessment
5. **CDIC Records**: CDICRecord.assessment_date
6. **GPA Assessments**: GeneralPaediatricAssessment.assessment_date
7. **Videos**: Video.recorded_on
8. **Attachments**: Attachment.uploaded_on

## UI/UX Design

### Component Structure
```
┌─────────────────────────────────────────────────────┐
│ Patient Timeline Card                                │
│ ┌─────────────────────────────────────────────────┐ │
│ │ [Filters: All | Assessments | Videos | Files  ] │ │
│ └─────────────────────────────────────────────────┘ │
│                                                       │
│  ●─────── Birth (2024-01-15)                         │
│  │                                                    │
│  ●─────── Video Assessment (2024-02-01)              │
│  │        [GMA] Normal development - Dr. Smith       │
│  │                                                    │
│  ●─────── HINE Assessment (2024-03-15)               │
│  │        Score: 68/78 - Dr. Johnson                 │
│  │                                                    │
│  ●─────── Video Uploaded (2024-04-10)                │
│           "Follow-up assessment video"               │
└─────────────────────────────────────────────────────┘
```

### Icon Mapping
- **Birth**: `fa-birthday-cake` (Primary)
- **GM Assessment**: `fa-video` + `fa-eye` (Video assessment)
- **HINE Assessment**: `fa-brain` (Neurological)
- **Developmental Assessment**: `fa-child` (Development)
- **CDIC Record**: `fa-hands-helping` (Support)
- **GPA Assessment**: `fa-stethoscope` (Medical)
- **Video**: `fa-video` (Video camera)
- **Attachment**: `fa-paperclip` (Files)

### Responsive Breakpoints
- **Desktop** (≥992px): Full vertical timeline with side-by-side event details
- **Tablet** (768px-991px): Simplified timeline with stacked event details
- **Mobile** (<768px): Compact timeline with collapsible event cards

## Implementation Phases

### Phase 1: Backend Event Aggregation
- Create view function to collect all patient events
- Implement event sorting by datetime
- Add event type categorization
- Optimize querysets with prefetch

### Phase 2: Timeline Template Component
- Create timeline card template structure
- Implement vertical timeline layout
- Add event type icons and styling
- Integrate with patient view

### Phase 3: Filtering and Interactivity
- Implement client-side event type filtering
- Add inline preview modals
- Enable links to detailed views (new window)
- Add keyboard navigation support

### Phase 4: Responsive Design
- Implement mobile-optimized layout
- Test across device sizes
- Optimize touch interactions
- Ensure accessibility compliance

## Success Criteria

1. **Functionality**: Timeline displays all patient events in chronological order
2. **Performance**: Page load time remains <2 seconds with 100+ events
3. **Usability**: Filtering works smoothly without page reload
4. **Accessibility**: Keyboard navigation works for all interactive elements
5. **Compatibility**: Functions correctly on Chrome, Firefox, Safari, Edge
6. **Responsive**: Usable on devices from 320px to 2560px width
7. **Integration**: Follows existing AdminLTE design patterns

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Performance degradation with large event counts | High | Medium | Use load-all approach initially; monitor and implement pagination if needed |
| Inconsistent datetime formats across models | Medium | Low | Normalize all datetimes in view function |
| Mobile layout complexity | Medium | Medium | Progressive enhancement from desktop to mobile |
| Browser compatibility issues | Low | Low | Use standard Bootstrap/AdminLTE components |

## Dependencies

- Existing patient assessment models (GMAssessment, HINEAssessment, etc.)
- AdminLTE 3.2 + Bootstrap 4.6 framework
- Font Awesome 6.4 icon library
- jQuery 3.6 (for Bootstrap components)

## Open Questions

- Should we add export/print functionality in a future iteration?
- Should date range filtering be added based on user feedback?
- Do we need to track user interactions with timeline for analytics?

## Related Changes

None (standalone feature addition)

## Approval Requirements

- Technical lead approval
- UX review for responsive design
- Medical staff feedback on icon choices and event categorization
