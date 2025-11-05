# Design: Patient Timeline Card

**Change ID:** `add-patient-timeline-card`

## Architecture Overview

The Patient Timeline Card is a read-only visualization component that aggregates events from multiple existing data sources without introducing new models or database schemas. It follows Django's MTV (Model-Template-View) pattern with view-level data aggregation.

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Patient View Page                      │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Existing Patient Details (Overview, Birth, etc.)  │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Existing Assessments Tabs (GMA, HINE, DA, etc.)   │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  NEW: Patient Timeline Card                         │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  Timeline Filter Controls (JS)               │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  Timeline Events List (Server-rendered)      │  │  │
│  │  │  - Birth Event                                │  │  │
│  │  │  - Assessment Events                          │  │  │
│  │  │  - Media Events                               │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Existing Media Tabs (Videos, Attachments)         │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Data Flow

### Request Flow
```
1. User navigates to patient detail view
   ↓
2. View function (patient_view) called
   ↓
3. Helper function aggregates timeline events
   ↓
4. Events sorted chronologically
   ↓
5. Context enriched with timeline_events
   ↓
6. Template renders timeline card
   ↓
7. JavaScript enables client-side filtering
```

### Event Aggregation Logic
```python
def get_patient_timeline_events(patient):
    """
    Aggregate all patient events into unified timeline.
    Returns list of event dictionaries sorted by datetime.
    """
    events = []

    # Birth event (always first)
    events.append({
        'datetime': patient.dob_tob,
        'type': 'birth',
        'icon': 'fa-birthday-cake',
        'color': 'primary',
        'title': 'Birth',
        'description': f'Born at {patient.getPOG}',
        'detail_url': None,
        'can_preview': False,
    })

    # GM Assessments (video assessments)
    for gma in patient.gmassessment_set.select_related('video_file'):
        events.append({
            'datetime': gma.date_of_assessment,
            'type': 'assessment_gma',
            'icon': 'fa-video fa-eye',  # Combined icon
            'color': 'info',
            'title': 'GM Assessment',
            'description': f'{gma.getDiagnosis} - {gma.assessment_done_by}',
            'detail_url': reverse('assessment-view', args=[gma.id]),
            'can_preview': True,
            'preview_data': {...},
        })

    # HINE Assessments
    for hine in patient.hine_assessments.all():
        events.append({
            'datetime': hine.date_of_assessment,
            'type': 'assessment_hine',
            'icon': 'fa-brain',
            'color': 'warning',
            'title': 'HINE Assessment',
            'description': f'Score: {hine.score} - {hine.assessment_done_by}',
            'detail_url': reverse('hine-assessment-view', args=[hine.id]),
            'can_preview': True,
            'preview_data': {...},
        })

    # ... Similar for DA, CDIC, GPA ...

    # Videos
    for video in patient.video_files.all():
        events.append({
            'datetime': video.recorded_on,
            'type': 'media_video',
            'icon': 'fa-video',
            'color': 'success',
            'title': 'Video Recorded',
            'description': video.caption,
            'detail_url': reverse('video:view', args=[video.id]),
            'can_preview': False,
        })

    # Attachments
    for attachment in patient.attachments.all():
        events.append({
            'datetime': attachment.uploaded_on,
            'type': 'media_attachment',
            'icon': 'fa-paperclip',
            'color': 'secondary',
            'title': f'Attachment: {attachment.get_attachment_type_display()}',
            'description': attachment.title,
            'detail_url': reverse('attachment-view', args=[attachment.id]),
            'can_preview': True,
            'preview_data': {...},
        })

    # Sort by datetime (newest first for display)
    return sorted(events, key=lambda e: e['datetime'], reverse=True)
```

## Component Design

### Backend Components

#### 1. View Function Enhancement
**File**: `patients/views.py`

```python
@login_required(login_url="user-login")
def view_patient(request, id):
    """Enhanced patient view with timeline events."""
    patient = get_object_or_404(Patient, pk=id)

    # Existing context assembly
    context = {
        'patient': patient,
        # ... existing context items ...
    }

    # Add timeline events
    context['timeline_events'] = get_patient_timeline_events(patient)

    return render(request, "patients/view.html", context)
```

