# NDAS Codebase Review — Logical Inconsistencies, Bugs & Performance Issues

**Date:** 2026-08-23  
**Command:** `/bmad-review` — find logical inconsistancies, bugs and performance issues. make complete document to use fixation later.  
**Total findings:** 208 across 8 apps  

This document is the fixation backlog for this review. Each finding gives the exact location, the trigger condition, a concrete guard/fix, and the consequence if left unaddressed. No severity/priority ranking is assigned per the review method -- see **Suggested fixation order** below for a practical starting point.

## Scope & method

- **Scope:** Whole-codebase review of Python backend source (models, views, forms, urls, admin, middleware, utils, custom_codes, management commands) across all Django apps: patients, users, video, reports, problemlist, institution, referral, and the shared ndas core / custom_codes. Migrations, templates (~27k lines), and static JS/CSS were excluded from this pass.
- **Lenses run:** adversarial, edge-case-hunter (independent passes -- adversarial requires >=10 real findings; edge-case-hunter is pure path-tracing, no editorializing)
- **Lenses skipped and why:**
  - **verification-gap:** This lens traces changed behavior in a diff against its tests. There was no diff to review (working tree clean, main branch) so there was no 'changed behavior' to trace. Recommend running bmad-review with the verification-gap lens on future PRs/diffs instead.
  - **structure:** applies_to docs only; content reviewed here is code.
  - **prose:** applies_to docs only; content reviewed here is code.
- **Method:** 8 parallel review passes, one per app, each running the adversarial lens (>=10 findings min) and the edge-case-hunter lens independently, plus an also_consider brief for Django-specific performance (N+1 queries, missing select_related/prefetch_related, missing db_index) and app-specific risk areas (multi-tenancy for institution/referral, file handling for video/reports, security infra for ndas core).
- **Machine-readable version:** `codebase-review-2026-08-23.json` (same findings, structured for tooling/tracking)

## Findings by app

| App | Adversarial | Edge-case | Total |
|---|---|---|---|
| `patients` | 14 | 9 | 23 |
| `problemlist` | 16 | 13 | 29 |
| `referral` | 12 | 15 | 27 |
| `reports` | 15 | 12 | 27 |
| `ndas_core` | 15 | 10 | 25 |
| `users` | 19 | 10 | 29 |
| `institution` | 13 | 11 | 24 |
| `video` | 14 | 10 | 24 |
| **Total** | | | **208** |

## Cross-cutting themes

Patterns that recur across multiple apps -- worth fixing as a batch rather than one finding at a time:

1. **`for_institution(None)` returns unfiltered cross-tenant data.** The institution-scoped manager treats a `None` institution as "no filter" instead of "no access." Hit in `referral/views.py` (x2), `institution/managers.py`, and implicated in `reports/utils/excel_generator.py` ignoring institution scoping entirely. This is the single highest-value fix in the whole review -- it is a repeated cross-institution PHI leak pattern, not an isolated bug.
2. **Bare/broad `except Exception` swallowing real errors.** `ndas/custom_codes/error_handlers.py` (`log_and_suppress`), `users/middleware.py` (`UserActivityMiddleware`), `referral/signals.py` (notification creation), `video/models.py` (metadata extraction), `reports/utils/pdf_generator.py` (logo loading) -- all hide genuine failures (including security-relevant ones) with no logging, so bugs and dropped notifications go permanently unnoticed.
3. **`get_object_or_404()` + `Http404` not handled by the shared error decorator.** `ndas/custom_codes/error_handlers.py` only special-cases `ObjectDoesNotExist`, not `Http404` -- meaning the CLAUDE.md-mandated `get_object_or_404()` pattern generates misleading "unexpected error" logs and redirects instead of real 404s, project-wide.
4. **N+1 queries and redundant `.count()` calls are systemic.** Independently found in `patients` (GPA/DA managers), `problemlist` (stats dict), `users` (admin lists), `video` (list views), `institution` (dashboard), and `reports` (sheet builders re-counting after iterating). None are individually severe, but they compound under load across nearly every list/manager view in the app.
5. **Missing `db_index=True` on fields that are filtered/ordered on in hot paths.** `patients.pog_wks`/`apgar_*`, `referral.patient_name`, recurring across apps -- filters used by reports and referral lookups do full table scans.
6. **File-handling and audit-trail write paths lack atomicity around DB + storage.** `video/models.py` (orphaned files on `IntegrityError`), `video/views.py` (delete file before DB row), `reports/views.py` (report ownership not checked on delete/history) -- several file-touching write paths are not wrapped in `transaction.atomic()` with cleanup on failure.
7. **Duplicate same-named helper functions with diverging behavior.** `sanitize_filename` exists in both `validators.py` and `sanitization.py` with different rules; `clean_profile_picture` is copy-pasted between two forms in `users/forms.py`. Both are silent-drift risks: a future fix to one copy leaves the other stale.
8. **Password/account-security gaps concentrated in `users/`.** `validate_password()` is never called on registration/admin-create forms, email uniqueness is case-sensitive (bypassable), and `is_suspicious_activity()` is detected but never acted on. Recommend treating `users/forms.py` and `users/views.py` auth paths as one fix batch.

## Suggested fixation order

Not a formal severity ranking (per review method), but a practical starting point given what these findings actually touch:

1. **Cross-tenant data leaks** -- `for_institution(None)` in `referral/views.py:38-41,444-447`, `institution/managers.py:22-30`, and institution scoping missing entirely from `reports/utils/excel_generator.py`.
2. **Auth/permission bypasses** -- `patients/views.py:1672-1681` (bookmark IDOR), `referral/views.py:548-572` (CSRF-unsafe GET mutating notification state), `institution/middleware.py:136-138` (open redirect), `ndas/custom_codes/delete_helpers.py:47-50` (any staff can delete any bookmark).
3. **Medical-data-correctness bugs** -- `ndas/custom_codes/custom_methods.py:623-628` (`Q(...) and Q(...)` short-circuit breaks DX_NORMAL classification), `patients/views.py:2824-2830` (HINE "normal" filter threshold mismatch), `patients/models.py:471-478` (birth-weight validation never runs), `patients/models.py:748-751` (`.last()` vs `.first()` on HINE score).
4. **Security-sanitization gaps** -- `ndas/custom_codes/validators.py:42-61` (sanitize-then-unescape XSS bypass), `ndas/custom_codes/sanitization.py:37-61` (reverse-tabnabbing), `patients/models.py:1931-1937` (virus scan stub always reports clean).
5. **Everything else**, grouped by the cross-cutting themes above (N+1 queries, missing indexes, error-swallowing, duplicate helpers) -- mechanical, lower-risk fixes that are easiest to batch by pattern rather than by app.

---

## patients — patient records, assessments (GMA/HINE/DA/CDIC/GPA), attachments, bookmarks

### Adversarial (14)

**1. `patients/models.py:1786-1804 and patients/models.py:1947-1958`**
- **Problem:** Attachment.file_size_display is defined twice; the later definition silently overrides the first
- **Fix:** `rename or remove the duplicate `file_size_display` property so only one definition (with the file_size auto-populate logic) remains`
- **Consequence:** the file_size auto-population/save side effect is dead code and never runs, leaving file_size unset for legacy rows

**2. `patients/models.py:1769-1784 and patients/models.py:1975-1978`**
- **Problem:** Attachment.is_safe_to_view is defined twice with conflicting security semantics (first allows 'pending' scan status, second requires is_scanned and 'clean')
- **Fix:** `delete the redundant definition and keep a single explicit policy, e.g. `return self.file_exists and self.scan_result == 'clean'``
- **Consequence:** the documented 'allow viewing pending scans with a warning' behavior never actually executes, silently changing access rules

**3. `patients/models.py:1931-1937`**
- **Problem:** _schedule_virus_scan always sets is_scanned=True and scan_result='clean' with a TODO noting no real scanner is wired up
- **Fix:** `leave scan_result='pending' until an async scanner (e.g. ClamAV) actually processes the file, then update the record`
- **Consequence:** infected or malicious uploads are marked 'clean' and served via is_safe_to_view/can_be_previewed with false security assurance

**4. `patients/models.py:471-478`**
- **Problem:** Patient.clean() calls plain validate_birth_weight(self.birth_weight), which never returns a tuple, so `if result is not None` is always False
- **Fix:** `call `is_valid, message = validate_birth_weight_for_gestational_age(self.birth_weight, self.pog_wks, pog_days)` instead`
- **Consequence:** the documented POG-specific birth-weight validation never runs; medically implausible weight/gestational-age combinations are silently accepted

**5. `patients/forms.py:461-468 (also widget min at 243-251) vs ndas/custom_codes/validators.py:387-389`**
- **Problem:** PatientForm.clean_birth_weight allows 200-8000g while the model field validator only allows 300-8000g
- **Fix:** `change clean_birth_weight bounds to 300-8000 to match validate_birth_weight and CLAUDE.md`
- **Consequence:** a 200-299g submission passes form validation then raises an uncaught ValidationError inside Patient.save(), surfacing as a generic 'error occurred' message

**6. `patients/forms.py:605-615`**
- **Problem:** 'Other' GMA indication detection hardcodes indication.id == 27
- **Fix:** `look up the 'Other' indication by a stable field (e.g. title/abr) instead of a hardcoded PK`
- **Consequence:** if seed data IDs differ across environments/reseeds, the 'please specify details' requirement silently stops being enforced

**7. `patients/models.py:2225-2247 and patients/models.py:2269-2287`**
- **Problem:** Bookmark's model_mapping/_get_bookmarked_object still maps 'Video' to ('patients','Video'), but Video was moved to the video app (migrations 0003/0004; models.py imports `from video.models import Video`)
- **Fix:** `change the mapping entries to ('video', 'Video') to match the current app location`
- **Consequence:** apps.get_model('patients','Video') raises LookupError, caught by a bare except, so Video bookmark validation and bookmarked_object resolution are silently always broken

**8. `patients/models.py:748-751`**
- **Problem:** getRC computes last_hine_record via HINEAssessment.objects.filter(patient=self).last() on a queryset ordered by Meta ordering ['-date_of_assessment']
- **Fix:** `use `.order_by('-date_of_assessment').first()` (matching get_latest_hine_assessment) instead of `.last()``
- **Consequence:** QuerySet.last() on a descending-ordered queryset returns the OLDEST HINE score, so the physiotherapy-referral recommendation is computed from stale/wrong data

**9. `patients/views.py:3524-3526 (registered at patients/urls.py:12)`**
- **Problem:** view function `print(request): pass` returns None instead of an HttpResponse, and shadows the builtin print in this module
- **Fix:** `implement the view to `return render(...)` or `return HttpResponse(...)`, or remove the route if unused`
- **Consequence:** any request to /print/ raises 'The view patients.views.print didn't return an HttpResponse object' (500 error)

**10. `patients/views.py:1672-1681`**
- **Problem:** bookmark_manager_user(request, username) has no check that request.user owns `username` (or is staff/superuser) and no institution scoping
- **Fix:** `add `if request.user.username != username and not request.user.is_superuser: return HttpResponseForbidden()` plus institution_scope filtering`
- **Consequence:** any authenticated user can view any other user's private bookmark list by visiting /manager/bookmarks/user/<other_username>/ (IDOR, cross-institution data leak)

**11. `patients/views.py:3213-3238 and patients/views.py:3326-3348`**
- **Problem:** da_assessment_manager age_range filter iterates the entire unpaginated var_da_list in Python, calling getAssessmentAgeInMonths per record, to build an id__in filter
- **Fix:** `annotate an age-in-months expression in the DB (e.g. via ExpressionWrapper/ExtractDay on date_of_assessment - patient__dob_tob) and filter there`
- **Consequence:** every request with an age_range filter does a full table scan and loads all matching rows into memory before pagination, degrading badly as records grow

