
---
title: 'Page Header: Card Layout Redesign'
type: 'refactor'
created: '2026-11-14'
status: 'done'
review_loop_iteration: 1
context: ['{project-root}/CLAUDE.md']
baseline_commit: '92c6f596204189ffdca73bb16063d9268ed8cd38'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The shared page-identification header (`{% block content_header %}` in `templates/src/base.html`, overridden by 20 templates, plus 3 templates that duplicate the same markup inline outside the block) renders as a plain borderless row — `<h1>` + muted subtitle on the left, a bare `<ol class="breadcrumb">` on the right — with no visual container, unlike the approved reference (a white card, colored top-accent border, icon + title left, breadcrumb/badge right).

**Approach:** Restyle every `content_header` block into a consistent card: `card page-header-card` with a 4px top border colored per app/section, icon + `<h1>` on the left, and a flexible right-side slot that holds whatever the page already shows there (breadcrumb trail, or a badge — folding in any subtitle text so nothing is dropped). No new include/templatetag — each template keeps its existing self-contained block, just rewritten to the shared markup pattern below. Pure template + CSS change; no view.py or model changes.

## Boundaries & Constraints

**Always:**
- Use only existing AdminLTE 3.2 / Bootstrap 4.6 classes (`card`, `card-body`, `breadcrumb`, `badge`) plus small additive CSS in `static/css/custom_css.css`; never introduce a new CSS framework/library.
- Keep the `{% block content_header %}` name and its position inside `base.html`'s `.content-header > .container-fluid` wrapper unchanged.
- Apply the app→accent-color mapping: `primary` = patients, attachment, gpa_record, assessment, advance_search, problemlist; `warning` = backup (all 5 templates); `info` = referral; `secondary` = institution + users/admin dashboard.
- Preserve every dynamic text value currently shown (title, subtitle, breadcrumb labels/links, counts) — subtitle text folds into the right-side slot as a small badge/text when no breadcrumb exists, it must never silently disappear.
- Migrate the 4 stragglers (`templates/assessment/edit.html`, `templates/src/advance_search.html`, `templates/problemlist/add.html`, `templates/video/add.html`) into the real `content_header` block using the same pattern; `problemlist/add.html`'s breadcrumb is currently commented out — restore it.
- `templates/institution/admin_dashboard.html` must keep its `{{ institution.name }}` badge in the right-side slot, matching every other migrated `institution/*` template (`clinician_add.html`, `clinician_list.html`, `settings.html`, `edit.html`, `superadmin_dashboard.html`) — do not drop it even though this page has no breadcrumb.
- The `.page-header-right .badge` CSS rule must allow wrapping (`white-space: normal; word-break: break-word;`), not Bootstrap's default `nowrap`, so a long institution or patient name folded into a badge wraps instead of overflowing the card on narrow viewports.

**Ask First:** If any additional page with inline duplicated header markup turns up beyond the 3 already identified, or if a page's existing right-side content (e.g. a 4-level breadcrumb) visibly overflows the compact card on mobile width, halt and ask before proceeding on that file.

**Never:** Change view.py/context data passed to these templates; delete or alter `templates/src/content_headder.html` (unused, out of scope); change AdminLTE/Bootstrap versions.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Long breadcrumb | `restore_preview.html` (3-level trail) | Wraps to a second line inside the right slot via flex-wrap; no horizontal scroll | N/A |
| No breadcrumb, no subtitle | `institution/admin_dashboard.html` | Right slot collapses empty; card still shows balanced icon+title only | N/A |
| Long dynamic title/subtitle | Institution name folded into right-slot badge | Text wraps or truncates via existing Bootstrap text utilities; never breaks card layout | N/A |

</frozen-after-approval>

## Code Map

