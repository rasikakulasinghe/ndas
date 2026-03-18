---
title: 'Security & Performance Hardening — Adversarial Review 2026-03-12'
slug: 'adversarial-review-2026-03-12'
created: '2026-03-12'
status: 'adversarial-findings-resolved'
stepsCompleted: [1, 2, 3, 4, 5, 6]
tech_stack: ['Django 4.2', 'Python 3.x', 'django-ratelimit 4.1.0', 'SQLite/PostgreSQL']
files_to_modify:
  - patients/views.py
  - patients/models.py
  - institution/middleware.py
  - institution/views.py
  - institution/models.py
  - users/views.py
  - video/models.py
code_patterns:
  - 'institution_scope(request, field) validated against _ALLOWED_SCOPE_FIELDS frozenset; raises ImproperlyConfigured on unknown path; returns {} when request.institution is None'
  - 'Patient.objects.for_institution(inst) is the manager shortcut'
  - 'get_object_or_404() is the NDAS standard for object resolution'
  - 'Bookmark model uses generic object_id field — no patient FK; institution scope must be enforced at object resolution time'
  - 'CustomUser model has email_verification_token and email fields; neither has a unique DB constraint enforced at application layer against MultipleObjectsReturned'
  - 'RateLimitedPasswordResetView is a CBV wrapping Django auth_views.PasswordResetView with class-level @method_decorator'
  - 'video/models.py does NOT import transaction from django.db'
  - 'institution/views.py already imports transaction, logger, timezone, ratelimit'
  - 'No AuditLog model exists in the codebase — institution switch uses only logger.info()'
  - 'N+1 properties on Patient model: isNewPatient, isDischarged, isScreeningPositive, isLastGMANormal, isLastHINENormal, isLastDANormal, isDiagnosisNormal (delegates to prior 3), isBookmarked, getGMAIndicationsList, getDiagnosisList — none use @cached_property'
test_patterns:
  - 'patients/tests/test_views.py — comprehensive view tests including DeleteEndpointErrorSanitizationTest (lines 556-618)'
  - 'users/tests.py — empty stub, no tests to break'
  - 'institution app — check for existing tests before modifying middleware/views'
---

# Tech-Spec: Security & Performance Hardening — Adversarial Review 2026-03-12

**Created:** 2026-03-12

## Overview

### Problem Statement

10 open CRITICAL/HIGH findings from the 2026-03-12 adversarial review span multi-tenancy enforcement gaps, N+1 query performance from Patient model properties, per-request middleware DB calls without caching, rate limiting bypass vectors (IP-only login and password reset), concurrent video upload race conditions, and missing audit trails for institution context switches.

### Solution

Targeted backend fixes across 7 files plus one migration. Patient model properties migrated to queryset annotations with backwards-compatible fallbacks; middleware gets per-request caching; rate limiting extended to per-username and per-email; institution access switches get a persistent audit log model; `MultipleObjectsReturned` gaps closed in users and middleware; video upload `save()` restructured with `transaction.atomic()` around the DB write phase only.

### Scope

**In Scope:**
- Finding #1 (CRITICAL): Institution scope not enforced on patient resolution in `bookmark_view` (`patients/views.py:1572`)
- Finding #3 (CRITICAL): `MultipleObjectsReturned` uncaught in `users/views.py:300,342` and `institution/middleware.py:69`
- Finding #4 (HIGH): N+1 queries from Patient model properties — full migration to queryset annotations (`patients/models.py:384–543`)
- Finding #5 (HIGH): Compound N+1 via `isDiagnosisNormal` — resolved as part of Finding #4 annotation migration (`patients/models.py:479–481`)
- Finding #6 (HIGH): Middleware fires raw DB query on every request — per-request caching (`institution/middleware.py:69`)
- Finding #7 (HIGH): Weak login rate limiting (IP-only) — add per-username rate limit (`users/views.py:36`)
- Finding #8 (HIGH): Weak password reset rate limiting (IP-only) — add per-email rate limit (`users/views.py:369–382`)
- Finding #9 (HIGH): `institution_scope()` returns `{}` when institution is None — guard at security-sensitive call sites (`patients/views.py:1595`)
- Finding #11 (HIGH): No transaction isolation on concurrent video uploads (`video/models.py:215–285`)
- Finding #12 (HIGH): No persistent audit trail for institution context switches (`institution/views.py:78+`)

