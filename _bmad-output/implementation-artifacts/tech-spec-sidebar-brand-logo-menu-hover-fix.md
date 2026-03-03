---
title: 'Sidebar Brand Logo & Menu Hover Fix'
slug: 'sidebar-brand-logo-menu-hover-fix'
created: '2026-03-03'
status: 'completed'
stepsCompleted: [1, 2, 3, 4, 5, 6]
tech_stack: ['Django 4.2', 'AdminLTE 3.2', 'Bootstrap 4.6']
files_to_modify:
  - 'templates/src/main_sidebar_menu.html'
  - 'static/css/ndas-sidebar.css'
code_patterns: ['institution_context processor', 'user_type/is_superadmin context vars', 'AdminLTE brand-link pattern']
test_patterns: []
---

# Tech-Spec: Sidebar Brand Logo & Menu Hover Fix

**Created:** 2026-03-03

## Overview

### Problem Statement

The left-side main navigation sidebar has four UX issues:

1. **Logo not displaying properly** — The brand-link area shows the default AdminLTE wrench fallback instead of the institution's logo. When no institution logo is uploaded, there is no institution-specific fallback (just a generic unrelated icon).
2. **No institution name tooltip** — Hovering over the brand-link gives no indication of which institution is active.
3. **Brand-link click always goes to `home`** — Regardless of user role, clicking the brand area redirects to the generic patient dashboard. ADMIN users should reach the Institution Admin Dashboard; SUPERADMIN should reach the Superadmin Dashboard (or Institution Selector if no institution is active); regular USER stays on `home`.
4. **Menu items visually resize on hover** — The `.nav-icon` scale transform (110%) makes menu items appear to grow on hover. For treeview sub-items, `border-left` is only added on hover (not reserved in normal state), causing a horizontal layout shift each time the cursor enters.

### Solution

Pure template + CSS changes — no backend views, models, or URLs required:

1. Rewrite the brand-link opening `<a>` tag in `main_sidebar_menu.html`: conditionally set `href` by user role and add a `title` tooltip attribute.
2. Replace the logo `{% if %}` block in `main_sidebar_menu.html`: show the institution logo at correct size (no circular crop), show an initial-letter badge when the institution has no logo, and keep the original fallback only when there is no active institution at all.
3. Fix `ndas-sidebar.css`: replace `transform: scale(1.1)` with `opacity` on icon hover; pre-reserve `border-left` space on treeview items.

### Scope

**In Scope:**
- `templates/src/main_sidebar_menu.html` — brand-link `<a>` tag (href + title) and logo `{% if %}` block
- `static/css/ndas-sidebar.css` — icon hover rule, treeview nav-link normal + hover rules

**Out of Scope:**
- Backend views, models, migrations, URL changes
- Navbar, footer, or any other template
- Logo upload/management (handled separately at `institution:institution-settings`)
- Any other sidebar section (menu items, referral badge, admin links)

---

## Context for Development

### Codebase Patterns

**Institution context variables** — injected by `institution/context_processors.py` into every authenticated template (no extra imports needed in templates):

| Variable | Type | Value |
|---|---|---|
| `active_institution` | `Institution` object or `None` | `None` when SUPERADMIN has not context-switched |
| `user_type` | `str` | `'SUPERADMIN'`, `'ADMIN'`, or `'USER'` |
| `is_superadmin` | `bool` | Shorthand for `user_type == 'SUPERADMIN'` |

**CSS load order** (from `templates/src/basic_plane.html`):
1. AdminLTE 3.2 CDN — base sidebar styles
2. `custom_css.css` — minor border-radius override for nav-link
3. `ndas-sidebar.css` ← **our file, loads last** — specificity is sufficient without `!important`

**AdminLTE brand-link convention** — `<a class="brand-link">` wraps `<img class="brand-image">` (expected 33×33px) and `<span class="brand-text">`. AdminLTE adds elevation shadow via `elevation-3` class.

**Existing hover rules causing the problem (in `ndas-sidebar.css`):**

