---
title: 'Add institution field to admin user add/edit, scoped by role'
type: 'feature'
created: '2026-09-03'
status: 'done'
review_loop_iteration: 1
context: []
baseline_commit: '009c28016ff5bd4d9f1f37c14a89bf625a7f795f'
---

<!-- Target: 900–1300 tokens. -->

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `admin_user_add`/`admin_user_edit` (users app, gated by `@admin_required` = staff OR superuser) have no institution handling at all today — a non-superuser staff ("institutional") admin can create a user with `institution=None`, and nothing stops a POST from setting/leaving any institution on a user regardless of who's creating them.

**Approach:** Add a superuser-only `institution` field to `AdminUserCreationForm`/`AdminUserEditForm`, following the exact `is_superuser`-gated pattern `admin_user_list`/`UserSearchForm` already use (field structurally popped for non-superusers, not just hidden). Superuser's Add form defaults the field's initial value to the seeded default institution (`Institution.objects.filter(slug=settings.DEFAULT_INSTITUTION_SLUG)`). Non-superuser staff admins never see the field; the view force-assigns the new/edited user's institution to `request.institution` (their own) on create, and edit relies on the existing `get_institution_scoped_user_or_404` fetch (already same-institution-only) with the field removed so POST can't override it.

## Boundaries & Constraints

**Always:**
- Institution field visible/settable only when `request.user.is_superuser` — same gating already used by `UserSearchForm`/`admin_user_list`.
- Non-superuser staff admin creating a user: new user's `institution` is forced to `getattr(request, 'institution', None)`, ignoring any `institution` value in POST (field not in `form.fields`, so Django ignores it).
- **Phase-gated blocking (amended, loop 1):** only block non-superuser creation when `settings.MULTI_INSTITUTION_ENABLED` is `True` AND the staff admin's own institution is `None` (the genuine "not yet onboarded" case) — show an error, no state change. When `MULTI_INSTITUTION_ENABLED` is `False`, `InstitutionContextMiddleware` never resolves `request.institution` for anyone; in that mode do NOT block — create the user with `institution=None`, matching this view's pre-existing (pre-spec) behavior exactly.
- Superuser's **Add** form initial value = seeded default institution; field stays optional (`required=False`) so a superuser can still clear it (e.g. creating another SUPERADMIN with no institution, matching `CustomUser.institution`'s `null=True`).
- Superuser's **Edit** form shows the target user's current institution (plain ModelForm behavior) — no forced default on edit.
- **Add** form institution queryset = `Institution.objects.filter(is_active=True).order_by('name')`, matching `UserSearchForm`.
- **Edit** form institution queryset (amended, loop 1) = the same active-institutions queryset **plus** the instance's current institution even if it has since been deactivated (`Q(is_active=True) | Q(pk=instance.institution_id)`), so the target user's real institution is never silently missing from the choices — prevents an unrelated field edit from defaulting the `<select>` to the alphabetically-first active institution and silently reassigning the user.

**Never:**
- Do not touch `user_type`, `is_superuser`, or `is_staff` handling in these forms/views.
- Do not modify `institution/institution_clinician_add` or any other institution-app view.
- Do not modify `CustomUserRegistrationForm`, `CustomUserEditForm`, `get_institution_scoped_user_or_404`, or `admin_user_delete`/`toggle_status`/`activity`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Superuser opens Add form | GET `admin_user_add` as superuser | Institution select rendered, initial = default institution | N/A |
| Superuser adds user, changes institution | POST with `institution=<other pk>` | New user's institution = chosen one | N/A |
| Superuser adds user, clears institution | POST with `institution=''` | New user's institution = `None` | N/A |
| Staff (non-superuser) admin adds user | POST `admin_user_add`, no institution field in form | New user's institution = staff admin's own institution | N/A |
| Staff admin tampers with institution POST field | POST includes forged `institution=<other pk>` | Ignored; institution still forced to staff admin's own | N/A |
| Staff admin has no institution assigned (Phase 2, `MULTI_INSTITUTION_ENABLED=True`) | POST `admin_user_add`, `request.institution is None` | No user created | Form re-rendered with error message |
| Staff admin adds user under Phase 1 (`MULTI_INSTITUTION_ENABLED=False`) | POST `admin_user_add`; middleware never sets `request.institution` for anyone | User created normally, `institution=None` (unchanged from pre-spec behavior) | N/A |
| Superuser edits a user's institution | POST `admin_user_edit` with new `institution` | User's institution updated | N/A |
| Staff admin edits own-institution user | GET/POST `admin_user_edit`, no institution field | User's institution unchanged | N/A |
| Superuser/staff admin opens Edit for a user whose institution was since deactivated | GET `admin_user_edit` for that user | Institution select includes and pre-selects that (inactive) institution | N/A |

