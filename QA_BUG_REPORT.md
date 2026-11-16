# NDAS QA Bug Report

**Date:** 2026-11-16
**Environment:** Local dev server (`venv\Scripts\python.exe manage.py runserver`), SQLite dev DB, `http://127.0.0.1:8000/`
**Tester:** Automated QA pass via browser automation (Chrome DevTools MCP), no code changes made.

## Scope

**Covered:**
- Full CRUD pass (Create/Read/Update/Delete where exposed) on `patients/`, `users/`, `problemlist/`, partially `video/` and `reports/` (generation only, not upload), `institution/`, `backup/` (access/permission only), `referral/` (access only).
- Three roles tested: Superadmin (`qa_tester`), Institution Admin (`qa_inst_admin`, `user_type=ADMIN`), plain Clinician/User (`qa_crud_user`, `user_type=USER`, non-staff).
- Permission/authorization boundary checks across roles (direct URL access to admin-only/institution-scoped endpoints).
- Responsive/UI pass at 1920x1080, 1366x768, 1024x768, 768x1024, 375x667 on: login page, patient list (manager), patient add form, patient detail/view (incl. delete modal), video view, reports builder.
- Console error / network error monitoring (`list_console_messages`, `list_network_requests`) during the above.

**Not covered** — see "Not Covered / Follow-up Needed" section.

---

## Critical

*(none found)*

---

## High

### H1 — Superadmin accounts without `user_type=SUPERADMIN` are silently blocked from Backup, with no UI path to fix it
- **App/Section:** `backup/`, `users/` (user creation), Phase 2 role system
- **URL:** `http://127.0.0.1:8000/backup/`
- **Steps to repro:**
  1. Create or use a Django superuser (`is_superuser=True`, `is_staff=True`) whose `user_type` field is still the default `USER` (this is exactly what `python manage.py createsuperuser` produces, since `user_type` is a custom field with `default=UserType.USER` that the standard Django user-creation flow never touches).
  2. Log in as that superuser and navigate to `/backup/`.
- **Expected:** A Django superuser should be able to trigger backups (per CLAUDE.md: "Superusers delete any" / have full access elsewhere in the app).
- **Actual:** Redirected to `/` with "You don't have permission to trigger a backup." `backup/views.py:313-316` (`backup_create`) checks `request.user.user_type not in (UserType.ADMIN, UserType.SUPERADMIN)` — it never looks at `is_superuser`/`is_staff` at all. There is also no field in the "Add New User" UI (`/users/admin/users/add/`, `users/views.py` admin_user_add, template `templates/users/admin/user_add.html`) or the user-edit UI to set `user_type`; it can currently only be changed via the Django shell/ORM.
- **Affects:** Any superuser created through the normal Django/admin workflow rather than hand-patched in the DB. Reproduced directly: test account `qa_tester` (is_superuser=True, is_staff=True) was blocked until `user_type` was manually set to `SUPERADMIN` via shell.
- **Likely fix location:** `backup/views.py:313-316` should also allow `request.user.is_superuser`, OR `user_type` should be auto-synced to `SUPERADMIN` whenever `is_superuser` is set (e.g. in a `save()` override or a signal), OR the Add/Edit User forms should expose `user_type`.

### H2 — Institution Admin's sidebar shows 4 "Administration" links that their role cannot actually use
- **App/Section:** `users/`, sidebar template
- **URL:** Any page while logged in as a `user_type=ADMIN` (Institution Admin) account, e.g. `http://127.0.0.1:8000/institution/clinicians/`
- **Steps to repro:**
  1. Log in as a user with `user_type=ADMIN` and `is_staff=False`, `is_superuser=False` (reproduced with `qa_inst_admin`).
  2. Observe the sidebar's "Administration" section shows: "Staff Dashboard", "Users", "Add User", "Activity Logs".
  3. Click any of them (or navigate directly): `/users/admin/dashboard/`, `/users/admin/users/`, `/users/admin/users/add/`, `/users/admin/activity-logs/`.