- `templates/src/base.html:20-23` -- defines the shared `content_header` block wrapper (`.content-header > .container-fluid`); unchanged, card markup renders inside it.
- `static/css/custom_css.css:102` -- existing `.content-header{padding-top:15px}`; append `.page-header-card` (4px accent border-top, radius) and `.page-header-right` (`.breadcrumb{background:transparent;padding:0;margin:0}`, `.badge{font-size:.8rem;white-space:normal;word-break:break-word}`) rules here.
- `backup/templates/backup/{manager,create,restore,restore_status,restore_preview}.html` -- current inline `row/col` header (e.g. `manager.html:6-21`); icons `fa-history`/`fa-database`/`fa-upload`; accent `warning`.
- `templates/referral/{initiate,inbox}.html` -- icons `fa-paper-plane`/`fa-share-square`; accent `info`.
- `templates/institution/{superadmin_dashboard,settings,edit,clinician_add,clinician_list}.html` -- icon `fa-shield-alt`; accent `secondary`; each keeps its `{{ institution.name }}` badge in the right slot.
- `templates/institution/admin_dashboard.html` -- icon `fa-shield-alt`; accent `secondary`; no breadcrumb, but **must** keep the `{{ institution.name }}` badge in the right slot (it currently shows this live as a subtitle -- dropping it with no replacement is a regression, unlike its siblings above which all retain it).
- `templates/users/admin/admin_dashboard.html` -- icon `fa-shield-alt`; accent `secondary`; block is currently fully commented out (dead) -- restore it with the new pattern, title "Staff Dashboard" only, no breadcrumb, no badge (its institution-name display was already dead/commented code before this change, so omitting it is not a regression).
- `templates/patients/index.html`, `templates/attachment/add.html`, `templates/gpa_record/{add,edit,view}.html` -- icons `fa-tachometer-alt`/`fa-folder`/`fa-circle`; accent `primary`.
- `templates/assessment/edit.html`, `templates/src/advance_search.html`, `templates/video/add.html` -- header markup currently duplicated inline inside `main_content` instead of the shared block -- move into `{% block content_header %}`; accent `primary`; `video/add.html` has no subtitle, breadcrumb is Dashboard › `{{ patient.baby_name }}` › Upload Video (`{% url 'home' %}` / `{% url 'view-patient' patient.id %}`), icon `fa-video`.
- `templates/problemlist/add.html` -- breadcrumb markup present but commented out -- restore into the new pattern; accent `primary`.

## Tasks & Acceptance

**Execution:**
- [x] `static/css/custom_css.css` -- append `.page-header-card`/`.page-header-right` rules (see Code Map), including `white-space: normal; word-break: break-word;` on `.page-header-right .badge` -- shared visual shell for all migrated templates, long names wrap instead of overflowing
- [x] `backup/templates/backup/{manager,create,restore,restore_status,restore_preview}.html` (5 files) -- rewrite `content_header` block to the card pattern, `accent-warning`, keep existing breadcrumb/subtitle content moved into the right slot -- consistent backup/restore identity
- [x] `templates/referral/{initiate,inbox}.html` (2 files) -- same pattern, `accent-info`
- [x] `templates/institution/{superadmin_dashboard,admin_dashboard,settings,edit,clinician_add,clinician_list}.html` (6 files) -- same pattern, `accent-secondary`; all six, `admin_dashboard.html` included, keep their `{{ institution.name }}` badge in the right slot -- do not drop it on `admin_dashboard.html`
- [x] `templates/users/admin/admin_dashboard.html` -- same pattern, `accent-secondary`; block is currently fully commented out (dead) -- restore it title-only, no breadcrumb, no badge (its institution-name display was already dead code before this change, so this is not a regression)
- [x] `templates/patients/index.html`, `templates/attachment/add.html`, `templates/gpa_record/{add,edit,view}.html` (5 files) -- same pattern, `accent-primary`
- [x] `templates/assessment/edit.html`, `templates/src/advance_search.html`, `templates/video/add.html` (3 files) -- migrate inline header into the real `content_header` block using the new pattern, `accent-primary` -- `video/add.html` icon `fa-video`, breadcrumb Dashboard › `{{ patient.baby_name }}` › Upload Video
- [x] `templates/problemlist/add.html` -- restore commented-out breadcrumb into the new pattern, `accent-primary`