#### 2. Timeline Helper Module
**File**: `patients/timeline_utils.py` (new file)

```python
"""
Utility functions for patient timeline event aggregation.
Centralizes timeline logic for reusability and testing.
"""

from django.urls import reverse
from typing import List, Dict, Any
from datetime import datetime

def get_patient_timeline_events(patient) -> List[Dict[str, Any]]:
    """Main aggregation function (see pseudocode above)."""
    pass

def format_event_datetime(dt: datetime) -> Dict[str, str]:
    """
    Format datetime for timeline display.
    Returns dict with 'date' and 'time' strings.
    """
    return {
        'date': dt.strftime('%b %d, %Y'),
        'time': dt.strftime('%I:%M %p'),
        'iso': dt.isoformat(),
    }

def get_event_age_at_time(patient, event_datetime: datetime) -> str:
    """
    Calculate patient age at event time.
    Returns formatted age string (e.g., "2 months, 5 days").
    """
    pass
```

### Frontend Components

#### 1. Timeline Card Template
**File**: `templates/patients/partials/patient_timeline.html`

```django
{# Patient Timeline Card Component #}
<div class="row">
  <div class="col-12">
    <div class="card card-success card-outline" id="timeline-card">
      <div class="card-header">
        <h3 class="card-title">
          <i class="fas fa-history"></i> Patient Timeline
        </h3>
        <div class="card-tools">
          {# Event Type Filters #}
          <div class="btn-group btn-group-sm" role="group" aria-label="Filter timeline events">
            <button type="button" class="btn btn-outline-primary active" data-filter="all">
              All Events
            </button>
            <button type="button" class="btn btn-outline-info" data-filter="assessment">
              Assessments
            </button>
            <button type="button" class="btn btn-outline-success" data-filter="media">
              Media
            </button>
          </div>
        </div>
      </div>
      <div class="card-body">
        <div class="timeline">
          {% for event in timeline_events %}
            <div class="timeline-item" data-event-type="{{ event.type }}">
              {# Timeline marker with icon #}
              <div class="timeline-marker bg-{{ event.color }}">
                <i class="fas {{ event.icon }}"></i>
              </div>

              {# Timeline content #}
              <div class="timeline-content">
                <div class="timeline-header">
                  <h5 class="timeline-title">{{ event.title }}</h5>
                  <span class="timeline-date text-muted">
                    {{ event.datetime|date:"M d, Y" }} at {{ event.datetime|time:"g:i A" }}
                  </span>
                </div>
                <p class="timeline-description">{{ event.description }}</p>

                {# Action buttons #}
                <div class="timeline-actions">
                  {% if event.detail_url %}
                    <a href="{{ event.detail_url }}"
                       class="btn btn-sm btn-outline-primary"
                       target="_blank"
                       rel="noopener noreferrer">
                      <i class="fas fa-external-link-alt"></i> View Details
                    </a>
                  {% endif %}

                  {% if event.can_preview %}
                    <button type="button"
                            class="btn btn-sm btn-outline-info timeline-preview-btn"
                            data-event-id="{{ event.id }}"
                            data-event-type="{{ event.type }}">
                      <i class="fas fa-eye"></i> Quick Preview
                    </button>
                  {% endif %}
                </div>
              </div>
            </div>
          {% empty %}
            <div class="alert alert-info">
              <i class="fas fa-info-circle"></i> No timeline events available yet.
            </div>
          {% endfor %}
        </div>
      </div>
    </div>
  </div>
</div>
```

#### 2. Timeline JavaScript Module
**File**: `static/js/patient-timeline.js`

