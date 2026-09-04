# NDAS AI Agent Instructions

Workflow guidance for AI agents. For project patterns and architecture, see `CLAUDE.md`.

**Last Updated:** 2025-12-25

<!-- bmad:context -->
<!-- Verified 2026-09-04 against 1b13db6. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## NDAS

Django medical system for patient records, video-based neurodevelopmental assessments, and evaluation workflows. Solo-maintained, single `main` branch, no CI. Architecture and patterns: `CLAUDE.md`. Generated reference docs (data models, API contracts, source tree, dev guide): `docs/index.md`.

## Policy

- Never commit `.env` — real config (including `SECRET_KEY`) was committed here before; it's gitignored now, don't re-add it.
- Never set `MULTI_INSTITUTION_ENABLED=True` in production until `institution/tests/test_isolation.py` passes on staging — any cross-institution data leak is a blocking defect.

## Where things are

- Proposals / architecture changes: use the BMAD skills `bmad-spec` and `bmad-architecture` — OpenSpec was removed from this repo (old pointers are dead).
- Security test suites `video/tests/test_security.py`, `users/tests/test_security.py`, `reports/tests/test_security.py` cover ownership/isolation/rate-limit checks — run them when touching views or permissions in those apps.
- Known-but-not-yet-fixed issues (scoped, evidenced, deliberately deferred): `_bmad-output/implementation-artifacts/deferred-work.md` — check it before assuming a rough edge you hit is unknown.

## Running and verifying

- No `requirements.txt` is tracked (deleted, never restored) — reconstruct from the working `venv` (`pip freeze`) rather than `pip install -r requirements.txt`.
- `python run_qa_tests.py` is a separate Playwright E2E smoke suite (needs `python manage.py runserver` already running, logs in as `testadmin`) — distinct from `python manage.py test`.
- Test fixtures: `UserActivityMiddleware` doesn't run under the test client — set `added_by=user` manually in `Model.objects.create()` inside `setUp()`. Authenticate with `force_login(user)`, not `client.login()`. Test classes that render full templates need `@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})` or they fail on a staticfiles manifest error.

## Conventions that differ from defaults

- Historical/audit FK fields (e.g. `InstitutionSwitchLog.previous_institution_id`) use `IntegerField`, not `ForeignKey(..., on_delete=SET_NULL)` — so the historical ID survives the related record's deletion.
- Atomic cache ops use `cache.add(key, value, timeout)`, never `cache.get()` + `cache.set()` — the latter race-conditions.
- Bookmark app/model resolution for a `bookmark_type` goes through the shared `Bookmark.MODEL_MAPPING` (`patients/models.py`) — never hardcode an app label per type; a wrong label here silently broke Video-bookmark validation twice via a swallowed exception.
- A superuser-only `ModelForm` field (e.g. `institution` on `AdminUserCreationForm`/`AdminUserEditForm`/`UserSearchForm`) is hidden by `del form.fields['field']` in the view on every GET-render and POST-validate branch — not `required=False` or template-only hiding, which leaves it POST-able by a non-superuser. Pattern: `users/views.py` admin_user_add/admin_user_edit/admin_user_list.
- Attachment uploads verify real (content-sniffed) MIME type against extension, not extension alone — `ndas/custom_codes/validators.py::validate_file_content_matches_extension`, mirroring the existing video-upload check. A new attachment extension needs an entry in `ATTACHMENT_ALLOWED_MIMES` too, or the check silently no-ops for it.

## Known pitfalls

- Inline `<script>` tags need `nonce="{{ request.csp_nonce }}"` in DEBUG too, not just production — `unsafe-inline`/`unsafe-eval` are removed from `CSP_SCRIPT_SRC` in both; a script without a nonce silently fails everywhere.
- `institution_scope()` (`ndas/custom_codes/custom_methods.py`) raises `PermissionDenied` when a non-superuser has `institution_id` set but `request.institution` is `None` — that signals a middleware misconfiguration; never swallow it.
- `protected_media_view` (`institution/views.py`) is routed through Django in *both* DEBUG and production now — Nginx must `proxy_pass /media/` to it, never `alias` straight to disk; aliasing bypasses the institution-isolation check entirely (see `DEPLOYMENT.md` §2.6). This was a real gap until 2026-09.
- Staff may only edit/delete videos they personally uploaded (`video.added_by == request.user`); a bare `is_staff` bypass was a real security defect here once — gate unrestricted access on `is_superuser`, not `is_staff`.
- `InstitutionScopedManager.for_institution(None)` returns ALL records — intentional Phase 1-compatibility fallback, not a bug. Don't "fix" it.
- Any new report-download endpoint must verify the `report_owner_{file_id}_{session_key}` cache key set by `report_builder` before serving the file — a UUID/file_id alone is not access control.
- Any view that changes a user's own password must call `update_session_auth_hash(request, user)` right after `form.save()` — Django invalidates the session's auth hash on password change, so skipping this silently logs the user out on their very next request (`userChangePassword` shipped without it once).
- Superuser bypass checks use `request.user.is_superuser` everywhere except `institution/middleware.py`'s context resolution, which keys off `user_type == UserType.SUPERADMIN` instead — nothing enforces these two stay in sync on an account, so don't assume one implies the other.

<!-- /bmad:context -->
