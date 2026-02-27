---
title: 'Nav & Sidebar Institution + Referral UX Improvements'
slug: 'nav-sidebar-institution-referral-ux'
created: '2026-02-27'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Django 4.2', 'AdminLTE 3.2', 'Bootstrap 4.6', 'HTMX']
files_to_modify:
  - 'templates/src/navbar.html'
  - 'templates/src/main_sidebar_menu.html'
  - 'templates/referral/notification_count_badge.html'
code_patterns: ['institution_tags', 'is_superadmin context', 'HTMX OOB swap']
test_patterns: []
---

# Tech-Spec: Nav & Sidebar Institution + Referral UX Improvements

**Created:** 2026-02-27

## Overview

### Problem Statement

The sidebar and top navbar have three UX gaps introduced by the Phase 2 multi-institution rollout:

1. **SUPERADMIN has no sidebar access to institution management** (institution-selector, institution-add, superadmin-dashboard) — these views exist and are deployed but are completely absent from the sidebar, forcing SUPERADMIN to rely on direct URL entry.
2. **The referral notification bell has no "See All" footer link** — users receiving notifications cannot navigate to the Referral Inbox in one click from the dropdown.
3. **The Referral Inbox sidebar item has a "Story 5.2 placeholder" comment but no badge** — users can't see unread referral count in the sidebar.

Secondary gaps:
- ADMIN institution section is unlabelled and missing `institution-settings`.
- The navbar bell is conditionally hidden when `request.institution` is None (SUPERADMIN pre-context-switch); the "View All Referrals" footer is scoped to the same guard — it is only reachable for institution-scoped users. SUPERADMIN can still access the Referral Inbox via the sidebar link.

### Solution

Pure-template changes (no backend views or URLs needed):

1. Add SUPERADMIN institution management links inside the existing `Administration` sidebar section, gated by `{% if is_superadmin %}`.
2. Add `institution-settings` link and a `nav-header` to the existing ADMIN institution block for clarity.
3. Add "View All Referrals →" as a persistent `dropdown-footer` anchor in `navbar.html`, outside the HTMX-loaded notification panel container.
4. Add a sidebar referral badge via HTMX Out-of-Band (OOB) swap — piggybacks on the navbar bell's existing 60s poll with zero extra HTTP requests.

### Scope

**In Scope:**
- `templates/src/navbar.html` — "View All Referrals →" footer link in bell dropdown
- `templates/src/main_sidebar_menu.html` — SUPERADMIN institution items, ADMIN items cleanup, sidebar referral badge span
- `templates/referral/notification_count_badge.html` — OOB swap element for sidebar badge sync
- Active-state URL detection updates for new items

**Out of Scope:**
- No new Django views, URLs, or models
- No CSS framework changes
- No changes to notification logic or HTMX polling intervals
- No changes to `notification_panel.html` or `notification_count` view

---

## Context for Development

### Codebase Patterns

