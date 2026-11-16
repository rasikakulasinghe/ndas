---
title: 'QA Bug Report (2026-11-16) — Fix Batch'
type: 'bugfix'
created: '2026-11-16'
status: 'in-progress'
review_loop_iteration: 0
context: []
baseline_commit: '4532d4fa0cb8ff80ad41ef8922e1b915ee028c9a'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `QA_BUG_REPORT.md` (2026-11-16 QA pass) found 6 independently-shippable, non-by-design bugs: a Django superuser whose `user_type` is still the default `USER` is blocked from `/backup/` (H1); the sidebar shows 4 "Administration" links to Institution Admins that `admin_required` then blocks (H2); 5 inline `onclick` handlers in the report builder are silently dropped by CSP (M1); the admin "Add User" form accepts 8-char passwords while the project's real policy (`AUTH_PASSWORD_VALIDATORS`, `ndas/settings.py:130-141`) requires 12+ (M2); the patient-delete modal's action buttons sit below the fold on mobile (M3); 19 report-builder checkboxes have no `<label for>` (L1). M4 (no last-superadmin safeguard) is explicitly by-design per CLAUDE.md and L2 is confirmed-correct — neither gets a code change.

**Approach:** 6 small, isolated fixes, each mirroring a pattern already proven elsewhere in this codebase (institution-scoping via `request.institution`, CSP-safe `addEventListener` binding, `validate_password()` usage). No refactors, no new abstractions.

## Boundaries & Constraints

**Always:** For H1, fix at the model layer (`CustomUser.save()`) so every existing `user_type` check across the app (backup, institution, sidebar) is corrected at once, instead of patching each call site. For H2, mirror `admin_user_list`'s/`admin_activity_logs`'s existing `request.institution`-scoping pattern when opening `admin_dashboard` to non-superusers. For M2, reuse the exact `validate_password()` pattern already used in `institution/forms.py`'s `clean()`.

**Ask First:** Nothing identified — all 6 fixes are mechanical and scoped to the report's own "likely fix location" suggestions.

**Never:** Do not implement a last-superadmin-standing safeguard (M4 — by design per CLAUDE.md, no code change). Do not touch L2 (confirmed correct, no-op). Do not touch `CustomUserRegistrationForm`'s password validation (not flagged by the report). Do not change `delete_helpers.py` business-rule logic, only the shared delete-modal CSS. Do not change CSS framework/Bootstrap version.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| H1 superuser backup | `is_superuser=True`, `user_type=USER`, save() called (incl. `createsuperuser`) | `user_type` auto-set to `SUPERADMIN`; `/backup/` now accessible | N/A |
| H1 existing superuser | Pre-existing row, `is_superuser=True`, `user_type=USER`, never re-saved | Data migration backfills `user_type=SUPERADMIN` | N/A |
| H2 institution admin | `user_type=ADMIN`, `is_staff=False`, visits `/users/admin/dashboard/` | Access granted; stats scoped to own institution only | N/A |
| H2 cross-institution leak | Same as above | Must NOT see other institutions' user counts/activity | Scope query by `request.institution` |
| M2 weak password | Admin submits 11-char password on `/users/admin/users/add/` | Rejected: "too short, 12 characters" (matches `/institution/clinicians/add/`) | `ValidationError` surfaced on `password1` field |
| M1 CSP toggle | Click "All"/"None"/"Show Field Selection" on `/reports/` | Checkboxes toggle; no CSP console violation | N/A |

</frozen-after-approval>

## Code Map

- `users/models.py:139` (`CustomUser.__str__`, before `full_name` property) -- add `save()` override: if `is_superuser` and `user_type != SUPERADMIN`, set `user_type = SUPERADMIN` (append to `update_fields` if passed)
- `users/migrations/0011_sync_superuser_user_type.py` (new) -- `RunPython` data migration backfilling `user_type='SUPERADMIN'` for all existing `is_superuser=True` rows; reverse is a no-op
- `users/decorators.py:7-16` (`admin_required`) -- also accept `user_type in (UserType.ADMIN, UserType.SUPERADMIN)`, not just `is_staff`/`is_superuser`; import `UserType` from `ndas.custom_codes.choice`
- `users/views.py:563-595` (`admin_dashboard`) -- scope `total_users`/`active_users`/`staff_users`/`recent_logins`/`recent_activities`/`recent_users` by `request.institution` when `not request.user.is_superuser`, exactly mirroring `admin_user_list` (`users/views.py:608-617`) and `admin_activity_logs` (`users/views.py:942-947`)
- `reports/templates/reports/builder.html:297,300,408,419,422` -- replace inline `onclick="togglePatientFields(...)"` / `toggleFieldSelection()` / `toggleAssessmentFields(...)` with `id` attributes + `addEventListener` registration inside the existing `<script nonce="{{ request.csp_nonce }}">` block at line 493
- `reports/templates/reports/builder.html:318-402` -- add `id="patient_field_{value}"` to the 19 `patient-field` checkboxes (currently no `id`) and `for="patient_field_{value}"` on each sibling `<label class="form-check-label">`
- `users/forms.py:1-11` (imports), `:464-468` (`AdminUserCreationForm.clean_password1`) -- replace the ad-hoc `len(password1) < 8` check with `django.contrib.auth.password_validation.validate_password(password1)` (same pattern as `institution/forms.py:135-139`); update `password1`'s `help_text` (`users/forms.py:418`) to drop the inaccurate "8 characters" claim
- `templates/src/partials/delete_confirmation_modal.html:6` (`.modal-dialog`) -- add `modal-dialog-scrollable`, or bound `.modal-content` to `max-height: 90vh` with `overflow-y: auto` on `.modal-body` only, so the footer (Cancel/Delete) stays visible without scrolling the whole modal

