# Reviewer Gate — Version/Reality-Check Pass

**Scope:** CHANGED/NEW sections only — AD-3 (amended), AD-5 (amended), AD-6 (amended), AD-18 (new), AD-19 (new) — per the 2026-09-17 amendment (single `db_export.json`, date-scoped export cascade, date-scoped/partial restore). AD-1, AD-2, AD-4, AD-7–AD-17 were not re-reviewed (unchanged, already passed this lens in the prior finalized pass).

**Lens:** every committed decision must be web-researched or reality-checked, not asserted from training data — current library/framework versions, and that each named technology still exists and fits the stated use.

**Verdict: PASS WITH NOTES**

The technical claims in the changed sections check out against the real repo and the real installed Django source. No fabricated API, no phantom dependency. Two things are worth recording: a real environment/version discrepancy the spine doesn't mention (not a spine defect, but relevant to "was this reality-checked"), and one claim that is accurate but rests on a well-known idiom rather than a single canonical Django API name, which a future implementer should not over-trust as a one-liner.

---

## 1. New-dependency claim (Stack section: "No new external dependencies")

**Checked:** `requirements.txt` (repo root) and `ndas/settings.py`.

- `zipfile`, `hashlib`, `subprocess`, `json` — Python stdlib, not third-party; correctly not listed in `requirements.txt`, nothing to add.
- `django.core.serializers` — part of Django itself (`django/core/serializers/__init__.py`, confirmed present in the installed package), not a separate PyPI package.
- `python-magic` (0.4.27) and `django-ratelimit` (4.1.0) — both already pinned in `requirements.txt`, reused as-is per AD-11.

**Verdict:** claim holds. No new package required by AD-3/AD-5/AD-6/AD-18/AD-19.

## 2. Django API reality-check

Checked directly against the installed package source under `venv/Lib/site-packages/django/` (see §4 for the version caveat) rather than from memory alone:

- `QuerySet.iterator()` — real, `django/db/models/query.py:516` (`def iterator(self, chunk_size=None)`). Matches AD-3's "streams... via `.iterator()`" claim.
- `django.core.serializers.serialize(format, queryset, **options)` — real, `django/core/serializers/__init__.py:128`. The `"python"` format serializer is a real, distinct serializer class (`django/core/serializers/python.py`, `class Serializer(base.Serializer)`), producing the `{model, pk, fields}`-shaped dict AD-5 describes — this is exactly `python.py`'s `end_object` output shape, correctly characterized.
- `django.core.serializers.deserialize(format, stream_or_string, **options)` — real, `django/core/serializers/__init__.py:138`.
- "Deserializing with `pk=None` to force a new PK on save" (AD-19 step 4) — this is not a single named Django API call; it's the standard idiom of either zeroing the `"pk"` key in the raw dict before calling `deserialize()`, or setting `obj.object.pk = None` on the returned `DeserializedObject` before `.save()`. Both variants are real and commonly used, and `base.py`'s `build_instance()` (line 303) is the underlying machinery that makes this behave correctly (it does its own get-or-create/pk handling per model). The spine's phrasing is accurate but compresses an idiom into what reads like an API keyword — flagging so whoever implements this doesn't go looking for a literal `pk=None` kwarg on `deserialize()` itself.
- `MigrationRecorder.applied_migrations()` — real, `django/db/migrations/recorder.py:84`, confirming AD-6's `schema_version` hash source is a genuine API, not invented.
- `Patient.objects.for_institution(institution).filter(created_at__date__range=(start, end))`-style chaining (AD-18) — `for_institution()` is real and confirmed in `institution/managers.py` (`InstitutionScopedManager.for_institution`, returns `self.get_queryset().filter(institution=institution)` or unfiltered if `institution is None`). Chaining `.filter(created_at__date__range=...)` afterward is standard QuerySet chaining, nothing exotic. `PatientManager` (patients/models.py) extends this manager, so `Patient.objects.for_institution(...)` is a real, callable method, not asserted-from-memory.

**Verdict:** all cited APIs are real and behave as described.

## 3. `Patient` model field grounding (AD-19's conflict-matching keys)

**Checked:** `patients/models.py` lines 156–191, `ndas/custom_codes/Custom_abstract_class.py`.

