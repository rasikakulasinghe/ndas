---
title: 'Deferred-Work Batch 3: Sanitization Investigation + Logging Hardening'
type: 'bugfix'
created: '2026-11-12'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Three confirmed-still-open `deferred-work.md` entries: a claimed HTML-comment obfuscation bypass of `sanitize_text_input()`'s protocol-strip; `logs/security.log`'s handler being silently skipped whenever `DEBUG=True` (dev); and backup-download log lines misleadingly reusing the restore-scoped `django.security.restore` logger.

**Approach:** Independently verify the sanitization claim empirically before touching anything (it turned out not to be a live bypass — see Spec Change Log); remove the `security_file` handler's `require_debug_false` filter and add a `console` handler for `django.security`/`users.middleware` when `DEBUG=True`; give backup downloads their own `django.security.backup` child logger.

</frozen-after-approval>

## Spec Change Log

- **Sanitization entry investigated, not fixed**: empirically tested `sanitize_text_input()` against the HTML-comment obfuscation payload the ledger entry described (and several variants). None produce a live "javascript:"-prefixed string: HTML comments have no special meaning inside a URL scheme or plain text to any browser's URL parser (unlike the real tab/newline-stripping quirk the existing regex already defends against), so the payload either passes through inert or gets swallowed entirely by the generic tag-strip regex's over-matching. The original finding's premise doesn't hold. Left open on the ledger as "investigated, not exploitable" rather than marked resolved or silently dropped — no code change, since widening the regex to treat arbitrary non-alphanumeric noise as skippable would reintroduce the exact false-positive risk the entry itself warned about, for no real security benefit.
- **Caught a test-runner quirk while writing `ndas/tests/test_logging_settings.py`**: Django's `manage.py test` forces `settings.DEBUG = False` for the whole run regardless of the real environment value (unrelated to this change). The test originally compared against `settings.DEBUG` and failed under `manage.py test` even though the LOGGING dict was built correctly; fixed by re-reading the real value via `decouple.config('DEBUG', ...)` directly, exactly as `ndas/settings.py` itself does.

## Suggested Review Order

1. [ndas/settings.py](../../ndas/settings.py) — LOGGING dict: `security_file`'s filter removed, shared `_SECURITY_LOG_HANDLERS`.
2. [backup/views.py](../../backup/views.py) — `download_security_logger` + its 5 call sites, comments on the restore/backup split.
3. [ndas/tests/test_logging_settings.py](../../ndas/tests/test_logging_settings.py) — new tests pinning the LOGGING dict.
4. [backup/tests/test_download_views.py](../../backup/tests/test_download_views.py) — `SECURITY_LOGGER` constant updated.
5. [_bmad-output/implementation-artifacts/deferred-work.md](deferred-work.md) — 2 entries resolved, 1 investigated-not-exploitable, 2 new defer entries appended.