## Tasks & Acceptance

**Execution:**
- [x] `users/models.py` -- add `CustomUser.save()` override auto-syncing `user_type` to `SUPERADMIN` for superusers -- fixes H1 at the root for every `user_type` check in the app
- [x] `users/migrations/0011_sync_superuser_user_type.py` -- data migration backfilling existing superusers -- fixes H1 for accounts created before this change (e.g. the real owner account)
- [x] `users/decorators.py` -- `admin_required` accepts `user_type` ADMIN/SUPERADMIN -- fixes H2's permission mismatch
- [x] `users/views.py` -- institution-scope `admin_dashboard`'s stats for non-superusers -- prevents H2's fix from introducing a cross-institution data leak
- [x] `reports/templates/reports/builder.html` -- move 5 `onclick` handlers into the CSP-nonced script block -- fixes M1
- [x] `reports/templates/reports/builder.html` -- add `id`/`for` pairing to 19 `patient-field` checkboxes -- fixes L1
- [x] `users/forms.py` -- `AdminUserCreationForm` uses `validate_password()` -- fixes M2's policy inconsistency
- [x] `templates/src/partials/delete_confirmation_modal.html` -- bound modal height, scrollable body -- fixes M3

**Acceptance Criteria:**
- Given a freshly-created Django superuser (`createsuperuser`, default `user_type=USER`), when they visit `/backup/`, then they are not redirected away with a permission error.
- Given an existing superuser row from before this change, when the migration runs, then its `user_type` becomes `SUPERADMIN`.
- Given a `user_type=ADMIN`, non-staff Institution Admin, when they click any of the 4 sidebar "Administration" links, then they reach the page instead of being redirected to their own profile.
- Given that same Institution Admin on `/users/admin/dashboard/`, when the page renders, then the counts reflect only their own institution, not the whole system.
- Given any role on `/reports/`, when they click "All"/"None"/"Show Field Selection", then the checkboxes toggle and no CSP violation appears in the console.
- Given an admin submitting an 11-character password on `/users/admin/users/add/`, when the form is validated, then it is rejected with the same "at least 12 characters" message `/institution/clinicians/add/` gives.
- Given the report builder's 19 `patient_fields` checkboxes, when inspected, then each has a unique `id` and its label has a matching `for`.
- Given the patient-delete modal on a 375×667 viewport, when opened, then Cancel/Delete are reachable without scrolling the page behind the modal (scrolling the modal body itself is acceptable only if the footer stays pinned/visible).

## Design Notes

H1's root-cause fix (model `save()` override) is deliberately chosen over patching every `user_type not in (ADMIN, SUPERADMIN)` check in `backup/views.py` (6+ call sites) and `institution/views.py` — syncing the field once at the source keeps every existing and future check correct without hunting down call sites. H2's `admin_dashboard` scoping reuses the exact `request.institution` pattern already present in `admin_user_list`/`admin_activity_logs` in the same file — not a new convention.

## Verification

**Commands:**
- `venv\Scripts\python.exe manage.py makemigrations users --check` -- expected: no missing migrations after `0011` is added (run `makemigrations users` first to generate it from the model change, then verify its content matches the intended backfill)
- `venv\Scripts\python.exe manage.py test users backup institution reports` -- expected: all pass (one run at a time; shared SQLite test DB)

**Manual checks (if no CLI):**
- `/reports/` in a browser: click the 3 toggle buttons, confirm no CSP console errors and checkboxes respond.
- `/patient/view/<id>/` delete modal at 375×667: confirm Cancel/Delete visible or reachable without surprise.