- `is_superadmin` — boolean, injected by `institution/context_processors.py:institution_context()`. Use `{% if is_superadmin %}` in templates. **Never** use `{% if request.user.is_superuser %}` (breaks SUPERADMIN context switching — confirmed in `project-context.md`).
- `user_type` — string ('SUPERADMIN' | 'ADMIN' | 'USER'), same context processor. `UserType.SUPERADMIN` implies `is_superuser=True` on the Django user.
- `active_institution` — Institution object or None; None when SUPERADMIN has not yet selected a context. **Never** use `request.user.institution` in templates — use `active_institution`.
- `Administration` sidebar section gate: `{% if user.is_staff or user.is_superuser %}` — SUPERADMIN satisfies this (`is_superuser=True`). ADMIN users do **not** use this gate; they have their own `{% if user_type == 'ADMIN' %}` block.
- Sidebar active-state pattern: `{% if request.resolver_match.url_name == 'name' %}active{% endif %}`
- Sidebar menu-open pattern: `{% if 'keyword' in request.resolver_match.url_name %}menu-open{% endif %}`
- HTMX OOB swap: element in response with `hx-swap-oob="true"` and matching `id` gets swapped into DOM independently of the primary swap target.
- **Phase 2 feature flag gate**: `MULTI_INSTITUTION_ENABLED` controls Phase 2 behaviour. When `False`, `InstitutionContextMiddleware` acts as a passthrough. The context processor still runs but `user_type` is effectively 'USER' for all users (no ADMIN/SUPERADMIN users exist in Phase 1), so `{% if is_superadmin %}` and `{% if user_type == 'ADMIN' %}` naturally resolve to False — the new sidebar items are invisible. No explicit feature-flag check needed in templates.
- **No inline scripts**: All changes are HTML attributes and anchor tags only. No `<script>` blocks introduced — CSP nonce (`{{ request.csp_nonce }}`) not required.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `templates/src/navbar.html` | Top navbar — has existing bell dropdown (lines 113–136) |
| `templates/src/main_sidebar_menu.html` | Sidebar — Administration section (lines 262–329), ADMIN institution block (331–345), REFERRALS section (213–225) |
| `templates/referral/notification_count_badge.html` | 3-line template returning `<span class="badge badge-warning navbar-badge">{{ count }}</span>` |
| `institution/context_processors.py` | Source of `is_superadmin`, `user_type`, `active_institution` |
| `institution/urls.py` | All institution URL names: `institution-selector`, `institution-add`, `superadmin-dashboard`, `superadmin-reports`, `institution-settings` |
| `referral/urls.py` | `referral-inbox`, `notification-count` |
| `referral/views.py:507-523` | `notification_count` view — confirmed render call: `return render(request, 'referral\notification_count_badge.html', {'count': count})`; returns `HttpResponse('')` when `not request.institution` |
| `templates/src/basic_plane.html:65` | HTMX CDN load — confirmed version: `htmx.org@1.9.12` (OOB requires ≥1.7 ✅) |

### Technical Decisions

- **OOB swap for sidebar badge**: The navbar bell already polls `notification-count` every 60s. Rather than adding a second HTMX element that also polls the same endpoint, we use HTMX OOB swap: `notification_count_badge.html` emits a secondary `<span hx-swap-oob="true" id="sidebar-referral-badge">` in addition to the primary badge. HTMX **strips OOB elements from the response body before applying the primary swap** — so the primary target `#notification-bell-count` receives only the navbar badge span (or an empty body when count=0). The OOB element is then applied independently. Zero-count path: when count=0, the primary `{% if count > 0 %}` emits nothing, and the OOB span with `style="display:none"` is the only content in the response — HTMX strips it for the OOB swap and the primary target is cleared to empty. This is the correct result. Confirmed: project uses HTMX 1.9.12 (≥1.7, OOB supported).
- **"View All Referrals" placement**: Added directly in `navbar.html` outside `#notification-panel-container` so it renders immediately without waiting for the HTMX panel load, and is always visible even when the user has no notifications.
- **No backend changes**: All requirements are satisfiable purely in templates.
- **ADMIN institution block is intentionally flat (non-treeview)**: The three ADMIN institution items (Admin Dashboard, Clinicians, Institution Settings) are rendered as flat `<li>` links under a `nav-header`, not as a collapsible treeview group. This is deliberate — three items don't warrant a collapsible drawer. A future dev should not "fix" this by wrapping in a treeview unless the section grows beyond 4–5 items.

---

## Implementation Plan

### Tasks

**Task 1 — Add "View All Referrals →" footer to navbar bell dropdown**
- **File:** `templates/src/navbar.html`
- **Where:** Inside the bell `<div class="dropdown-menu dropdown-menu-lg dropdown-menu-right">`, after the closing `</div>` of `#notification-panel-container` and before the closing `</div>` of the dropdown-menu itself (line 133 closes the container div, line 134 closes the dropdown-menu — insert between them)
- **Action:** Insert a `<div class="dropdown-divider"></div>` followed by an `<a>` anchor with class `dropdown-item dropdown-footer` linking to `{% url 'referral:referral-inbox' %}`

```html
<!-- INSERT between line 133 (</div> closes #notification-panel-container) and line 134 (</div> closes .dropdown-menu) -->
<div class="dropdown-divider"></div>
<a href="{% url 'referral:referral-inbox' %}" class="dropdown-item dropdown-footer text-center">
  <i class="fas fa-arrow-right mr-1"></i> View All Referrals
</a>
```