**12. `patients/views.py:3666-3667 and patients/views.py:3714-3715`**
- **Problem:** gpa_manager/gpa_manager_by_patient loop `for gpa in page_obj: gpa.isBookmarked = gpa.is_bookmarked`, and is_bookmarked runs a DB query per instance
- **Fix:** `prefetch bookmarked ids once via `Bookmark.objects.filter(bookmark_type='GPA', object_id__in=[g.id for g in page_obj])` and map them in Python`
- **Consequence:** N+1 queries (up to 25 extra per page load) on every GPA manager page view

**13. `patients/views.py:2824-2830 and patients/views.py:2907-2913 vs patients/models.py:2674-2689`**
- **Problem:** hine_assessment_manager score_range='normal' filters score__gte=60, but HINEAssessment.is_normal/severity_category define 'Normal' as score > 73 (60-73 is 'Mild Abnormality')
- **Fix:** `change the 'normal' filter to `score__gt=73` to match the model's canonical definition`
- **Consequence:** clinicians filtering for 'normal' HINE results are shown patients with mild neurological abnormality as if they were normal

**14. `patients/views.py:339-387`**
- **Problem:** patient_view materializes six full related querysets with list(...) (videos, attachments, GMA, HINE, DA, CDIC) before slicing [:5] in Python
- **Fix:** `use `.count()` for the counts and a DB-level `queryset.order_by('-id')[:5]` for the displayed items instead of `list(queryset)[:5]``
- **Consequence:** for long-followed patients with hundreds/thousands of records, every patient-detail page load pulls the entire history into memory

### Edge-case hunter (9)

**1. `patients/models.py:516-547`**
- **Unhandled path:** isScreeningPositive has no branch for (hine_record_count==0 and latest_gma_assessment==False) nor for last_hine_score==73
- **Guard:** `add explicit final `return True` / `return False` covering the GMA-abnormal-no-HINE case and the score==73 boundary`
- **Consequence:** function falls through and returns None (falsy) for these states, hiding a screening-positive result from callers/templates

**2. `patients/models.py:97-132 vs patients/models.py:832-861`**
- **Unhandled path:** with_status_annotations orders 'latest' GMA/HINE by -id while get_latest_gma_assessment/get_latest_hine_assessment order by -date_of_assessment
- **Guard:** `order both the annotation subqueries and the instance methods by the same field, e.g. '-date_of_assessment'`
- **Consequence:** a backdated assessment entry makes list-view status badges disagree with the patient detail page's 'latest assessment'

**3. `patients/forms.py:738-750`**
- **Unhandled path:** clean_attachment treats cleaned_data['attachment']==False (user checked 'clear' on ClearableFileInput) the same as 'no new file supplied'
- **Guard:** `check `if attachment is False: return None` before the 'preserve existing file' branch`
- **Consequence:** a user who explicitly clears the attachment via the form checkbox has the old file silently restored instead of removed

**4. `patients/timeline_utils.py:199-204`**
- **Unhandled path:** GMA timeline block reads gma.observation, a field that does not exist on GMAssessment
- **Guard:** `remove the observation reference or use an existing field (e.g. management_plan/diagnosis_other)`
- **Consequence:** AttributeError is raised on the first GMA record and caught by the outer except, dropping every GM Assessment event from the patient's timeline

**5. `patients/timeline_utils.py:268-271`**
- **Unhandled path:** CDIC event datetime is only made timezone-aware conditionally (`if timezone.is_aware(patient.dob_tob)`) while all other event types use always-aware DateTimeFields
- **Guard:** `always call `timezone.make_aware(assessment_datetime)` when USE_TZ is enabled, regardless of dob_tob's awareness`
- **Consequence:** mixing naive and aware datetimes raises TypeError during the final sort, caught by the outer except, silently returning an unsorted timeline

**6. `patients/models.py:1818-1831 and patients/views.py:2121-2128`**
- **Unhandled path:** Attachment.save() unconditionally calls full_clean() (which stats the file) even when the caller restricts update_fields to non-file fields
- **Guard:** `skip attachment-file validation in clean()/save() when 'attachment' is not in the passed update_fields`
- **Consequence:** a title/description-only edit can fail with FileNotFoundError if the underlying file is temporarily unavailable, and every such edit does an unneeded storage stat call

**7. `patients/views.py:761-777 and patients/views.py:800-816`**
- **Unhandled path:** search_results calls patients.count() to check for a single match, then Paginator (which also counts) and again inside the success message, on the same queryset
- **Guard:** `evaluate `patients.count()` once into a local variable and reuse it for the branch check, paginator hint, and message`
- **Consequence:** every multi-result name search issues redundant duplicate COUNT queries against the patients table

**8. `patients/views.py:392-397 vs patients/models.py:133-137,605-616`**
- **Unhandled path:** patient_view's bookmark lookup `Bookmark.objects.filter(bookmark_type='Patient').filter(object_id=...).first()` is not scoped by request.user, unlike the model's own user-scoped _is_bookmarked annotation
- **Guard:** `add `.filter(owner=request.user)` to the bookmark lookup in patient_view, matching the F9-fixed annotation behavior`
- **Consequence:** the bookmark button/state on the patient detail page reflects any user's bookmark, not the viewing user's, inconsistent with list-view badges

**9. `patients/views.py:3536-3560 and patients/views.py:3566-3595`**
- **Unhandled path:** gpa_add/gpa_edit call form.save() with no try/except, unlike every other add/edit view in this file (patient_add, assessment_add, cdic_assessment_add, hine_assessment_add, da_assessment_add)
- **Guard:** `wrap `gpa_record.save()` in the same try/except pattern used by the sibling views, logging and showing a user-facing error message`
- **Consequence:** an IntegrityError or model-level ValidationError not caught by the form surfaces as an unhandled 500 instead of a graceful error message

---

## problemlist — clinical problem list & audit trail

### Adversarial (16)

**1. `problemlist/models.py:85-90`**
- **Problem:** get_status_badge_class hardcodes status strings instead of using PROBLEM_STATUS enum
- **Fix:** `badge_classes = {'active': 'warning', 'chronic': 'info', 'resolved': 'success', 'inactive': 'secondary'}`
- **Consequence:** Adding/renaming a status in choice.py silently falls back to a generic grey badge everywhere

**2. `problemlist/models.py:95-100`**
- **Problem:** get_severity_badge_class hardcodes severity strings instead of using SEVERITY_CHOICES enum
- **Fix:** `badge_classes = {'mild': 'success', 'moderate': 'warning', 'severe': 'danger', 'life_threatening': 'dark'}`
- **Consequence:** New/renamed severity value loses its distinct badge coloring without any error, easy to miss in review

**3. `problemlist/views.py:348`**
- **Problem:** Allowed status list is hardcoded instead of derived from PROBLEM_STATUS.values
- **Fix:** `if new_status in ['active', 'resolved', 'chronic', 'inactive']:`
- **Consequence:** Business rule duplicated in two places (choice.py and views.py) can drift and silently block a valid new status

**4. `problemlist/views.py:349-367`**
- **Problem:** No check that new_status differs from old_status before saving and logging
- **Fix:** `old_status = problem.status; problem.status = new_status; ...; ProblemAction.objects.create(action=f"Status changed from {old_status} to {new_status}", ...)`
- **Consequence:** Resubmitting the same status creates a false 'Status changed from X to X' entry in the clinical audit trail

**5. `problemlist/views.py:330-375`**
- **Problem:** problem_status_change has no @ratelimit and no locking/version check unlike sibling problem_add/edit/delete views
- **Fix:** `@login_required(login_url="user-login")\ndef problem_status_change(request, pk):`
- **Consequence:** Endpoint is unprotected against abuse/spamming and against two concurrent editors silently overwriting each other's status change

**6. `problemlist/views.py:405-443`**
- **Problem:** problem_action_add lacks the @ratelimit decorators present on problem_add/problem_edit/problem_delete
- **Fix:** `@login_required(login_url="user-login")\ndef problem_action_add(request, pk):`
- **Consequence:** Audit-log creation endpoint can be spammed without the throttling applied to every other write path in this app

**7. `problemlist/forms.py:110-159`**
- **Problem:** Local variable date_resolved is captured before cleaned_data['date_resolved'] is auto-populated/cleared, then reused in later checks
- **Fix:** `date_resolved = cleaned_data.get('date_resolved')  # captured at line 110, stale by line 135-159`
- **Consequence:** Valid submissions can be wrongly rejected (stale future date after status leaves 'resolved') or cross-checks silently skipped (auto-populated date never validated against onset/identified)

**8. `problemlist/views.py:281-290`**
- **Problem:** Deletion error handler returns the raw exception message to the client
- **Fix:** `return JsonResponse({..., "message": f"An error occurred during deletion: {str(e)}"}, status=500)`
- **Consequence:** Internal error detail (DB/constraint internals) leaks to the browser of any authenticated user in a medical-records system

**9. `problemlist/models.py:119-124`**
- **Problem:** ProblemAction.problem uses on_delete=CASCADE with no soft-delete or archival for the audit log
- **Fix:** `problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='actions', ...)`
- **Consequence:** Deleting a Problem permanently erases its entire clinical audit trail, undermining the record-keeping purpose the model's own docstring describes

**10. `problemlist/views.py:130-163`**
- **Problem:** problem_edit saves clinical field changes (severity, action_taken, outcome, description) without creating a ProblemAction entry
- **Fix:** `if form.is_valid():\n    form.save()\n    messages.success(...)\n    return redirect("problem-view", pk=problem.pk)`
- **Consequence:** Only status changes are captured in the audit timeline; substantive clinical edits leave no action-log trace of what changed

**11. `problemlist/views.py:463-520 and 523-621`**
- **Problem:** problem_analysis and problem_analysis_export duplicate the same ~30 lines of filter-building logic
- **Fix:** `patient_id/status_filter/severity_filter/date_from/date_to filters repeated verbatim in both view functions`
- **Consequence:** A future filter change applied to one view and not the other makes the Excel export silently diverge from the analysis page results

**12. `problemlist/views.py:330-375`**
- **Problem:** Endpoint unconditionally returns the _problem_row.html HTMX partial with no check that the request is actually an HTMX/AJAX call
- **Fix:** `return render(request, "problemlist/_problem_row.html", {"problem": problem})`
- **Consequence:** A non-HTMX form POST to this URL renders a bare table-row fragment as the entire page response

**13. `problemlist/views.py:500-505`**
- **Problem:** Four separate .count() queries run against the same filtered queryset to build the stats dict
- **Fix:** `stats = {'active': problems.filter(status='active').count(), 'chronic': problems.filter(status='chronic').count(), ...}`
- **Consequence:** Four extra round trips per analysis page load instead of one aggregate with conditional counts, worse as data grows

**14. `problemlist/admin.py:1-3`**
- **Problem:** Problem and ProblemAction are never registered with the Django admin site
- **Fix:** `from django.contrib import admin\n# Register your models here.`
- **Consequence:** No admin-side path exists to review, bulk-correct, or investigate problem-list/audit records outside the app UI

**15. `problemlist/models.py:76-78`**
- **Problem:** Only declared index is Index(fields=['patient','status']), which doesn't match problem_manager's actual filter+order pattern
- **Fix:** `indexes = [models.Index(fields=['patient', 'status'])]`
- **Consequence:** The default listing query (filter by patient, order by -date_identified) doesn't benefit from the declared composite index

**16. `problemlist/views.py:25-59`**
- **Problem:** problem_manager has no pagination on the per-patient problem list
- **Fix:** `problems = Problem.objects.filter(patient=patient).annotate(priority=...).order_by('priority', '-date_identified')`
- **Consequence:** A patient with a very long problem history renders every row in a single request/table with no limit

### Edge-case hunter (13)

**1. `problemlist/views.py:348`**
- **Unhandled path:** new_status missing, blank, or outside the four allowed values
- **Guard:** `else: messages.error(request, 'Invalid status.')`
- **Consequence:** Request silently no-ops with a 200 response and no feedback that nothing changed

