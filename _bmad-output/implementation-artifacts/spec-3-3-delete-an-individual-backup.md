---
title: 'Story 3.3: Delete an individual backup'
type: 'feature'
created: '2026-09-29'
status: 'done'
review_loop_iteration: 1
context: []
baseline_commit: '4c14751c2262c4a014fa780986b65c4faf19992f'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An admin who no longer needs a specific backup has no way to remove it -- only automatic, age-based pruning will exist (Story 3.4, and even that is opt-in and system-wide), so an unwanted or mistaken backup sits forever, consuming disk.

**Approach:** A password-verified delete action on each row of Story 3.1's history page, using the project's existing unified delete-confirmation modal and DELETE-endpoint pattern (`patient_delete` is the closest precedent). Scoped exactly like Stories 3.1/3.2: an institutional admin deletes only their own institution's backups, a super admin any. Deletion removes both the `.zip` and the `BackupJob` row, is refused for a job that is not yet finished or still actively guarding a restore, and is a distinct code path from Story 3.4's future automatic sweep.

## Boundaries & Constraints

**Always:**
- **View, scope and method.** New `backup_delete(request, pk)`, URL `backup/history/<int:pk>/delete/`, name `backup:backup-delete`. `@login_required`, `@require_http_methods(["DELETE"])`, `@ratelimit(key='user', rate='5/m', method='DELETE')` + `@ratelimit(key='ip', rate='10/m', method='DELETE')` (matches `patient_delete`'s own rate-limit pair), `@handle_view_errors(...)`. The row must come from `_history_jobs_for(institution, is_superadmin)` (Story 3.1/3.2's exact scoped queryset) via `get_object_or_404`, per the same scope rule as download -- a `pk` outside the viewer's scope or that does not exist is a plain 404.
- **Contract.** Matches `patient_delete`'s exact request/response shape (the project's unified delete pattern): `DELETE` with JSON body `{password}`; `request.user.check_password(password)`; on success `JsonResponse({success: True, message, redirect_url})`; on any refusal `JsonResponse({success: False, error, message}, status=...)` (400/401/403/404 as `patient_delete` uses them, plus 500 for the one genuine-I/O-failure case named below). No new response shape.
- **Deletable statuses only.** Only a `completed` or `failed` job may be deleted -- never `pending`/`running` (a background `run_backup`/`run_restore` process may still be writing that job's archive or reading it as its snapshot; deleting mid-write/mid-read would corrupt or orphan an active process, the same danger AD-9 already names for the automatic sweep). Refused with a clear message, no partial deletion.
- **Job-type scope.** Only `job_type` in (`backup`, `pre_restore_snapshot`) may be deleted through this endpoint. A `restore`-type job -- even `completed`/`failed` -- is refused (same 400 "Cannot delete" style/logging as the status guard above) and shows no delete affordance in `manager.html` either, regardless of status. This protects Story 2.6's restore audit trail, which exists specifically to preserve restore history; pruning restore rows, if ever wanted, is a future story's decision, not this one's.
- **Snapshot-in-use guard.** A `pre_restore_snapshot` row that is still `job.pre_restore_snapshot` for any `BackupJob` currently `pending`/`running` is refused -- deleting the one rollback path for an active restore is never allowed. Checked at delete time (not pre-computed on the list). Once no restore using it is still in flight, the same snapshot becomes deletable like any other row (super admin only, per AD-14's existing visibility rule -- unchanged, already enforced by `_history_jobs_for`).
- **Deletion itself.** Inside one `transaction.atomic()`: delete the `.zip` and its containing job directory (`backup/services.py:get_archive_dir`), then delete the `BackupJob` row. A missing/already-gone archive directory (`FileNotFoundError`) is not an error -- the row is still removed. Any other `OSError` (permission denied, file locked, disk I/O fault) is a genuine failure: it blocks the delete entirely -- nothing is removed, the `BackupJob` row is left intact so the admin can retry or investigate -- and the response is a `JsonResponse({success: False, ...}, status=500)`, logged the same way as any other refusal. Nothing else on disk or in the database is touched; `pre_restore_snapshot`/`restore_upload` FKs pointing at other rows are `SET_NULL`/untouched by Django's own cascade behaviour, not special-cased here.
- **Modal and list integration.** `backup/templates/backup/manager.html` renders `{% load delete_modal_tags %}` + `{% delete_modal job %}` per row (the project's unified pattern -- same as any other entity's manager page), gated on `job.status in ('completed', 'failed') and job.job_type != 'restore'`; a `pending`/`running` row, or any `restore`-type row regardless of status, shows no delete action. `ndas/custom_codes/delete_helpers.py` gains a `BackupJob` case in `get_entity_warning_items`, `get_entity_detail_items` and `get_redirect_url` (additive `elif` branches only, no existing entity type touched); `get_entity_display_name` needs no new case (`BackupJob.__str__` already gives a clean fallback). `delete_modal_tags.py`'s `url_map` gains a `'BackupJob'` entry.
- **Logging.** A successful delete and every refusal (wrong status, snapshot-in-use, bad password, out-of-scope/unknown pk) write one line to `logs/security.log` via the existing `security_logger`, matching Story 3.2's download logging.

**Ask First:** None -- reusing `_history_jobs_for`'s institution scoping instead of the generic `has_delete_permission`/`validate_can_delete` (which model ownership as staff+`added_by`, not institution scope, and don't fit `BackupJob`), and the two safety refusals (not-yet-finished, snapshot-in-use) that AD-15 doesn't state verbatim but AD-9 already establishes the same rationale for, are this spec's own calls, flagged in Design Notes.

**Never:**
- No use of `has_delete_permission`/`validate_can_delete` for `BackupJob` (institution scope, not staff/`added_by`, governs it -- see Design Notes). No new entity-type branch added to those two functions.
- No change to `_history_jobs_for`, Story 3.2's download view, or Story 3.1's other columns.
- No automatic/age-based pruning (Story 3.4) -- this is the manual path only, and must not share code with the future sweep beyond the archive-removal helper it may also use later.
- No soft-delete; the `BackupJob` row is actually removed, matching AD-15's literal wording ("removes... the `BackupJob` row").
- No deletion of a `restore`-type job's history row through this endpoint, regardless of status -- protects Story 2.6's restore audit trail.
- No silently proceeding to delete the `BackupJob` row when archive removal fails for a reason other than "already gone" -- a genuine `OSError` must block the delete, not just be logged.

## I/O & Edge-Case Matrix

| Scenario | Behaviour |
|----------|-----------|
| Institutional admin deletes their own institution's completed backup | `.zip` and row removed; `{success: true}`; one INFO log line |
| Super admin deletes any backup, including a `pre_restore_snapshot` not in use | Removed, same as above |
| Institutional admin attempts another institution's backup | 404 (never offered in their list to begin with) |
| Wrong/incorrect password | `{success: false}`, 401, nothing deleted, one WARNING log line |
| Job is `pending` or `running` | Refused, 400, nothing deleted; no delete affordance shown for it either |
| Job is `job_type=restore` (any status, including completed/failed) | Refused, 400, nothing deleted; no delete affordance shown for it either |
| `pre_restore_snapshot` still backing a `pending`/`running` restore | Refused, 400, nothing deleted |
| Archive `.zip` already missing from disk (previously pruned/moved) | Row still removed; deletion still succeeds (not an error) |
| Archive removal fails for a real reason (permission denied, file locked, disk I/O fault) | Refused, 500, nothing deleted -- row and archive both left as-is |
| Delete request for an unknown or already-deleted pk | 404 |
| Non-admin, or admin with no institution context | Denied, matching the existing gate; one WARNING log line |
| Two delete requests for the same job in quick succession | The second sees 404 once the first has removed the row (no double-delete, no crash) |

</frozen-after-approval>

## Code Map

- `backup/views.py:192` (`_history_jobs_for`) -- read as precedent only, **not reused verbatim** (superseded during implementation): its `job_type` filtering makes a `restore`-type job's pk indistinguishable from an unknown one (both 404), but the frozen "Job-type scope" rule requires a `restore`-type job to get its own 400. The actual scoped lookup is a new `_deletable_jobs_for(institution, is_superadmin)` (same institution-scope rule, no `job_type` filtering) with `job_type`/`status`/`is_superadmin`-for-snapshot guards run explicitly in `backup_delete` afterward -- see the review-loop-iteration-2 Spec Change Log entry for the AD-14 regression this deviation initially introduced, and its fix.
- `backup/services.py:44` (`get_archive_dir`) -- delete this directory (containing the `.zip`) before removing the row. Distinguish `FileNotFoundError` (not an error -- proceed to delete the row) from any other `OSError` (genuine failure -- do NOT delete the row; return `JsonResponse({success: False, error: 'Deletion failed', message: ...}, status=500)` before entering/committing the row deletion). Precedent for a 500 JSON refusal: `reports/views.py:317` (`JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)`).
- `patients/views.py:456` (`patient_delete`) -- the exact contract precedent: decorator stack, `{password}` JSON body, `check_password`, JSON response shape (`success`/`error`/`message`/`redirect_url`), status codes (400/401/403/404).
- `ndas/custom_codes/choice.py` (`BackupJobType`) -- reuse `BACKUP`/`PRE_RESTORE_SNAPSHOT`/`RESTORE` as-is for the new job-type guard (`job.job_type != BackupJobType.RESTORE`).
- `ndas/custom_codes/delete_helpers.py` -- `get_entity_warning_items` (~line 185), `get_entity_detail_items` (~line 255), `get_redirect_url` (~line 143): add one `elif entity_type == 'BackupJob':` branch to each. In `get_entity_detail_items`'s `Scope` sub-branch, also handle `scope_type == 'multi'` by joining `entity.scopes.all()` institution names -- mirror `backup/templates/backup/manager.html:100-103`'s existing `{% elif job.scope_type == 'multi' %}{% for inst in job.scopes.all %}...` pattern exactly (this was missed on the first implementation pass: only `single`/`system` were handled, so a multi-institution backup's delete modal silently showed no Scope line). `get_entity_display_name` (~line 105) needs no change -- its fallback already uses `str(entity)`, and `BackupJob.__str__` (`models.py`) returns `f"BackupJob[{pk}] {job_type}/{status}"`.
- `ndas/templatetags/delete_modal_tags.py:91` (`url_map`) -- add `'BackupJob': f'/backup/history/{entity_id}/delete/'`.
- `templates/src/partials/delete_confirmation_modal.html`, `static/js/delete-confirmation.js` -- read only; the JS's `execute()` sends `DELETE` with `{password}` JSON and expects the `success`/`message`/`redirect_url` shape verbatim -- no changes needed to either file.
- `backup/urls.py` -- add `path('history/<int:pk>/delete/', views.backup_delete, name='backup-delete')`, beside `backup-download`.
- `backup/models.py` (`BackupJob.pre_restore_snapshot`, related_name `restores_using_snapshot`) -- query this reverse relation, filtered to `status__in=(PENDING, RUNNING)`, for the snapshot-in-use guard. **Race-condition fix (patch, from review):** the first implementation checked this *before* entering `transaction.atomic()`, leaving a TOCTOU window where a new restore could attach to this snapshot between the check and the delete. Re-do the `restores_using_snapshot` check *inside* the same `transaction.atomic()` block, immediately before `job.delete()`, so it is atomic with the deletion itself.
- `ndas/custom_codes/choice.py:254` (`BackupJobStatus`) -- reuse `COMPLETED`/`FAILED`/`PENDING`/`RUNNING` as-is.
- Facts (verified): the delete-confirmation JS/modal/tag stack requires no entity-specific JS -- everything entity-specific is server-rendered context or the URL map; `has_delete_permission`/`validate_can_delete` are called only by views (`patient_delete` etc.), never by `delete_modal`'s inclusion tag, so `BackupJob` deletion working correctly does not require touching either function.
- **Other patch fixes carried from the first review round (all trivial, no intent change):**
  - `backup_delete`'s JSON-body parsing must check `isinstance(data, dict)` before calling `data.get('password', ...)` -- a valid-JSON-but-non-dict body (e.g. a bare list or number) must return 400, not raise `AttributeError`.
  - The view's docstring must not claim "no page ever rendered" -- `handle_view_errors` turns a `Ratelimited` exception into a redirect, matching `patient_delete`'s own existing, accepted behavior; reword to acknowledge that rate-limit/unexpected-error handling follows the same precedent as `patient_delete` rather than overclaiming an all-JSON contract.
  - Test: assert the exact `redirect_url` value in the happy-path response (`self.assertEqual(data['redirect_url'], reverse('backup:backup-history'))`), not just that the key is present.
  - Test: assert (`assertContains`/`assertNotContains` on `delete-trigger-btn` or the job's `delete_modal_id`) that a `completed` job's row shows the delete affordance and that `pending`/`running` and `restore`-type rows do not.

## Tasks & Acceptance

**Execution:**
- [x] `backup/views.py` -- `backup_delete` view: admin/institution gate, scoped lookup (404), password check (400/401, `isinstance(data, dict)` guard), status guard (400 for `pending`/`running`), job-type guard (400 for `job_type=restore`, now an allowlist requiring `job_type in (backup, pre_restore_snapshot)` -- see Code Map deviation note), snapshot-in-use guard re-checked atomically immediately before delete (400), a super-admin-only guard for `pre_restore_snapshot` (403 -- review-round-2 patch, see Spec Change Log), archive+row removal distinguishing `FileNotFoundError` (proceed) from other `OSError` (500, row kept), log every outcome.
- [x] `backup/urls.py` -- `backup:backup-delete` route.
- [x] `ndas/custom_codes/delete_helpers.py` -- `BackupJob` case in `get_entity_warning_items`, `get_entity_detail_items` (including the `scope_type == 'multi'` sub-case and the `scope_type == 'single'`-with-null-`scope`-FK fallback), `get_redirect_url`.
- [x] `ndas/templatetags/delete_modal_tags.py` -- `BackupJob` entry in `url_map`.
- [x] `backup/templates/backup/manager.html` -- `{% load delete_modal_tags %}` + `{% delete_modal job %}` per row, gated on a server-computed `job.is_deletable` (`completed`/`failed` AND `job_type != restore`).
- [x] Tests for every matrix row: happy path (institutional admin and super admin, including a `pre_restore_snapshot`, and asserting the exact `redirect_url` value), out-of-scope 404, wrong password, `pending`/`running` refusal, `restore`-type-job refusal, institutional-admin-cannot-delete-snapshot refusal (403), snapshot-in-use refusal (including the race-window fix), missing-archive-on-disk still succeeds, genuine archive-removal `OSError` returns 500 and keeps the row, double-delete race, non-admin/no-institution-context denial, non-dict JSON body 400, manager.html delete-affordance visibility (shown for completed/failed non-restore, hidden for pending/running/restore), both log outcomes. 28 tests total, all passing (confirmed both in isolation and in the full 704-test `backup` app suite).

**Acceptance Criteria:**
- Given an institutional admin, when they delete a backup, then only a backup belonging to their own institution can be deleted.
- Given a super admin, when they delete a backup, then any backup, regardless of institution, can be deleted.
- Given a delete action is confirmed, when it executes, then both the `.zip` on disk and the `BackupJob` row are removed -- distinct from Story 3.4's automatic age-based pruning.
- Given a `restore`-type job or a genuine archive-removal I/O failure, when a delete is attempted, then the `BackupJob` row is never removed.

## Spec Change Log

- **2026-09-30, review-loop iteration 1 (intent_gap loopback).** Two ambiguities inside the frozen intent, independently surfaced by all three review layers on the first implementation pass, were resolved by the human and the frozen block amended accordingly:
  1. *Job-type scope.* The first pass deleted any job_type the shared `_history_jobs_for` queryset returns, including a completed/failed `restore`-type row -- silently erasable audit history that Story 2.6 was built to preserve. **Resolved:** excluded `restore`-type jobs from this endpoint entirely (new "Job-type scope" Always-bullet, Never-bullet, I/O matrix row, and `manager.html` gating clause).
  2. *Archive-removal I/O failures.* The first pass's "first-best-effort" reading caught *any* `OSError` from `shutil.rmtree` (not just a missing archive) and still deleted the `BackupJob` row regardless -- risking a silently orphaned, unrecoverable `.zip` while the UI reported success. **Resolved:** only `FileNotFoundError` is treated as success-as-usual; any other `OSError` now blocks the delete, returns a 500 JSON refusal, and keeps the row (amended "Deletion itself" Always-bullet, new Never-bullet, new I/O matrix row, Contract bullet's status-code list).
  - **KEEP (positive preservation -- worked well on the first pass, must survive re-derivation):** the overall view/URL/contract shape byte-matching `patient_delete` (decorators, `{password}` JSON body, response shape, status codes); reusing `_history_jobs_for` verbatim for scoping; the password-check-then-status-guard-then-snapshot-guard-then-delete ordering; the additive `elif`-only integration into `delete_helpers.py`/`delete_modal_tags.py`; the 21-test suite's breadth and structure (happy path/refusal/rate-limit split across classes); running the *full* `backup` app test suite (not just the new module) as final verification, which caught zero regressions across 697 tests.
  - Six smaller **patch** findings from the same review round (TOCTOU race on the snapshot-in-use guard, missing `scope_type == 'multi'` handling in `get_entity_detail_items`, non-dict JSON body crashing instead of 400, an overclaiming docstring line, and two test-coverage gaps around `redirect_url`'s exact value and `manager.html`'s delete-affordance visibility) are folded into this same re-derivation; see Code Map and Tasks above.

- **2026-10-01, review-loop iteration 2 (patch-only, no further loopback).** Re-derived code reviewed again by all three layers. One **critical patch** finding, confirmed independently by two review layers plus a direct code read: the re-derivation's `_deletable_jobs_for` helper (written to let a `restore`-type job get its own 400 instead of `_history_jobs_for`'s blanket 404 -- see Code Map) dropped `_history_jobs_for`'s exclusion of `pre_restore_snapshot` for non-superadmins entirely, along with the `restore` exclusion -- so an institutional admin could delete a `pre_restore_snapshot` scoped to their own institution, contradicting AD-14 and this spec's own "Snapshot-in-use guard" bullet ("super admin only... already enforced by `_history_jobs_for`" -- no longer true once that reuse stopped). **Fixed:** the job-type guard in `backup_delete` is now an allowlist (`job_type in (backup, pre_restore_snapshot)`, not `!= restore`), plus a new explicit `is_superadmin` guard (403) for `pre_restore_snapshot`. New regression test: `test_institutional_admin_cannot_delete_snapshot_scoped_to_own_institution`. Four smaller **patch** fixes bundled in the same pass: `get_entity_detail_items`'s `Scope` fallback for a null `scope` FK (matches `manager.html`'s em-dash), passing `modal_id` explicitly to `{% delete_modal %}` instead of relying on two independent recomputations agreeing, softening the TOCTOU docstring claim from "closes" to "narrows" the race window, and moving a local import to module level after confirming (empirically, via `manage.py check`) it caused no circular import. Full `backup` suite re-verified clean (704 tests) after these fixes, independently, twice (once by the implementer, once by this session).