---

**Task 2 — Add sidebar referral badge span**
- **File:** `templates/src/main_sidebar_menu.html`
- **Where:** Referral Inbox nav-item `<p>` tag (currently line 218–223)
- **Action:** Wrap the "Referral Inbox" text and add an OOB-target badge span

```html
<!-- REPLACE the existing Referral Inbox <a> content -->
<a href="{% url 'referral:referral-inbox' %}" class="nav-link {% if request.resolver_match.url_name == 'referral-inbox' %}active{% endif %}">
  <i class="nav-icon fas fa-share-square"></i>
  <p>
    Referral Inbox
    <span id="sidebar-referral-badge" class="right badge badge-warning" style="display:none"></span>
  </p>
</a>
```

---

**Task 3 — Update notification_count_badge.html to OOB-sync sidebar badge**
- **File:** `templates/referral/notification_count_badge.html`
- **Action:** Append OOB swap element after the existing navbar badge span

```html
{% if count > 0 %}
<span class="badge badge-warning navbar-badge">{{ count }}</span>
{% endif %}
{# OOB: sync sidebar Referral Inbox badge. Explicit display style on both branches — no implicit browser defaults. #}
<span id="sidebar-referral-badge"
      hx-swap-oob="true"
      class="right badge badge-warning"
      style="{% if count %}display:inline{% else %}display:none{% endif %}">
  {% if count %}{{ count }}{% endif %}
</span>
```

---

**Task 4 — Add SUPERADMIN institution management items to Administration section**
- **File:** `templates/src/main_sidebar_menu.html`
- **Where:** Inside the Administration `<ul class="nav nav-treeview">`, after the existing "Activity Logs" item and before `{% if user.is_superuser %}` (currently around line 305)
- **Action:** Insert SUPERADMIN-gated institution links

```html
<!-- INSERT before {% if user.is_superuser %} (Update Subscription block) -->
{% if is_superadmin %}
<li class="nav-item">
  <a href="{% url 'institution:institution-selector' %}"
     class="nav-link {% if request.resolver_match.url_name == 'institution-selector' %}active{% endif %}">
    <i class="far fa-circle nav-icon"></i>
    <p>All Institutions</p>
  </a>
</li>
<li class="nav-item">
  <a href="{% url 'institution:institution-add' %}"
     class="nav-link {% if request.resolver_match.url_name == 'institution-add' %}active{% endif %}">
    <i class="far fa-circle nav-icon"></i>
    <p>Add Institution</p>
  </a>
</li>
<li class="nav-item">
  <a href="{% url 'institution:superadmin-dashboard' %}"
     class="nav-link {% if request.resolver_match.url_name == 'superadmin-dashboard' %}active{% endif %}">
    <i class="far fa-circle nav-icon"></i>
    <p>Superadmin Dashboard</p>
  </a>
</li>
<li class="nav-item">
  <a href="{% url 'institution:superadmin-reports' %}"
     class="nav-link {% if request.resolver_match.url_name == 'superadmin-reports' %}active{% endif %}">
    <i class="far fa-circle nav-icon"></i>
    <p>Aggregate Reports</p>
  </a>
</li>
{% endif %}
```

---

**Task 5 — Update Administration menu-open condition for institution namespace**
- **File:** `templates/src/main_sidebar_menu.html`
- **Where:** Administration `<li class="nav-item ...">` opening tag (line 264)
- **Action:** Add `or (is_superadmin and request.resolver_match.namespace == 'institution')` to keep the menu open when SUPERADMIN navigates institution views

```django
{# CHANGE FROM: #}
class="nav-item {% if 'admin' in request.resolver_match.url_name %}menu-open{% endif %}"

{# CHANGE TO: #}
class="nav-item {% if 'admin' in request.resolver_match.url_name or (is_superadmin and request.resolver_match.namespace == 'institution') %}menu-open{% endif %}"
```

Apply the same update to the Administration `<a href="#">` `active` class condition (line 269).

---