**2. `problemlist/views.py:349-360`**
- **Unhandled path:** new_status equals the problem's current status
- **Guard:** `if new_status == old_status: return render(request, ..., {"problem": problem})`
- **Consequence:** Redundant save and a misleading 'changed from X to X' ProblemAction record are still created

**3. `problemlist/views.py:330`**
- **Unhandled path:** problem_status_change has no @require_http_methods, so GET requests reach the function
- **Guard:** `@require_http_methods(["POST"])`
- **Consequence:** GET requests fall through with new_status=None with no explicit method rejection

**4. `problemlist/views.py:369-372`**
- **Unhandled path:** messages.success() queued while the response body is the _problem_row.html HTMX partial
- **Guard:** `return render(request, "problemlist/_problem_row.html", {"problem": problem})`
- **Consequence:** Success/error message is never shown in the swapped fragment and surfaces later on an unrelated page

**5. `problemlist/forms.py:135-138`**
- **Unhandled path:** status != 'resolved' path clears cleaned_data['date_resolved'] but the future-date check still reads the pre-clear local variable
- **Guard:** `if date_resolved and date_resolved > timezone.now().date(): raise ValidationError(...)`
- **Consequence:** Submission rejected for a date_resolved value that will actually be saved as None

**6. `problemlist/forms.py:122-138`**
- **Unhandled path:** Multiple future-date violations present in one submission (onset, identified, resolved)
- **Guard:** `raise forms.ValidationError({'date_of_onset': '...'})  # aborts clean() before later checks run`
- **Consequence:** Only the first violation is reported per request; remaining errors surface only after a further resubmission

**7. `problemlist/views.py:464-467,485-489`**
- **Unhandled path:** date_from/date_to GET values not validated as dates before use
- **Guard:** `problems = problems.filter(date_identified__gte=date_from)`
- **Consequence:** Malformed date string reaches queryset evaluation unvalidated, raising an unhandled error

**8. `problemlist/views.py:464,476-477`**
- **Unhandled path:** patient GET parameter not validated as numeric before filtering
- **Guard:** `problems = problems.filter(patient_id=patient_id)`
- **Consequence:** Non-numeric patient id value reaches queryset evaluation unvalidated, raising an unhandled error

**9. `problemlist/views.py:113,141,392,419`**
- **Unhandled path:** problem.patient / .added_by accessed after get_object_or_404 with no select_related on Problem
- **Guard:** `problem = get_object_or_404(Problem, pk=pk, **institution_scope(request))`
- **Consequence:** Each of these four view paths issues extra per-request queries for the related patient/user rows

**10. `problemlist/views.py:591-606`**
- **Unhandled path:** Export loop iterates the full filtered queryset with no row-count limit
- **Guard:** `for problem in problems: ws.append([...])`
- **Consequence:** An unbounded result set is fully materialized into one in-memory workbook in a single request

**11. `problemlist/models.py:91,101`**
- **Unhandled path:** status/severity value absent from the badge_classes dict
- **Guard:** `return badge_classes.get(self.status, 'secondary')`
- **Consequence:** Falls through to a generic 'secondary' badge with no log or indication the value was unrecognized

**12. `problemlist/views.py:345-367`**
- **Unhandled path:** Two concurrent requests change the same problem's status without select_for_update or a version check
- **Guard:** `problem.status = new_status; problem.save()`
- **Consequence:** Second save silently overwrites the first editor's status change with no conflict detection

**13. `problemlist/views.py:116,394`**
- **Unhandled path:** action_count computed via a separate .count() call on a distinct queryset from the one rendered as actions
- **Guard:** `action_count = getCountZeroIfNone(problem.actions.all())`
- **Consequence:** The actions data is evaluated twice (once for count, once for the list) in the same request

---

## referral (Phase 2) — cross-institution referrals

### Adversarial (12)

**1. `referral/views.py:38-41`**
- **Problem:** referral_initiate fetches patient via Patient.objects.for_institution(institution) without guarding institution=None
- **Fix:** `patient = get_object_or_404(Patient.objects.for_institution(institution), id=patient_id)`
- **Consequence:** InstitutionScopedManager.for_institution(None) returns ALL patients unfiltered, letting a no-institution-context user (e.g. SUPERADMIN) initiate a referral exposing any institution's patient snapshot

**2. `referral/views.py:444-447`**
- **Problem:** patient_referrals_tab fetches patient via Patient.objects.for_institution(institution) without guarding institution=None
- **Fix:** `patient = get_object_or_404(Patient.objects.for_institution(institution), id=patient_id)`
- **Consequence:** Same for_institution(None)-returns-all bug lets a no-institution-context user view any patient's referral timeline across institutions

**3. `referral/forms.py:35-39,58-64 combined with referral/views.py:46,100`**
- **Problem:** self-institution exclusion and self-referral validation are both wrapped in `if sending_institution:` — silently skipped when institution is falsy
- **Fix:** `if sending_institution: self.fields['to_institution'].queryset = ...exclude(pk=sending_institution.pk) / if to_institution and self.sending_institution: raise ValidationError(...)`
- **Consequence:** Combined with the institution=None leak, no-self-institution-referral rule is entirely bypassable and the resulting record is saved with institution=None, becoming visible to any future no-context user

**4. `referral/views.py:296-304 and 211-219 (_thread_panel_response)`**
- **Problem:** referral_reply and referral_thread_panel authorize solely on institution membership (`institution=institution`), never on request.user being the specific from_clinician/to_clinician
- **Fix:** `sent = ReferralSent.objects.filter(referral_uuid=referral_uuid, institution=institution).first()`
- **Consequence:** Any clinician at either institution can read and post 'clinical opinion' replies on referral threads not addressed to them, unlike referral_close which correctly restricts to from_clinician/admin

**5. `referral/views.py:108-135 (get_institution_clinicians)`**
- **Problem:** Endpoint has no @ratelimit decorator (every sibling view in the file has one) and never checks target institution.is_active
- **Fix:** `clinicians = CustomUser.objects.filter(institution_id=institution_id, is_active=True, user_type=UserType.USER)`
- **Consequence:** Unthrottled enumeration of clinician names/usernames across every institution, including suspended ones, by iterating institution_id

**6. `referral/models.py:273-277 vs 58-72,158-164 (Notification.recipient not nullable, referral clinician FKs SET_NULL/null=True)`**
- **Problem:** signals.py creates Notification(recipient=instance.to_clinician/sent.from_clinician) which can be None if that user account was deleted
- **Fix:** `Notification.objects.create(recipient=instance.to_clinician, ...)  # recipient has no null=True`
- **Consequence:** IntegrityError on save is swallowed by the broad except in signals.py, silently dropping referral/reply/closure notifications with no retry or alert

**7. `referral/views.py:355-397 (referral_close)`**
- **Problem:** Status is read (`sent.status == CLOSED`) then updated in a separate step with no row lock or select_for_update between check and act
- **Fix:** `if sent.status == ReferralStatus.CLOSED: return _thread_panel_response(...)  # then later: with db_transaction.atomic(): ...update(status=CLOSED)`
- **Consequence:** Two concurrent close requests both pass the pre-check, causing referral_status_changed to fire twice and duplicate closure notifications to be sent to both clinicians

**8. `referral/views.py:383-393`**
- **Problem:** Close permission only checks UserType.ADMIN scoped to request.user.institution or the exact from_clinician; UserType.SUPERADMIN is never checked
- **Fix:** `is_inst_admin = (user_type == UserType.ADMIN and request.user.institution == institution)`
- **Consequence:** No escalation path exists for a platform SUPERADMIN to close a stuck/abandoned referral when the originating clinician/admin is unavailable

**9. `referral/utils.py:39-76 vs 128-151`**
- **Problem:** demographics/perinatal snapshot blocks have no try/except while problem_list and attachments blocks in the same function do
- **Fix:** `demographics = {'baby_name': patient.baby_name, ...}  # no try/except, unlike: try: ... except Exception: pass  # for problem_list`
- **Consequence:** Any Patient attribute rename/removal (schema drift) hard-crashes referral creation entirely instead of degrading gracefully like the rest of the function

**10. `referral/forms.py:75-84 and referral/views.py:320-332`**
- **Problem:** ReferralReplyForm.body has min_length=10 but no max_length, and referral_reply saves it straight into an unbounded TextField
- **Fix:** `body = forms.CharField(label='Clinical Opinion', widget=forms.Textarea(...), min_length=10)  # no max_length`
- **Consequence:** A malicious clinician can repeatedly (10/min) post arbitrarily large payloads, inflating DB storage and degrading thread_panel rendering for both institutions

**11. `referral/views.py:548-572 (notification_mark_read)`**
- **Problem:** State-mutating action (marks notification read) is exposed on a @require_GET endpoint, which Django's CSRF protection does not cover
- **Fix:** `@require_GET ... notif.is_read = True; notif.save(update_fields=['is_read', ...])`
- **Consequence:** A third-party page embedding this URL (img/link) while the clinician is logged in can silently force-mark arbitrary owned notification IDs as read

**12. `referral/views.py:459-464 (patient_referrals_tab)`**
- **Problem:** Incoming referrals are matched to the local patient purely by ReferralReceived.filter(to_institution=institution, patient_name=patient.baby_name)
- **Fix:** `received_referrals = ReferralReceived.objects.filter(to_institution=institution, patient_name=patient.baby_name or '')`
- **Consequence:** Two unrelated local patients sharing the same baby_name (common NICU naming) will have each other's referral threads and clinical snapshots shown on the wrong patient's tab

### Edge-case hunter (15)

**1. `referral/views.py:36-41`**
- **Unhandled path:** institution resolves to None (no request.institution, no request.user.institution)
- **Guard:** `patient = get_object_or_404(Patient.objects.for_institution(institution), id=patient_id)`
- **Consequence:** for_institution(None) branch returns every patient in the system, unlike referral_inbox's `if institution else .none()` guard

**2. `referral/views.py:442-447`**
- **Unhandled path:** institution resolves to None for patient_referrals_tab
- **Guard:** `patient = get_object_or_404(Patient.objects.for_institution(institution), id=patient_id)`
- **Consequence:** Unfiltered patient lookup exposes any institution's patient referral timeline

**3. `referral/models.py:83-88,173-178 (ReferralStatus: PENDING/REPLIED/CLOSED)`**
- **Unhandled path:** Receiving clinician wants to formally decline a referral instead of replying or closing
- **Guard:** `status = models.CharField(choices=ReferralStatus.choices, default=ReferralStatus.PENDING)`
- **Consequence:** No REJECTED/DECLINED state or transition exists; a declined referral has no distinct representation from an unanswered PENDING one

**4. `referral/views.py:338-341 (referral_reply)`**
- **Unhandled path:** A second/third reply arrives while status is already REPLIED
- **Guard:** `ReferralSent.objects.filter(referral_uuid=referral_uuid).update(status=ReferralStatus.REPLIED, updated_at=now)`
- **Consequence:** Repeated replies collapse into the same REPLIED state with no per-direction 'awaiting your response' distinction

**5. `referral/forms.py:41-51`**
- **Unhandled path:** to_institution id in POST data refers to an inactive/suspended institution
- **Guard:** `self.fields['to_clinician'].queryset = CustomUser.objects.filter(institution_id=to_inst_id, is_active=True, user_type=UserType.USER)`
- **Consequence:** Clinician dropdown populates from a suspended institution's roster; only the separately-filtered to_institution field ultimately blocks submission

**6. `referral/signals.py:31,34`**
- **Unhandled path:** instance.to_clinician is None or instance.from_institution is None (both SET_NULL/nullable FKs)
- **Guard:** `Notification.objects.create(recipient=instance.to_clinician, title=f'New referral from {instance.from_institution.name}', ...)`
- **Consequence:** IntegrityError or AttributeError raised and only caught by the generic except, dropping the referral-received notification entirely

**7. `referral/signals.py:73-78,83`**
- **Unhandled path:** sent.from_institution, sent.to_institution, sent.from_clinician or sent.to_clinician is None when a reply notification is built
- **Guard:** `title=f'Reply from {instance.sender_institution.name}'  # recipient = sent.to_clinician or sent.from_clinician, either possibly None`
- **Consequence:** Reply notification silently fails to send to the intended recipient with no fallback

