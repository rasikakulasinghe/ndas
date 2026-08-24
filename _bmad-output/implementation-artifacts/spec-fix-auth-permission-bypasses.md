---
title: 'Fix auth/permission bypasses (bookmark IDOR, CSRF GET mutation, open redirect, bookmark delete)'
type: 'bugfix'
created: '2026-08-24'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '19ed5310b10da81ac4b9855ec33da80fc6f5fd90'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Four independent access-control bugs from the codebase review's "auth/permission bypasses" group: (1) `bookmark_manager_user` has no check that `request.user` owns the requested `username`, letting any authenticated user view any other user's private bookmark list (IDOR); (2) `notification_mark_read` mutates state (`is_read=True`) on a `@require_GET` endpoint, which Django's CSRF protection never covers, so a third-party page can silently force-mark a victim's own notifications as read; (3) the GRACE-subscription middleware redirects to the raw, unvalidated `HTTP_REFERER` header, an open redirect; (4) `has_delete_permission()` grants *any* staff user delete rights on *any* `Bookmark`, contradicting the documented "staff delete own records" rule — and is redundant besides, since the generic `added_by`-ownership branch above it already covers legitimate same-user deletes.

**Approach:** (1) Add an ownership/superuser guard to `bookmark_manager_user`, returning `HttpResponseForbidden()` for a mismatch, matching the existing pattern already used in `bookmark_view`/`bookmark_delete`. (2) Convert `notification_mark_read` from `@require_GET` to POST-only, update its one template call site from an `<a href>` link to a small POST form (styled to look identical), and update the three existing tests that call it via GET. (3) Validate `HTTP_REFERER` with Django's own `url_has_allowed_host_and_scheme` before redirecting; fall back to `'/'` when it fails. (4) Delete the over-permissive Bookmark-specific branch in `has_delete_permission()` and rely on an explicit `entity.owner == user` check for Bookmark (the model's documented ownership field, already used by `bookmark_manager_user`/`bookmark_delete`).

## Boundaries & Constraints

**Always:** Preserve existing 404-not-403 behavior for `notification_mark_read`'s cross-user case (unchanged — `get_object_or_404` already scopes by `recipient=request.user`). Keep the notification link's post-mark-as-read redirect behavior identical from the user's perspective (click → marked read → navigated to target).

**Ask First:** Nothing expected — each of the four fixes is narrow and precedented by an existing correct pattern elsewhere in the same file.

**Never:** Do not touch the generic `added_by`-based ownership branch in `has_delete_permission()` (correct, used by every other entity type). Do not add institution scoping to `bookmark_manager_user` beyond the ownership check — out of scope per the review finding. Do not change `notification_mark_all_read` (already POST, unaffected).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Bookmark manager, own username | `request.user.username == username` | Bookmark list renders normally | N/A |
| Bookmark manager, other's username | `request.user.username != username`, not superuser | 403 Forbidden | N/A |
| Bookmark manager, superuser | any `username`, `request.user.is_superuser` | Bookmark list renders (unchanged) | N/A |
| Notification mark-read, GET | Third-party page or browser navigates via GET | 405 Method Not Allowed | N/A |
| Notification mark-read, POST, own notification | Valid CSRF token, owner's notification | Marked read, redirected to `notif.link` | N/A |
| Notification mark-read, POST, other's notification | Valid CSRF token, `recipient != request.user` | 404 (unchanged) | N/A |
| GRACE redirect, same-origin referer | `HTTP_REFERER: /patient/` | Redirects to `/patient/` (unchanged) | N/A |
| GRACE redirect, external referer | `HTTP_REFERER: https://evil.example/phish` | Redirects to `/` instead | N/A |
| Bookmark delete, owner | `entity.owner == user`, `user.is_staff` | Delete permitted (unchanged) | N/A |
| Bookmark delete, non-owner staff | `entity.owner != user`, `user.is_staff` | Delete denied (was: permitted — this is the fix) | N/A |

</frozen-after-approval>

## Code Map

- `patients/views.py:1672-1681` (`bookmark_manager_user`) -- add ownership/superuser guard
- `patients/views.py:1536-1537,1566-1567` -- READ-ONLY reference: existing `HttpResponseForbidden()` guard pattern to replicate
- `referral/views.py:548-572` (`notification_mark_read`) -- change decorator to POST-only
- `referral/views.py:575-578` (`notification_mark_all_read`) -- READ-ONLY reference: existing POST+CSRF pattern for a notification action in this file
- `templates/referral/notification_panel.html:8-21` -- convert the mark-read `<a href>` link into a POST form per notification
- `referral/tests/test_notification_panel.py:103-131` (`NotificationMarkReadTest`) -- update 3 tests from `client.get` to `client.post`
- `institution/middleware.py:136-138` (`_check_subscription`, GRACE branch) -- validate referer before redirecting
- `institution/tests/test_middleware.py:75-83` -- READ-ONLY reference: existing GRACE+POST test using a same-origin relative referer; must keep passing unmodified
- `ndas/custom_codes/delete_helpers.py:39-50` (`has_delete_permission`) -- replace the over-permissive Bookmark branch with an owner check
- `patients/models.py:2135-2144` (`Bookmark.owner`) -- READ-ONLY reference: documented ownership field ("User who created this bookmark")

## Tasks & Acceptance