**Out of Scope:**
- Finding #2: Virus scanning — deferred as a separate epic (requires ClamAV or equivalent infrastructure)
- Finding #10: Department/team-based access control — deferred pending data model for departments/teams
- Findings #13–#22: All MEDIUM and LOW severity findings

---

## Context for Development

### Codebase Patterns

- `institution_scope(request, field='patient__institution')` lives in `ndas/custom_codes/custom_methods.py`. Validated against `_ALLOWED_SCOPE_FIELDS` frozenset (defined after the function). Returns `{field: inst}` when `request.institution` is not None; returns `{}` (empty dict) when None — **no institution filtering in Phase 1 / transitional state**. Call sites must guard against this.
- `Patient.objects.for_institution(inst)` is the scoped manager shortcut used throughout `patients/views.py`.
- `get_object_or_404()` is the project standard. Accepts a queryset as first arg.
- **Bookmark model**: Uses generic `object_id` field — no `patient` FK. `bookmark_view` (line 1561) fetches only the Bookmark object and passes `{"bookmark": bookmark}` to `bookmark/view.html`. It does NOT currently resolve `object_id` to a Patient record at all. Institution scope on the bookmark itself uses `owner__institution`.
- **`MultipleObjectsReturned` gaps**: `institution/middleware.py:69` catches only `Institution.DoesNotExist`. `users/views.py:300` catches only `CustomUser.DoesNotExist` on `email_verification_token` lookup. `users/views.py:342` catches only `CustomUser.DoesNotExist` on `email` lookup.
- **Middleware caching**: `_resolve_superadmin_context()` calls `Institution.objects.get(pk=active_id, is_active=True)` on every request for superadmin users. No per-request or session caching exists. Fix: check `hasattr(request, '_institution_cache')` before querying; set `request._institution_cache` after successful query.
- **Login rate limit**: `@ratelimit(key='ip', rate='3/m', method='POST', block=True)` on `loginPage`. IP-only — no per-username.
- **Password reset rate limit**: `@method_decorator(ratelimit(key='ip', rate='3/h', method='POST', block=True), name='post')` on `RateLimitedPasswordResetView(auth_views.PasswordResetView)`. IP-only — no per-email. Must override `post()` to apply per-email check via `is_ratelimited()`.
- **N+1 model properties** (none use `@cached_property`, none pre-annotated): `isNewPatient` (Video.exists), `isDischarged` (CDICRecord.first), `isScreeningPositive` (GMAssessment + 2x HINEAssessment), `isLastGMANormal` (GMAssessment.first), `isLastHINENormal` (HINEAssessment.first), `isLastDANormal` (DevelopmentalAssessment.first), `isDiagnosisNormal` (delegates to prior 3 → up to 6 queries), `isBookmarked` (Bookmark.get), `getGMAIndicationsList` (M2M .all()), `getDiagnosisList` (GMAssessment + HINEAssessment + DA .first() + M2M).
- **Video `save()`**: No `transaction` imported in `video/models.py`. Sequence: patient existence check → file size → metadata I/O (long) → `super().save()`. Fix: restructure so all I/O is done first, then wrap validation + `super().save()` in `transaction.atomic()`. Do NOT hold the transaction open during file I/O.
- **Audit trail**: `institution/views.py:institution_switch()` calls `logger.info()` on context switch but writes no persistent record. No `AuditLog` model exists anywhere in the codebase. Fix requires a new `InstitutionSwitchLog` model in `institution/models.py` and one migration.
- `institution/views.py` already imports: `transaction`, `IntegrityError`, `logger`, `timezone`, `ratelimit`, `login_required`.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `patients/views.py` | Finding #1 (`bookmark_view`:1561), Finding #9 (`institution_scope` usage:1595) |
| `patients/models.py` | Findings #4/#5 (N+1 properties:384–543) |
| `institution/middleware.py` | Finding #3 (`MultipleObjectsReturned`:69), Finding #6 (per-request DB query:69) |
| `institution/views.py` | Finding #12 (no persistent audit trail:78–109) |
| `institution/models.py` | New `InstitutionSwitchLog` model for Finding #12 |
| `users/views.py` | Finding #3 (`MultipleObjectsReturned`:300,342), Finding #7 (login rate limit:36), Finding #8 (password reset rate limit:369) |
| `video/models.py` | Finding #11 (no transaction isolation in `save()`:215–285) |
| `ndas/custom_codes/custom_methods.py` | `institution_scope()` function (lines 1–30); `_ALLOWED_SCOPE_FIELDS` frozenset |
| `patients/tests/test_views.py` | Existing tests — 818 lines; `DeleteEndpointErrorSanitizationTest` at lines 556–618 |
| `_bmad-output/adversarial-review-2026-03-12.md` | Full finding descriptions |

