# Adversarial Review Findings: NDAS Medical System

**Date:** 2026-05-16  
**Scope:** Full Django codebase — `patients/`, `users/`, `video/`, `reports/`, `institution/`, `ndas/`  
**Focus:** Major bugs, performance issues, security vulnerabilities (frontend & backend)

---

## 1. IDOR on All Assessment PDF Downloads — No Institution Scoping (`reports/views.py:329–410`)

All five PDF download views (`download_gm_assessment_pdf`, `download_hine_assessment_pdf`, `download_da_assessment_pdf`, `download_cdic_assessment_pdf`, `download_gpa_assessment_pdf`) use `get_object_or_404(GMAssessment, id=assessment_id)` with **zero institution filtering**. Any authenticated user from Institution A can increment `assessment_id` and download another institution's patient assessment PDF. This is a textbook IDOR on a medical document — a direct HIPAA-class data breach vector. The fix is trivial: add `**institution_scope(request)` to every `get_object_or_404` call here. That it's missing from five consecutive endpoints suggests it was never reviewed as a group.

---

## 2. `bookmark_manager_user` Exposes Any User's Bookmarks to Any Logged-In User (`patients/views.py:1674–1682`)

`bookmark_manager_user(request, username)` fetches the target user by username then returns `Bookmark.objects.filter(owner=user)` with no check that `request.user == user` or that the requesting user shares an institution. Any authenticated user can view any other user's full bookmark list — revealing which patients they've flagged as important, which assessments they're tracking, etc. This is a privacy leak requiring a single permission guard.

---

## 3. `userViewByUsername` Leaks Cross-Institution User Profiles (`users/views.py:211–213`)

```python
def userViewByUsername(request, username):
    custom_user = get_object_or_404(CustomUser, username=username)
    return render(request, 'users/user_view.html', {'custom_user': custom_user,})
```

No institution scope. No permission check. Any authenticated user can view any other user's profile — including name, email, mobile number, profile picture, and role — by guessing or enumerating usernames. The nearby `userEdit` view (line 224) at least checks `is_staff or request.user.pk == selected_user.pk`; this view checks nothing at all.

---

## 4. `admin_activity_logs` Exposes Cross-Institution Activity to All Staff (`users/views.py:847–858`)

```python
activities = UserActivityLog.objects.select_related('user').all().order_by('-login_timestamp')
```

`@admin_required` permits any `is_staff` user. Staff at Institution A can view every login, logout, and action from every user at Institution B. Medical audit logs contain sensitive operational patterns. The fix is filtering by `user__institution=_inst` for non-superusers, mirroring the correct pattern already used in `admin_user_list` (line 566–570).

---

## 5. `help_article` View Has No Institution Scoping (`patients/views.py:1319–1320`)

```python
def help_article(request, pk):
    article = get_object_or_404(Help, id=pk)
```

If Help articles are institution-specific (likely, given the institution model), this allows any authenticated user to read any institution's help content. Even if Help articles are considered "public within the app," this still violates the institution isolation contract that every other resource in this codebase observes.

---

## 6. Missing Rate Limiting on Password Change and User Edit (`users/views.py:216, 270`)

`userEdit` (line 216) and `userChangePassword` (line 270) have no `@ratelimit` decorator. The login view has rate limiting at `5/m` and `3/m` (lines 42–43). The password reset view has `3/h` (lines 334–335). But the in-session password change is completely unthrottled. An attacker with a valid session can iterate through password guesses against `userChangePassword` at full network speed, or spam profile updates to corrupt data.

---

## 7. CSP Completely Disabled for Scripts in DEBUG Mode (`ndas/settings.py:294–295`)

```python
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", ...)
```

Both `'unsafe-inline'` and `'unsafe-eval'` are present in DEBUG. The comment at line 287 says "when nonces are present for styles, `'unsafe-inline'` is ignored" — that's for *styles*, not scripts. For scripts, `'unsafe-inline'` completely disables CSP XSS protection. `'unsafe-eval'` additionally allows `eval()`, `setTimeout(string)`, etc. This means any XSS vulnerability in debug deployments (staging environments, dev tunnels exposed to the internet) bypasses the CSP entirely. The production config is correct; the debug config isn't just loose, it's inert.

---

## 8. `institution_scope()` Returns Empty Dict `{}` for Superusers / Missing Institution Context — Silent Data Scope Expansion (`ndas/custom_codes/custom_methods.py:23–29`)

```python
return {field: inst} if inst is not None else {}
```

When `request.institution` is `None` (superuser context or session edge case), `institution_scope()` returns `{}`, and `Model.objects.filter(**{})` returns **all records across all institutions**. This is documented as intentional for superusers, but it creates an invisible footgun: 37 call sites rely on this returning a safe empty dict. If a staff user's institution is accidentally cleared (null FK, middleware failure, session replay), their queries silently become institution-unscoped. There is no guard at the call sites, and no alarm when `{}` is returned for a non-superuser. A middleware guard that logs or raises when a staff user has no institution would catch this class of failure.

---

## 9. Dashboard Makes ~15 Separate Database Queries on Every Page Load With No Caching (`patients/views.py:108–165`)