```javascript
/**
 * Patient Timeline Component
 * Handles filtering and preview modal interactions
 */
const PatientTimeline = {
  /**
   * Initialize timeline filtering
   */
  initFilters() {
    const filterButtons = document.querySelectorAll('[data-filter]');
    const timelineItems = document.querySelectorAll('.timeline-item');

    filterButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const filter = this.dataset.filter;

        // Update active button state
        filterButtons.forEach(b => b.classList.remove('active'));
        this.classList.add('active');

        // Filter timeline items
        timelineItems.forEach(item => {
          const eventType = item.dataset.eventType;

          if (filter === 'all') {
            item.style.display = '';
          } else if (filter === 'assessment' && eventType.startsWith('assessment_')) {
            item.style.display = '';
          } else if (filter === 'media' && eventType.startsWith('media_')) {
            item.style.display = '';
          } else {
            item.style.display = 'none';
          }
        });
      });
    });
  },

  /**
   * Initialize preview modals
   */
  initPreviews() {
    const previewButtons = document.querySelectorAll('.timeline-preview-btn');

    previewButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const eventId = this.dataset.eventId;
        const eventType = this.dataset.eventType;

        // Show loading state
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';

        // Load preview content (could use HTMX or fetch API)
        // For now, using simple modal with pre-loaded data
        PatientTimeline.showPreviewModal(eventType, eventId);

        // Reset button state
        this.disabled = false;
        this.innerHTML = '<i class="fas fa-eye"></i> Quick Preview';
      });
    });
  },

  /**
   * Show preview modal
   */
  showPreviewModal(eventType, eventId) {
    // Implementation depends on preview data structure
    // Could use Bootstrap modal or custom overlay
  },

  /**
   * Initialize all timeline features
   */
  init() {
    this.initFilters();
    this.initPreviews();
  }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('timeline-card')) {
    PatientTimeline.init();
  }
});
```

#### 3. Timeline Styles
**File**: `static/css/patient-timeline.css`

```css
/* Timeline Container */
.timeline {
  position: relative;
  padding: 20px 0;
  margin: 0;
}

/* Vertical timeline line */
.timeline::before {
  content: '';
  position: absolute;
  left: 30px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #dee2e6;
}

/* Timeline Item */
.timeline-item {
  position: relative;
  padding-left: 70px;
  margin-bottom: 30px;
  min-height: 60px;
}

/* Timeline Marker (circle with icon) */
.timeline-marker {
  position: absolute;
  left: 0;
  top: 0;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 2;
}

/* Timeline Content */
.timeline-content {
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 15px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.timeline-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.timeline-date {
  font-size: 0.875rem;
}

.timeline-description {
  margin-bottom: 10px;
  color: #495057;
}

.timeline-actions {
  display: flex;
  gap: 8px;
}

/* Responsive Design */
@media (max-width: 768px) {
  .timeline::before {
    left: 20px;
  }

  .timeline-item {
    padding-left: 55px;
  }

  .timeline-marker {
    width: 40px;
    height: 40px;
    font-size: 1.2rem;
  }

  .timeline-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .timeline-actions {
    flex-direction: column;
    width: 100%;
  }

  .timeline-actions .btn {
    width: 100%;
  }
}

/* Accessibility */
.timeline-item:focus-within {
  outline: 2px solid #007bff;
  outline-offset: 4px;
}

/* Animation for filtered items */
.timeline-item {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.timeline-item[style*="display: none"] {
  opacity: 0;
  transform: translateX(-10px);
}
```

## Data Optimization Strategy

### Queryset Optimization
```python
def get_patient_timeline_events(patient):
    # Use select_related for ForeignKey relationships
    gm_assessments = patient.gmassessment_set.select_related(
        'video_file',
        'added_by'
    ).all()

    # Use prefetch_related for ManyToMany
    cdic_records = patient.cdicrecord_set.prefetch_related(
        'developmental_concerns'
    ).all()

    # Fetch all related data in single queries
    videos = patient.video_files.select_related('uploaded_by').all()
    attachments = patient.attachments.select_related('uploaded_by').all()

    # ... aggregate and return events
```

### Caching Strategy (Future Enhancement)
```python
from django.core.cache import cache

def get_patient_timeline_events(patient, use_cache=True):
    cache_key = f'patient_timeline_{patient.id}'

    if use_cache:
        cached_events = cache.get(cache_key)
        if cached_events:
            return cached_events

    events = _build_timeline_events(patient)

    # Cache for 5 minutes
    cache.set(cache_key, events, 300)

    return events
```

## Security Considerations

1. **Access Control**: Timeline respects existing `@login_required` decorator
2. **URL Generation**: Uses Django's `reverse()` to prevent URL injection
3. **XSS Protection**: All user-generated content auto-escaped by Django templates
4. **CSRF**: Read-only component, no forms to protect
5. **Data Exposure**: Only shows data user already has access to via existing views