## Design Notes

- **Scope via `_history_jobs_for`, not `has_delete_permission`.** The generic helper models ownership as `user.is_staff and entity.added_by == user` (or `is_superuser`); `BackupJob` has no meaningful per-record "owner" in that sense -- AD-15's actual rule ("institutional admin: only their own institution's backups") is the same institution-scope rule Stories 3.1/3.2 already implement. Reusing `_history_jobs_for` keeps one scoping definition instead of two divergent ones. Approved at the first checkpoint (2026-09-29).
- **Two safety refusals AD-15 doesn't spell out, borrowed from AD-9's stated rationale.** AD-15's own text is thin ("removes both the `.zip`... and the `BackupJob` row"). AD-9 (automatic pruning) explicitly excludes a `pending`/`running` source job and any `pre_restore_snapshot` still backing an in-flight restore, for reasons (corrupting an active write/read, destroying the one rollback path mid-restore) that apply just as much to a manual delete. Extending the same two exclusions to Story 3.3 prevents a super admin from being able to do by hand exactly what AD-9 forbids automatically. Approved at the first checkpoint (2026-09-29).
- **Missing archive on disk is not a delete failure; any other I/O failure is.** A backup whose `.zip` already vanished (e.g. moved/pruned outside the app) should still have its now-orphaned `BackupJob` row removable -- otherwise a user could never clear a broken history entry. But a *genuine* removal failure (permission denied, file locked, disk fault) must not be treated the same way, or the row disappears while the archive silently survives with nothing left to account for it. Resolved by the human in review-loop iteration 1 (see Spec Change Log).
- **`restore`-type jobs are out of scope for this endpoint.** Resolved by the human in review-loop iteration 1 (see Spec Change Log) -- protects Story 2.6's restore audit trail from being erasable through a feature whose stated purpose ("delete a backup") was never meant to cover restore operations.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test backup --noinput` (background; one run at a time) -- 704 tests, OK (confirmed independently twice after the review-loop-iteration-2 patches).
- `venv/Scripts/python.exe manage.py test backup.tests.test_delete_views --noinput` -- 28 tests, OK.
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run backup` -- no changes (no model changes in this story).

## Suggested Review Order

**Entry point & access control**

- Start here -- the whole delete contract: decorators, scoping, and every guard in sequence.
  [`views.py:724`](../../backup/views.py#L724)

- Admin/institution gate -- who may even attempt a delete, before any row is looked up.
  [`views.py:737`](../../backup/views.py#L737)

**Scoping & the AD-14 fix (review-loop iteration 2)**

- New scoped lookup, deliberately not `_history_jobs_for` -- read the docstring for why.
  [`views.py:671`](../../backup/views.py#L671)

- Job-type allowlist, not a denylist -- only `backup`/`pre_restore_snapshot` reach this point.
  [`views.py:835`](../../backup/views.py#L835)

- The fix itself: a non-superadmin can never delete a `pre_restore_snapshot`, in-use or not.
  [`views.py:849`](../../backup/views.py#L849)

**Safety guards**

- Status guard -- never a `pending`/`running` job (background process may still touch its archive).
  [`views.py:826`](../../backup/views.py#L826)

- Snapshot-in-use guard, re-checked atomically immediately before delete to narrow the TOCTOU window.
  [`views.py:870`](../../backup/views.py#L870)

**Archive removal & error handling**

- Missing archive succeeds silently; any other `OSError` blocks the delete and returns 500.
  [`views.py:883`](../../backup/views.py#L883)

**Wiring**

- New route, sitting beside `backup-download`.
  [`urls.py:16`](../../backup/urls.py#L16)

**UI integration**

- Delete affordance gated on a server-computed flag, not template boolean logic.
  [`views.py:536`](../../backup/views.py#L536)

- Button + modal, explicit `modal_id` passed through instead of relying on double computation.
  [`manager.html:123`](../../backup/templates/backup/manager.html#L123)

- `BackupJob` case added to the shared delete-modal detail/warning/redirect helpers (additive only).
  [`delete_helpers.py:254`](../../ndas/custom_codes/delete_helpers.py#L254)

- `BackupJob` entry in the shared delete-modal URL map.
  [`delete_modal_tags.py:104`](../../ndas/templatetags/delete_modal_tags.py#L104)

**Tests**

- The regression test for the AD-14 fix -- read this one closely.
  [`test_delete_views.py:339`](../../backup/tests/test_delete_views.py#L339)

- Restore-type-job refusal and the TOCTOU race-window test -- the two trickiest matrix rows.
  [`test_delete_views.py:252`](../../backup/tests/test_delete_views.py#L252)

- Full test suite, covering every remaining I/O-matrix row and the manager.html visibility gating.
  [`test_delete_views.py:47`](../../backup/tests/test_delete_views.py#L47)