**8. `referral/signals.py:122-137`**
- **Unhandled path:** sent.to_clinician or sent.from_clinician is None when closure notifications are created
- **Guard:** `Notification.objects.create(recipient=sent.to_clinician, title=f'Referral from {sent.from_institution.name} has been closed', ...)`
- **Consequence:** One or both closure notifications silently fail to send, leaving a clinician unaware the thread is sealed

**9. `referral/views.py:459-464`**
- **Unhandled path:** Two distinct patients at the receiving institution share the same baby_name
- **Guard:** `received_referrals = ReferralReceived.objects.filter(to_institution=institution, patient_name=patient.baby_name or '')`
- **Consequence:** No secondary key (snapshot patient_id/DOB) disambiguates; wrong patient's referral thread is displayed

**10. `referral/models.py:150-153,208-213`**
- **Unhandled path:** patient_name is filtered on every patient_referrals_tab render but carries no db_index or Meta.indexes entry
- **Guard:** `patient_name = models.CharField(max_length=200, help_text=...)  # no db_index=True`
- **Consequence:** Full table scan on ReferralReceived for every patient-tab page view as data grows

**11. `referral/views.py:228-230`**
- **Unhandled path:** received.to_clinician is None (deleted account) when the thread panel is opened
- **Guard:** `if received and not received.is_read and received.to_clinician == request.user: received.is_read = True`
- **Consequence:** Comparison against None never matches request.user; the thread stays permanently unread regardless of who views it

**12. `referral/views.py:159-165`**
- **Unhandled path:** to_clinician on ReferralReceived becomes NULL (SET_NULL after account deletion)
- **Guard:** `received_referrals = ReferralReceived.objects.for_institution(institution).filter(to_clinician=request.user)`
- **Consequence:** Referral thread disappears from every institution user's inbox listing while remaining directly reachable via the thread-panel URL

**13. `referral/views.py:529-545 and 575-598`**
- **Unhandled path:** request.institution is None for notification_panel/notification_mark_all_read (unlike notification_count which explicitly guards)
- **Guard:** `notifications = Notification.objects.filter(recipient=request.user, institution=request.institution).order_by('-created_at')[:20]`
- **Consequence:** Silently renders an empty panel / no-op mark-all-read with no distinguishing message for the missing-institution-context state

**14. `referral/views.py:371-397 (referral_close)`**
- **Unhandled path:** Two close requests for the same referral_uuid arrive concurrently, both before either commits
- **Guard:** `if sent.status == ReferralStatus.CLOSED: return _thread_panel_response(...)`
- **Consequence:** Both requests pass the stale check and both send referral_status_changed, duplicating closure notifications

**15. `referral/views.py:201-219 (_thread_panel_response)`**
- **Unhandled path:** sent/received are fetched without select_related on from_institution/to_institution/from_clinician/to_clinician/patient
- **Guard:** `sent = ReferralSent.objects.filter(referral_uuid=referral_uuid, institution=institution).first()`
- **Consequence:** Each related-object access in the rendered thread panel issues a separate query, unlike the select_related used in referral_inbox and patient_referrals_tab

---

## reports — PDF/Excel report generation

### Adversarial (15)

**1. `reports/utils/excel_generator.py:766,785,800,815,830,845`**
- **Problem:** ExcelReportGenerator.generate() accepts an institution param but never applies it to the actual data querysets
- **Fix:** `queryset = Patient.objects.for_institution(institution).select_related(...) instead of Patient.objects.select_related(...).all()`
- **Consequence:** Any staff user's Excel export includes every institution's patients/assessments, a cross-tenant PHI leak

**2. `reports/utils/excel_generator.py:779 vs 794,809,824,839,854 and 441-442,473-474,506-507,547-548,583-584`**
- **Problem:** anonymize flag is only threaded into add_patients_sheet; assessment sheet builders never receive or apply it
- **Fix:** `pass anonymize into add_gm_assessments_sheet/etc. and mask assessment.patient.bht/baby_name when set`
- **Consequence:** Requesting an 'anonymized' export still leaks real patient name/BHT through every assessment sheet

**3. `reports/views.py:264-297`**
- **Problem:** delete_report performs no ownership/session check before removing the file, unlike download_report
- **Fix:** `reuse the cache.get(f"report_owner_{file_id}_{session_key}") check from download_report before os.remove(file_path)`
- **Consequence:** Any authenticated user who learns a file_id can delete another user's generated report (DoS)

**4. `reports/views.py:210-259`**
- **Problem:** report_history lists every file in the shared temp dir with no per-user/session filtering
- **Fix:** `filter listed files by cache.get(f"report_owner_{filename}_{session_key}") == request.user.pk before appending to reports`
- **Consequence:** Any logged-in user sees other users' report filenames/sizes, and can feed file_ids into the unguarded delete endpoint

**5. `reports/utils/excel_generator.py:444-445,476-477`**
- **Problem:** add_gm_assessments_sheet/add_hine_assessments_sheet read getattr(assessment,'age_at_assessment_weeks','') but no such attribute exists on GMAssessment/HINEAssessment
- **Fix:** `compute age_delta = assessment.date_of_assessment.date() - assessment.patient.dob_tob.date() and derive weeks/days explicitly`
- **Consequence:** 'Age at Assessment' columns are silently blank in every GM/HINE export, misleading researchers into thinking data is missing

**6. `reports/utils/excel_generator.py:515-520`**
- **Problem:** add_developmental_assessments_sheet reads language_age_from/social_age_from etc, but the DevelopmentalAssessment model's real fields are hsl_age_from/hsl_age_to/hsl_details and seb_age_from/seb_age_to/seb_details
- **Fix:** `assessment.hsl_age_from, assessment.hsl_age_to, assessment.hsl_details, assessment.seb_age_from, ...`
- **Consequence:** Hearing/Speech/Language and Social/Emotional/Behavioral clinical data is never exported; columns are always empty

**7. `reports/utils/excel_generator.py:779-782,794-797,809-812,824-827,839-842,854-857`**
- **Problem:** each sheet builder fully iterates queryset, then generate() calls queryset.count() again to populate metadata
- **Fix:** `have add_*_sheet return the row count it already produced instead of re-querying with .count()`
- **Consequence:** Doubles the DB round trips for every sheet in every export, worse as dataset size grows

**8. `reports/utils/excel_generator.py:980-998,1030-1035`**
- **Problem:** cross_institution_aggregate() computes gma/hine/cdic/gpa/da counts per institution for the Network Summary sheet, then recomputes the identical five counts per institution again for the per-institution breakdown sheets
- **Fix:** `cache the five counts per institution in a dict on the first pass and reuse them for the per-institution sheets`
- **Consequence:** Query count doubles (10 count() queries per institution instead of 5), scaling poorly with institution count

**9. `reports/utils/excel_generator.py:202-207,361,438,470,503,544,580,882-946,959-1062`**
- **Problem:** entire workbook is built with openpyxl Workbook() (not write_only) and querysets are iterated without .iterator()
- **Fix:** `use Workbook(write_only=True) plus queryset.iterator(chunk_size=...) for large patient/assessment exports`
- **Consequence:** Large hospital-wide exports hold the full ORM result set and full XLSX in memory, risking OOM/slow requests

**10. `reports/utils/excel_generator.py:126-138 (patients/models.py:224 pog_wks, 262-282 apgar_1/5/10)`**
- **Problem:** apply_advanced_filters range-filters on pog_wks and apgar_1/5/10 for every report type, but none of those Patient fields carry db_index=True or a covering index
- **Fix:** `add db_index=True to pog_wks/apgar_1/apgar_5/apgar_10 or a Meta.indexes entry covering them`
- **Consequence:** Every filtered report/export triggers a full table scan on Patient as the table grows

**11. `reports/views.py:348-354 (repeated at 367-375,388-396,409-417,430-438)`**
- **Problem:** view fetches the assessment via get_object_or_404 for the institution-scope check, then discards it and generator.generate(assessment_id) fetches the same row again
- **Fix:** `pass the already-fetched assessment instance into the generator instead of re-querying by id`
- **Consequence:** Every assessment PDF download performs two identical DB queries for the same row

**12. `reports/tasks.py:38-96; reports/utils/pdf_generator.py:216-229`**
- **Problem:** generate_patient_pdf_task and PatientPDFGenerator.generate() take a bare patient_id with no institution/ownership check at all
- **Fix:** `require an institution/user argument and filter Patient.objects.for_institution(institution).get(id=patient_id)`
- **Consequence:** Any caller of this task/generator can pull a full patient PDF across institutions with no authorization check

**13. `reports/utils/pdf_generator.py:202-307,219-226`**
- **Problem:** PatientPDFGenerator.generate() accepts start_date/end_date and prefetches gm_assessments/hine_assessments/developmental_assessments/cdic_records/gpa_assessments/videos/attachments, but the story never renders any of them and the dates are never applied as a filter
- **Fix:** `either drop the unused prefetch_related() calls or actually filter/render the assessments by date range in the story`
- **Consequence:** Wasted prefetch query cost per report and a date-range filter that silently does nothing

**14. `reports/views.py:230-231,321-324; reports/tasks.py:183-199`**
- **Problem:** download_report/report_history hardcode a 24-hour expiry while cleanup_old_reports() honors the admin-configurable ReportConfig 'temp_file_retention_hours'
- **Fix:** `read the same ReportConfig retention value in download_report/report_history instead of a literal 24`
- **Consequence:** Admin-configured longer retention is ignored (users get 404 on still-valid files); shorter retention leaves stale files downloadable

**15. `reports/views.py:187-195`**
- **Problem:** report_builder returns f'Error generating report: {str(e)}' straight to the rendered template on any exception
- **Fix:** `log str(e) server-side and show a generic user-facing message instead of interpolating the raw exception`
- **Consequence:** Internal exception text (ORM field names, file paths, stack details) is disclosed to end users

### Edge-case hunter (12)

**1. `reports/views.py:86-95,103-112`**
- **Unhandled path:** pog_min/pog_max/apgar_min/apgar_max parsing swallows ValueError with bare pass
- **Guard:** `on ValueError, add an error to context/messages instead of silently dropping the filter`
- **Consequence:** User submits an invalid numeric filter and gets an unfiltered report with no indication the filter was ignored

**2. `reports/views.py:98-102; reports/utils/excel_generator.py:132-138`**
- **Unhandled path:** apgar_timepoint from POST is used unchecked to build field_name = f'apgar_{timepoint}' for a dynamic ORM filter
- **Guard:** `if apgar_timepoint not in ('1','5','10'): reject before adding to filters`
- **Consequence:** Arbitrary POST value produces a Django FieldError, aborting report generation

**3. `reports/utils/excel_generator.py:126-138`**
- **Unhandled path:** pog_min/pog_max and apgar_min/apgar_max are applied with no cross-field bound check (min>max, negative, out of 0-10 range)
- **Guard:** `validate apgar_min<=apgar_max and 0<=value<=10, pog_min<=pog_max before filtering`
- **Consequence:** An impossible range silently yields zero rows instead of surfacing a validation error to the user

**4. `reports/utils/pdf_generator.py:364-370`**
- **Unhandled path:** age_delta computed from assessment.date_of_assessment - patient.dob_tob with no guard for assessment date preceding date of birth (GMAssessment.clean() does not validate this, unlike DevelopmentalAssessment)
- **Guard:** `if age_delta.days < 0: age_at_assessment = 'N/A (invalid dates)'`
- **Consequence:** Bad data produces a nonsensical negative-week/day age string on the generated PDF

**5. `reports/utils/pdf_generator.py:58-65`**
- **Unhandled path:** get_page_size() only catches ReportConfig.DoesNotExist; get_value() can raise ValueError on a value_type/value mismatch
- **Guard:** `except (ReportConfig.DoesNotExist, ValueError): return A4`
- **Consequence:** A misconfigured pdf_page_size config value crashes every PDF generator on __init__