### Technical Decisions

| Finding | Decision |
|---------|----------|
| **#1 (bookmark_view)** | Implement patient resolution: after fetching the bookmark, add `patient = get_object_or_404(Patient.objects.for_institution(getattr(request, 'institution', None)), id=bookmark.object_id)` and pass `patient` into the template context. Stale cross-institution bookmarks 404. Add code comment explaining architectural constraint. |
| **#3 (middleware)** | Extend the `except` clause at line 70 to `except (Institution.DoesNotExist, Institution.MultipleObjectsReturned)` — both cases redirect to institution selector and clear the stale session key. |
| **#3 (users)** | `verify_email` (line 300): add `except CustomUser.MultipleObjectsReturned` — treat as invalid token (same path as `DoesNotExist`). `resend_verification_email` (line 342): add `except CustomUser.MultipleObjectsReturned` — use same neutral message as `DoesNotExist` path. |
| **#4/#5 (N+1)** | Add `with_status_annotations()` to the `Patient` queryset (via the existing custom manager). It adds `Exists()` / `Subquery()` annotations for each N+1 property. Update properties to check `getattr(self, '_annotated_<name>', None)` first and fall back to direct DB query — so single-object access still works. Update the dashboard and patient list views to call `.with_status_annotations()`. Read each property's full implementation before writing annotations to confirm exact query targets and field names. |
| **#6 (middleware caching)** | Before the `Institution.objects.get()` call in `_resolve_superadmin_context`, add: `if hasattr(request, '_institution_cache'): request.institution = request._institution_cache; return None`. After the successful get, add: `request._institution_cache = request.institution`. |
| **#7 (login rate limit)** | Stack a second decorator on `loginPage`: `@ratelimit(key='post:username', rate='5/m', method='POST', block=True)` placed directly above the existing `@ratelimit(key='ip', ...)` decorator. Both limits must pass independently. |
| **#8 (password reset)** | Override `post()` on `RateLimitedPasswordResetView`. Import `is_ratelimited` from `django_ratelimit.core`. Inside `post()`, extract `email = request.POST.get('email', '').lower().strip()`. Call `is_ratelimited(request, fn=self.post, key='user_or_ip', rate='5/h', method='POST', increment=True)` — if rate limited, add a form error and re-render. Neutral message: _"If an account with this email exists, a reset link will be sent."_ |
| **#9 (institution_scope guard)** | At `bookmark_delete` and any other security-critical view where `institution_scope()` is splatted and `request.institution` may be None: add an explicit early-return guard before the queryset call. Pattern: `if not getattr(request, 'institution', None): return HttpResponseForbidden()` — or redirect to institution selector for superadmins. Document the guard with a comment. |
| **#11 (video save)** | Import `transaction` from `django.db` in `video/models.py`. Restructure `save()`: move all I/O (patient check, file size, metadata extraction) before the `transaction.atomic()` block. Inside `with transaction.atomic():`, for updates (`self.pk` is not None on PostgreSQL), re-fetch using `select_for_update()` before `super().save()`. Wrap the engine check as before: `if 'postgresql' in settings.DATABASES['default']['ENGINE']`. Import `settings` from `django.conf`. |
| **#12 (audit trail)** | New `InstitutionSwitchLog` model in `institution/models.py`: fields `user` (FK `settings.AUTH_USER_MODEL`, `on_delete=SET_NULL, null=True`), `institution` (FK `Institution`, `on_delete=SET_NULL, null=True`), `previous_institution_id` (`IntegerField(null=True, blank=True)`), `switched_at` (`DateTimeField(auto_now_add=True)`), `ip_address` (`GenericIPAddressField(null=True, blank=True)`). In `institution_switch()`, after the session update, create the log inside `try/except Exception` — log creation failure must never block the switch. Get IP from `request.META.get('REMOTE_ADDR')`. |

---

## Implementation Plan

### Tasks

**Ordering:** Task 1 (model + migration, prerequisite for Task 2) → Task 2 (audit logging) → Task 3 (middleware: caching + MultipleObjectsReturned) → Task 4 (users MultipleObjectsReturned) → Task 5 (login rate limit) → Task 6 (password reset rate limit) → Task 7 (bookmark patient resolution) → Task 8 (institution_scope guard) → Task 9 (video save transaction) → Task 10 (N+1 annotation migration, most complex, independent)

---