```css
/* Lines 34–43 — icon always transitions, scales on hover */
.nav-sidebar .nav-icon {
  transition: all 0.3s ease;
  width: 20px;
  text-align: center;
}
.nav-sidebar .nav-link:hover .nav-icon {
  transform: scale(1.1);   /* ← causes visual size jump */
}

/* Lines 58–67 — treeview normal state has no border-left reserved */
.nav-treeview .nav-item .nav-link {
  margin: 1px 5px;
  padding-left: 35px;
  font-size: 0.9rem;
  /* no border-left here → layout shift on hover */
}
.nav-treeview .nav-item .nav-link:hover {
  background-color: rgba(255, 255, 255, 0.08) !important;
  border-left: 2px solid rgba(255, 255, 255, 0.3);  /* ← appears from nothing */
}
```

**Existing brand-link block (lines 7–21 of `main_sidebar_menu.html`) to be replaced:**

```django
{# Story 3.3 — Institution brand-logo slot (FR58) #}
<a href="{% url 'home' %}" class="brand-link">
  {% if active_institution and active_institution.logo %}
    <img src="{{ active_institution.logo.url }}"
         class="brand-image elevation-3"
         alt="{{ active_institution.name }}"
         style="max-height:33px; max-width:33px; object-fit:contain;">
  {% else %}
    <img src="{% static 'img/AdminLTELogo.png' %}"
         class="brand-image img-circle elevation-3"
         alt="NDAS">
  {% endif %}
  <span class="brand-text font-weight-light">
    {% if active_institution %}{{ active_institution.name|truncatechars:20 }}{% else %}NDAS{% endif %}
  </span>
</a>
```

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `templates/src/main_sidebar_menu.html` | Sidebar template — brand-link block lines 7–21 to replace |
| `static/css/ndas-sidebar.css` | Sidebar CSS — icon hover lines 40–43, treeview hover lines 64–67 |
| `institution/context_processors.py` | Source of `active_institution`, `user_type`, `is_superadmin` |
| `institution/models.py` | `Institution.logo` is nullable `ImageField`; `Institution.name` is `CharField` |
| `institution/urls.py` | Existing URLs: `institution:institution-admin-dashboard`, `institution:superadmin-dashboard`, `institution:institution-selector` |
| `templates/src/basic_plane.html` | Confirms `ndas-sidebar.css` loads after AdminLTE (line 29) |

### Technical Decisions

- **No new files**: all changes are edits to the two existing files.
- **No backend changes**: all four issues are pure template/CSS.
- **Logo fallback**: when `active_institution` has no `.logo`, render a `<span>` initial-letter badge (dark background, white text, 33×33px, 4px border-radius). This is institution-specific and meaningful; the generic AdminLTE wrench is shown only when there is no active institution at all.
- **`img-circle` removal**: the institutional logo path must not use `img-circle` — circular crop is appropriate only for profile avatars, not logos. The default NDAS fallback keeps `img-circle` (no regression).
- **Brand href routing**: inline Django template `{% if %}` blocks produce the URL string — no JS redirect — preserving native browser right-click / middle-click behaviour.
- **Badge does not use `brand-image` class**: AdminLTE's `.brand-image` sets `opacity: .8`. The badge `<span>` replicates the needed layout properties (`float: left; margin: -.8rem .8rem -.8rem 0`) inline instead of inheriting the class, so opacity is full (1.0). As a consequence, `.brand-link:hover .brand-image { transform: scale(1.05) }` in `ndas-sidebar.css` will not target the badge — only the `<img>` elements, which is the intended behaviour.
- **Treeview border-left unified to 2px across all states**: normal (transparent), hover (white 30%), and active (white solid) all use `border-left: 2px`. Previously the active state used 3px, causing a 1px shift on activation.
- **Tasks 3 + 4 are one atomic HTML edit**: the `<a>` opening tag (Task 3) and logo block (Task 4) together replace a contiguous block of lines 7–21. A developer should apply both in a single edit operation.

---

## Implementation Plan

### Tasks

- [x] **Task 1: Fix icon hover — replace `scale` with `opacity` in CSS**
  - File: `static/css/ndas-sidebar.css`
  - Action: Replace lines 40–43:
    ```css
    /* BEFORE */
    .nav-sidebar .nav-link:hover .nav-icon {
      transform: scale(1.1);
    }
    ```
    With:
    ```css
    /* AFTER */
    .nav-sidebar .nav-link:hover .nav-icon {
      opacity: 0.85;
    }
    ```
  - Notes: `opacity` is a composited visual effect — it does not affect layout dimensions. The `transition: all 0.3s ease` on `.nav-sidebar .nav-icon` (line 35) will animate this smoothly. No other icon rules change.