**6. `reports/tasks.py:183-187`**
- **Unhandled path:** retention_config.get_value() ValueError is not caught by the inner except ReportConfig.DoesNotExist
- **Guard:** `except (ReportConfig.DoesNotExist, ValueError): retention_hours = 24`
- **Consequence:** A bad INTEGER config value aborts the entire cleanup_old_reports run instead of falling back to the default

**7. `reports/utils/excel_generator.py:1000-1010`**
- **Unhandled path:** when institutions.count() == 0, last_data_row stays at the header row (1) and totals_row becomes 2, so the SUM formula range starts after it ends
- **Guard:** `if institutions.exists(): build totals row, else write 'No institutions' placeholder`
- **Consequence:** Generated formula like =SUM(D2:D1) is a malformed/backwards range with zero institutions

**8. `reports/utils/excel_generator.py:1016-1019`**
- **Unhandled path:** sheet_name = inst.name[:31] has no sanitization of Excel-forbidden characters (: \ / ? * [ ]) and no collision handling after truncation
- **Guard:** `sanitize forbidden chars and dedupe truncated names (e.g. append a counter) before create_sheet()`
- **Consequence:** openpyxl raises on an invalid or duplicate sheet title, aborting the whole network export

**9. `reports/views.py:313-315`**
- **Unhandled path:** cache key uses request.session.session_key with no None guard
- **Guard:** `if not request.session.session_key: raise PermissionDenied(...) before building the cache key`
- **Consequence:** A request with no session resolves to a literal '...None' cache key, an unintended shared lookup path

**10. `reports/utils/excel_generator.py:108-200`**
- **Unhandled path:** apply_advanced_filters branches on model_type via if/elif for 'patient'/'gm'/'hine'/'developmental'/'cdic'/'gpa' with no final else
- **Guard:** `add an else clause that logs/raises on an unrecognized model_type`
- **Consequence:** A typo'd or new model_type silently returns the queryset completely unfiltered with no warning

**11. `reports/utils/excel_generator.py:407-413; reports/views.py:70-78`**
- **Unhandled path:** selected_fields comes straight from request.POST.getlist('patient_fields'); unknown names fall through to getattr(patient, field, '')
- **Guard:** `validate patient_fields against field_header_map.keys() before use, rejecting anything outside the allow-list`
- **Consequence:** A crafted field name can pull an arbitrary Patient attribute into the export, bypassing the intended field/anonymization allow-list

**12. `reports/utils/pdf_generator.py:117-130,144-157`**
- **Unhandled path:** institution/template logo .path access is wrapped in bare except Exception: pass with no logging
- **Guard:** `log the exception (e.g. logger.warning) before falling back to omitting the logo`
- **Consequence:** A remote/S3 storage backend (NotImplementedError on .path) silently drops the logo on every report with no diagnostic trail

---

## ndas core & custom_codes — shared infra: settings, middleware, validators, sanitization, delete_helpers, error_handlers

### Adversarial (15)

**1. `ndas/settings.py:40-55`**
- **Problem:** CLAUDE.md documents an exact 14-item MIDDLEWARE order but settings.py inserts an undocumented 'institution.middleware.InstitutionContextMiddleware' before the production-only validation middleware
- **Fix:** `Update CLAUDE.md's Middleware Stack section to include InstitutionContextMiddleware at its actual position, or move institution scoping earlier/document why it runs last`
- **Consequence:** Future edits assume the documented 13/14-item list is authoritative and reorder middleware around a step that doesn't exist in the docs, breaking institution scoping or security headers

**2. `ndas/settings.py:334-335`**
- **Problem:** SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE default to False even when DEBUG=False, unlike EMAIL_BACKEND/SESSION_ENGINE/CSP which branch on DEBUG automatically
- **Fix:** `SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)`
- **Consequence:** A production deployment that forgets to set the env vars silently sends session/CSRF cookies over plain HTTP

**3. `ndas/custom_codes/sanitization.py:37-61`**
- **Problem:** ALLOWED_ATTRIBUTES['a'] permits target without bleach forcing rel="noopener noreferrer" when target="_blank" is present
- **Fix:** `after bleach.clean, force rel='noopener noreferrer' on any <a target="_blank"> via a bleach Attribute callback`
- **Consequence:** Reverse-tabnabbing: injected/linkified links opened in a new tab can use window.opener to redirect the original clinical session to a phishing page

**4. `ndas/custom_codes/validators.py:42-61`**
- **Problem:** sanitize_text_input() strips <tag> patterns and event handlers BEFORE calling html.unescape() at line 61, so entity-encoded payloads like '&lt;script&gt;alert(1)&lt;/script&gt;' pass every filter untouched and are then decoded back into live markup by the trailing unescape call
- **Fix:** `text = html.unescape(text) once at the very start, then run the tag/event-handler/protocol strips on the decoded text`
- **Consequence:** Stored/reflected XSS via double-encoded payloads in any medical text field that later reaches non-autoescaped output (PDF/Excel export, email, mark_safe template use)

**5. `ndas/custom_codes/validators.py:52`**
- **Problem:** Dangerous-protocol strip regex r"(javascript|data|vbscript):" requires the literal contiguous string, so inserting whitespace/control chars (e.g. 'java\tscript:') bypasses removal while browsers still parse it as the javascript: scheme
- **Fix:** `text = re.sub(r'(?:j\s*a\s*v\s*a\s*s\s*c\s*r\s*i\s*p\s*t|data|vbscript)\s*:', '', text, flags=re.IGNORECASE)`
- **Consequence:** Crafted attribute values still execute script URLs after 'sanitization', defeating the stated XSS protection

**6. `ndas/custom_codes/validators.py:481-565 (esp. 542 and 553-563)`**
- **Problem:** validate_attachment_file() checks value.size against MAX_VIDEO_SIZE (2GB) for every attachment type instead of the type-specific limit computed at 499-501, and 'MIME type validation' only calls mimetypes.guess_type() on the filename, never inspecting file bytes
- **Fix:** `pick max_size by extension category (image/doc/video) before the size check; use python-magic (magic.from_buffer) on the uploaded bytes as CLAUDE.md claims, not mimetypes.guess_type(name)`
- **Consequence:** A 1.9GB 'image' or 'document' upload is accepted (contradicts the documented 10MB/100MB limits) and a renamed malicious file with an allowed extension passes MIME 'validation' untouched

**7. `ndas/custom_codes/validators.py:74-148 vs ndas/custom_codes/sanitization.py:119-181`**
- **Problem:** Two different functions are both named sanitize_filename (different default max_length, different dotfile/traversal handling) in validators.py and sanitization.py, and CLAUDE.md's own Quick Reference imports it from validators.py while custom_methods.py's institution-path helpers import the sanitization.py one
- **Fix:** `rename one (e.g. sanitize_filename_fs vs sanitize_filename_display) or make one call the other so behavior can't silently diverge by import choice`
- **Consequence:** A future edit imports the wrong module's sanitize_filename and gets weaker traversal/length guarantees without any error, since both have the same name and signature shape

**8. `ndas/custom_codes/custom_methods.py:150-156`**
- **Problem:** get_ip_address() trusts the client-supplied HTTP_X_FORWARDED_FOR header verbatim with no proxy allowlist or format validation
- **Fix:** `only trust X-Forwarded-For when request came through a known trusted proxy (django's SECURE_PROXY_SSL_HEADER-style allowlist), else use REMOTE_ADDR`
- **Consequence:** Any client can spoof the IP recorded in security/audit logs (getFullDeviceDetails, login logging), undermining forensic trust in a medical system's audit trail

**9. `ndas/custom_codes/custom_methods.py:623-628`**
- **Problem:** PtStatus.DX_NORMAL builds its exclude() filter with Python's `and` operator between three Q objects instead of `&`; `and` short-circuits and returns only the last Q object, so the GMA-abnormal and HINE-abnormal conditions are silently dropped from the query
- **Fix:** `return var_ptl.exclude(Q(gmassessment__diagnosis_conclusion='ABNORMAL') | Q(hine_assessments__score__lt=73) | Q(developmental_assessments__is_dx_normal=False)).filter(_has_videos=True).distinct()`
- **Consequence:** Patients with an abnormal GMA or HINE result but a normal/absent developmental assessment are wrongly classified as 'DX_NORMAL' in dashboards and lists — a real misdiagnosis-categorization bug in a medical record system

**10. `ndas/custom_codes/delete_helpers.py:47-50`**
- **Problem:** has_delete_permission() grants ANY staff user delete rights on ANY Bookmark object, without checking entity.added_by/ownership, contradicting the documented 'Staff delete own records' rule
- **Fix:** `if entity.__class__.__name__ == 'Bookmark' and entity.added_by == user: return True  # or use an 'owner' field with equivalent ownership check`
- **Consequence:** Any staff account can delete other clinicians' bookmarks — a documented-rule violation and unintended cross-user data destruction

**11. `ndas/custom_codes/delete_helpers.py:76-86`**
- **Problem:** validate_can_delete() only blocks Video deletion when referenced by GMAssessment.video_file; it never checks HINEAssessment, DevelopmentalAssessment, CDICRecord or GPARecord even though CLAUDE.md's assessment list (GPA, HINE, CDIC, Developmental) implies videos can be attached to those too
- **Fix:** `aggregate reference counts across all assessment models that have a video_file/video FK before allowing delete`
- **Consequence:** A video still referenced by a HINE/Developmental/CDIC/GPA assessment can be deleted, breaking those assessment records and violating the documented 'Videos blocked if in assessments' rule

**12. `ndas/custom_codes/error_handlers.py:53-64 and 116-127`**
- **Problem:** handle_view_errors() only special-cases django.core.exceptions.ObjectDoesNotExist, but CLAUDE.md mandates get_object_or_404() everywhere, which raises django.http.Http404 — a different exception that falls through to the generic 'except Exception' branch
- **Fix:** `except Http404 as e: ... raise  (or re-render a proper 404) — add an explicit Http404 branch before the catch-all`
- **Consequence:** Every 404 produced by the mandated get_object_or_404() pattern is logged via logger.exception() as an 'unexpected error' and returned as a redirect with a misleading generic message instead of a real 404 response

**13. `ndas/custom_codes/error_handlers.py:105-114`**
- **Problem:** The PermissionDenied branch ignores the caller-supplied redirect_url parameter and always redirects to 'home', unlike every other branch in the same decorator
- **Fix:** `return redirect(redirect_url) if redirect_url else redirect('home')`
- **Consequence:** Views that configure a specific redirect_url for permission errors silently get sent to 'home' instead, breaking intended navigation/UX and making the parameter misleading

**14. `ndas/custom_codes/error_handlers.py:133-162`**
- **Problem:** log_and_suppress() catches bare `Exception` for any decorated function with no exclusion list, so PermissionDenied, SuspiciousOperation, or programming errors (TypeError/AttributeError) are all silently swallowed and replaced with default_return
- **Fix:** `except (ExpectedTransientError1, ExpectedTransientError2) as e: ...  # avoid bare Exception, or re-raise security-relevant exception types`
- **Consequence:** Real bugs and security-relevant failures in any function wrapped with this decorator disappear silently, masking the root cause and returning a 'successful-looking' default value

**15. `ndas/templatetags/delete_modal_tags.py:91-104 vs ndas/custom_codes/delete_helpers.py:163-177`**
- **Problem:** delete_modal_tags.py's url_map keys the GPA record as 'GeneralPaediatricAssessment' while delete_helpers.py's redirect map and warning/detail logic key it as 'GPARecord' — the two files disagree on the class name for the same entity
- **Fix:** `use a single canonical model class name (e.g. 'GPARecord') consistently in both url_map and redirect_map`
- **Consequence:** Delete modal for the GPA record falls through to the guessed fallback URL '/gparecord/delete/{id}/', which likely doesn't exist, breaking the delete action for that entity type

### Edge-case hunter (10)