**Task 6 — Improve ADMIN institution block: add header + settings link**
- **File:** `templates/src/main_sidebar_menu.html`
- **Where:** Lines 331–345 (the `{% if user_type == 'ADMIN' %}` block)
- **Action:** Add `nav-header`, add `institution-settings` link, add active check for settings
- **Clinician URL audit (confirmed):** The full set of clinician-related URL names in `institution/urls.py` is: `institution-clinician-list`, `institution-clinician-add`, `institution-clinician-toggle-status`. The toggle-status endpoint is a POST-only action with no standalone page, so it is correctly excluded from active-state detection. No other sub-pages exist — the active state for `institution-clinician-list` and `institution-clinician-add` is complete.

**BEFORE (current code to be replaced — verify this matches before editing):**
```html
{% if user_type == 'ADMIN' %}
<li class="nav-item">
  <a href="{% url 'institution:institution-admin-dashboard' %}" class="nav-link {% if request.resolver_match.url_name == 'institution-admin-dashboard' %}active{% endif %}">
    <i class="nav-icon fas fa-tachometer-alt"></i>
    <p>Admin Dashboard</p>
  </a>
</li>
<li class="nav-item">
  <a href="{% url 'institution:institution-clinician-list' %}" class="nav-link {% if request.resolver_match.url_name == 'institution-clinician-list' or request.resolver_match.url_name == 'institution-clinician-add' %}active{% endif %}">
    <i class="nav-icon fas fa-user-md"></i>
    <p>Clinicians</p>
  </a>
</li>
{% endif %}
```

**AFTER (replace entire block with):**
```html
{# REPLACE the existing {% if user_type == 'ADMIN' %} block #}
{% if user_type == 'ADMIN' %}
<li class="nav-header">MY INSTITUTION</li>
<li class="nav-item">
  <a href="{% url 'institution:institution-admin-dashboard' %}"
     class="nav-link {% if request.resolver_match.url_name == 'institution-admin-dashboard' %}active{% endif %}">
    <i class="nav-icon fas fa-tachometer-alt"></i>
    <p>Admin Dashboard</p>
  </a>
</li>
<li class="nav-item">
  <a href="{% url 'institution:institution-clinician-list' %}"
     class="nav-link {% if request.resolver_match.url_name == 'institution-clinician-list' or request.resolver_match.url_name == 'institution-clinician-add' %}active{% endif %}">
    <i class="nav-icon fas fa-user-md"></i>
    <p>Clinicians</p>
  </a>
</li>
<li class="nav-item">
  <a href="{% url 'institution:institution-settings' %}"
     class="nav-link {% if request.resolver_match.url_name == 'institution-settings' %}active{% endif %}">
    <i class="nav-icon fas fa-cog"></i>
    <p>Institution Settings</p>
  </a>
</li>
{% endif %}
```

---

### Acceptance Criteria

**AC1 — Navbar "View All Referrals" footer**
- **Given** any authenticated user with an active institution (`request.institution` is set) opens the navbar bell dropdown
- **When** the dropdown is visible
- **Then** a "View All Referrals" footer link is shown at the bottom of the dropdown panel
- **And** clicking it navigates to the Referral Inbox page (`/referral/inbox/`)
- **Edge case (loading):** Footer is visible even when the HTMX notification panel is still loading or shows "No notifications"
- **Known constraint:** SUPERADMIN who has not yet selected an institution context has no `request.institution`, so the bell (and this footer) are not rendered. They can still reach Referral Inbox via the sidebar "Referral Inbox" link. This is intentional and not a defect.

**AC2 — Sidebar referral badge (OOB sync)**
- **Given** a user has unread notifications (`count > 0`) and the navbar bell has polled
- **When** the bell HTMX poll completes
- **Then** the sidebar "Referral Inbox" item shows a yellow badge with the unread count
- **And** when count returns to 0, the sidebar badge is hidden (display:none)
- **Edge case:** On first page load (`hx-trigger="load"`) the sidebar badge is initialised correctly

**AC3 — SUPERADMIN institution items in Administration section**
- **Given** the logged-in user is SUPERADMIN (`is_superadmin=True`)
- **When** viewing the sidebar Administration section
- **Then** four new items appear: "All Institutions", "Add Institution", "Superadmin Dashboard", "Aggregate Reports"
- **And** the Administration menu stays open (`menu-open` class) when navigating any `institution:` namespace URL
- **And** the Administration menu stays open when navigating any URL whose `url_name` contains 'admin' (existing behaviour preserved)
- **And** the Administration menu is **closed** when SUPERADMIN navigates to an unrelated page (e.g., patient list, search) whose `url_name` does not contain 'admin' and whose namespace is not `institution`
- **And** the correct item is highlighted active on its respective page

