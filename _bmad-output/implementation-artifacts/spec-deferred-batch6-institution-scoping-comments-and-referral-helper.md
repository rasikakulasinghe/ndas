---
title: 'Deferred-Work Batch 6: Institution-Scoping Comments & Referral Helper Dedup'
type: 'bugfix'
created: '2026-11-13'
status: 'done'
baseline_commit: 'c99822b587f82b4f73b031ae51ce580e2efc241b'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Three verified-still-open `deferred-work.md` entries. (1) ~17 call sites across `video/views.py`, `problemlist/views.py`, `institution/views.py`, and `ndas/custom_codes/custom_methods.py` call `Patient.objects.for_institution(institution)` and deliberately rely on its documented Phase-1 behavior (unfiltered when `institution` is `None`), but carry no inline comment saying so — unlike the handful of sibling call sites (`excel_generator.py:230`, `custom_methods.py`'s `get_user_patient_list` docstring) that already do, leaving each uncommented site looking like an oversight rather than a deliberate choice. (2) `bookmark_edit` (`patients/views.py`) looks up its `Bookmark` with no institution scoping at all, unlike its siblings `bookmark_view`/`bookmark_delete` in the same file, which both guard explicitly — correct (bookmarks are owner-scoped, not institution-scoped) but undocumented. (3) `referral/views.py` repeats `institution = getattr(request, 'institution', None) or getattr(request.user, 'institution', None)` verbatim at 6 call sites (not the 3 originally logged — 3 more views were added since).

**Approach:** Add a one-line comment at every uncommented `for_institution()` call site in the 4 flagged files, confirming the Phase-1-unfiltered reliance is deliberate. Add one comment line to `bookmark_edit` confirming bookmarks are intentionally owner-scoped, not institution-scoped. Extract a `resolve_institution(request)` helper in `referral/views.py` and replace all 6 duplicated call sites. Annotate the three ledger entries as resolved.

## Boundaries & Constraints

**Always:** The comment additions (items 1-2) are documentation-only — no behavior change, no new tests needed for them. `resolve_institution(request)` must return byte-for-byte the same value the inline expression already returns (verified by the existing referral view tests continuing to pass unchanged, plus one new direct unit test on the helper itself).

**Ask First:** None — none of these changes alter access-control behavior.

**Never:** No conversion of any `for_institution()` call site to `for_institution_or_none()` — all ~17 sites were verified to deliberately rely on the unfiltered-when-`None` Phase-1 behavior (not the old ad-hoc `for_institution(x) if x else Model.objects.none()` guard pattern the original ledger entry described finding elsewhere), so converting them would be a real behavior change, not a documentation fix. No change to `get_institution_logo_path`'s "pending" slug fallback (tracked separately in `deferred-work.md`; needs its own product decision). No change to any access-control logic in `referral/views.py` beyond the mechanical extraction.

## I/O & Edge-Case Matrix

<!-- No meaningful I/O scenarios: items 1-2 are comment-only, item 3 is a behavior-preserving extraction verified by existing tests plus one new direct unit test on the helper (see Tasks). -->

</frozen-after-approval>

## Code Map

- `video/views.py:35,254,375,415,419` -- each `Patient.objects.for_institution(...)` call; add a one-line comment above or beside each, e.g. `# institution=None -> unfiltered across all institutions (Phase 1 safe, deliberate)`.
- `problemlist/views.py:40,76,476,499,549` -- same five uncommented call sites, same comment.
- `institution/views.py:681,719` -- same two uncommented call sites (the file's other institution-scoping site at `:550` already has its own comment -- leave it). Same comment.
- `ndas/custom_codes/custom_methods.py:46,61,81,125` -- `get_gma_diagnosis_data`, `get_all_diagnosis_data`, `get_userStats`, `get_admissions_data_barchart`; same comment. (`:625`'s call site already has Phase-1 context via its enclosing function's docstring at `:613` -- leave it.)
- `patients/views.py:1734` `bookmark_edit` -- add one comment line above the `Bookmark.objects...get(id=pk)` lookup, matching `bookmark_view`/`bookmark_delete`'s existing comment style (`:1564-1565`, `:1601-1602`): e.g. `# Bookmarks are owner-scoped, not institution-scoped (see the ownership check below) -- no institution_scope() guard needed here, unlike bookmark_view/bookmark_delete.`
- `referral/views.py:60,186,246,332,407,481` -- the six identical `institution = getattr(request, 'institution', None) or getattr(request.user, 'institution', None)` lines, inside `referral_initiate`, `referral_inbox`, `_thread_panel_response`, `referral_reply`, `referral_close`, `patient_referrals_tab` respectively. Add a module-level `resolve_institution(request)` function near the top of the file (beside `_is_thread_participant`, around `:19-40`) returning that same expression, and replace all 6 sites with `institution = resolve_institution(request)`.
- `referral/tests/` -- add one new test file or a small test class asserting `resolve_institution(request)` returns `request.institution` when set, falls back to `request.user.institution` when `request.institution` is absent/`None`, and returns `None` when neither is set.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- annotate the three entries (summaries starting "The ad hoc `for_institution(x) if x else Model.objects.none()` guard pattern", "bookmark_edit's `Bookmark.objects.get(id=pk)` lookup", "referral/views.py's three institution-scoped call sites") with `RESOLVED by:` lines.

## Tasks & Acceptance

**Execution:**
- [x] `video/views.py`, `problemlist/views.py`, `institution/views.py`, `ndas/custom_codes/custom_methods.py` -- add the Phase-1-deliberate comment at each of the 16 uncommented sites (the spec's planning estimate of 17 included one call site, `institution/views.py:681`, that turned out adjacent to `:719` -- 16 distinct sites total, both already-commented sites correctly left alone).
- [x] `patients/views.py` -- add the owner-scoped comment to `bookmark_edit`.
- [x] `referral/views.py` -- add `resolve_institution(request)`; replace all 6 call sites.
- [x] Add the new `resolve_institution` unit test (`referral/tests/test_resolve_institution.py`, 5 cases).
- [x] Run the existing `referral` test suite unchanged and confirm it still passes -- 71/71 except the 2 pre-existing, already-documented `test_notification_bell` failures (unrelated; confirmed independently).
- [x] `deferred-work.md` -- annotate the three entries as resolved.
- [x] Review hardening (blind-hunter, independently confirmed): added the missed comment at `reports/utils/excel_generator.py:782` (the original ledger entry named 5 files; the initial pass covered only 4); replaced the generic Phase-1 comment at `institution/views.py`'s two sites with an accurate one (`institution_admin_dashboard` already redirects away when `institution is None`, so it can never be `None` at those two call sites -- the generic comment was misleading there); added a short comment at `referral/views.py:167`'s `get_institution_clinicians`, the one `getattr(request, 'institution', None)` site deliberately left outside the new helper (it never falls back to `request.user.institution`, unlike the six converted sites); fixed the new test file's docstring (claimed "three branches," actually covers four); removed two stray leading blank lines from this spec file itself. Appended a new, separate `deferred-work.md` entry for `patients/views.py`'s own ~20 uncommented sites (never part of this entry's original scope, out of size for this batch).

**Acceptance Criteria:**
- Given any of the 17 flagged `for_institution()` call sites, when read by a future developer, then a comment explains the `None`-institution behavior is deliberate, not an oversight.
- Given `bookmark_edit`, when read alongside `bookmark_view`/`bookmark_delete`, then a comment explains why it has no `institution_scope()` guard.
- Given `referral/views.py`'s 6 call sites, when any needs its institution-resolution logic changed in the future, then it is changed in exactly one place (`resolve_institution`).
- Given the full `referral` test suite, when run after the extraction, then every test still passes unchanged.

## Design Notes

The original ledger entry for item 1 described finding the dangerous `for_institution(x) if x else Model.objects.none()` ad-hoc guard pattern at 3 referral call sites and asked whether the same shape existed in these 5 other files. Investigation (this spec's planning) found it does not -- every site in all 5 files already calls `for_institution()` plain, correctly relying on its own documented unfiltered-when-`None` behavior. The actual, narrower gap is purely a missing comment, not a latent bug; this spec fixes that narrower gap rather than performing the conversion the entry's title suggested, since converting would change behavior these call sites don't want changed.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test referral` (with `SECURE_SSL_REDIRECT=False` for the run) -- expected: all pass, including the new `resolve_institution` test.

**Manual checks (if no CLI):**
- Grep each of the 4 files' `for_institution(` call sites and confirm every one now has an adjacent Phase-1-deliberate comment, except the 3 already-commented sites this spec explicitly leaves alone.

## Suggested Review Order

**Referral helper extraction (the one real behavior-preserving change)**

- The extracted helper itself -- byte-for-byte identical to the inline expression it replaces.
  [`referral/views.py:19`](../../referral/views.py#L19)

- The deliberately-excluded 7th site, documented as different semantics, not an oversight.
  [`referral/views.py:167`](../../referral/views.py#L167)

- Direct unit coverage of the helper's branches.
  [`test_resolve_institution.py:17`](../../referral/tests/test_resolve_institution.py#L17)

**Institution-scoping documentation (comment-only, verified per-site for accuracy)**

- A site where `institution` is provably never `None` (an earlier redirect already handled it) -- the generic comment would have been wrong here, so it got a call-site-specific one instead.
  [`institution/views.py:681`](../../institution/views.py#L681)

- A genuinely deliberate Phase-1-unfiltered site, for contrast.
  [`video/views.py:35`](../../video/views.py#L35)

- The one site review caught missing from the original four-file pass.
  [`excel_generator.py:782`](../../reports/utils/excel_generator.py#L782)

- `bookmark_edit`'s owner-vs-institution scoping, documented to match its siblings' existing style.
  [`patients/views.py:1734`](../../patients/views.py#L1734)

**Ledger**

- The corrected "RESOLVED by" note, naming all five audited files and the one call-site exception.
  [`deferred-work.md:302`](deferred-work.md#L302)

- The new entry for `patients/views.py`'s own ~20-site concentration, explicitly out of this batch's scope.
  [`deferred-work.md:347`](deferred-work.md#L347)
