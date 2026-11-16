---
title: 'Page Header: Icon Removal, Compact Title & Right-Aligned Secondary Slot'
type: 'refactor'
created: '2026-11-16'
status: 'done'
review_loop_iteration: 1
context: ['{project-root}/CLAUDE.md']
baseline_commit: 'd6163ef6958fff953a44170a2eb260969e12d1f7'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The shared page-header-card pattern (e.g. `templates/patients/index.html`, screenshot `Screenshot 2026-11-16 161420.png`) renders a leading icon before an oversized (`h4`) title, and a badge + breadcrumb right-hand slot that wraps left-aligned instead of right-aligned — producing an unbalanced header across all 18 templates that use it.

**Approach:** Extract the header shell into a reusable `{% page_header %}` block template tag (new `ndas/templatetags/page_header_tags.py`) that renders the card/title/right-slot without an icon, with a smaller title class, and with the right slot right-aligned; migrate all 23 templates that use this pattern (18 under the project-root `templates/`, plus 5 under `backup/templates/backup/` — Django's `APP_DIRS` also loads templates from each app's own directory) to it and update `static/css/custom_css.css` accordingly.

## Boundaries & Constraints

**Always:**
- New tag pair `page_header` / `endpage_header` lives in `ndas/templatetags/page_header_tags.py`, loaded via `{% load page_header_tags %}`. The nodelist between the tags renders verbatim as the `.page-header-right` slot's inner content (badge `<span>`s, `<ol class="breadcrumb">` trails) — migration must not change any badge/breadcrumb text, filters, or URLs.
- The tag's `title` argument must be passed through `django.utils.html.conditional_escape` before being concatenated into the manually-built HTML string (`Node.render` bypasses Django's autoescape), and the final string returned via `mark_safe`.
- Keep the existing `border-top border-{accent}` color mapping unchanged (primary/secondary/warning/info, per the prior "Page Header: Card Layout Redesign" spec).
- Drop every leading `<i class="fas fa-...">` icon from all 18 migrated titles — no icon markup remains in the header.
- Replace `<h1 class="h4 m-0">...</h1>` with the tag's own `<h1 class="page-header-title m-0">`; add `.page-header-title` to `custom_css.css` with a font-size smaller than Bootstrap's `h4` (~1.5rem) — target ~1.15rem, `font-weight: 600`.
- Change `.page-header-right` to stack children vertically and right-align them (`flex-direction: column; align-items: flex-end;`) instead of the current horizontal wrap, so a badge and a breadcrumb/text line always sit flush right, badge above breadcrumb.
- Migrate exactly these 23 templates (every current user of `page-header-card`, confirmed via `grep -rl "page-header-card" templates/ backup/templates/ reports/templates/` — Django's `APP_DIRS: True` means every installed app's own `templates/` folder is also in scope, not just the project-root `templates/`): `assessment/edit.html`, `attachment/add.html`, `gpa_record/add.html`, `gpa_record/edit.html`, `gpa_record/view.html`, `institution/admin_dashboard.html`, `institution/clinician_add.html`, `institution/clinician_list.html`, `institution/edit.html`, `institution/settings.html`, `institution/superadmin_dashboard.html`, `patients/index.html`, `problemlist/add.html`, `referral/inbox.html`, `referral/initiate.html`, `src/advance_search.html`, `users/admin/admin_dashboard.html`, `video/add.html` (the original 18, all under the project-root `templates/`), plus `backup/templates/backup/manager.html`, `backup/templates/backup/create.html`, `backup/templates/backup/restore.html`, `backup/templates/backup/restore_preview.html`, `backup/templates/backup/restore_status.html` (5 more, under the `backup` app's own `templates/` dir, all using `accent="warning"`/`border-warning` already).
- Add `{% load page_header_tags %}` to each migrated template, after `{% extends %}` alongside any existing `{% load %}` line.

**Ask First:** If a 19th `page-header-card` usage turns up during implementation that isn't in the list above, halt and ask before migrating it.

**Never:** Change view.py/context data passed to these templates; change Bootstrap/AdminLTE version; change the accent-color mapping; reintroduce icons; touch `templates/src/content_headder.html` (unused, out of scope).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Badge + breadcrumb both present | `patients/index.html` | Badge on its own right-aligned line; breadcrumb right-aligned directly below it, both flush to the card's right edge | N/A |
| Breadcrumb only, no badge | `video/add.html` | Breadcrumb trail right-aligned alone; no empty badge gap | N/A |
| Multi-item breadcrumb | `assessment/edit.html` (4 `<li>`s) | Items still render left-to-right inside the `<ol>`, but the whole trail right-anchors against the card edge | N/A |
| Long institution/patient name in badge | `referral/initiate.html` | Badge still wraps (`white-space: normal`, unchanged) instead of overflowing | N/A |

</frozen-after-approval>

## Code Map

- `ndas/templatetags/page_header_tags.py` -- NEW: defines the `page_header`/`endpage_header` block tag; renders the card/title/`.page-header-right` shell, escapes `title`, accepts `accent` and `title` kwargs, inner nodelist becomes the right-slot content. Sibling of existing `ndas/templatetags/delete_modal_tags.py` (same package, same `{% load %}` convention).
- `static/css/custom_css.css:107-130` -- existing `.page-header-card` / `.page-header-right` / `.page-header-right .badge` rules (from the prior "Page Header: Card Layout Redesign" spec, now `status: done`); add `.page-header-title`, change `.page-header-right` to column/flex-end.
- 23 templates listed under Boundaries -- each currently has the exact structure `<div class="card page-header-card border-top border-{accent} shadow-sm mb-0"><div class="card-body d-flex justify-content-between align-items-center flex-wrap py-2"><h1 class="h4 m-0"><i class="fas fa-ICON mr-2"></i>TITLE</h1><div class="page-header-right">[badge?]<ol class="breadcrumb">...</ol></div></div></div>` inside `{% block content_header %}`. The 5 `backup/templates/backup/*.html` additions all use `accent="warning"`, a badge, and a 1-3 item breadcrumb (`restore_preview.html` has the longest, 3 items) -- same shape as the already-migrated set, no new variant.

## Tasks & Acceptance

**Execution:**
- [x] `ndas/templatetags/page_header_tags.py` -- create the `page_header`/`endpage_header` tag -- single reusable source of the header shell (icon-free title, right-aligned slot).
- [x] `static/css/custom_css.css` -- add `.page-header-title`; change `.page-header-right` to `flex-direction: column; align-items: flex-end;` -- delivers the visual fix site-wide from one place.
- [x] Migrate each of the 23 templates (listed under Boundaries, including the 5 `backup/templates/backup/*.html` files) -- add `{% load page_header_tags %}`, replace the card/title wrapper with `{% page_header accent="..." title="..." %}` ... `{% endpage_header %}`, keep the existing badge/breadcrumb markup unchanged as the tag's inner content -- removes the icon and applies the new shell everywhere without touching per-page dynamic content.
- [x] `ndas/tests/test_page_header_tags.py` -- add a `SimpleTestCase` covering title escaping, the tag's actual `accent`/`title` default-fallback and unknown-kwarg-ignored behavior (via `token_kwargs`), and nodelist (badge/breadcrumb) passthrough -- closes the zero-test-coverage gap a review pass found on the new tag.

**Acceptance Criteria:**
- Given any of the 23 migrated pages, when rendered, then the header shows no icon before the title, the title is visibly smaller than the previous `h4` size, and any badge/breadcrumb content is right-aligned against the card's right edge.
- Given a page with both a badge and a breadcrumb (e.g. `patients/index.html`), when rendered, then the badge appears above the breadcrumb, both right-aligned, matching the reference screenshot's intended fix.
- Given the `page_header` tag renders a title, when the output HTML is inspected, then the title text is present HTML-escaped (verifying the manual-string-building path doesn't bypass autoescaping).

## Spec Change Log

- `users/admin/admin_dashboard.html` was the one exception to the Code Map's "current structure" description: it has neither a badge nor a breadcrumb (no `.page-header-right` div at all in the original markup). Migrated it as `{% page_header accent="secondary" title="Staff Dashboard" %}{% endpage_header %}` with an empty nodelist, which renders an empty `.page-header-right` div. This has no visible effect (the div has no content and takes no flex space) and keeps one tag implementation for all 18 templates rather than special-casing this one. Not a 19th `page-header-card` usage, so the "Ask First" boundary doesn't apply.
- **patch (review loopback, round 2):** A second review pass on the round-2 fix (5 backup templates) found no further scope gaps (fresh repo-wide `page-header-card` search confirmed zero stragglers), but flagged that the tag shipped with zero automated test coverage and that `manage.py test backup` was never listed in Verification despite being the app this round touched. **Amendment:** added `ndas/tests/test_page_header_tags.py` (title escaping, the tag's actual lenient `accent`/`title` default-fallback and unknown-kwarg-ignored behavior, nodelist passthrough) and added `manage.py test backup`/the new test module to the Verification commands; expanded the manual-check list to name the specific backup pages. Note: the re-derivation after the round-1 revert regenerated `page_header_tags.py` using `django.template.base.token_kwargs` (silent defaults, unrecognized kwargs ignored) rather than round 1's manual per-kwarg `TemplateSyntaxError` validation — both satisfy every Boundaries/Acceptance-Criteria requirement (escaping, shell markup, no icon), so this was accepted as-is rather than re-driven a third time; the new test module asserts the actual (lenient) behavior. Two pre-existing, out-of-scope issues the same pass surfaced (not caused by this story) were logged to `deferred-work.md` instead of fixed here: `backup/create.html`'s badge always shows `institution.name` even when a superadmin is about to trigger a system-wide backup (unlike `manager.html`'s badge, which already branches on `is_superadmin`); and `restore.html`/`restore_preview.html`/`restore_status.html` all pass the identical `title="Restore"` for three distinct workflow steps.
- **bad_spec (review loopback):** The original discovery command (`grep -rl "page-header-card" templates/`) only searched the project-root `templates/` directory. Django's `APP_DIRS: True` (see `ndas/settings.py` `TEMPLATES`) also loads templates from each app's own `<app>/templates/` folder, and 5 templates under `backup/templates/backup/` (`manager.html`, `create.html`, `restore.html`, `restore_preview.html`, `restore_status.html`) use the identical pre-refactor `page-header-card`/`page-header-right` markup but were missed by that command and absent from the 18-template list. Because the `.page-header-right` CSS rule is global, the implemented CSS change silently reflowed these 5 un-migrated pages (row→column, center→flex-end) without updating their markup to the new icon-free shell — an unreviewed, out-of-scope side effect caught by two independent review passes (verification-gap, edge-case-hunter) and confirmed directly (`grep -rl "page-header-card" backup/templates/` → 5 hits). **Amendment:** widen the migration list from 18 to 23 templates by adding these 5 backup templates, migrated with the same `{% page_header %}` pattern and `accent="warning"` (the existing `border-warning` class already used by all 5, matching the backup app's accent per CLAUDE.md's accent mapping). **KEEP — confirmed working, must survive re-derivation:** the `page_header`/`endpage_header` tag design in `ndas/templatetags/page_header_tags.py` (shell-only abstraction; nodelist passthrough for badge/breadcrumb content, unchanged); the `conditional_escape` + `mark_safe` escaping of `title`/`accent`; the `.page-header-title` CSS addition; the `.page-header-right` column/flex-end CSS change itself (now correct once all consumers are migrated); the exact per-template migration pattern already applied to the original 18 templates (no changes needed there); the `users/admin/admin_dashboard.html` empty-nodelist handling noted above.

## Design Notes

The tag only abstracts the *outer* shell (card wrapper, title markup/class, `.page-header-right` opening/closing div) — the badge and breadcrumb markup stay exactly as each template authors them today (same `{% if %}`, `{% url %}`, `|pluralize` usage), passed through as the tag's nodelist rather than as string kwargs. This avoids needing to model every badge's text-building logic (e.g. `referral/inbox.html`'s `{{ thread_count }} thread{{ thread_count|pluralize }}`) as a tag parameter, while still centralizing the one part that actually changed (shell markup + CSS).

Example migration (`patients/index.html`):
```django
{% load page_header_tags %}
{% block content_header %}
{% page_header accent="primary" title="Dashboard" %}
  <span class="badge badge-pill badge-light border">{% if active_institution %}{{ active_institution.name }}{% else %}NDAS Network{% endif %}</span>
  <ol class="breadcrumb"><li class="breadcrumb-item active">Dashboard</li></ol>
{% endpage_header %}
{% endblock content_header %}
```

## Verification

**Commands:**
- `venv\Scripts\python.exe manage.py check` -- expected: no template/tag errors.
- `venv\Scripts\python.exe manage.py test ndas.tests.test_page_header_tags` -- expected: passes; pins the tag's title-escaping, required-kwarg validation, and nodelist passthrough (added per review-loop finding: the tag shipped with zero automated coverage).
- `venv\Scripts\python.exe manage.py test patients` -- expected: passes (pre-existing baseline has 2 failures + 2 errors in `DashboardTestCase`/`LatestAssessmentTiebreakerTest`, unrelated to header markup; no new failures).
- `venv\Scripts\python.exe manage.py test backup` -- expected: passes (covers the 5 newly-migrated `backup/templates/backup/*.html` templates; this is a ~12-16 minute suite, run it alone, in the background).

**Manual checks (if no CLI):**
- Load `/` (patients dashboard), `/institution/admin/`, one GPA-record page, `/backup/create/`, and `/backup/history/` in a browser; confirm the header matches the reference screenshot's intended fix (no icon, smaller title, right-aligned secondary slot, badge above breadcrumb). The restore-preview and restore-status pages need an in-flight uploaded backup archive to reach; if one isn't readily available, inspecting their rendered `{% page_header %}` call (same pattern, already covered by the automated test above) stands in for a manual load.

## Suggested Review Order

**Reusable shell (the new abstraction)**

- Entry point: defines the `page_header`/`endpage_header` tag pair and how `accent`/`title` kwargs resolve (lenient defaults via `token_kwargs`, not strict validation).
  [`page_header_tags.py:66`](../../ndas/templatetags/page_header_tags.py#L66)

- The actual shell markup and the manual-string-escaping requirement (`conditional_escape` + `mark_safe`) that keeps this safe from XSS.
  [`page_header_tags.py:31`](../../ndas/templatetags/page_header_tags.py#L31)

**Visual fix (CSS)**

- `.page-header-title` adds the smaller font; `.page-header-right` switches from a horizontal wrap to a right-aligned column — this is what actually produces the reference screenshot's fix.
  [`custom_css.css:113`](../../static/css/custom_css.css#L113)

**Representative migrations (same pattern, 23x)**

- The original bug-report page (badge + single-item breadcrumb, both accent and the dashboard's own screenshot came from here).
  [`patients/index.html:6`](../../templates/patients/index.html#L6)

- A badge-only, no-breadcrumb case (the one template with an empty nodelist, documented in the Spec Change Log).
  [`institution/admin_dashboard.html:7`](../../templates/institution/admin_dashboard.html#L7)

- One of the 5 backup-app templates added in the round-2 scope-correction (missed by the original root-`templates/`-only discovery grep).
  [`backup/manager.html:8`](../../backup/templates/backup/manager.html#L8)

**Tests (peripherals)**

- Pins the title-escaping requirement and the tag's actual lenient kwarg-fallback behavior — added in review round 2 to close a zero-coverage gap.
  [`test_page_header_tags.py:26`](../../ndas/tests/test_page_header_tags.py#L26)