</frozen-after-approval>

## Code Map

- `users/forms.py:412-468` -- `AdminUserCreationForm` -- add `institution` field (mirror `UserSearchForm` at `users/forms.py:529-534`) + add to `Meta.fields`
- `users/forms.py:471-502` -- `AdminUserEditForm` -- same institution field addition + `Meta.fields`; add `__init__` override widening the queryset to include `self.instance.institution_id` via `Q(is_active=True) | Q(pk=self.instance.institution_id)` (guard `instance.pk` truthy / `institution_id` not None before adding the `Q`)
- `users/views.py:667-693` -- `admin_user_add` -- pop field for non-superuser, force `user.institution`, default initial via `settings.DEFAULT_INSTITUTION_SLUG` for superuser GET; block-on-`None` only applies when `settings.MULTI_INSTITUTION_ENABLED` is `True`
- `users/views.py:696-746` -- `admin_user_edit` -- pop field for non-superuser (GET+POST); no other logic change (institution already correct via `get_institution_scoped_user_or_404` at line 699)
- `users/views.py:597-607` -- `admin_user_list` -- reuse reference for the exact `is_superuser` pop pattern
- `ndas/settings.py:173` -- `MULTI_INSTITUTION_ENABLED` -- gate for the Phase-1/Phase-2 blocking distinction
- `institution/middleware.py:41-51,96-104` -- `InstitutionContextMiddleware` -- confirms `request.institution` is never set when `MULTI_INSTITUTION_ENABLED=False` (Phase 1 branch skips resolution entirely)
- `templates/users/admin/user_add.html:196-223` -- "Permissions & Status" card -- add superuser-gated institution `<select>`, mirror `user_list.html:36-40` `{% if request.user.is_superuser %}` guard
- `templates/users/admin/user_edit.html:177-220` (same card) -- same addition
- `ndas/settings.py:174` -- `DEFAULT_INSTITUTION_SLUG` -- source of the seeded default institution
- `users/tests/test_crud.py:132,208` -- `AdminUserManagementTest`, `AdminUserListInstitutionFilterTest` -- pattern reference for new test class; `UserTestBase` (line 28) for fixtures

## Tasks & Acceptance

**Execution:**
- [x] `users/forms.py` -- add `institution` `ModelChoiceField` (`required=False`, active-institutions queryset, `form-control` widget) to `AdminUserCreationForm` and `AdminUserEditForm`, include `'institution'` in both `Meta.fields` -- lets ModelForm save it when present
- [x] `users/forms.py::AdminUserEditForm.__init__` -- widen the `institution` field's queryset to also include the instance's current institution when it's set and inactive, so it's never missing from the rendered choices
- [x] `users/views.py::admin_user_add` -- `del form.fields['institution']` when not superuser (GET and POST); on superuser GET set `form.fields['institution'].initial` to the default institution; on POST for non-superuser, after `form.save(commit=False)`, if `settings.MULTI_INSTITUTION_ENABLED` and `request.institution is None`, bail with an error; otherwise set `user.institution = getattr(request, 'institution', None)` then `user.save()`
- [x] `users/views.py::admin_user_edit` -- `del form.fields['institution']` when not superuser (GET and POST); no other change
- [x] `templates/users/admin/user_add.html` -- add institution `<select>` in the Permissions & Status card, wrapped in `{% if request.user.is_superuser %}`
- [x] `templates/users/admin/user_edit.html` -- same
- [x] `users/tests/test_crud.py` -- new `AdminUserAddEditInstitutionScopingTest(UserTestBase)` covering the I/O matrix above (needs an `Institution` fixture with the seeded default slug plus one other active institution, plus one `override_settings(MULTI_INSTITUTION_ENABLED=False)` case and one deactivated-current-institution edit case)