- [x] **Task 2: Fix treeview border-left — pre-reserve space and unify border width across all states**
  - File: `static/css/ndas-sidebar.css`
  - Action: Replace lines 58–73 (the treeview nav-link normal, hover, **and active** block — all three rules must be updated together):
    ```css
    /* BEFORE — lines 58–73 */
    .nav-treeview .nav-item .nav-link {
      margin: 1px 5px;
      padding-left: 35px;
      font-size: 0.9rem;
    }

    .nav-treeview .nav-item .nav-link:hover {
      background-color: rgba(255, 255, 255, 0.08) !important;
      border-left: 2px solid rgba(255, 255, 255, 0.3);
    }

    .nav-treeview .nav-item .nav-link.active {
      background-color: rgba(255, 255, 255, 0.15) !important;
      border-left: 3px solid #ffffff;
      font-weight: 500;
    }
    ```
    With:
    ```css
    /* AFTER */
    .nav-treeview .nav-item .nav-link {
      margin: 1px 5px;
      padding-left: 35px;
      font-size: 0.9rem;
      border-left: 2px solid transparent; /* reserve space — prevents hover shift */
    }

    .nav-treeview .nav-item .nav-link:hover {
      background-color: rgba(255, 255, 255, 0.08) !important;
      border-left: 2px solid rgba(255, 255, 255, 0.3);
    }

    .nav-treeview .nav-item .nav-link.active {
      background-color: rgba(255, 255, 255, 0.15) !important;
      border-left: 2px solid #ffffff; /* unified to 2px — was 3px, caused 1px shift vs normal/hover */
      font-weight: 500;
    }
    ```
  - Notes: All three states (normal, hover, active) must use the same `border-left` **width** (2px). Previously the active state used 3px, which caused a 1px horizontal shift whenever an item became active. Only the border colour changes between states — the space is always reserved. **Do not touch any other rules in this file.**

- [x] **Task 3 + 4 (atomic): Rewrite the brand-link block in the sidebar template**
  - File: `templates/src/main_sidebar_menu.html`
  - Action: Replace lines 7–21 (the entire brand-link block, from the `{# Story 3.3 #}` comment through the closing `</a>`) with:
    ```django
    {# Story 3.3 — Institution brand-logo slot (FR58) #}
    {# Brand-link: role-conditioned href + institution name tooltip #}
    {% if is_superadmin and active_institution %}
    <a href="{% url 'institution:superadmin-dashboard' %}" class="brand-link"
       title="{{ active_institution.name }}">
    {% elif is_superadmin %}
    <a href="{% url 'institution:institution-selector' %}" class="brand-link"
       title="NDAS">
    {% elif user_type == 'ADMIN' %}
    <a href="{% url 'institution:institution-admin-dashboard' %}" class="brand-link"
       title="{{ active_institution.name }}">
    {% else %}
    <a href="{% url 'home' %}" class="brand-link"
       title="{% if active_institution %}{{ active_institution.name }}{% else %}NDAS{% endif %}">
    {% endif %}
      {% if active_institution and active_institution.logo %}
        <img src="{{ active_institution.logo.url }}"
             class="brand-image elevation-3"
             alt="{{ active_institution.name }}"
             style="width:33px; height:33px; object-fit:contain;">
      {% elif active_institution %}
        {# Institution active but no logo — show initial-letter badge #}
        {# Do NOT use class="brand-image" here: AdminLTE sets opacity:.8 on that class, which fades the badge #}
        {# Replicate brand-image layout manually via float+margin in inline style #}
        <span class="elevation-3 d-flex align-items-center justify-content-center"
              style="width:33px; height:33px; background:#495057; color:#fff;
                     font-weight:700; font-size:1rem; border-radius:4px;
                     float:left; margin:-.8rem .8rem -.8rem 0;">
          {{ active_institution.name|slice:":1"|upper }}
        </span>
      {% else %}
        <img src="{% static 'img/AdminLTELogo.png' %}"
             class="brand-image img-circle elevation-3"
             alt="NDAS">
      {% endif %}
      <span class="brand-text font-weight-light">
        {% if active_institution %}{{ active_institution.name|truncatechars:20 }}{% else %}NDAS{% endif %}
      </span>
    </a>
    ```
  - Notes:
    - `{% load static %}` is already on line 1 of the file — no new load tag needed.
    - `is_superadmin`, `user_type`, `active_institution` are all injected by `institution_context` context processor — available with no extra view code.
    - The `else` branch (USER) has an inline conditional for `title` because `active_institution` may or may not be set for a USER.
    - ADMIN users always have `active_institution` set — guaranteed by `SubscriptionCheckMiddleware` and `UserActivityMiddleware` in the middleware stack. The ADMIN branch's direct `{{ active_institution.name }}` is safe; Django template attribute lookup silently produces empty string on None, so no crash risk even in edge cases.
    - No `img-circle` on the institutional logo path — only on the NDAS fallback (no regression).
    - The `<span>` badge deliberately does **not** use `class="brand-image"` — AdminLTE's `.brand-image` rule sets `opacity: .8`, which would make the badge look faded. Instead, the layout properties normally provided by `.brand-image` (`float: left; margin: -.8rem .8rem -.8rem 0`) are replicated in the inline style. `elevation-3` is kept for the drop shadow.
    - Because the badge `<span>` does not carry `class="brand-image"`, the existing `ndas-sidebar.css` rule `.brand-link:hover .brand-image { transform: scale(1.05) }` (lines 17–19) will **not** target it — the badge is immune to the hover scale effect. The `<img>` logo path retains the scale as intended.