- **Expected:** Either the links work for this role, or they are hidden for a role that cannot use them.
- **Actual:** All four redirect straight back to the user's own profile page (`/users/view/<pk>/`) with "You do not have permission to access this area." — dead-end navigation links shown to a role that can never use them.
- **Root cause:** `templates/src/main_sidebar_menu.html:336` gates this whole block on `{% if user_type == 'ADMIN' or is_superadmin %}`, but the views behind those 4 links (`admin_dashboard`, `admin_user_list`, `admin_user_add`, `admin_activity_logs` in `users/views.py`) are all decorated with `@admin_required`, defined in `users/decorators.py:7-16`, which checks `request.user.is_staff or request.user.is_superuser` — the legacy flags, not the Phase 2 `user_type` field. The two permission systems disagree.
- **Likely fix location:** `templates/src/main_sidebar_menu.html:336` (and/or the inner `{% if %}` per-link if some should stay hidden) should match whatever `users/decorators.py:7` actually checks, or `admin_required` should be updated to also accept `user_type == ADMIN`/`SUPERADMIN` if that's the intended design.

---

## Medium

### M1 — Report builder's field-selection toggle buttons are non-functional due to CSP blocking inline `onclick`
- **App/Section:** `reports/` (Generate Report / builder page)
- **URL:** `http://127.0.0.1:8000/reports/`
- **Steps to repro:**
  1. Log in (any role with report access) and open `/reports/`.
  2. Open DevTools console, or just click "All"/"None" under "Patient Demographics" or "Assessment Records", or "Show Field Selection".
- **Expected:** Buttons select/deselect the relevant checkboxes.
- **Actual:** Nothing visibly happens; browser console logs 5 CSP violations: *"Executing inline event handler violates the following Content Security Policy directive 'script-src 'self' 'nonce-...''"*. The security middleware's strict CSP (per CLAUDE.md: `script-src 'self'` with per-request nonce, no `'unsafe-inline'`) blocks these handlers outright.
- **Root cause:** `reports/templates/reports/builder.html` uses inline `onclick=` attributes at lines **297, 300, 408, 419, 422** (`togglePatientFields(true/false)`, `toggleFieldSelection()`, `toggleAssessmentFields(true/false)`), which the CSP middleware (`ndas/custom_codes/security_middleware.py`) silently blocks.
- **Likely fix location:** `reports/templates/reports/builder.html:297,300,408,419,422` — replace inline `onclick=` with `addEventListener` bound in a `<script nonce="{{ request.csp_nonce }}">` block (or an external JS file), consistent with the rest of the app's CSP-safe JS (the page's own console logs show `NDASEventHandlers` doing exactly this pattern elsewhere).

### M2 — Password minimum length is inconsistent between the two "create user" flows
- **App/Section:** `users/` vs `institution/` (clinician creation)
- **URL:** `/users/admin/users/add/` vs `/institution/clinicians/add/`
- **Steps to repro:**
  1. On `/users/admin/users/add/`, note the help text says "Password must be at least 8 characters long," and an 8–11 character password is accepted.
  2. On `/institution/clinicians/add/`, enter an 11-character password (e.g. `QaTest!2026`) — rejected: "This password is too short. It must contain at least 12 characters."
- **Expected:** Consistent password policy across all "create NDAS user" entry points.
- **Actual:** Two different minimums (8 vs 12) enforced by two different forms for what is the same underlying `CustomUser` model.
- **Likely fix location:** Whichever form/validator backs `/institution/clinicians/add/` (an institution app clinician-creation form) vs. the admin `UserCreationForm`/validator used by `users/views.py` `admin_user_add` — align on one `validate_password`/`MinimumLengthValidator` setting.