**1. `ndas/custom_codes/custom_methods.py:639-640`**
- **Unhandled path:** getPatientList() falls to `else: return None` for any pts_type value not in the explicit enum branches
- **Guard:** `else: raise ValueError(f'Unsupported pts_type: {pts_type}')`
- **Consequence:** Caller iterates/filters the returned None as if it were a QuerySet, raising an unhandled AttributeError/TypeError

**2. `ndas/custom_codes/custom_methods.py:623-628`**
- **Unhandled path:** Q(...) and Q(...) and Q(...) short-circuits to only the last operand; the GMA-abnormal and HINE-abnormal branches of the intended condition are never evaluated
- **Guard:** `combine with `&` (bitwise) instead of `and`: Q(a) & Q(b) & Q(c)`
- **Consequence:** DX_NORMAL queryset silently ignores two of the three intended exclusion conditions

**3. `ndas/custom_codes/delete_helpers.py:40-43`**
- **Unhandled path:** entity.added_by is None (legacy/system-created record) is not handled — `entity.added_by == user` is always False in that case
- **Guard:** `if hasattr(entity, 'added_by') and user.is_staff and (entity.added_by == user or entity.added_by is None): ...`
- **Consequence:** Orphaned records with no recorded creator become permanently undeletable by any staff user, only a superuser can remove them

**4. `ndas/custom_codes/error_handlers.py:53-64`**
- **Unhandled path:** django.http.Http404 raised inside a decorated view (e.g. via get_object_or_404) is not matched by the ObjectDoesNotExist except clause and has no dedicated branch
- **Guard:** `except Http404: raise  # let Django's normal 404 handling take over`
- **Consequence:** 404s are misrouted into the generic Exception branch, producing a redirect + generic error message instead of a 404 response

**5. `ndas/custom_codes/validators.py:107,137-139`**
- **Unhandled path:** ext is not length-capped before `max_name_length = max_length - len(ext) - 1` is computed; a pathologically long extension drives max_name_length negative
- **Guard:** `ext = ext[:20]  # cap extension length before computing max_name_length`
- **Consequence:** name[:negative_index] silently truncates/empties the base filename, so the returned filename is dominated by (a truncated slice of) the attacker-supplied extension string

**6. `ndas/custom_codes/custom_methods.py:150-156`**
- **Unhandled path:** user_ip_address.split(',')[0] is used without stripping whitespace or validating it's a well-formed IP; an empty or malformed X-Forwarded-For value is not handled
- **Guard:** `ip = (user_ip_address.split(',')[0].strip() or request.META.get('REMOTE_ADDR'))`
- **Consequence:** Malformed or empty forwarded-for values get stored/logged as the 'IP address' verbatim, corrupting audit records

**7. `ndas/custom_codes/delete_helpers.py:175-176`**
- **Unhandled path:** `if entity_type == 'Problem' and patient_id:` treats patient_id == 0 as falsy, an unhandled boundary distinct from patient_id is None
- **Guard:** `if entity_type == 'Problem' and patient_id is not None:`
- **Consequence:** A Problem entity tied to a patient with pk 0 would redirect to the generic '/' fallback instead of its problem-manager URL

**8. `ndas/custom_codes/error_handlers.py:105-114`**
- **Unhandled path:** The redirect_url parameter path is never read inside the PermissionDenied branch even though it's a documented, always-available parameter of the decorator
- **Guard:** `return redirect(redirect_url) if redirect_url else redirect('home')`
- **Consequence:** Callers passing redirect_url for permission errors get an unexpected destination with no way to override it

**9. `ndas/custom_codes/sanitization.py:143-166 vs ndas/custom_codes/validators.py:127-129`**
- **Unhandled path:** A filename that is entirely a leading dot (e.g. '.env') is handled two different ways across the two same-named sanitize_filename functions: sanitization.py strips leading dots to bare 'env', validators.py prefixes 'file_' to keep 'file_env'
- **Guard:** `define one shared dotfile-handling rule and have both call sites use it`
- **Consequence:** Same input produces different stored filenames depending on which module happened to be imported at that call site

**10. `ndas/custom_codes/validators.py:493`**
- **Unhandled path:** validate_attachment_file skips all validation when `isinstance(value, FieldFile) and not isinstance(value.file, UploadedFile)`, but doesn't handle the case where value.file access itself raises (e.g. missing file on disk) before the isinstance check completes
- **Guard:** `wrap the FieldFile.file access in try/except (OSError, ValueError) before the isinstance check`
- **Consequence:** Editing an unrelated field on a model whose existing attachment file is missing from storage can raise an unhandled exception during full_clean()

---

## users — auth, sessions, admin user management, subscriptions

### Adversarial (19)

**1. `users/middleware.py:56-177`**
- **Problem:** SubscriptionCheckMiddleware runs unconditionally even when MULTI_INSTITUTION_ENABLED=True
- **Fix:** `class SubscriptionCheckMiddleware(MiddlewareMixin): def process_request(self, request): ... (no settings.MULTI_INSTITUTION_ENABLED check)`
- **Consequence:** Users get gated by a stale global Subscription unrelated to their institution, and every authenticated request pays a duplicate DB fetch already done by InstitutionContextMiddleware

**2. `users/views.py:209,218,863`**
- **Problem:** institution=request.institution / user__institution=request.institution accessed without getattr fallback
- **Fix:** `custom_user = get_object_or_404(CustomUser, id=pk, institution=request.institution)`
- **Consequence:** AttributeError/500 for any non-superuser view when MULTI_INSTITUTION_ENABLED=False, since no middleware sets request.institution in that mode

**3. `users/utils.py:69-104`**
- **Problem:** get_geolocation_from_ip makes a synchronous 5s external HTTP call on every login/logout/admin action
- **Fix:** `response = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=5)`
- **Consequence:** Attacker floods failed logins to tie up worker threads for up to 5s each, causing self-inflicted DoS on the auth endpoint

**4. `users/utils.py:185-214 (also users/middleware.py:180-190 and users/views.py:194-202)`**
- **Problem:** logoutPage calls log_logout_activity() explicitly, then logout() fires user_logged_out which calls it again via the signal receiver after session.flush() already cleared session_key
- **Fix:** `def logoutPage(request): ... log_logout_activity(request, user); logout(request)  # signal handler runs again post-flush`
- **Consequence:** Every logout writes a duplicate audit row and makes two extra geolocation HTTP calls; the signal-path lookup always misses (session_key already None) and silently fails

**5. `users/utils.py:122-161, users/views.py:636-641`**
- **Problem:** Admin CRUD actions call log_user_activity(request, request.user, LOGIN_SUCCESS/ADMIN_ACTION, ...) which reuses login-specific suspicious-activity heuristics
- **Fix:** `log_user_activity(request, request.user, UserActivityLog.LOGIN_SUCCESS, failed_reason=f"Admin action: Created user: {user.username}")`
- **Consequence:** Every admin create/edit/toggle burns 2 extra COUNT queries plus a geolocation HTTP call, and can log misleading 'suspicious activity' warnings against the admin's own account

**6. `users/models.py:401-416`**
- **Problem:** is_suspicious_activity() only returns a bool that gets logged as a warning, nothing acts on it
- **Fix:** `if activity_log.is_suspicious_activity(): logger.warning(...)  # no lockout/throttle triggered`
- **Consequence:** Brute-force/credential-stuffing patterns are detected but never blocked, giving a false sense of protection

**7. `users/forms.py:52-57,155-160,449-460`**
- **Problem:** CustomUserRegistrationForm/AdminUserCreationForm never call django.contrib.auth.password_validation.validate_password
- **Fix:** `def clean_password2(self): ... if password1 != password2: raise ValidationError(...)  # no validate_password(password1, self.instance)`
- **Consequence:** AUTH_PASSWORD_VALIDATORS (length, common-password, similarity checks) are silently bypassed at account creation

**8. `users/forms.py:11-160`**
- **Problem:** CustomUserRegistrationForm has no clean_email while CustomUserEditForm does
- **Fix:** `class Meta: fields = ['username', 'position', ... 'email', ...]  # no clean_email override`
- **Consequence:** Duplicate emails can be registered; Django's PasswordResetForm.get_users() would then email every matching account for one reset request

**9. `users/forms.py:239-249`**
- **Problem:** clean_email/clean_username use case-sensitive exact filter() instead of iexact
- **Fix:** `existing_user = CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk)`
- **Consequence:** Case-variant duplicate emails (User@x.com vs user@x.com) bypass uniqueness while Django's password reset treats them as the same account

**10. `users/admin.py:10-24`**
- **Problem:** CustomUserAdmin does not override add_fieldsets while mobile_primary is a required, non-blank model field
- **Fix:** `class CustomUserAdmin(UserAdmin): list_display = (...)  # no add_fieldsets override`
- **Consequence:** Creating a user via Django admin's 'Add user' popup fails validation/IntegrityError because mobile_primary is never presented on that form

**11. `users/views.py:626-833`**
- **Problem:** admin_user_add, admin_user_edit, admin_user_toggle_status, admin_user_delete carry no @ratelimit decorator
- **Fix:** `@admin_required\ndef admin_user_add(request): ...  # no @ratelimit unlike userEdit/userChangePassword`
- **Consequence:** A compromised or malicious admin session can script unthrottled mass account creation/deactivation

**12. `users/views.py:42-43`**
- **Problem:** ratelimit key='post:username' uses the raw un-normalized POST username
- **Fix:** `@ratelimit(key='post:username', rate='5/m', method='POST', block=False)`
- **Consequence:** Attacker bypasses the 5/min per-username brute-force limit by varying case (Admin, ADMIN, admin all count separately)

**13. `users/admin.py:88-207`**
- **Problem:** UserActivityLogAdmin overrides has_add_permission and has_change_permission to False but never has_delete_permission
- **Fix:** `def has_change_permission(self, request, obj=None): return False  # has_delete_permission not defined`
- **Consequence:** Any staff user with the delete_useractivitylog permission can bulk-delete audit trail rows, defeating the immutability intent

**14. `users/utils.py:322-337`**
- **Problem:** cleanup_user_data()/cleanup_old_records()/cleanup_expired_sessions() are never invoked by any scheduled task or management command
- **Fix:** `def cleanup_user_data(): deleted_logs = UserActivityLog.cleanup_old_records(days=90) ...  # only reachable via manual admin action`
- **Consequence:** Documented 90-day/30-day GDPR data retention is unenforced unless an admin remembers to click the admin action

**15. `users/utils.py:107-119`**
- **Problem:** _is_private_ip treats any IP starting with '172.' as private
- **Fix:** `private_ranges = ['127.', '10.', '172.', '192.168.', '::1']`
- **Consequence:** Public IPs in 172.32.0.0-172.255.255.255 (e.g. many cloud/CDN ranges) are wrongly skipped for geolocation, corrupting audit location data

**16. `users/views.py:612-621,842-851`**
- **Problem:** admin_user_list/admin_user_activity call queryset.count() explicitly in addition to Paginator, which already runs its own count()
- **Fix:** `context = {'page_obj': page_obj, ..., 'total_users': users.count()}`
- **Consequence:** Every paginated admin list page issues a redundant duplicate COUNT query against a potentially large table

**17. `users/views.py:710-801,804-833`**
- **Problem:** admin_user_delete/admin_user_toggle_status only guard against self-deactivation, not deactivating the last other superuser
- **Fix:** `if user == request.user: ... return  # no check for CustomUser.objects.filter(is_superuser=True, is_active=True).count() <= 1`
- **Consequence:** An admin can deactivate every other superuser account, locking the system out of administrative access

**18. `users/forms.py:101-153,301-353`**
- **Problem:** clean_profile_picture is duplicated verbatim between CustomUserRegistrationForm and CustomUserEditForm
- **Fix:** `def clean_profile_picture(self): ... max_dimension = 4000 ...  # identical block in two classes`
- **Consequence:** A future fix to file-size/dimension limits applied to only one form silently leaves the other form with the old, weaker validation