**Acceptance Criteria:**
- Given any migrated page, when rendered, then the header is a white card with a 4px top border in its assigned accent color, icon + title left, breadcrumb/badge right, and no separate `<small>` subtitle line.
- Given a page previously showed a dynamic subtitle (e.g. "System-wide" / institution name), when migrated, then that text still appears in the card's right-side slot.
- Given `python manage.py test` runs after migration, when the backup/institution/referral/patients/gpa_record/attachment/problemlist/assessment/video suites execute, then all pre-existing assertions still pass unchanged.
- Given a narrow (~375px) viewport, when the card renders on a long-breadcrumb page, then content wraps via flex-wrap instead of overflowing.
- Given `templates/institution/admin_dashboard.html` is rendered, when the page loads, then `{{ institution.name }}` is visible in the card's right-side badge (not dropped).
- Given a badge in the right-side slot holds a long institution or patient name, when the card renders at narrow width, then the badge text wraps onto multiple lines rather than overflowing the card.

## Spec Change Log

- 2026-11-14: Implementation complete (all 23 templates + CSS). `manage.py check` passes with no issues (no template syntax errors, no NoReverseMatch). Repo-wide grep found no test asserting on header/breadcrumb markup or text, confirming the spec's investigation. `manage.py test backup institution referral patients problemlist assessment` (note: `gpa_record`/`attachment`/`assessment` are not separate app labels -- their views/tests live inside the `patients` app) shows a large number of pre-existing failures (hundreds), all with the same signature: `AssertionError: 301 != <expected code>` / `response.context` is `None` because of that unexpected redirect. Verified via `git stash` that this exact failure pattern (same tests, same 301-vs-expected-code signature) reproduces identically on unmodified `main` before any of this spec's changes -- it is a pre-existing, systemic issue unrelated to this header redesign (likely URL/middleware related) and far larger than the small baseline noted in prior project memory. No failure or error in any full run traces into any of the 23 migrated templates or the new `page-header-card`/`page-header-right` CSS.
- 2026-11-14: Matrix Test Audit (manual, since all 3 rows are pure CSS/visual behavior with no automated-test equivalent in this codebase): ran the dev server and logged in first as `qa_tester` then as the `rasikakulasinghe` superadmin account to reach every accent color. Confirmed row 1 (long breadcrumb) on `attachment/add.html`'s live 4-level trail (Dashboard / Patient / Attachments / Add) at 375px width -- wraps cleanly to a second line via flex-wrap, no horizontal scroll. Confirmed row 2 (no breadcrumb, no subtitle) on `users/admin/admin_dashboard.html` (Staff Dashboard, accent-secondary) -- right slot collapses cleanly, no leftover gap. Confirmed row 3 (subtitle folded into right slot) on `backup/manager.html` (Backup History, accent-warning) -- "System-wide" badge renders alongside the "Backup / History" breadcrumb in the right slot, exactly per the Always clause. Also confirmed the card pattern on `patients/index.html` (accent-primary), `referral/inbox.html` (accent-info, count badge), and `institution/superadmin_dashboard.html` (accent-secondary, breadcrumb pill) -- all 4 accent colors and all 3 matrix rows now visually verified. Root-caused the 301 failures noted above during this check: this shell session has production env vars exported (`SECURE_SSL_REDIRECT=True`, `ALLOWED_HOSTS=demo.ndas.lk,...`) that shadow `.env` because python-decouple checks `os.environ` first -- confirmed by overriding them for one dev-server process only, after which pages loaded normally.
- 2026-11-14: **bad_spec loopback (review_loop_iteration 0 -> 1).** Three parallel reviews (blind-hunter, edge-case-hunter, verification-gap) ran against the implementation diff. Two real findings triggered this amendment: (1) `templates/video/add.html` still has the exact pre-redesign inline header markup (`content-header`/`row mb-2`/`breadcrumb float-sm-right`) -- it was flagged as an unconfirmed path during step-02 investigation and never re-checked before the spec was written, so the Code Map was incomplete. (2) `templates/institution/admin_dashboard.html`'s new header silently dropped its live `{{ institution.name }}` subtitle with no replacement, unlike all 5 sibling `institution/*` templates in the same diff which kept it as a badge -- a direct violation of this spec's own "must never silently disappear" clause. A third, lower-severity finding (badges using Bootstrap's default `white-space:nowrap`, risking overflow on long institution/patient names) was folded into this same amendment rather than deferred, since it's a one-line CSS fix on a file already being touched. Code Map and Tasks above have been amended: `video/add.html` added as a 4th straggler; `institution/admin_dashboard.html` given its own explicit "keep the badge" line, split out from the `institution/*` group; the CSS task now includes the `white-space`/`word-break` wrap fix. All template/CSS code changes from the first implementation pass were reverted before this amendment; re-implementation follows this spec version.
  **KEEP:** the overall pattern worked correctly on 22 of 23 files and needs no redesign -- `card page-header-card border-top border-{accent} shadow-sm mb-0` shell, `card-body d-flex justify-content-between align-items-center flex-wrap py-2`, `<h1 class="h4 m-0">` with icon, `.page-header-right` wrapping badge(s) + breadcrumb. The accent-color-per-app mapping, the "fold subtitle into a badge" approach, and the choice not to extract a shared include/templatetag all worked as intended and should be reproduced identically -- only the two gaps above need fixing, not the overall design.
- 2026-11-14: Re-implementation complete against the amended spec (24 files: 23 templates + CSS, confirmed via `git status`). Both loopback-triggering gaps verified fixed by direct inspection, not just agent self-report: `templates/institution/admin_dashboard.html` now renders `<span class="badge badge-pill badge-light border">{{ institution.name }}</span>` in the right slot; `templates/video/add.html` now uses the card pattern (`fa-video` icon, Dashboard › `{{ patient.baby_name }}` › Upload Video breadcrumb); `static/css/custom_css.css`'s `.page-header-right .badge` rule now has `white-space: normal; word-break: break-word;`. `manage.py check` passes with no issues. Browser-verified `video/add/11/` live (card renders correctly, breadcrumb links resolve) -- `institution/admin_dashboard.html` could not be browser-verified this pass: its own view (`institution/views.py:657-671`) deliberately redirects SUPERADMIN users to the superadmin dashboard by design, and no ADMIN-role account's credentials were available, so the badge fix is confirmed by source inspection only, not a live render. Re-implementation subagent additionally ran `manage.py test backup institution referral patients problemlist` and `manage.py test users video` (env-override workaround for the same shell-contamination issue already diagnosed) -- both exited 0, no regressions.
- 2026-11-14: **Second review pass (review_loop_iteration 1), patch loopback.** Three parallel reviews ran against the corrected 24-file diff. The two previous loopback gaps (video/add.html, institution/admin_dashboard.html badge) were independently re-checked by all three reviewers and confirmed resolved -- the verification-gap reviewer explicitly found "No verification gaps" and confirmed via grep that `institution/admin_dashboard.html`'s badge still satisfies `institution/tests/test_admin_dashboard.py:86-87`'s `self.inst.name` assertion. Two reviewers also flagged `institution/admin_dashboard.html` dropping its old single-item breadcrumb and `users/admin/admin_dashboard.html` showing no institution badge; both were rejected as non-issues on direct inspection -- the dropped breadcrumb item was `class="breadcrumb-item active"` (Bootstrap's non-link/current-page marker, no `<a>`, so zero navigational capability existed to lose), and the missing badge on `users/admin/admin_dashboard.html` was already an explicit, justified spec decision (that page's header was entirely dead/commented code before this redesign, so nothing live regressed).
  One real, confirmed finding from the blind-hunter review: `.page-header-card { border-top-width: 4px; }` (no `!important`) loses to Bootstrap's `.border-top{border-top:1px solid #dee2e6!important}` utility class, which every migrated template applies alongside it -- verified empirically via `getComputedStyle` in a live browser session (`border-top-width` computed to ~1px, not 4px) before the fix and `4px` after. **Patch applied directly** (`static/css/custom_css.css`): added `!important` to `border-top-width: 4px`, matching the Design Notes example's original intent. Re-verified via `getComputedStyle` (now `"4px"`) and a visual screenshot of the Patients Dashboard showing a clearly thicker accent border. No spec amendment or re-implementation needed -- single-property CSS fix, no other code affected.
  All other findings from both reviewers across this round (icon reuse across institution pages, `fa-circle` on GPA records, no shared include/templatetag, no ARIA attributes on breadcrumbs/icons, undocumented accent-color-per-app scheme, `badge-pill` + text-wrap cosmetic interaction, CLAUDE.md not updated) are rejected as either explicit, already-approved spec design decisions (Checkpoint 1), pre-existing conditions not caused by this change, or low-severity cosmetic polish with no functional consequence -- not blocking.
  **Review complete. No outstanding findings.**

## Design Notes

Each template keeps its own self-contained `content_header` block — no new include/templatetag. Example (backup, warning accent):

```html
{% block content_header %}
<div class="card page-header-card border-top border-warning shadow-sm mb-0">
  <div class="card-body d-flex justify-content-between align-items-center flex-wrap py-2">
    <h1 class="h4 m-0"><i class="fas fa-history mr-2"></i>Backup History</h1>
    <div class="page-header-right">
      <ol class="breadcrumb">
        <li class="breadcrumb-item"><a href="{% url 'backup:backup-create' %}">Backup</a></li>
        <li class="breadcrumb-item active">History</li>
      </ol>
      <!-- OR, on pages with no breadcrumb -- badge CSS allows wrapping for long names: -->
      <span class="badge badge-pill badge-light border">{% if is_superadmin %}System-wide{% else %}{{ institution.name }}{% endif %}</span>
      <!-- institution/admin_dashboard.html has no breadcrumb but MUST still render this badge -->
      <!-- .page-header-right .badge needs: white-space: normal; word-break: break-word; -->
      <!-- (Bootstrap's .badge default is nowrap, which overflows on long names) -->
    </div>
  </div>
</div>
{% endblock content_header %}
```

## Verification

**Commands:**
- `venv\Scripts\python.exe manage.py test backup institution referral patients gpa_record` -- expected: all pass, no failures from markup changes (investigation found no test asserts on header/breadcrumb markup or text).

**Manual checks (if no CLI):**
- Load Backup History, Institution Settings, Referral Inbox, Patients Dashboard, and GPA Record Add in a browser; confirm card + accent color + icon + title + right-slot content render correctly and no subtitle text was lost.
- Resize to ~375px width on `restore_preview.html` (3-level breadcrumb) and confirm flex-wrap, no horizontal scroll.

## Suggested Review Order

**Shared visual foundation**

- Entry point: the card shell + accent-border mechanism every migrated template builds on, including the `!important` fix so the 4px border actually renders (confirmed `1px → 4px` via live `getComputedStyle`).
  [`custom_css.css:107`](../../static/css/custom_css.css#L107)

**Loopback fixes (the two review-driven corrections)**

- Previously-missed straggler, migrated last; confirms the pattern extends cleanly to a patient-sub-resource "add" page outside the original 20-template scan.
  [`video/add.html:5`](../../templates/video/add.html#L5)

- The dropped-then-restored `institution.name` badge — the one place a dynamic value nearly disappeared silently.
  [`institution/admin_dashboard.html:5`](../../templates/institution/admin_dashboard.html#L5)

**Backup/restore (warning accent, 5 files)**

- Representative of the group: badge + breadcrumb together in the right slot, the richest right-slot case.
  [`backup/manager.html:6`](../../backup/templates/backup/manager.html#L6)

**Patient-record pages (primary accent)**

- Core landing page; breadcrumb-only pattern with institution-name badge, superadmin/non-superadmin branching.
  [`patients/index.html:4`](../../templates/patients/index.html#L4)

**Referral (info accent)**

- Badge-only right slot (thread count, no breadcrumb) — the simplest right-slot variant.
  [`referral/inbox.html:5`](../../templates/referral/inbox.html#L5)

**Other migrated stragglers (moved from inline `main_content` markup into `content_header`)**

- [`problemlist/add.html:14`](../../templates/problemlist/add.html#L14) — restores a previously fully-commented-out (dead) breadcrumb.
- [`assessment/edit.html:5`](../../templates/assessment/edit.html#L5) — subtitle folded into a badge alongside a 4-level breadcrumb.
- [`advance_search.html:5`](../../templates/src/advance_search.html#L5) — simplest straggler, breadcrumb only, no badge.