- [x] **Task 1: Create `InstitutionSwitchLog` model and migration** (Finding #12, prerequisite)
  - **File:** `institution/models.py`
  - **Action:**
    1. Add the following model at the end of the file (after existing models):
       ```python
       class InstitutionSwitchLog(models.Model):
           user = models.ForeignKey(
               settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
               null=True, related_name='institution_switch_logs'
           )
           institution = models.ForeignKey(
               'Institution', on_delete=models.SET_NULL,
               null=True, related_name='switch_logs'
           )
           previous_institution_id = models.IntegerField(null=True, blank=True)
           switched_at = models.DateTimeField(auto_now_add=True)
           ip_address = models.GenericIPAddressField(null=True, blank=True)

           class Meta:
               ordering = ['-switched_at']
               indexes = [models.Index(fields=['user', 'switched_at'])]

           def __str__(self):
               return f"{self.user} → Institution {self.institution_id} at {self.switched_at}"
       ```
    2. Confirm `from django.conf import settings` is imported at the top of `institution/models.py`.
    3. Run `python manage.py makemigrations institution` to generate the migration.
  - **Notes:** `SET_NULL` on both FKs ensures the log record is preserved even if the user or institution is later deleted. `previous_institution_id` is an integer (not FK) to preserve the historical ID even after deletion.

---

- [x] **Task 2: Add persistent audit record to `institution_switch` view** (Finding #12)
  - **File:** `institution/views.py`
  - **Action:**
    1. Import `InstitutionSwitchLog` at the top: `from institution.models import Institution, InstitutionSwitchLog`
    2. In `institution_switch()`, immediately after `request.session['active_institution_id'] = institution.pk` (the session update), add:
       ```python
       # Persistent audit trail — failure must never block the switch
       try:
           previous_id = request.session.get('_prev_institution_id')
           InstitutionSwitchLog.objects.create(
               user=request.user,
               institution=institution,
               previous_institution_id=previous_id,
               ip_address=request.META.get('REMOTE_ADDR'),
           )
       except Exception as e:
           logger.error("Failed to write InstitutionSwitchLog: %s", e)
       ```
    3. Before the session update, capture the previous institution ID:
       ```python
       # Capture previous institution before overwriting
       request.session['_prev_institution_id'] = request.session.get('active_institution_id')
       ```
  - **Notes:** The `try/except Exception` ensures audit log failure is silent to the user — only logged. `_prev_institution_id` is written to session just before the switch to record the previous state.

---

- [x] **Task 3: Add per-request caching and fix `MultipleObjectsReturned` in middleware** (Findings #6 + #3)
  - **File:** `institution/middleware.py`
  - **Action:**
    1. In `_resolve_superadmin_context()`, before the `try` block at line 68, add the cache check:
       ```python
       # Per-request cache: avoid repeated DB hits within a single request cycle
       if hasattr(request, '_institution_cache'):
           request.institution = request._institution_cache
           return None
       ```
    2. Extend the `except` clause at line 70 from:
       ```python
       except Institution.DoesNotExist:
       ```
       to:
       ```python
       except (Institution.DoesNotExist, Institution.MultipleObjectsReturned):
       ```
    3. After the successful `request.institution = Institution.objects.get(...)` assignment, add:
       ```python
       request._institution_cache = request.institution
       ```
  - **Notes:** `request._institution_cache` is request-scoped — it dies with the request object and never leaks between requests. `MultipleObjectsReturned` is treated identically to `DoesNotExist`: clear the stale session key and redirect to the selector, since both indicate an invalid session state.

---

- [x] **Task 4: Fix `MultipleObjectsReturned` in `users/views.py`** (Finding #3)
  - **File:** `users/views.py`
  - **Action:**
    1. At line ~300 (`verify_email`, `CustomUser.objects.get(email_verification_token=token)`), extend the except clause:
       ```python
       except (CustomUser.DoesNotExist, CustomUser.MultipleObjectsReturned):
           messages.error(request, 'Invalid verification link.')
           return redirect('user-login')
       ```
    2. At line ~342 (`resend_verification_email`, `CustomUser.objects.get(email=email)`), extend the except clause:
       ```python
       except (CustomUser.DoesNotExist, CustomUser.MultipleObjectsReturned):
           messages.success(request, 'If an account with this email exists and is unverified, a link has been sent.')
           return redirect('user-login')
       ```
  - **Notes:** For `verify_email`, treating `MultipleObjectsReturned` as an invalid token is correct — the token field should be unique, so duplicates indicate a data anomaly. For `resend_verification_email`, the neutral message prevents distinguishing between not-found, duplicate, and verified-account states (enumeration resistance).

---

- [x] **Task 5: Add per-username rate limit to login view** (Finding #7)
  - **File:** `users/views.py`, `loginPage` function (~line 36)
  - **Action:**
    1. Stack a second `@ratelimit` decorator immediately above the existing one:
       ```python
       @ratelimit(key='post:username', rate='5/m', method='POST', block=True)
       @ratelimit(key='ip', rate='3/m', method='POST', block=True)
       def loginPage(request):
       ```
  - **Notes:** Both decorators apply independently — an attacker must bypass both. `post:username` reads from `request.POST['username']`. Rate `5/m` is slightly higher than the IP limit to accommodate legitimate fast retries (e.g., caps lock). The IP decorator remains unchanged as the outer defence. If the username field name in the login form is not `username`, verify the POST key name first.

---

- [x] **Task 6: Add per-email rate limit to password reset view** (Finding #8)
  - **File:** `users/views.py`, `RateLimitedPasswordResetView` class (~line 369)
  - **Action:**
    1. Import `is_ratelimited` at the top of the file: `from django_ratelimit.core import is_ratelimited`
    2. Override `post()` on `RateLimitedPasswordResetView`:
       ```python
       class RateLimitedPasswordResetView(auth_views.PasswordResetView):
           def post(self, request, *args, **kwargs):
               email = request.POST.get('email', '').lower().strip()
               if email:
                   limited = is_ratelimited(
                       request,
                       fn=self.post,
                       key=f'email:{email}',
                       rate='5/h',
                       method='POST',
                       increment=True,
                   )
                   if limited:
                       # Neutral message — same as success to prevent timing attacks
                       from django.contrib import messages as _messages
                       _messages.info(
                           request,
                           'If an account with this email exists, a reset link has been sent.'
                       )
                       return redirect(self.request.path)
               return super().post(request, *args, **kwargs)
       ```
  - **Notes:** `is_ratelimited()` uses the same cache backend as `@ratelimit`. The email key is lowercased and stripped to prevent trivial bypass via case variation. The per-email limit (5/h) is applied in addition to the existing per-IP limit (3/h) — both must pass. Neutral redirect message prevents confirming whether the account exists.

---

- [x] **Task 7: Implement patient resolution in `bookmark_view`** (Finding #1)
  - **File:** `patients/views.py`, `bookmark_view` function (~line 1561)
  - **Action:**
    1. After the `bookmark = get_object_or_404(...)` line (line 1562), add:
       ```python
       # Resolve bookmarked patient with institution scope.
       # Institution scope enforced here — stale cross-institution bookmarks will 404.
       # Architectural note: Bookmark.object_id is a generic field (no patient FK).
       patient = get_object_or_404(
           Patient.objects.for_institution(getattr(request, 'institution', None)),
           id=bookmark.object_id
       )
       ```
    2. Update the render call to include `patient` in context:
       ```python
       return render(request, "bookmark/view.html", {"bookmark": bookmark, "patient": patient})
       ```
    3. Remove the existing TODO comment at line 1572 (it will now be implemented).
  - **Notes:** This enforces institution scope at patient resolution time — the correct fix given the generic `object_id` design. If `bookmark.object_id` references a patient in a different institution, `for_institution()` excludes it and `get_object_or_404` raises 404. The template `bookmark/view.html` should be checked to see if it already references `patient` — if it does via `bookmark.object_id`, update it to use `patient` directly. If the template does not currently render patient data at all, the context addition is additive and safe.

---

- [x] **Task 8: Add `institution_scope()` empty-dict guard at security-sensitive call sites** (Finding #9)
  - **File:** `patients/views.py` (~line 1595 and other bookmark operation views)
  - **Action:**
    1. Identify all views in `patients/views.py` that use `**institution_scope(request, ...)` in a security-critical context (delete, edit, or access-controlled views). Search for `institution_scope(request` in the file.
    2. For `bookmark_delete` and any other bookmark views that use `institution_scope(request, 'owner__institution')`, add an explicit None guard before the queryset:
       ```python
       # Guard: if institution context is absent, deny access rather than silently returning unscoped results
       if not getattr(request, 'institution', None):
           return HttpResponseForbidden()
       ```
       Place this guard at the top of the view function body, before any queryset that relies on `institution_scope()`.
    3. Confirm `HttpResponseForbidden` is imported: `from django.http import HttpResponseForbidden` (add if not present).
  - **Notes:** The guard is needed for views that are security-sensitive and where `{}` (no filter) would expose cross-institution data. It is NOT needed for views that already use `Patient.objects.for_institution(None)` — that manager handles None explicitly. Bookmark views are the priority target since bookmarks have no patient FK and rely entirely on `owner__institution` scoping. For a superadmin in transitional state (`institution=None`), returning 403 is the correct behaviour — they must select an institution context first.

---

- [x] **Task 9: Wrap `video/models.py save()` in `transaction.atomic()`** (Finding #11)
  - **File:** `video/models.py`
  - **Action:**
    1. Add `transaction` and `settings` imports at the top of the file:
       ```python
       from django.db import models, transaction
       from django.conf import settings
       ```
    2. Restructure `save()` to separate I/O phase from the DB write phase:
       ```python
       def save(self, *args, **kwargs):
           # === PHASE 1: I/O and validation (outside transaction — may be long) ===

           # Patient existence check
           if self.patient_id and not getattr(self, '_patient_validated', False):
               try:
                   from patients.models import Patient
                   Patient.objects.get(pk=self.patient_id)
                   self._patient_validated = True
               except Patient.DoesNotExist:
                   raise ValidationError({'patient': _('Selected patient does not exist.')})

           # File size population (in-memory)
           if self.video_file and not self.file_size_bytes:
               try:
                   self.file_size_bytes = self.video_file.size
               except (ValueError, OSError) as e:
                   logger.warning(...)

           # Metadata extraction (I/O — done outside the transaction to avoid holding DB connection)
           if self.video_file and not self.duration_seconds:
               # ... existing extraction logic unchanged ...
               pass

           # Pre-save validation
           self.clean()

           # === PHASE 2: Atomic DB write ===
           with transaction.atomic():
               # On PostgreSQL: lock existing record to prevent concurrent overwrites
               if self.pk and 'postgresql' in settings.DATABASES['default']['ENGINE']:
                   Video.objects.select_for_update().filter(pk=self.pk).exists()
               super().save(*args, **kwargs)
       ```
    3. The key change: `self.clean()` and `super().save()` must be inside `with transaction.atomic():`. All file I/O remains outside the transaction block.
  - **Notes:** Moving `self.clean()` inside the atomic block ensures validation and write are atomic. The `select_for_update()` on the existing record (update case, PostgreSQL only) prevents two concurrent saves from overwriting each other's metadata. For new records (`self.pk is None`), the atomic block still provides correct rollback semantics if `super().save()` fails. The engine check follows the established NDAS pattern from the previous spec.

---

- [x] **Task 10: Migrate Patient N+1 properties to queryset annotations** (Findings #4 + #5)
  - **File:** `patients/models.py` (properties at lines 384–543) + patient list views
  - **Action:**
    1. **Read all 10 property implementations fully** before writing annotations — confirm exact model field names queried (especially `is_normal` field names on `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`).
    2. Add the following imports at the top of `patients/models.py` if not already present:
       ```python
       from django.db.models import Exists, OuterRef, Subquery, BooleanField, Value
       from django.db.models.functions import Coalesce
       ```
    3. Add a `with_status_annotations()` classmethod to the existing `PatientManager` (or wherever the `for_institution` manager is defined):
       ```python
       def with_status_annotations(self):
           from video.models import Video
           from .models import CDICRecord, GMAssessment, HINEAssessment, DevelopmentalAssessment
           # (adjust imports to avoid circular — use lazy imports if needed)
           return self.annotate(
               _is_new_patient=Exists(
                   Video.objects.filter(patient=OuterRef('pk'))
               ),
               _is_discharged=Exists(
                   CDICRecord.objects.filter(patient=OuterRef('pk'), is_discharged=True)
               ),
               _is_last_gma_normal=Subquery(
                   GMAssessment.objects.filter(patient=OuterRef('pk'))
                   .order_by('-id').values('is_normal')[:1],
                   output_field=BooleanField()
               ),
               _is_last_hine_normal=Subquery(
                   HINEAssessment.objects.filter(patient=OuterRef('pk'))
                   .order_by('-id').values('is_normal')[:1],
                   output_field=BooleanField()
               ),
               _is_last_da_normal=Subquery(
                   DevelopmentalAssessment.objects.filter(patient=OuterRef('pk'))
                   .order_by('-id').values('is_normal')[:1],
                   output_field=BooleanField()
               ),
               _is_bookmarked=Exists(
                   Bookmark.objects.filter(bookmark_type='Patient', object_id=OuterRef('pk'))
               ),
           )
       ```
       **IMPORTANT**: Confirm exact field names (`is_normal`, `is_discharged`) by reading the full model definitions before implementing. Adjust field names to match actual schema.
    4. Update each N+1 property to check for the annotation first:
       ```python
       @property
       def isNewPatient(self):
           """True if patient has at least one video. Uses annotation if pre-fetched."""
           annotated = getattr(self, '_is_new_patient', None)
           if annotated is not None:
               return annotated
           from video.models import Video
           return Video.objects.filter(patient=self.pk).exists()
       ```
       Apply this same pattern to: `isDischarged`, `isLastGMANormal`, `isLastHINENormal`, `isLastDANormal`, `isBookmarked`.
    5. Update `isDiagnosisNormal` similarly — it will use the three pre-annotated values if available:
       ```python
       @property
       def isDiagnosisNormal(self):
           return self.isLastGMANormal and self.isLastHINENormal and self.isLastDANormal
       ```
       No change needed here — delegation to the updated properties handles the annotation path.
    6. **Update views that iterate patient lists**: Search for all views in `patients/views.py` that pass patient querysets to templates (e.g., dashboard, `patient_manager`, search results). Add `.with_status_annotations()` to each queryset. Pattern:
       ```python
       patients_qs = Patient.objects.for_institution(_inst).with_status_annotations()
       ```
    7. `getDiagnosisList`, `getGMAIndicationsList`, and `isScreeningPositive` are more complex (involve multiple subqueries or M2M). For these three: add `@cached_property` as an interim optimisation (eliminates repeated access cost per instance) and add a TODO comment for full annotation migration in a follow-up.
  - **Notes:** Read each property implementation before writing annotations — field names like `is_normal` are assumptions from the investigation summary and must be confirmed. Circular import risk between `patients/models.py` and `video/models.py` — use lazy imports inside `with_status_annotations()`. Run `python manage.py test patients` after each sub-step. The `isScreeningPositive` property fires 3 queries — full annotation is deferred to follow-up; `@cached_property` is the interim fix.

---

### Acceptance Criteria

- [x] **AC1:** Given a user operating under Institution A's context, when they request `bookmark_view` for a bookmark whose `object_id` references a patient belonging to Institution B, then the response is HTTP 404 — the cross-institution patient is not served.

- [x] **AC2:** Given two `Institution` records that share the same `pk` (data integrity violation), when a superadmin with that pk in `session['active_institution_id']` makes any request, then the request redirects to the institution selector (HTTP 302) — no HTTP 500 is raised.

- [x] **AC3:** Given two `CustomUser` records with the same `email_verification_token`, when `verify_email` is called with that token, then the response is a redirect to `user-login` with an "Invalid verification link" message — no HTTP 500 is raised.

- [x] **AC4:** Given two `CustomUser` records with the same email address, when `resend_verification_email` is called with that email, then the response shows the neutral "If an account with this email exists..." message — no HTTP 500 is raised and no account existence is confirmed.

- [x] **AC5:** Given a superadmin user, when they make 3 consecutive requests in the same test session, then `assertNumQueries` confirms only 1 Institution DB query is issued across all 3 requests (cache hit on requests 2 and 3).

- [x] **AC6:** Given 5 login POST requests from 5 different IP addresses but the same `username` within 1 minute, when the 6th request arrives with the same username, then it is blocked with HTTP 429 — the per-username limit fires regardless of IP diversity.

- [x] **AC7:** Given 5 password reset POST requests from different IPs for the same email address within 1 hour, when the 6th request arrives for the same email, then it receives the neutral rate-limit message and is not forwarded to Django's password reset email sender.

- [x] **AC8:** Given a superadmin switches from Institution A (id=1) to Institution B (id=2), when the switch completes successfully, then an `InstitutionSwitchLog` record exists with `institution_id=2`, `previous_institution_id=1`, `user=superadmin`, and a non-null `switched_at`.

- [x] **AC9:** Given the `InstitutionSwitchLog.objects.create()` call raises an exception (e.g., DB unavailable), when the exception occurs during a switch, then the institution switch still succeeds (session updated, user redirected) and the error is only recorded in the application log — no HTTP 500.

- [x] **AC10:** Given a patient list of 20 patients is loaded via a view that calls `.with_status_annotations()`, when `assertNumQueries` is run against the view, then the query count is bounded (does not increase with the number of patients for the annotated properties).

- [x] **AC11:** Given a single `Patient` instance fetched without `.with_status_annotations()`, when `patient.isNewPatient` is accessed, then it falls back to the direct DB query path and returns the correct boolean result.

- [x] **AC12:** Given two concurrent `Video.save()` calls for the same existing video record on PostgreSQL, when both are processed, then the second save either waits for the first to complete (lock wait) or raises a database error — no silent partial overwrite of metadata fields.

- [x] **AC13:** Given a request is processed where `bookmark_delete` is called and `request.institution` is None (transitional state), when the view processes the request, then it returns HTTP 403 — no unscoped bookmark access is permitted.

- [x] **AC14:** Given all 10 tasks are applied, when `python manage.py test patients` is run, then all existing tests in `patients/tests/test_views.py` pass (including `DeleteEndpointErrorSanitizationTest`).

---

## Additional Context

### Dependencies

- No new PyPI packages required. All fixes use:
  - Django built-ins: `transaction.atomic()`, `select_for_update()`, `Exists()`, `Subquery()`, `OuterRef()`, `GenericIPAddressField`, `auto_now_add`
  - Existing `django-ratelimit 4.1.0`: `is_ratelimited()` from `django_ratelimit.core` (already installed)
  - `HttpResponseForbidden` from `django.http` — confirm import in `patients/views.py`
  - `settings` from `django.conf` — confirm import in `video/models.py`
- **One migration required:** `institution` app — `InstitutionSwitchLog` model (Task 1)
- Task 10 depends on confirming exact field names (`is_normal`, `is_discharged`) in assessment models before implementing annotations

### Testing Strategy

- **After each task:** Run `python manage.py test patients` — all 818-line test suite must stay green.
- **Task 1 (model):** `python manage.py migrate` to apply migration; confirm table is created.
- **Task 2 (audit log):** Unit test — simulate a superadmin institution switch, assert `InstitutionSwitchLog.objects.count() == 1` with correct fields. Test that a `create()` exception does not block the switch.
- **Task 3 (middleware caching):** Use `assertNumQueries(1)` on a test that sends 3 requests with the same superadmin session — confirm only 1 Institution query total.
- **Task 4 (MultipleObjectsReturned users):** Create two users with the same token/email in a test fixture; call the views; assert redirect (not 500).
- **Task 5 (per-username rate limit):** Send 6 login POST requests with the same username from different mock IPs; assert 6th returns 429.
- **Task 6 (per-email rate limit):** Send 6 password reset POST requests with the same email from different IPs; assert 6th returns the neutral message without invoking `PasswordResetView.post()`.
- **Task 7 (bookmark resolution):** Create a bookmark with an `object_id` pointing to a patient in a different institution; request `bookmark_view`; assert HTTP 404.
- **Task 9 (video transaction):** Mark test `@skipUnless(postgresql)` for the `select_for_update()` path. Test that a `ValidationError` in `clean()` rolls back the entire save.
- **Task 10 (N+1 annotations):** Use `assertNumQueries(N)` where N is fixed regardless of patient list size. Separately test that single-instance access without annotations still returns correct results.

### Notes

- **Task application order matters:** Task 1 must precede Task 2. All other tasks are independent of each other and of Tasks 1–2.
- **Task 10 (N+1) — highest risk:** Read every property implementation before writing annotations. The field names `is_normal` and `is_discharged` are inferred from the investigation summary — confirm actual schema before coding. Circular import between `patients/models.py` and `video/models.py` is the most likely implementation blocker — use lazy/deferred imports inside `with_status_annotations()`.
- **`isScreeningPositive`, `getDiagnosisList`, `getGMAIndicationsList`:** Full annotation of these three is deferred. Interim fix: add `@cached_property` to eliminate repeated per-request access cost. Track full annotation as follow-up.
- **Task 9 (video) — I/O outside transaction:** Do NOT move metadata extraction inside `transaction.atomic()`. Holding a DB transaction open during file I/O risks connection pool exhaustion under load. The atomic block covers only the validation + `super().save()` sequence.
- **Finding #9 (institution_scope guard):** The `{}` return when `institution is None` is a documented Phase 1 compatibility behaviour — not a bug. The guard is specifically for views where `{}` would mean "show all institutions" (cross-tenancy breach), not for views where `for_institution(None)` already handles the None case gracefully.
- **SQLite / `select_for_update()` (Task 9):** The PostgreSQL engine check follows the existing NDAS pattern. On SQLite, the atomic block still provides correct rollback semantics. Full lock protection requires PostgreSQL in production.