## Accessibility Compliance

### WCAG 2.1 AA Requirements
- **Keyboard Navigation**: All interactive elements (filter buttons, preview buttons) keyboard accessible
- **ARIA Labels**: Proper `role` and `aria-label` attributes on controls
- **Color Contrast**: Minimum 4.5:1 contrast ratio for text
- **Focus Indicators**: Visible focus states for keyboard users
- **Semantic HTML**: Proper heading hierarchy and landmark regions
- **Screen Reader Support**: Descriptive link text and button labels

### Implementation
```html
{# Accessible filter controls #}
<div class="btn-group" role="group" aria-label="Filter timeline events">
  <button type="button"
          class="btn btn-outline-primary active"
          data-filter="all"
          aria-pressed="true">
    All Events
  </button>
  {# ... more buttons with aria-pressed ... #}
</div>

{# Skip link for keyboard users #}
<a href="#timeline-content" class="sr-only sr-only-focusable">
  Skip to timeline
</a>
```

## Performance Considerations

### Expected Load Times
- **10 events**: <50ms additional render time
- **50 events**: <200ms additional render time
- **100 events**: <500ms additional render time
- **500+ events**: Consider pagination (future enhancement)

### Optimization Techniques
1. **Database**: `select_related` and `prefetch_related` for N+1 query prevention
2. **Template**: Minimal logic in templates, preprocessing in view
3. **CSS**: Single stylesheet loaded once, cached by browser
4. **JavaScript**: Vanilla JS with no framework overhead
5. **Icons**: Font Awesome already loaded globally

## Testing Strategy

### Unit Tests
- Timeline event aggregation function
- Event sorting logic
- Datetime formatting helpers
- Age calculation at event time

### Integration Tests
- Patient view renders timeline card
- Filter functionality works correctly
- Preview modals load proper data
- Links open in new windows

### Accessibility Tests
- Keyboard navigation through all controls
- Screen reader compatibility (NVDA/JAWS)
- Color contrast validation
- Focus indicator visibility

### Responsive Tests
- Desktop (1920px, 1440px, 1024px)
- Tablet (768px, 820px)
- Mobile (375px, 414px, 360px)

## Error Handling

### Missing Data Scenarios
- **No events**: Display friendly message "No timeline events yet"
- **Missing assessment data**: Show event with "Details unavailable"
- **Deleted related objects**: Filter out orphaned events
- **Invalid datetimes**: Log error, skip event, continue rendering

### Exception Handling
```python
def get_patient_timeline_events(patient):
    events = []

    try:
        # Birth event (always present)
        events.append(create_birth_event(patient))
    except Exception as e:
        logger.error(f"Error creating birth event for patient {patient.id}: {e}")

    try:
        # GMA events
        for gma in patient.gmassessment_set.all():
            events.append(create_gma_event(gma))
    except Exception as e:
        logger.error(f"Error loading GMA events for patient {patient.id}: {e}")

    # ... continue for other event types with individual try/except ...

    return sorted(events, key=lambda e: e.get('datetime', timezone.now()), reverse=True)
```

## Future Enhancements (Out of Scope)

1. **Pagination**: Implement if timeline exceeds 100 events
2. **Date Range Filtering**: Allow filtering by custom date ranges
3. **Export Functionality**: PDF or CSV export of timeline
4. **Manual Events**: Allow adding clinical events manually
5. **Event Notifications**: Alert users to new events
6. **Timeline Sharing**: Generate shareable timeline views
7. **Advanced Filtering**: Multi-select event types, keyword search
8. **Analytics**: Track which events are most viewed

## Dependencies and Integration Points

### Existing System Integration
- **Patient Model**: Source of birth event and related querysets
- **Assessment Models**: GMAssessment, HINEAssessment, DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment
- **Media Models**: Video, Attachment
- **URL Configuration**: Uses existing URL patterns for detail views
- **Template System**: Extends `src/base.html`, follows AdminLTE patterns
- **Static Files**: Integrates with existing asset pipeline

### External Dependencies
- Bootstrap 4.6 (already present)
- Font Awesome 6.4 (already present)
- jQuery 3.6 (already present, for Bootstrap components)

No new external dependencies required.