### M3 — Patient delete confirmation modal: primary action buttons start below the fold on mobile
- **App/Section:** `patients/` (delete confirmation modal), shared `delete_confirmation_modal.html`
- **URL:** `http://127.0.0.1:8000/patient/view/<id>/` → "Delete Patient"
- **Breakpoints reproduced:** 375x667 (mobile). Likely also 414x896 and other short mobile viewports.
- **Steps to repro:** On a mobile-width viewport, open a patient's "Delete Patient" modal.
- **Expected:** Cancel/Delete action buttons visible or obviously reachable without the user needing to realize they must scroll.
- **Actual:** The modal's warning text + patient-details block + password field already fill the viewport height; the "Cancel"/"Delete Patient" buttons render just past the bottom edge with no visual affordance (no visible scrollbar cue inside the modal) that more content/actions exist below. Confirmed reachable via Tab-triggered auto-scroll or manual scroll — it is not a hard blocker, but on a real touchscreen with no keyboard, a user has to realize they need to scroll the modal (not the page) to find the delete button.
- **Likely fix location:** The shared modal template (`templates/src/partials/delete_confirmation_modal.html`) — ensure `.modal-dialog` uses a bounded height (e.g. `modal-dialog-scrollable` or `max-height: 90vh` on `.modal-content` with `overflow-y:auto` on `.modal-body` only, footer pinned), so the action buttons are always visible without scrolling the whole modal body.

### M4 — No safeguard against a superuser deactivating every other admin/superadmin account
- **App/Section:** `users/` admin user management
- **URL:** `/users/admin/users/`
- **Observation:** `admin_user_delete` (`users/views.py:793+`) and `admin_user_toggle_status` (`users/views.py:889+`) only block **self**-deactivation/deletion; any superuser can deactivate/soft-delete any *other* user, including the one other superuser account in the system (reproduced: `qa_tester` could see live "Deactivate"/"Delete" controls for `rasikakulasinghe`, the real owner account).
- **Note:** This matches the documented rule in CLAUDE.md ("Superusers delete any"), so it is **by design**, not a confirmed bug — flagging as Medium only because it means a single compromised or careless superuser session can lock out every other admin in the system with no "last superuser" guard. Worth a product decision, not necessarily a code fix.

---

## Low

### L1 — 24 form fields across the app have no associated `<label>` (accessibility)
- **App/Section:** Observed on `/reports/` (report builder) via browser console: *"No label associated with a form field (count: 24)"*. Likely recurs on other pages built with the same component patterns (e.g. filter chips, inline checkboxes).
- **Expected:** Every input/checkbox/radio has a programmatically associated label (`<label for=...>` or `aria-label`) for screen-reader users.
- **Actual:** 24 instances flagged by Chrome's own accessibility checker on a single page load of `/reports/`.
- **Likely fix location:** `reports/templates/reports/builder.html` — audit checkbox/radio markup (many are rendered as `<input>` + sibling text without a wrapping/`for`-linked `<label>`).

### L2 — Institution dropdown correctly hides inactive institutions, but no indication why
- Not a bug — confirmed correct behavior (`QA Test Institution Updated`, `is_active=False`, is correctly excluded from the "Add New User" institution `<select>`). Documented here only because it initially looked suspicious; no action needed.

---

## Responsive / UI Findings

All of the following were checked at 1920x1080, 1366x768, 1024x768 (tablet landscape), 768x1024 (tablet portrait), and 375x667 (mobile). Only deviations are listed; everything else rendered cleanly with proper reflow (AdminLTE sidebar auto-collapses at ≤1024px, patient table collapses to a card layout on mobile instead of overflowing, forms stack correctly, video player is responsive).

| # | Page | Breakpoint(s) | Finding |
|---|------|---------------|---------|
| R1 | Patient delete modal (`/patient/view/<id>/`) | 375x667 (mobile) | See **M3** above — buttons start below the fold inside the modal. |
| R2 | Patient manager list (`/manager/patient/`) | 768x1024 (tablet) | Table requires horizontal scroll to see all columns (Gender/DOB/Diagnosis/Created By/Actions) at this width before collapsing to the mobile card layout at ≤414px. This is a reasonable, intentional `table-responsive` pattern, not a layout break — noted for awareness only, not a bug. |