### Acceptance Criteria

- [x] **AC1 — ADMIN click routing**: Given a user with `user_type == 'ADMIN'`, when they click the brand logo or text, then the browser navigates to `institution:institution-admin-dashboard` (URL `/institution/admin/`).

- [x] **AC2 — SUPERADMIN with active institution click routing**: Given a SUPERADMIN who has performed a context switch to an institution (so `active_institution` is not None), when they click the brand logo or text, then the browser navigates to `institution:superadmin-dashboard` (URL `/institution/superadmin/`).

- [x] **AC3 — SUPERADMIN without active institution click routing**: Given a SUPERADMIN who has not yet switched to any institution (`active_institution` is None), when they click the brand logo or text, then the browser navigates to `institution:institution-selector` (URL `/institution/`).

- [x] **AC4 — USER click routing**: Given a regular user (`user_type == 'USER'`), when they click the brand logo or text, then the browser navigates to `home`.

- [x] **AC5 — Tooltip with active institution**: Given any logged-in user where `active_institution` is set, when they hover over the brand-link area, then a native browser tooltip displays the full institution name (not truncated).

- [x] **AC6 — Tooltip without active institution**: Given a SUPERADMIN with no active institution, when they hover over the brand-link area, then the tooltip displays "NDAS".

- [x] **AC7 — Logo renders when institution has a logo**: Given an institution with a logo uploaded, when the sidebar is rendered, then the institution's logo image is displayed at 33×33px with `object-fit: contain` and no circular crop.

- [x] **AC8 — Initial-letter badge renders when institution has no logo**: Given an institution with no logo uploaded (`active_institution.logo` is falsy), when the sidebar is rendered, then a dark square badge (33×33px, `#495057` background) containing the first letter of the institution name (uppercase, white, bold) is displayed in the brand-image position.

- [x] **AC9 — Default NDAS logo fallback preserved**: Given no active institution (SUPERADMIN before context switch), when the sidebar is rendered, then the default circular AdminLTE logo (`img/AdminLTELogo.png`) is displayed — identical to the original behaviour.

- [x] **AC10 — No layout shift on main nav item hover**: Given any top-level sidebar menu item (Dashboard, Add Patient, Search, etc.), when the user moves the cursor over it, then the row height and width do not change (no visible jump or expansion).

- [x] **AC11 — No layout shift on treeview item hover**: Given any treeview sub-item (within Assessments, Files & Media, Reports, Administration, or Support), when the user moves the cursor over it, then the icon and text do not shift horizontally. The left accent border should appear in place without moving surrounding content.

- [x] **AC12 — Subtle hover feedback retained**: Given any sidebar menu item, when the user hovers, then a subtle visual change is still visible (background tint for main items; left border colour change for treeview items; icon opacity change for all items). No hover feedback is removed entirely.

- [x] **AC13 — No layout shift on treeview active state**: Given a treeview sub-item that is currently active (e.g. navigating directly to the GM Assessment page), then the left border of that item does not cause a horizontal shift compared to non-active items — the left border space is identical in width (2px) whether the item is normal, hovered, or active.