**19. `users/views.py:958-997`**
- **Problem:** subscription_update checks request.user.is_superuser manually instead of using the superuser_required decorator already defined in decorators.py
- **Fix:** `if not request.user.is_superuser: messages.error(...); return redirect('home')`
- **Consequence:** Duplicated authorization logic drifts from the shared decorator over time, risking inconsistent enforcement across admin views

### Edge-case hunter (10)

**1. `users/views.py:510`**
- **Unhandled path:** days = int(request.POST.get('days', 30)) has no bounds/type guard
- **Guard:** `days = int(request.POST.get('days', 30))`
- **Consequence:** Non-numeric input raises ValueError (500); an extreme value raises OverflowError from timedelta(days=huge_number)

**2. `users/models.py:652-659,662-770`**
- **Unhandled path:** remaining_days recomputes date.today() fresh on every call while is_active/is_expired/is_grace_period read from a 60s cache
- **Guard:** `today = date.today(); return (self.expiration_date - today).days  # not part of cache_data dict`
- **Consequence:** remaining_days can disagree with the cached status fields across a date rollover within the cache TTL window

**3. `users/models.py:818-836`**
- **Unhandled path:** extend_subscription(days) does not validate the sign or magnitude of days
- **Guard:** `subscription.duration_days += days  # no check that days > 0`
- **Consequence:** Passing a negative days value silently shrinks (rather than extends) the subscription duration

**4. `users/middleware.py:65-76`**
- **Unhandled path:** EXEMPT_URLS lists '/users/login/' but not the bare '/users/' path that urls.py also maps to the login view
- **Guard:** `EXEMPT_URLS = ['/users/login/', '/users/logout/', ...]  # '/users/' missing`
- **Consequence:** An authenticated user with an expired subscription visiting '/users/' is force-logged-out instead of getting the login view's own redirect handling

**5. `users/views.py:280-295`**
- **Unhandled path:** invalid password-change form falls through to messages.error(request, form.error_messages)
- **Guard:** `messages.error(request, form.error_messages)`
- **Consequence:** form.error_messages is the class-level message template dict, not the populated form.errors, so the user never sees the actual validation reason

**6. `users/urls.py:9-10`**
- **Unhandled path:** two different path patterns ('' and 'login/') are both registered under the same url name 'user-login'
- **Guard:** `path("", views.loginPage, name='user-login'), path("login/", views.loginPage, name='user-login'),`
- **Consequence:** reverse('user-login') resolution is ambiguous/order-dependent, making generated links inconsistent

**7. `users/views.py:734-742`**
- **Unhandled path:** json.loads(request.body) result is used with .get() without checking it is a dict
- **Guard:** `data = json.loads(request.body); password = data.get('password', '')`
- **Consequence:** A syntactically valid JSON body that is a list/number/string (e.g. '[1,2]') passes json.loads but raises an uncaught AttributeError on .get()

**8. `users/models.py:17-140`**
- **Unhandled path:** CustomUser.email (inherited from AbstractUser) has no unique=True or db_index despite being used as a lookup key in resend_verification_email and password reset
- **Guard:** `class CustomUser(AbstractUser, TimeStampedModel): ... USERNAME_FIELD = "username"  # email left unindexed/non-unique`
- **Consequence:** CustomUser.objects.get(email=email) can raise MultipleObjectsReturned and full-table-scans as the users table grows

**9. `users/views.py:627-652, users/forms.py:424-431`**
- **Unhandled path:** AdminUserCreationForm.Meta.fields omits institution/user_type, so admin_user_add never sets them
- **Guard:** `fields = ['username', 'first_name', ... 'is_active', 'is_staff', 'additional_notes']  # no institution/user_type`
- **Consequence:** Users created via the admin panel always get institution=None, leaving them outside their creating admin's institution scope

**10. `users/middleware.py:29-53`**
- **Unhandled path:** UserActivityMiddleware.process_request wraps its entire body in a bare except Exception: pass with no logging
- **Guard:** `except Exception:\n    # Fail silently to avoid breaking the application\n    pass`
- **Consequence:** Real bugs (e.g. cache backend misconfiguration, DB errors) in session-activity tracking are permanently invisible with no log trace

---

## institution (Phase 2) — multi-institution scoping, middleware, admin

### Adversarial (13)