**Execution:**
- [x] `patients/views.py` -- in `bookmark_manager_user`, add `if request.user.username != username and not request.user.is_superuser: return HttpResponseForbidden()` before the query -- closes the bookmark-list IDOR
- [x] `referral/views.py` -- change `notification_mark_read`'s `@require_GET` to `@require_http_methods(["POST"])` -- closes the CSRF-unsafe GET mutation
- [x] `templates/referral/notification_panel.html` -- replace the per-notification `<a href="{% url 'referral:notification-mark-read' notif.pk %}">...</a>` with `<form method="post" action="...">{% csrf_token %}<button type="submit" class="dropdown-item ...">...</button></form>`, styled to preserve the current visual layout -- keeps the click-to-mark-read UX working under POST
- [x] `referral/tests/test_notification_panel.py` -- change the 3 `NotificationMarkReadTest` calls from `client.get(...)` to `client.post(...)` -- keeps tests aligned with the new POST-only contract
- [x] `institution/middleware.py` -- in the GRACE branch, validate `referer` with `django.utils.http.url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}, require_https=request.is_secure())` before redirecting, falling back to `'/'` when invalid -- closes the open redirect
- [x] `ndas/custom_codes/delete_helpers.py` -- replace lines 46-50 (`if user.is_staff: if entity.__class__.__name__ == 'Bookmark': return True`) with `if entity.__class__.__name__ == 'Bookmark' and user.is_staff: return getattr(entity, 'owner', None) == user` -- closes the any-staff-deletes-any-bookmark bug
- [x] `institution/tests/test_middleware.py` -- add a test asserting an external `HTTP_REFERER` (e.g. `https://evil.example/`) during GRACE+POST redirects to `/`, not the external URL
- [x] new test file `patients/tests/test_bookmark_security.py` -- add tests for `bookmark_manager_user`: own username succeeds, other's username is forbidden, superuser succeeds for any username
- [x] new test file `ndas/tests/test_delete_helpers.py` -- add tests for `has_delete_permission`: staff deletes own bookmark (owner match) succeeds, staff deletes another staff's bookmark fails, superuser deletes any bookmark succeeds

**Acceptance Criteria:**
- Given a user with no ownership of a bookmark list, when they GET `/manager/bookmarks/user/<other_username>/`, then they receive 403, not the list
- Given no CSRF token, when a GET request is made to `notification_mark_read`, then it is rejected with 405
- Given an attacker-controlled `Referer` header during a GRACE-period blocked POST, when the middleware redirects, then it never redirects off-site
- Given a staff user who does not own a bookmark, when `has_delete_permission` is checked, then it returns `False`

## Verification

**Commands:**
- `python manage.py test patients.tests.test_bookmark_security referral.tests.test_notification_panel institution.tests.test_middleware ndas.tests.test_delete_helpers` -- expected: all pass

## Suggested Review Order

**Bookmark IDOR (view another user's bookmark list)**

- Core fix: deny cross-user access before the query runs, matching the existing `HttpResponseForbidden()` pattern used by `bookmark_view`/`bookmark_delete`; also logs the attempt for audit trail.
  [`views.py:1674`](../../patients/views.py#L1674)

- Own-username / other's-username / superuser coverage.
  [`test_bookmark_security.py:45`](../../patients/tests/test_bookmark_security.py#L45)
  [`test_bookmark_security.py:53`](../../patients/tests/test_bookmark_security.py#L53)

**CSRF-unsafe GET mutation (notification mark-read)**

- Core fix: state mutation now requires POST, closing the CSRF gap a `@require_GET` endpoint can never have.
  [`views.py:280`](../../referral/views.py#L280)

- Template updated from a plain `<a href>` GET link to a POST form with a CSRF token, styled to look identical.
  [`notification_panel.html:8`](../../templates/referral/notification_panel.html#L8)

- The real security proof: a POST with no CSRF token is rejected (not just a GET is rejected by method).
  [`test_notification_panel.py:163`](../../referral/tests/test_notification_panel.py#L163)

- Method-rejection test, and a template-regression guard so a revert to the old link would be caught.
  [`test_notification_panel.py:152`](../../referral/tests/test_notification_panel.py#L152)
  [`test_notification_panel.py:100`](../../referral/tests/test_notification_panel.py#L100)

**Open redirect (GRACE-period middleware)**

- Core fix: validate the Referer with Django's own `url_has_allowed_host_and_scheme` before redirecting to it.
  [`middleware.py:139`](../../institution/middleware.py#L139)

- External-host and protocol-relative (`//evil.example/...`) bypass coverage — the latter is the classic naive-validation bypass.
  [`test_middleware.py:85`](../../institution/tests/test_middleware.py#L85)
  [`test_middleware.py:96`](../../institution/tests/test_middleware.py#L96)

**Bookmark delete over-permission (any staff → any bookmark)**

- Core fix: Bookmark ownership now checked via the `owner` field *before* the generic `added_by` branch, so a staff user who merely `added_by` a bookmark they don't `owner` isn't granted delete rights by falling through.
  [`delete_helpers.py:47`](../../ndas/custom_codes/delete_helpers.py#L47)

- Regression test for exactly the ordering bug two independent review layers caught: `added_by` ≠ `owner` must still deny.
  [`test_delete_helpers.py:71`](../../ndas/tests/test_delete_helpers.py#L71)