**AC4 — ADMIN institution block improved**
- **Given** the logged-in user is ADMIN (`user_type == 'ADMIN'`)
- **When** viewing the sidebar
- **Then** a section header "MY INSTITUTION" appears above the institution items
- **And** three items are present: "Admin Dashboard", "Clinicians", "Institution Settings"
- **And** each item shows active state when its page is loaded

**AC5 — Non-regression**
- **Given** a USER (`user_type == 'USER'`) who is not staff/superuser
- **When** viewing the sidebar
- **Then** no Administration section, no Institution section, and no SUPERADMIN items are visible
- **And** the REFERRALS section is visible and the Referral Inbox link is accessible (`referral_inbox` view confirmed `@login_required` only — no role gate; accessible to all authenticated users)

---

## Additional Context

### Dependencies

- All institution URLs referenced are registered in `institution/urls.py` and confirmed deployed: `institution-selector`, `institution-add`, `superadmin-dashboard`, `superadmin-reports`, `institution-settings`, `institution-admin-dashboard`, `institution-clinician-list`, `institution-clinician-add`.
- `notification-count` endpoint at `referral/views.py:507` returns the badge partial — no changes needed.
- HTMX is loaded via `templates/src/basic_plane.html:65` — confirmed version **1.9.12** (CDN, integrity-hashed). OOB swap requires ≥ 1.7 — this project satisfies that requirement.

**Task dependency order (implement in this sequence):**
1. Task 1 — navbar footer (independent, touch `navbar.html`)
2. Task 2 — sidebar badge span (must precede Task 3; DOM target must exist before first poll)
3. Task 3 — OOB in badge template (depends on Task 2; deploy together)
4. Task 5 — menu-open condition update (do before Task 4 to keep the edit in one pass)
5. Task 4 — SUPERADMIN institution items (same file as Task 5; do in same edit pass)
6. Task 6 — ADMIN block improvements (independent, same file)

### Testing Strategy

Manual verification (no automated tests required for template-only changes):

1. Log in as SUPERADMIN → confirm Administration section shows All Institutions, Add Institution, Superadmin Dashboard, Aggregate Reports
2. Navigate to `/institution/` → confirm Administration menu stays open
3. Log in as ADMIN → confirm INSTITUTION section shows Admin Dashboard, Clinicians, Institution Settings
4. Log in as USER → confirm neither Administration nor Institution sections appear
5. Trigger a referral notification → confirm navbar badge count and sidebar badge count sync on next poll
6. Open bell dropdown → confirm "View All Referrals →" footer is always present
7. Click "View All Referrals →" → confirm redirect to Referral Inbox page

### Notes

- The bell visibility guard `{% if request.user.is_authenticated and request.institution %}` remains unchanged. The "View All Referrals" footer is **inside** this guard — appropriate, as referrals are institution-scoped.
- Existing "Referral Inbox" sidebar item visibility (all authenticated users) is unchanged.
- Task ordering: Tasks 2 and 3 must be deployed together (OOB swap requires the DOM target `#sidebar-referral-badge` to exist before the HTMX poll fires).
- **SUPERADMIN no-institution context (bell + sidebar badge)**: When SUPERADMIN is on the institution-selector screen and has not yet switched into an institution, `request.institution` is `None`. The `notification_count` view returns `HttpResponse('')` in this state — an empty response contains no OOB element, so the sidebar badge is never initialised during that session visit. This is acceptable: notifications are institution-scoped and SUPERADMIN has no institution context to notify against. The sidebar Referral Inbox link remains visible and accessible.
- **Empty response and OOB**: When `notification_count` returns `HttpResponse('')` (no institution context), HTMX receives an empty body. No OOB swap fires. The `#sidebar-referral-badge` span retains its initial `style="display:none"` state. This is the correct behaviour — no stale badge count shown.