The dashboard view fires 12+ individual `.count()` queries plus subquery annotations — explicitly noted in the docstring as "~15 queries." These run synchronously on every dashboard load with no caching layer (no `cache.get/set`, no `@cache_page`). For an institution with thousands of patients, this is multiple table scans per request. The comment calls this a "70% reduction from baseline" — meaning the baseline was even worse — but the current state remains a performance regression trigger. A 5-minute cache on these aggregate counts would eliminate the database load on all but the first request per interval.

---

## 10. Assessment PDF Downloads Don't Close File Handles on Error (`reports/views.py:339–410`)

```python
response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
```

`open()` is called without a context manager. If `FileResponse` construction raises (e.g., out of memory, encoding error), the file handle leaks. `FileResponse` does close the file when the response is consumed normally, but exceptions between `open()` and response delivery leave the handle open. Under concurrent load or disk errors, this accumulates open handles until the process hits OS limits. Use `with open(...) as f: return FileResponse(f, ...)` with proper error handling, or pass the path directly to `FileResponse` if the Django version supports it.

---

## 11. `Bookmark.objects.all()` Called Globally for Superuser Stats (`ndas/custom_codes/custom_methods.py:80`)

```python
Bookmark.objects.filter(owner__institution=institution) if institution else Bookmark.objects.all()
```

When `institution` is `None`, every bookmark in the database is loaded to compute per-user statistics. With thousands of bookmarks across all institutions, this is an unbounded memory load in a stats function. Even if this is "superuser only," a deliberate or accidental superuser session on a large database will materialise the entire bookmarks table into Python. Use `Bookmark.objects.values('owner_id').annotate(count=Count('id'))` or an equivalent aggregation instead of loading objects.

---

## 12. `video_edit` and `video_delete` Allow Any Staff User to Modify Any Institution's Videos (`video/views.py:157–165, 472–484`)

```python
video = get_object_or_404(Video, id=video_id, **institution_scope(request))
if not request.user.is_staff and video.added_by != request.user:
    # deny
```

Institution scoping is applied at the `get_object_or_404` level (good), so cross-institution access is blocked. However, the `is_staff` bypass removes the `added_by` ownership check entirely for staff: any staff user *within the same institution* can edit or delete any other user's video regardless of who uploaded it. Given that video assessments are the core clinical record, staff-level lateral access to modify another clinician's uploaded files seems like a business logic defect. The permission model should require either superuser or the original uploader for modification.

---

## 13. `userViewByUsername` and `bookmark_manager_user` Chain Into a Full Enumeration Attack

`bookmark_manager_user` accepts a `username` URL parameter. Combining this with finding #2: an attacker needs only to guess or enumerate usernames (trivial via the public `userViewByUsername` endpoint in finding #3) to then view any user's bookmarks. The two vulnerabilities chain into a complete "who is watching which patient" intelligence leak requiring only a valid login.

---

## 14. Report Download Serves Temp Files Without Verifying Requesting User Owns the Report (`reports/views.py:260–320`)

`get_validated_report_path()` validates the UUID format and confirms the file is within `MEDIA_ROOT/reports/temp/` — good path traversal prevention. But it does **not** verify that the requesting user generated that report. Report UUIDs are randomly generated and unguessable in theory, but they're stored in temp storage for 24 hours. If a UUID leaks (logs, browser history, referrer header), any authenticated user can download that report. A session-keyed mapping from UUID to user (e.g., Django's cache or session store) would close this gap.

---

## 15. `admin_activity_logs` Counts All Records Twice — Double Query on Every Page Load (`users/views.py:849–856`)

```python
activities = UserActivityLog.objects.select_related('user').all().order_by('-login_timestamp')
paginator = Paginator(activities, 100)
...
'total_activities': activities.count(),
```

`Paginator` evaluates the queryset count internally. Then `activities.count()` fires a second `COUNT(*)` on the same unfiltered table. On a large deployment this is two full table scans per admin page load. Use `paginator.count` (already computed by `Paginator`) instead of re-querying.

---

## Summary by Severity

| # | Issue | Severity | Type |
|---|-------|----------|------|
| 1 | IDOR on all 5 assessment PDF downloads | Critical | Security |
| 2 | Bookmark exposure across users | High | Security |
| 3 | Cross-institution user profile leak | High | Security |
| 4 | Activity logs visible across institutions to staff | High | Security |
| 13 | Findings #2 + #3 chain into full enumeration | High | Security |
| 6 | No rate limiting on password change / user edit | High | Security |
| 8 | Silent institution scope expansion on `None` institution | High | Security |
| 14 | Report temp file downloadable by any authenticated user | Medium | Security |
| 12 | Staff can modify any video within same institution | Medium | Security/Logic |
| 7 | CSP inert in DEBUG mode (`unsafe-inline` + `unsafe-eval`) | Medium | Security |
| 5 | `help_article` not institution-scoped | Medium | Security |
| 9 | Dashboard runs ~15 DB queries per load, no cache | Medium | Performance |
| 11 | `Bookmark.objects.all()` materialises full table for superuser | Medium | Performance |
| 15 | Double `COUNT(*)` on activity log page | Low | Performance |
| 10 | File handles not closed on PDF error paths | Low | Reliability |