- [x] **AC14 — Badge renders at full opacity**: Given an institution with no logo, when the sidebar brand badge is rendered, then the initial-letter badge displays at full opacity (not faded), with white text clearly legible against the `#495057` background.

---

## Additional Context

### Dependencies

- `active_institution`, `user_type`, `is_superadmin` are guaranteed available in all authenticated templates via `institution/context_processors.py`, which is registered in `settings.TEMPLATES[0]['OPTIONS']['context_processors']`. No additional view changes required.
- All three institution dashboard URL names (`institution:institution-admin-dashboard`, `institution:superadmin-dashboard`, `institution:institution-selector`) already exist in `institution/urls.py`. No new URL definitions needed.
- Bootstrap 4.6 utility `d-flex`, `align-items-center`, `justify-content-center` — already loaded globally via CDN in `basic_plane.html`. The initial-letter badge `<span>` uses these safely.
- `{% static 'img/AdminLTELogo.png' %}` — existing file, unchanged, used only in the no-institution fallback branch.

### Testing Strategy

Manual browser verification only (pure template/CSS — no Django unit tests warranted):

1. **ADMIN routing** — Log in as an ADMIN user → verify brand area href resolves to `/institution/admin/` → click → lands on institution admin dashboard.
2. **SUPERADMIN routing (no context)** — Log in as SUPERADMIN, stay on institution selector screen → verify brand href resolves to `/institution/` → click → remains on institution selector.
3. **SUPERADMIN routing (with context)** — As SUPERADMIN, context-switch to any institution → verify brand href resolves to `/institution/superadmin/` → click → lands on superadmin dashboard.
4. **USER routing** — Log in as a regular USER → verify brand href resolves to `/` (home) → click → lands on patient dashboard.
5. **Tooltip** — With active institution → hover brand area → native tooltip shows full institution name. Without active institution → tooltip shows "NDAS".
6. **Logo — with logo** — Use an institution that has a logo uploaded → sidebar shows institution logo at 33×33px, no circular crop.
7. **Logo — no logo** — Use an institution that has no logo → sidebar shows dark badge with institution initial letter, bold white, centred.
8. **Logo — no institution** — Log in as SUPERADMIN before context switch → sidebar shows original circular NDAS logo (regression check).
9. **Hover — main items** — Hover each top-level nav item slowly → no height or width change observed.
10. **Hover — treeview items** — Expand Assessments, Files & Media, Reports, Administration, Support → hover each sub-item → text and icon do not shift horizontally.

### Notes

- **Tasks 3 + 4 are declared as one atomic task** because they together replace a contiguous HTML block (lines 7–21). A developer should apply these as a single edit, not two separate edits that leave broken HTML between them.
- **`transition: all` caution**: `ndas-theme.css` sets `transition: all var(--transition-speed) ease-in-out` on `.nav-sidebar .nav-link`. This transitions every property, including `border-left`. By adding `border-left: 2px solid transparent` to the normal state, the colour will animate smoothly on hover (transparent → white at 30% opacity) — this is a desirable side effect.
- **Future consideration (out of scope)**: the `brand-text` currently uses `truncatechars:20`. Long institution names are cut off with "…". If institution names are commonly longer than 20 chars, consider bumping to 24 or using CSS `overflow: hidden; text-overflow: ellipsis` instead of server-side truncation — but this is a separate UX decision.
- **SUPERADMIN tooltip edge case**: when `is_superadmin` is true and `active_institution` is None, the `title` is hardcoded to `"NDAS"` (the SUPERADMIN `elif` branch). This is correct — there is no institution name to show.

## Review Notes

- Adversarial review completed (2026-03-03)
- Findings: 11 total, 4 fixed, 7 skipped
- Resolution approach: auto-fix (real findings only)
- **Fixed:** F1 (AdminLTE version comment on badge margin), F2 (narrowed `.nav-icon` transition from `all` to `opacity`), F5 (added `aria-label` to all brand-link branches), F6 (added magic-string comment for `user_type == 'ADMIN'`)
- **Skipped as spec-intentional:** F3 (logo scale vs icon opacity inconsistency — intentional per spec), F4 (fixed img dimensions — spec-mandated)
- **Skipped as noise:** F7 (frontmatter stepsCompleted), F8 (opacity UX perception), F9 (single-letter badge ambiguity), F10 (SUPERADMIN branch readability), F11 (open-tag-inside-if pattern)