No horizontal page overflow, overlapping elements, or unreadable/truncated text was found on: login page, patient add/edit form (including the APGAR/period-of-gestation multi-select row and the 28-item GMA indications checkbox grid), patient view tabs (they wrap to multiple rows on narrow screens instead of overflowing), video view/player, or the reports builder form, at any tested breakpoint.

---

## Not Covered / Follow-up Needed

- **Actual video file upload** (`/video/add/<patient_id>/`) — form loads correctly and sets `added_by` in code (`video/views.py:45`), but no real file was uploaded/transcoded to confirm end-to-end (would require a real video file and exceeds a quick QA pass).
- **Referral initiate/reply/close flow** — `/referral/inbox/` loads cleanly with no console/network errors for all three roles, but no referral was actually created end-to-end (the test institution admin's institution had 0 patients; cross-institution referral requires at least two populated institutions and more setup time than this pass allowed).
- **Backup/Restore execution** — permission boundaries were tested (see H1), but no backup job was actually triggered/downloaded or restore performed, to avoid mutating the dev DB/disk during a report-only QA pass.
- **Excel export formula-injection (`escape_excel_row`) verification** — report generation was exercised successfully (Excel file downloaded without error), but the exported file's cell contents were not opened/inspected to verify formula-injection escaping on free-text fields.
- **Email-dependent flows** (password reset email, email verification send/resend) — not exercised; dev environment likely has no real SMTP configured.
- **Institution `superadmin` dashboard / aggregate reports / patient-move** (`/institution/superadmin/`, `/institution/superadmin/reports/`, `/institution/patient-move/<id>/`) — only access-boundary-checked (non-superadmin correctly redirected), not functionally exercised.
- **Deeper authorization bypass testing** (e.g. hitting delete/edit POST endpoints directly with a crafted request as a lower-privilege user, bypassing the UI which already hides the buttons) was out of scope for this UI-driven QA pass; the findings above are from what the UI exposes/blocks, not a full backend pentest.
- Only 3 of the project's documented roles were exercised (Superadmin, Institution Admin, plain User/Clinician). `is_staff=True`-but-not-superuser ("Staff") combinations (like the pre-existing `adminlrh` account) were not separately tested.

---

## Test Users / Data Created or Modified This Session

- **Reused pre-existing (but inactive) QA fixture accounts** — reactivated and password set to `QaTest!2026` for all three:
  - `qa_tester` (id 32) — was superuser but had `user_type=USER`; **changed `user_type` to `SUPERADMIN`** to test backup/institution-superadmin features (see H1). *This change was left in place* — revert if this account should go back to its prior state.
  - `qa_crud_user` (id 33) — plain user, `user_type=USER`, institution=Default Institution. Also had `is_email_verified` flipped `True` (was blocking login).
  - `qa_inst_admin` (id 34) — `user_type=ADMIN`, institution=QA Test Institution Updated. Also had `is_email_verified` flipped `True`.
- **Created and cleaned up (deleted/deactivated) during this session:**
  - Patient id 44 ("QA Test Baby One" → "QA Test Baby One Updated") — created, edited, then hard-deleted. ✅ Confirmed gone.
  - Problem id 21 ("QA Test Problem" on patient 7) — created, then hard-deleted. ✅ Confirmed gone.
  - User `qa_new_user1` (id 38) — created, edited, then soft-deleted (deactivated, per the app's delete-is-deactivate model). Left **inactive**, not hard-deleted (the app has no hard-delete for users).
  - Clinician `qa_clinician1` (institution "QA Test Institution Updated") — created via `/institution/clinicians/add/`, then deactivated. Left **inactive** (no delete option exists on that screen, only deactivate/reactivate).
- **Pre-existing clutter found but NOT created or removed by this session** (left untouched — looked like leftovers from an earlier, unrelated QA/test pass, out of scope to clean up without confirming with the project owner): patients 29–36 ("QA Test Baby Updated" x8), patients 38/39 ("BO Chathurika" x2), institution id 4 "QA Test Institution Updated" (deactivated), videos 16/17/25/26/32 ("QA Test Video"/"QA Test Video Updated"), and several `qa_*`-prefixed users beyond the three reused above.
