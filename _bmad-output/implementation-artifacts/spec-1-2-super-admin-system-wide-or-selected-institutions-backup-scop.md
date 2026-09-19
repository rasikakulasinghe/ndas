---
title: 'Story 1.2: Super admin — system-wide or selected-institutions backup scope'
type: 'feature'
created: '2026-09-18'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'a48085bb20701bffb912c256add64c0360a7aa02'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 1.1 only lets an admin (or a superadmin acting inside one institution's context) back up that single institution — a super admin has no way to back up an explicit multi-institution subset or the whole system in one job.

**Approach:** Add a `scope_type` (single/multi/system) field plus a `scopes` M2M to `BackupJob`; extend `backup_create`'s trigger form so a SUPERADMIN can pick a mode and (for multi) the institution set; refactor the export/estimate functions in `backup/services.py` to branch on the three institution-scoping shapes already decided in epic-1-context.md (`for_institution` single / `filter(__in=)` multi / `all_institutions()` system) instead of assuming one institution.

## Boundaries & Constraints

**Always:**
- Reuse exactly the 3-way scoping shapes from epic-1-context.md: single → `for_institution(inst)`; explicit multi-institution subset → `.filter(institution__in=selected)` (never routed through `for_institution`); system-wide → `all_institutions()`. Never call `for_institution(None)` as a stand-in for system-wide (the known unfiltered-fallback footgun).
- Only `UserType.SUPERADMIN` may choose `multi`/`system`; an `ADMIN` (or a superadmin with no elevated selection made) keeps Story 1.1's exact single-own-institution behavior byte-for-byte — all 32 existing `backup` tests keep passing unmodified.
- Multi/system institution selection lists only `Institution.objects.filter(is_active=True).order_by('name')` (matches `users/forms.py:426-428`'s existing convention).
- The atomic concurrency lock (from 1.1, `backup/views.py:113-124`) must extend to overlap-detection: a new job is refused if its resolved institution set intersects ANY existing `pending`/`running` job's resolved set. `system` intersects everything; two `multi` jobs intersect iff their institution sets share a member; `single` is the existing 1-institution case.
- `BackupJob.scope` (existing single FK) is used only when `scope_type='single'`; `scopes` (new M2M) only when `'multi'`; both empty when `'system'`. Existing 1.1 rows get `scope_type='single'` via migration default.
- A non-superadmin's POST body is never trusted for `scope_type`/institution selection — server-side, coerce to `single` + the requester's own institution regardless of what was submitted.
- The GET "recent jobs" listing (`backup/views.py:59`, currently `BackupJob.objects.filter(scope=institution)`) must also surface `multi`/`system` jobs a superadmin triggered — it cannot key off `scope` alone once `scope` is legitimately `None` for non-single jobs.

**Ask First:** None — the 3-way scoping shapes and the overlap-lock semantics above are fully decided from epic-1-context.md; no further architectural decisions remain.

**Never:**
- No manifest/checksum work (Story 1.3), no date-range filtering (Story 1.4), no progress-polling/notification UI changes (Story 1.5).
- No change to which 13 models are exported, their order, or the `referral`/`Bookmark` exclusions already fixed in Story 1.1.
- No Celery or other task-queue infrastructure (still a detached `subprocess.Popen`, unchanged from 1.1).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Superadmin: system-wide | POST `scope_type=system` | `BackupJob(scope_type=system, scope=None, scopes=[])`; export covers every institution | N/A |
| Superadmin: multi-select | POST `scope_type=multi`, institutions=[A,B] | `BackupJob.scopes={A,B}`; export scoped to A+B only, no leakage to any other institution | N/A |
| Superadmin: multi-select, empty | POST `scope_type=multi`, institutions=[] | Refused before any row is created | Validation error shown; no `BackupJob` row |
| Non-superadmin sends elevated scope | ADMIN POSTs `scope_type=system` (crafted) | Coerced server-side to `single` + requester's own institution (mirrors 1.1's UX, no 403) | N/A |
| Overlapping: system-wide already pending | Any new trigger while a `system` job is `pending`/`running` | Refused — system-wide overlaps every institution | Clear refusal message, no new row |
| Overlapping: multi vs multi | Pending job for {A,B}; new trigger for {B,C} | Refused (B overlaps) | Same as 1.1's existing refusal message |
| Non-overlapping: multi vs multi | Pending job for {A,B}; new trigger for {C,D} | Both proceed independently | N/A |

</frozen-after-approval>

## Code Map

- `institution/managers.py:22-30,32-37` -- `InstitutionScopedManager.for_institution(inst)` (filters `institution=inst`; **never** call with `None`) and `all_institutions()` (unfiltered, superadmin-only per docstring).
- `institution/models.py:24` -- `Institution.is_active` (BooleanField, db_index) drives selectable-institution filtering; `Meta.ordering = ['name']` (line 53).
- `users/forms.py:426-428` (also 481-483, 555-557) -- existing single-select convention: `forms.ModelChoiceField(required=False, queryset=Institution.objects.filter(is_active=True).order_by('name'))`. No multi-select institution precedent exists anywhere in the codebase; `patients/forms.py:307,652`'s `CheckboxSelectMultiple` is for unrelated medical-checklist fields only — same widget class is fine to reuse for institutions, but there's no institution-specific example to copy.
- `backup/models.py:65-73` -- `BackupJob.scope` (`ForeignKey`, `SET_NULL`, `null=True`) — docstring already says "Null = system-wide (Epic 1.2)"; add `scope_type` + `scopes` alongside it (index at line 79-81 covers `scope`+`status` only — extend/add as needed for the new overlap-lock query).
- `ndas/custom_codes/choice.py:242-254` -- `BackupJobType`/`BackupJobStatus` `TextChoices` pattern to mirror for the new `BackupJobScopeType`.
- `backup/services.py:47-92` (`_model_export_plan`), `:102-118` (`estimate_export_size_bytes`), `:121-130` (`has_sufficient_disk_space`), `:162-229` (`create_export`, reads `job.scope` at line 178 and raises on `None`) -- all four currently take/assume a single `institution`; each needs the same 3-shape branch.
- `backup/views.py:31-33` (`_get_admin_institution`), `:48-56` (permission + institution-context gate), `:113-124` (atomic concurrency lock, currently `filter(scope=institution, ...)`) -- extend the gate to branch on `SUPERADMIN` + submitted scope, and the lock query to overlap-check across `scope`/`scopes`/system-wide.
- `backup/templates/backup/create.html` -- Story 1.1's minimal trigger form; add the scope-mode selector, rendered only for `SUPERADMIN`.
- `ndas/settings.py:190` -- `MULTI_INSTITUTION_ENABLED` flag (read in `institution/middleware.py:42`, `users/views.py:696`) — not itself gating this story's UI, but confirms the project's existing single-vs-multi-institution deployment toggle exists; multi/system scope selection should still render regardless of this flag (it only affects request-time institution *context* resolution, not what a superadmin can explicitly choose here).

## Tasks & Acceptance

**Execution:**
- [x] `ndas/custom_codes/choice.py` -- add `BackupJobScopeType` (`single`/`multi`/`system`) `TextChoices`, mirroring `BackupJobType` -- needed before the model field exists
- [x] `backup/models.py` -- add `BackupJob.scope_type` (default `single`) and `scopes = ManyToManyField("institution.Institution", blank=True, related_name="backup_jobs_multi")` -- the new scope representation
- [x] `backup/migrations/0003_...` -- generated via `makemigrations backup`, defaulting existing rows to `scope_type='single'`
- [x] `backup/forms.py` (new) -- `BackupScopeForm`: mode field (single/multi/system, superadmin-only choices) + `ModelMultipleChoiceField(queryset=Institution.objects.filter(is_active=True).order_by('name'), required=False)` for the multi case
- [x] `backup/services.py` -- refactor `_model_export_plan`, `estimate_export_size_bytes`, `has_sufficient_disk_space`, `create_export` to accept a resolved scope (institutions list + system-wide flag) and branch using the three shapes -- must reproduce 1.1's exact single-institution queries unchanged
- [x] `backup/views.py` -- extend `backup_create`: resolve/validate submitted scope (superadmin-only for multi/system; coerce otherwise), extend the atomic lock to overlap-check, pass resolved scope into `BackupJob.objects.create(...)`, and fix the GET "recent jobs" query so it also finds the requesting superadmin's own `multi`/`system` jobs (not just `scope=institution`)
- [x] `backup/templates/backup/create.html` -- add scope-mode UI, superadmin-only
- [x] `backup/tests/test_services.py` -- new cases: system-wide export includes all institutions; multi-institution export includes only the selected set, no leakage
- [x] `backup/tests/test_views.py` -- new cases: superadmin system/multi triggers; non-superadmin scope-elevation attempt coerced; overlap-lock scenarios (system vs anything, multi vs multi overlapping/non-overlapping); empty multi-selection refused

**Acceptance Criteria:**
- Given a superadmin selects system-wide scope, when the job completes, then the archive's `db_export.json` contains records from every institution, not just one.
- Given a superadmin selects an explicit 2-institution subset, when the job completes, then only those two institutions' records appear — no leakage to a third institution's data.
- Given an ADMIN (non-superadmin) submits a crafted request with `scope_type=system`, when the trigger view processes it, then the job is created as `single` scoped to the requester's own institution, not system-wide.
- Given a system-wide job is `pending`, when any other trigger (any scope) is attempted, then it is refused with no new row created.
- Given two multi-institution jobs with disjoint institution sets, when both are triggered, then both proceed independently.

## Spec Change Log

_None yet — pre-review._

## Design Notes

Illustrative shape for the services.py refactor (not literal code):

```python
def _model_export_plan(institutions=None, system_wide=False):
    if system_wide:
        patient_qs = Patient.objects.all_institutions()
        video_qs = Video.objects.all()
    elif len(institutions) == 1:
        patient_qs = Patient.objects.for_institution(institutions[0])
        video_qs = Video.objects.filter(patient__institution=institutions[0])
    else:
        patient_qs = Patient.objects.filter(institution__in=institutions)
        video_qs = Video.objects.filter(patient__institution__in=institutions)
```

Overlap-lock query sketch: resolve the new request's institution-id set (or "all" sentinel for system-wide), then refuse if any existing `pending`/`running` `BackupJob` either is itself `system_wide`, or its own resolved institution-id set intersects the new one.

## Verification

**Commands:**
- `python manage.py test backup` -- expected: all existing 32 tests plus new scope-type tests pass
- `python manage.py makemigrations --check backup` -- expected: no missing migrations

**Manual checks (if no CLI):**
- Trigger a system-wide backup as a seeded superadmin in a local dev DB; unzip and confirm records from 2+ institutions appear in `db_export.json`.

## Suggested Review Order

**Scope model (schema change)**

- New tri-state field set backing single/multi/system — start here to understand the data shape everything else branches on.
  [`choice.py:257`](../../ndas/custom_codes/choice.py#L257)
- `scope_type` drives every branch below; default `single` keeps Story 1.1 rows valid.
  [`models.py:79`](../../backup/models.py#L79)
- `scopes` M2M only populated for `scope_type=multi`; empty for single/system.
  [`models.py:92`](../../backup/models.py#L92)

**Export scope branching (service layer)**

- Normalizes single Institution / iterable / system-wide into one descriptor; raises instead of the confusing `list(None)` TypeError a bare default would hit.
  [`services.py:51`](../../backup/services.py#L51)
- The three scoping shapes (`for_institution` / `filter(__in=)` / `all_institutions()`) applied per model; system branch is deliberately unfiltered by `is_active`.
  [`services.py:81`](../../backup/services.py#L81)
- Reads `job.scope_type`/`scope`/`scopes` to pick the right shape; fails loudly on an empty multi set rather than silently exporting nothing.
  [`services.py:272`](../../backup/services.py#L272)

**Scope resolution & overlap lock (view layer)**

- Server-side scope resolution — a non-superadmin's POST body is never trusted here, always coerced to single+own institution.
  [`views.py:39`](../../backup/views.py#L39)
- Entry point: permission gate → scope resolution → disk check → overlap lock → subprocess launch.
  [`views.py:127`](../../backup/views.py#L127)
- Overlap rule: a `system` job (new or existing) conflicts with everything; otherwise conflict iff institution-id sets intersect.
  [`views.py:245`](../../backup/views.py#L245)

**Form & UI**

- Superadmin-only scope selector; `clean()` refuses an empty multi-selection before any row is created.
  [`forms.py:18`](../../backup/forms.py#L18)
- Scope-mode radios + institution checkboxes, rendered only for `is_superadmin`; re-rendered with bound errors on validation failure (never a redirect that drops the user's picks).
  [`create.html:35`](../../backup/templates/backup/create.html#L35)

**Tests**

- Review order mirrors implementation order: model/service scope-shape tests, then view-level trigger/overlap/coercion tests.
  [`test_services.py`](../../backup/tests/test_services.py#L1)
  [`test_views.py`](../../backup/tests/test_views.py#L1)