**1. `institution/middleware.py:16-28`**
- **Problem:** ADMIN/USER of an EXPIRED-subscription institution navigates directly to any /institution/* URL
- **Fix:** `EXEMPT_URLS = [..., '/institution/', ...]  # skips _resolve_user_context entirely, so _check_subscription never runs`
- **Consequence:** EXPIRED institutions retain full access to clinician creation, branding settings, and admin dashboard even though every other route logs them out

**2. `institution/managers.py:22-30 + institution/middleware.py:95-103`**
- **Problem:** request.user.institution is None while MULTI_INSTITUTION_ENABLED=True (e.g. institution hard-deleted via SET_NULL, or never assigned)
- **Fix:** `_resolve_user_context sets request.institution = None and permits access; for_institution(None) then returns self.get_queryset() unfiltered`
- **Consequence:** Any USER/ADMIN whose institution FK becomes null gets unfiltered cross-tenant access to every institution's patients

**3. `institution/middleware.py:136-138`**
- **Problem:** Institution in GRACE status, non-GET request, attacker-controlled HTTP_REFERER header (e.g. cross-site form POST)
- **Fix:** `referer = request.META.get('HTTP_REFERER', '/'); return HttpResponseRedirect(referer)  # no same-origin validation`
- **Consequence:** Open redirect: authenticated NDAS users can be bounced to an attacker-controlled URL

**4. `institution/views.py:864-899 (docstring) + institution/middleware.py:27 + institution/views.py:735-740`**
- **Problem:** SUPERADMIN with an active session institution context navigates to institution:institution-settings, which its docstring claims is supported
- **Fix:** `_get_admin_institution returns getattr(request,'institution',None) or getattr(request.user,'institution',None); request.institution is never set because /institution/ is EXEMPT_URLS, and SUPERADMIN.institution is always None`
- **Consequence:** SUPERADMIN can never actually reach institution settings for the institution they are viewing — silently redirected home, feature dead on arrival

**5. `institution/views.py:572 and 586`**
- **Problem:** confirm/execute POST step targets a deactivated institution's pk as destination_institution_id
- **Fix:** `destination = get_object_or_404(Institution, pk=destination_id)  # missing is_active=True, unlike institution_switch line 103 and all_institutions line 552`
- **Consequence:** A patient can be moved into a deactivated/decommissioned institution and become inaccessible to any active admin

**6. `institution/views.py:582-624`**
- **Problem:** destination_institution_id posted equal to the patient's current institution (bypassing the UI's exclude())
- **Fix:** `no check `if destination.pk == (source_institution.pk if source_institution else None): reject``
- **Consequence:** A no-op 'move' still writes duplicate PatientMoveLog rows and a misleading audit trail

**7. `institution/views.py:609-624`**
- **Problem:** any patient move executes
- **Fix:** `both PatientMoveLog.objects.create() calls set identical from_institution=source_institution, to_institution=destination; only comment text distinguishes them as 'scoped to SOURCE'/'scoped to DESTINATION'`
- **Consequence:** Any audit query filtering by from_institution=X or to_institution=X returns the same move twice, corrupting per-institution audit counts/reports

**8. `institution/forms.py:143-196`**
- **Problem:** ADMIN submits institution_clinician_add with an email already used by another CustomUser (email field has no unique=True in users/models.py:530-535)
- **Fix:** `InstitutionClinicianForm has no clean_email uniqueness check, unlike InstitutionOnboardingForm.clean_admin_email (lines 122-126)`
- **Consequence:** Duplicate-email clinician accounts get silently created, breaking password-reset/notification flows that assume email uniqueness

**9. `institution/forms.py:199-215`**
- **Problem:** institution ADMIN self-service edits short_name via institution_settings
- **Fix:** `InstitutionSettingsForm defines clean_name and clean_logo but no clean_short_name, unlike SuperadminInstitutionEditForm.clean_short_name (255-256) and InstitutionOnboardingForm.clean_institution_short_name (113-114)`
- **Consequence:** Unsanitized, non-uppercased short_name is persisted and rendered in sidebar branding site-wide, inconsistent with sanitization applied through every other entry point

**10. `institution/models.py:33-38`**
- **Problem:** Any code path updates slug via QuerySet.update()/bulk_update() instead of instance.save()
- **Fix:** `slug-immutability is enforced only inside save()/clean(); Institution.objects.filter(pk=x).update(slug='new') bypasses both`
- **Consequence:** The documented 'immutable slug' invariant is silently violated, breaking any logic (media paths, URLs) that assumes slug stability

**11. `institution/middleware.py:16-28`**
- **Problem:** institution ADMIN or compromised staff account has Django-admin (is_staff) access
- **Fix:** `'/admin/' is in EXEMPT_URLS, bypassing both institution-context resolution and subscription checks; Django admin ModelAdmins for institution-scoped models are not shown to be institution-filtered`
- **Consequence:** Django admin becomes a full bypass of institution data isolation for any staff-flagged account

**12. `institution/views.py:36-39`**
- **Problem:** request reaches the app directly (not behind a trusted proxy) or a proxy forwards a client-supplied header verbatim
- **Fix:** `_get_client_ip trusts HTTP_X_FORWARDED_FOR unconditionally with no trusted-proxy allowlist`
- **Consequence:** InstitutionSwitchLog.ip_address audit entries can be forged by spoofing X-Forwarded-For, undermining the audit trail's forensic value

**13. `institution/views.py:47-80, 222-259, 266-284, 386-406, 524-546 (six separate call sites)`**
- **Problem:** a future view is added under institution/views.py without copy-pasting the `if user_type != UserType.SUPERADMIN: return redirect(...)` guard
- **Fix:** `no shared @superadmin_required / @admin_required decorator exists; each view repeats the same inline check`
- **Consequence:** A missed copy-paste of the inline permission check on a new view silently exposes a superadmin-only or admin-only endpoint

### Edge-case hunter (11)

**1. `institution/middleware.py:66`**
- **Unhandled path:** active_institution_id session value is 0
- **Guard:** `if active_id is not None:`
- **Consequence:** A valid institution pk of 0 is treated as 'no context', redirecting to the selector instead of resolving it

**2. `institution/middleware.py:129`**
- **Unhandled path:** HEAD request while institution subscription_status is GRACE
- **Guard:** `if request.method not in ('GET', 'HEAD') and not request.path.startswith('/referral/'):`
- **Consequence:** Read-only HEAD requests get redirected as if they were mutating writes during the grace period

**3. `institution/views.py:572,586`**
- **Unhandled path:** destination_institution_id POST field missing or non-numeric on confirm/execute steps
- **Guard:** `if not str(destination_id).isdigit(): messages.error(...); return redirect(...)`
- **Consequence:** get_object_or_404 raises ValueError, caught only by the outer generic handler, producing a non-specific 'move failed' message

**4. `institution/views.py:433,461-466`**
- **Unhandled path:** institution_id in POST refers to a non-existent institution for scope='per_institution'
- **Guard:** `except Http404 handled separately from the generic `except Exception` at line 461`
- **Consequence:** A true 404 (institution not found) is downgraded to a generic 'Report generation failed' flash message

**5. `institution/views.py:158`**
- **Unhandled path:** POST request whose QueryDict happens to be empty (zero keys)
- **Guard:** `form = InstitutionOnboardingForm(request.POST if request.method == 'POST' else None)`
- **Consequence:** form.is_valid() short-circuits False as an unbound form, silently re-rendering a blank form with no field errors shown

**6. `institution/models.py:34-38`**
- **Unhandled path:** save() called on an instance whose pk is set but no row exists yet (e.g. manually pre-assigned pk)
- **Guard:** `try: original = Institution.objects.get(pk=self.pk) except Institution.DoesNotExist: pass  (only clean() at line 46-47 does this, save() does not)`
- **Consequence:** Unhandled Institution.DoesNotExist crashes save() instead of proceeding to insert

**7. `institution/views.py:306-319,358-364`**
- **Unhandled path:** Patient.institution is NULL for some patients (transitional data) while MULTI_INSTITUTION_ENABLED=True
- **Guard:** `_assessment_counts keys results by patient__institution_id; the institution_data loop only iterates real Institution rows, so the None-keyed bucket is never read`
- **Consequence:** Assessment activity for un-institutioned patients silently vanishes from both per-institution cards and the platform-wide summary totals

**8. `institution/views.py:920-932`**
- **Unhandled path:** media path does not match the '{slug}/videos/...' or '{slug}/attachments/...' pattern (e.g. flat filename, or a different upload category like 'documents')
- **Guard:** `if len(parts) >= 2 and parts[1] in ('videos','attachments'): <enforce>  else: <falls through to unrestricted serve>`
- **Consequence:** Any media file outside the two recognized subfolder names is served to any authenticated user with no institution-boundary check at all

**9. `institution/views.py:552-554`**
- **Unhandled path:** patient.institution is None (source_institution is None) when opening the patient-move flow
- **Guard:** `.exclude(pk=source_institution.pk if source_institution else None) — excluding pk=None is a no-op`
- **Consequence:** Every active institution (correctly) appears selectable, but the code gives no explicit signal that the 'exclude source' branch never actually executed for this patient

**10. `institution/templatetags/institution_tags.py:42`**
- **Unhandled path:** SUPERADMIN has an active_institution but zero active institutions currently exist (e.g. all deactivated) in the same request
- **Guard:** `institutions = Institution.objects.filter(is_active=True).order_by('name') — no guard against an empty list feeding the context-switch dropdown`
- **Consequence:** Overlay renders a context-switcher dropdown with no options, offering no way back to the selector short of the direct URL

**11. `institution/views.py:679-717`**
- **Unhandled path:** institution_admin_dashboard's recent_registrations = Patient.objects.for_institution(institution).order_by('-created_at')[:5] has no select_related
- **Guard:** `recent_registrations = Patient.objects.for_institution(institution).select_related('added_by').order_by('-created_at')[:5]`
- **Consequence:** Template access to related fields (e.g. added_by) on each of the 5 rows triggers N+1 queries per dashboard load

---

## video — video upload, metadata extraction, storage

### Adversarial (14)

**1. `video/models.py:298-306`**
- **Problem:** hasattr(self.video_file, 'path') is true for any freshly-assigned upload since FieldFile always exposes the 'path' property
- **Fix:** `check hasattr(video_file, 'temporary_file_path') before 'path', or verify the underlying file is committed`
- **Consequence:** extraction reads a pre-storage path that does not exist yet, so duration/resolution silently stay unset for every new upload

**2. `video/models.py:284-296`**
- **Problem:** FileField.pre_save() writes the file to disk inside super().save(), independent of the DB transaction it runs in
- **Fix:** `delete the newly written file in an except block around super().save(), or defer the write with transaction.on_commit`
- **Consequence:** an IntegrityError (e.g. unique_video_per_patient_time_title) leaves a multi-GB orphaned file on disk with no DB row referencing it

**3. `video/views.py:581-588`**
- **Problem:** video.video_file.delete(save=False) runs before video.delete(), and the outer except at line 609 only logs a 500 if video.delete() then fails
- **Fix:** `delete the DB row first inside transaction.atomic(), remove the file only after commit`
- **Consequence:** video.delete() failing after the file is already removed leaves a DB record pointing at a nonexistent file

**4. `video/models.py:360-364`**
- **Problem:** hasattr(self.patient, 'dob_tob') triggers the FK descriptor, which raises Patient.DoesNotExist (not AttributeError) when patient is unassigned/dangling
- **Fix:** `use self.patient_id and a defensive Patient.objects.get(pk=...) like clean() already does (see comment at models.py:196-197)`
- **Consequence:** unhandled RelatedObjectDoesNotExist crashes age_on_recording and any admin page rendering it

**5. `video/admin.py:120-132`**
- **Problem:** file_info_display calls obj.file_size_display(), but file_size_display is a VideoAdmin method, not defined on the Video model (only file_size_mb exists)
- **Fix:** `use obj.file_size_mb (with a unit suffix) instead of obj.file_size_display()`
- **Consequence:** AttributeError crashes the Django admin change page for any Video with a file attached

**6. `video/admin.py:26-32`**
- **Problem:** search_fields references patient__name_baby and patient__name_mother, which are not real field names (actual fields are baby_name/mother_name)
- **Fix:** `fix to patient__baby_name, patient__mother_name`
- **Consequence:** FieldError ('Cannot resolve keyword name_baby') crashes any search performed in the Video admin

**7. `video/forms.py:132-154`**
- **Problem:** the ValidationError raised for a mismatched MIME type (line 137-140) is inside the try block covered by the following except Exception clause
- **Fix:** `add 'except ValidationError: raise' before the generic except, or move the raise outside the try`
- **Consequence:** the specific 'invalid file type detected' message is always replaced by the generic 'unable to validate' message, hiding the real reason from users

**8. `video/forms.py:147-149`**
- **Problem:** python-magic ImportError is caught and the upload proceeds without MIME validation
- **Fix:** `reject the upload (fail closed) when the MIME-check dependency is unavailable instead of silently continuing`
- **Consequence:** a disguised non-video file can be uploaded if libmagic/python-magic is missing, contradicting CLAUDE.md's documented MIME-checking guarantee

**9. `video/models.py:216-296`**
- **Problem:** save() only calls self.clean(), never self.full_clean()/clean_fields(), so field validators (validate_video_file, validate_recording_date, title RegexValidator, MaxValueValidator on duration_seconds) never run
- **Fix:** `call self.full_clean() (or explicit clean_fields()) inside save()`
- **Consequence:** any programmatic Video.save() outside VideoForm (management commands, scripts, admin bulk paths) can persist invalid titles, dates, or durations unchecked

**10. `video/urls.py:14-15 and video/views.py:470-499`**
- **Problem:** video_delete_confirm is fully implemented with its own permission logic but its URL is commented out/deprecated
- **Fix:** `remove the dead view entirely rather than leaving duplicate authorization logic live in source`
- **Consequence:** stale, unmaintained access-control logic can be silently re-registered or copy-pasted, reintroducing an inconsistent permission path

**11. `video/forms.py:82-85 (upload_to callback at ndas/custom_codes/validators.py:576)`**
- **Problem:** the form sanitizes the filename with sanitization.sanitize_filename (whitelist regex, max_length=255), then upload_to re-sanitizes with validators.sanitize_filename (blacklist regex, max_length=100)
- **Fix:** `use a single shared sanitize_filename implementation for both the form clean and the upload_to path`
- **Consequence:** filenames are silently re-truncated/altered a second time at storage time in ways the user never sees, increasing collision risk

**12. `video/views.py:164-234 (video_edit)`**
- **Problem:** uploading a replacement video_file on edit never deletes the previously stored file before/after saving the new one
- **Fix:** `capture the old video.video_file.name before form.save(), delete it from storage once the new file save succeeds`
- **Consequence:** every video edit that replaces the file leaves the old (up to 2GB) file permanently orphaned on disk

**13. `video/views.py:322-331, 381-386, 436-441`**
- **Problem:** queryset.count() is called explicitly for total_count, then Paginator(queryset, 25) performs its own independent .count() internally
- **Fix:** `reuse paginator.count for total_count instead of calling queryset.count() separately`
- **Consequence:** every video-list page load issues two separate COUNT(*) queries instead of one, doubling that cost under load

**14. `video/forms.py:55,98,103,120-130`**
- **Problem:** the widget accept attribute, MIME allow-list, and error message all claim WMV is a supported format, but the default ALLOWED_FILE_EXTENSIONS fallback (line 98) omits '.wmv', and CLAUDE.md's table doesn't list wmv either
- **Fix:** `align the extension whitelist, MIME list, and user-facing messages so WMV support is either fully present or fully removed`
- **Consequence:** uploading a .wmv file is rejected at the extension check with a message that simultaneously claims WMV is allowed, confusing users

### Edge-case hunter (10)

**1. `video/views.py:128-132`**
- **Unhandled path:** video.is_new_file() is called but the method was deliberately removed from the Video model (per models.py:371-374 comment)
- **Guard:** `is_new_file = not GMAssessment.objects.filter(video_file=video).exists()`
- **Consequence:** the call always raises AttributeError and falls into the except branch, so is_new_file is always True regardless of actual state

**2. `video/models.py:300-303`**
- **Unhandled path:** self.video_file.path never raises AttributeError for a wrapped UploadedFile, so the temporary_file_path() branch is never reached
- **Guard:** `check the underlying file type or _committed state before choosing between path and temporary_file_path()`
- **Consequence:** the correct-path branch for genuinely temp-file-backed large uploads is dead code, extraction always uses the wrong path

**3. `video/models.py:217-224`**
- **Unhandled path:** self.patient_id is None (unset) when save() is called
- **Guard:** `raise ValidationError({'patient': _('Patient is required.')}) when not self.patient_id`
- **Consequence:** falls through to super().save() and surfaces as a raw NOT NULL IntegrityError instead of a handled ValidationError

**4. `video/models.py:290-294`**
- **Unhandled path:** db_engine does not contain 'postgresql' (SQLite, MySQL)
- **Guard:** `extend select_for_update locking to other backends that support it (e.g. MySQL/InnoDB)`
- **Consequence:** concurrent updates to the same video row on non-Postgres backends race and can overwrite each other's metadata

**5. `video/models.py:312-316`**
- **Unhandled path:** self.video_file.chunks() raises partway through the write loop, before the try/finally block below it is entered
- **Guard:** `wrap the NamedTemporaryFile creation and chunk-write loop in the same try/finally that unlinks file_path`
- **Consequence:** an interrupted chunk write leaves a partial temp file on disk with no cleanup path

**6. `video/models.py:236-282`**
- **Unhandled path:** extract_video_metadata (custom_methods.py) internally catches all its own exceptions and only ever returns a dict or None, so it never raises
- **Guard:** `n/a — the except IOError/OSError/AttributeError/ValueError/TypeError/Exception blocks around the call are unreachable for this callee`
- **Consequence:** real extraction failures are only ever handled via the metadata-is-None else-branch, not the seemingly more detailed except blocks

**7. `video/management/commands/fix_video_durations.py:48-56`**
- **Unhandled path:** video_file__isnull=False is used to filter out fileless videos, but FileField cannot be NULL (only empty string)
- **Guard:** `use .exclude(video_file='') instead of video_file__isnull=False`
- **Consequence:** the reported 'Processing N videos' count includes videos with no file, which are only skipped later per-row

**8. `video/management/commands/fix_video_durations.py:116-120`**
- **Unhandled path:** metadata.get('duration_seconds') is falsy when a genuinely zero-duration/corrupt clip returns 0
- **Guard:** `check `'duration_seconds' in metadata and metadata['duration_seconds'] is not None` instead of truthiness`
- **Consequence:** a legitimate zero-duration result is treated identically to a failed extraction and silently never written, even with --force

**9. `video/views.py:246,314-320`**
- **Unhandled path:** bookmarked_filter is any non-empty query-string value, including '0' or 'false'
- **Guard:** `compare against an explicit truthy set, e.g. bookmarked_filter in ('1','true','yes')`
- **Consequence:** a caller passing bookmarked_only=0 to mean 'off' unexpectedly activates the bookmarked-only filter

**10. `video/views.py:46-49,76-78 (also 172-176,196-199)`**
- **Unhandled path:** recording date is before the patient's date of birth, and the deliberate raise ValueError('recording_date_before_dob') is caught by the generic except Exception
- **Guard:** `return/short-circuit immediately after form.add_error instead of raising, so it doesn't hit the generic except`
- **Consequence:** the user sees both the specific validation message and a spurious 'unexpected error occurred' message, and it is logged at ERROR level as if unexpected

---