Confirmed exactly as the spine states:
- `bht` — `CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)`
- `nnc_no` — `CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)`
- `ptc_no` — `CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)`
- `pc_no` — `CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)`

All four are `unique=True, null=True, blank=True` as claimed — i.e. genuinely "unique-if-set," which is exactly the property AD-19 leans on for "first non-null field wins" conflict matching. `created_at` is confirmed present via `TimeStampedModel` (`ndas/custom_codes/Custom_abstract_class.py`, `auto_now_add=True`), inherited by `Patient(TimeStampedModel, UserTrackingMixin)`.

Also confirmed in passing: `Institution.slug` is a real `SlugField(unique=True)` field (`institution/models.py`), supporting AD-3/AD-19's "target institution matched by slug" claim.

**Verdict:** grounding claim in AD-19 is accurate, not asserted from training data — it matches the live model file.

## 4. Finding: local venv Django version does not match `requirements.txt`'s pinned line (environment drift, not a spine defect)

`requirements.txt` pins `Django~=5.2.0` with an explicit comment explaining 5.2 LTS was chosen because the deployment host (cPanel, Python 3.11.15 max) cannot run Django 6.0, which requires Python ≥3.12. However, the actual local dev venv at `venv/Lib/site-packages/` has **Django 6.0.0** installed (`django-6.0.dist-info`; `python -c "import django; print(django.VERSION)"` → `(6, 0, 0, 'final', 0)`), running under Python 3.13.1.

This is **not** a defect in the spine's reasoning — every API the spine cites (`iterator()`, `serializers.serialize`/`deserialize`, `MigrationRecorder.applied_migrations()`, manager chaining) is stable and behaves identically across Django 5.2 and 6.0, and the spine correctly treats 5.2 (the `requirements.txt`/`CLAUDE.md`/deployment-target version) as ground truth rather than whatever happens to be installed locally. The spine even separately flags (Deferred section) that `architecture.md` itself has a stale Django-version claim — good hygiene. But the spine's own "Stack" section implicitly assumes the dev environment matches `requirements.txt`, and it doesn't right now. Worth a note back to the team: either the venv was built against the wrong lockfile, or someone `pip install --upgrade django`'d locally — either way, `pip install -r requirements.txt` in a fresh venv should be re-run before implementation starts, since a 6.0-vs-5.2 local/prod mismatch is exactly the kind of thing that produces "works on my machine" surprises on a feature this migration/serializer-heavy.

**Severity:** Low/informational — does not invalidate any AD, but is a real, verifiable discrepancy this reviewer lens exists to catch, and it sits directly under the DB-serialization-heavy feature this spine is designing.

## 5. Everything else asserted as fact in AD-3/AD-5/AD-6/AD-18/AD-19

No other unverifiable or incorrect factual claims found. Specifically also spot-checked and confirmed real (though outside the strict scope list): `Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `Problem`, `ProblemAction` are stated by the spine (and the prior finalized pass's memlog, independently verified then against the actual model files) to lack any scoped manager and be reachable only via a `patient` FK chain — this underlying fact is unchanged by the current amendment and was not re-derived here, consistent with the task's instruction that AD-3's original scoping-by-model list is out of scope for re-review; only the single-file consolidation and the date-filter branch layered on top of it were re-verified.

---

## Summary Table

| # | Item | Verified against | Result |
|---|------|-------------------|--------|
| 1 | No new dependency | `requirements.txt`, `ndas/settings.py` | PASS |
| 2 | Django APIs (`iterator`, `serialize`/`deserialize`, `pk=None` idiom, `MigrationRecorder`, manager chaining) | installed `django/` package source | PASS (one idiom-vs-API-name nuance flagged) |
| 3 | `Patient.bht/nnc_no/ptc_no/pc_no` unique/null/blank; `created_at` via `TimeStampedModel` | `patients/models.py`, `Custom_abstract_class.py` | PASS |
| 4 | Local venv Django 6.0 vs. `requirements.txt`'s pinned 5.2 | `venv/Lib/site-packages/django-6.0.dist-info`, `python -c "import django"` | FINDING (low severity, environment drift, not a spine error) |
| 5 | Other AD-3/5/6/18/19 factual assertions | repo + Django docs knowledge | No further issues found |