**Acceptance Criteria:**
- Given a superuser, when they GET `admin_user_add`, then the institution select's initial value is the seeded default institution and only lists active institutions.
- Given a superuser, when they POST `admin_user_add`/`admin_user_edit` with a chosen (or cleared) institution, then the saved user's institution matches exactly.
- Given a non-superuser staff admin with an institution assigned, when they POST `admin_user_add` (with or without a forged institution value), then the created user's institution equals the staff admin's own institution.
- Given a non-superuser staff admin with no institution assigned under `MULTI_INSTITUTION_ENABLED=True`, when they POST `admin_user_add`, then no user is created and an error message is shown.
- Given `MULTI_INSTITUTION_ENABLED=False`, when a non-superuser staff admin POSTs `admin_user_add`, then the user is created normally with `institution=None`, matching pre-spec behavior.
- Given a non-superuser staff admin, when they GET or POST `admin_user_edit` for a user in their own institution, then no institution field is rendered and that user's institution is unchanged after save.
- Given a user whose institution was deactivated after assignment, when a superuser opens `admin_user_edit` for that user, then the institution select includes and pre-selects that institution.

## Spec Change Log

- **Loop 1 (intent_gap, resolved by human):** Two review findings traced back to frozen `Boundaries & Constraints` bullets:
  1. *verification-gap* — the original "block staff-admin creation if institution is `None`" rule didn't distinguish Phase 2 "not yet onboarded" from Phase 1 (`MULTI_INSTITUTION_ENABLED=False`), where `request.institution` is never resolved for anyone — a real deployment mode this would have broken (staff admins permanently unable to create users). **Amended:** blocking now applies only when `MULTI_INSTITUTION_ENABLED=True`.
  2. *blind-hunter + edge-case-hunter (deduped)* — the institution queryset (`is_active=True` only) applied to the Edit form too, so a user whose institution was later deactivated would render with no matching `<select>` option, risking a silent reassignment on any unrelated edit. **Amended:** Edit form's queryset additionally includes the instance's current institution even if inactive; Add form queryset is unchanged (active-only).
  - **KEEP:** everything else from the original spec (the `is_superuser` field-popping pattern, forced institution on non-superuser add, default-institution initial on Add, optional/clearable field) — confirmed correct by the review layer, not touched by this amendment.
  - Code was reverted to `baseline_commit` before this amendment; re-implementation follows step-03 fresh.
  - A third finding (no `getattr` fallback around `settings.DEFAULT_INSTITUTION_SLUG`) was rejected — that setting always has a `default=` in `ndas/settings.py` and cannot be missing.

## Verification

**Commands:**
- `python manage.py test users -v 1` -- expected: `OK`, no new failures beyond the 2 pre-existing ones already logged in `deferred-work.md`

## Suggested Review Order

**View logic — who sees/controls the field**

- Entry point: superuser branch saves the form as-is; non-superuser branch blocks under Phase 2, else force-assigns the admin's own institution.
  [`views.py:670-711`](../../users/views.py#L670-L711)

- Same superuser-only gate applied to Edit — no force-assignment needed since `get_institution_scoped_user_or_404` already guarantees same-institution.
  [`views.py:735-786`](../../users/views.py#L735-L786)

- Default-institution initial, now `is_active=True`-filtered so it can't point at a deactivated row outside the field's own choices (patch, loop 2).
  [`views.py:727-729`](../../users/views.py#L727-L729)

**Form fields — queryset and the deactivated-institution fix**

- Superuser-facing `institution` field on both forms; active-institutions queryset, optional/clearable.
  [`forms.py:426-430`](../../users/forms.py#L426-L430)

- `AdminUserEditForm.__init__` widens the queryset to include the instance's current institution even if inactive — the loop-1 fix for silent reassignment on unrelated edits.
  [`forms.py:517-529`](../../users/forms.py#L517-L529)

**Templates — superuser-gated rendering**

- Institution `<select>` only rendered for superusers, mirroring `user_list.html`'s existing filter gate.
  [`user_add.html:222-234`](../../templates/users/admin/user_add.html#L222-L234)
  [`user_edit.html:211-223`](../../templates/users/admin/user_edit.html#L211-L223)

**Tests**

- Full matrix: superuser add/edit set-or-clear, staff-admin forced-own-institution + forged-POST-ignored, Phase 1 vs Phase 2 blocking, deactivated-institution edit (GET queryset + full POST round-trip).
  [`test_crud.py:265-509`](../../users/tests/test_crud.py#L265-L509)
