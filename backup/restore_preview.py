"""
Restore preview and confirmation -- Story 2.2.

Everything here works from the validated upload's `manifest_summary` plus live
database counts; the staged zip is never opened. Nothing in this module
applies, deletes or loads any domain data:

  * `build_preview(upload)` -- read-only. The archive's scope, each named
    institution's presence on this system, a per-model archive-vs-current
    table, the reasons confirmation is blocked, and a digest of the
    decision-relevant facts.
  * `confirm_upload(...)` -- records `confirmed_snapshot` on a `validated`
    upload and marks it `confirmed`, for a later story to apply.
  * `cancel_upload(...)` -- discards an upload's staged files and its row.

`backup/views.py` is the only caller (epic 1's rule: it is the sole entry
point into the service layer).
"""
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import timedelta

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from backup import restore_validation
from backup.services import _model_export_plan
from ndas.custom_codes.choice import BackupJobScopeType, RestoreAuthenticity, RestoreUploadStatus

security_logger = restore_validation.security_logger
logger = logging.getLogger(__name__)

ACTION_REPLACED = 'replaced'
ACTION_NOT_RESTORED = 'not_restored'

# The 13 export models in the export service's fixed order (asserted equal to
# `_model_export_plan`'s keys by the tests).
EXPORT_MODEL_KEYS = (
    'patients.patient',
    'referral.referralsent',
    'referral.referralreceived',
    'referral.referralmessage',
    'video.video',
    'patients.attachment',
    'patients.gmassessment',
    'patients.hineassessment',
    'patients.developmentalassessment',
    'patients.cdicrecord',
    'patients.generalpaediatricassessment',
    'problemlist.problem',
    'problemlist.problemaction',
)
REFERRAL_MODEL_KEYS = frozenset({
    'referral.referralsent',
    'referral.referralreceived',
    'referral.referralmessage',
})

# A `validating` upload whose row has not been saved for this long is treated
# as abandoned (its validator process died): validation saves progress at
# every percent change, so a live one keeps `updated_at` fresh.
STALE_VALIDATING_AFTER = timedelta(minutes=30)

CANCELLABLE_STATUSES = (
    RestoreUploadStatus.VALIDATED,
    RestoreUploadStatus.CONFIRMED,
    RestoreUploadStatus.REJECTED,
    RestoreUploadStatus.FAILED,
)

# Refusal codes returned by `confirm_upload` / `cancel_upload`.
NOT_VALIDATED = 'not_validated'
NOT_ACKNOWLEDGED = 'not_acknowledged'
BLOCKED = 'blocked'
DIGEST_MISMATCH = 'digest_mismatch'
LIVE_VALIDATION = 'live_validation'
FILES_NOT_REMOVED = 'files_not_removed'
GONE = 'gone'

SNAPSHOT_VERSION = 1


@dataclass
class Outcome:
    ok: bool
    code: str = ''
    message: str = ''


def model_label(key):
    return apps.get_model(key).__name__


def action_for(key):
    return ACTION_NOT_RESTORED if key in REFERRAL_MODEL_KEYS else ACTION_REPLACED


def _archive_counts(summary):
    counts = summary.get('record_counts')
    counts = counts if isinstance(counts, dict) else {}
    return {key: int(counts.get(key, 0) or 0) for key in EXPORT_MODEL_KEYS}


def _live_counts(existing_institutions):
    """Per-model counts in this system for the institutions that exist here,
    via the export service's own scoping. An empty list is the "multi" shape's
    footgun, so it is never passed: no institution here means zero rows."""
    if not existing_institutions:
        return {key: 0 for key in EXPORT_MODEL_KEYS}
    counts = {key: 0 for key in EXPORT_MODEL_KEYS}
    for key, queryset in _model_export_plan(list(existing_institutions)):
        counts[key] = queryset.count()
    return counts


def _digest(facts):
    canonical = json.dumps(facts, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('ascii')).hexdigest()


def can_cancel(upload, now=None):
    """Whether cancelling `upload` is allowed right now."""
    if upload.status in CANCELLABLE_STATUSES:
        return True
    if upload.status == RestoreUploadStatus.VALIDATING:
        return is_stale(upload, now)
    return False


def is_stale(upload, now=None):
    now = now or timezone.now()
    return now - upload.updated_at >= STALE_VALIDATING_AFTER


def _staged_archive_problem(upload):
    """Read-only stat of the staged archive (no hashing: re-verifying its
    SHA-256 before applying anything is the restore-apply story's job)."""
    try:
        size = restore_validation.get_upload_path(upload).stat().st_size
    except OSError:
        return "The staged archive file is missing. Cancel this upload and upload the archive again."
    if size != upload.size_bytes:
        return (
            "The staged archive file's size does not match the uploaded size. "
            "Cancel this upload and upload the archive again."
        )
    return None


def build_preview(upload):
    """
    The read-only preview of a validated upload. Returns a dict:

      facts         -- the digest input: archive_sha256, scope_type, institutions
                       (slug + exists-here), date_filter, archive counts, per-model
                       actions, authenticity. Non-volatile only.
      digest        -- SHA-256 over the canonical JSON of `facts`.
      institutions  -- [{slug, name, exists}] for display.
      models        -- [{key, label, archive_count, current_count, action}] x 13.
      live_counts   -- {model key: count now}; volatile, never part of the digest.
      block_reasons -- why confirmation is not possible (empty when it is).

    Writes nothing and touches no file.
    """
    Institution = apps.get_model('institution', 'Institution')
    summary = upload.manifest_summary if isinstance(upload.manifest_summary, dict) else {}
    match_summary = upload.match_summary if isinstance(upload.match_summary, dict) else None

    slugs = summary.get('institutions')
    slugs = sorted({s for s in slugs if isinstance(s, str)}) if isinstance(slugs, list) else []
    existing = {inst.slug: inst for inst in Institution.objects.filter(slug__in=slugs)}
    institutions = [
        {
            'slug': slug,
            'name': existing[slug].name if slug in existing else '',
            'exists': slug in existing,
        }
        for slug in slugs
    ]

    date_filter = summary.get('date_filter')
    date_filter = date_filter if isinstance(date_filter, dict) else {}
    # A bound set without `applied` is still a date-scoped archive.
    date_filter = {
        'applied': bool(date_filter.get('applied') or date_filter.get('start') or date_filter.get('end')),
        'start': date_filter.get('start'),
        'end': date_filter.get('end'),
    }

    archive_counts = _archive_counts(summary)
    actions = {key: action_for(key) for key in EXPORT_MODEL_KEYS}
    scope_type = summary.get('scope_type') if isinstance(summary.get('scope_type'), str) else ''

    # Story 2.4: a stable hash, not the partition itself, is what feeds the
    # digest -- exactly like every other archive-derived fact -- so a
    # corrupted/changed match_summary invalidates confirmation the same way a
    # changed manifest would, without bloating the digest input with the
    # (potentially large) skip/import/excluded lists themselves.
    match_summary_hash = _digest(match_summary) if match_summary is not None else None

    facts = {
        'archive_sha256': upload.archive_sha256,
        'scope_type': scope_type,
        'institutions': [{'slug': i['slug'], 'exists': i['exists']} for i in institutions],
        'date_filter': date_filter,
        'archive_counts': archive_counts,
        'actions': actions,
        'authenticity': upload.authenticity,
        'match_summary_hash': match_summary_hash,
    }

    live_counts = _live_counts([existing[s] for s in slugs if s in existing])
    models = [
        {
            'key': key,
            'label': model_label(key),
            'archive_count': archive_counts[key],
            'current_count': live_counts[key],
            'action': actions[key],
            'restored': actions[key] == ACTION_REPLACED,
        }
        for key in EXPORT_MODEL_KEYS
    ]

    block_reasons = []
    if upload.status != RestoreUploadStatus.VALIDATED:
        block_reasons.append("This upload is not validated, so it cannot be confirmed.")
    if not summary:
        block_reasons.append("The upload has no validated manifest summary.")
    if not institutions:
        block_reasons.append("The archive names no institutions.")
    if scope_type not in BackupJobScopeType.values:
        block_reasons.append("The archive's scope type is not one this system recognises.")
    missing = [i['slug'] for i in institutions if not i['exists']]
    if missing:
        block_reasons.append(
            "These institutions named by the archive do not exist on this system: "
            + ", ".join(restore_validation._clip(slug, 60) for slug in missing)
            + ". A restore never creates institutions and never restores only part of an archive."
        )
    if upload.status == RestoreUploadStatus.VALIDATED:
        problem = _staged_archive_problem(upload)
        if problem:
            block_reasons.append(problem)
    # Story 2.4: once a single-institution date-scoped archive's match has
    # been computed, its stored partition lifts the old blanket block; a
    # multi-/system-scoped date-scoped archive (no per-record institution can
    # be resolved for it) or one validated before this story shipped (no
    # match_summary yet) is still blocked, with wording that tells them apart.
    #
    # The block is lifted only for a fully usable match: `applied`, single
    # scope naming exactly one institution, a well-formed partition (skip,
    # import and excluded all lists) computed for that same institution slug.
    # Anything else is "no usable match" and `date_scope_match` stays None.
    match_is_usable = bool(
        date_filter['applied']
        and scope_type == BackupJobScopeType.SINGLE
        and len(slugs) == 1
        and match_summary is not None
        and all(isinstance(match_summary.get(part), list) for part in ('skip', 'import', 'excluded'))
        and match_summary.get('institution_slug') == slugs[0]
    )
    date_scope_match = match_summary if match_is_usable else None
    if date_filter['applied'] and not match_is_usable:
        if scope_type == BackupJobScopeType.SINGLE and len(slugs) == 1:
            block_reasons.append(
                "This archive is date-scoped, but it was validated before date-scoped matching existed "
                "or has no computed match, so it cannot be confirmed. Cancel this upload and upload "
                "the archive again."
            )
        elif scope_type == BackupJobScopeType.SINGLE:
            block_reasons.append(
                "This archive is date-scoped and single-institution, but it must name exactly one "
                "institution, so it cannot be confirmed."
            )
        else:
            block_reasons.append(
                "This archive is date-scoped. Restoring a date-scoped archive is only supported for "
                "a single-institution archive yet, so it cannot be confirmed."
            )

    return {
        'upload': upload,
        'facts': facts,
        'digest': _digest(facts),
        'institutions': institutions,
        'models': models,
        'live_counts': live_counts,
        'date_scope_match': date_scope_match,
        'block_reasons': block_reasons,
        'blocked': bool(block_reasons),
        'source_job_id': summary.get('source_job_id'),
        'generated_at': summary.get('generated_at'),
        'generated_by': summary.get('generated_by'),
        'date_filter': date_filter,
        'scope_type': scope_type,
        'is_unverified': upload.authenticity != RestoreAuthenticity.VERIFIED,
    }


def _snapshot(preview):
    return {
        **preview['facts'],
        'source_job_id': preview['source_job_id'],
        'generated_at': preview['generated_at'],
        'generated_by': preview['generated_by'],
        'live_counts_at_confirmation': preview['live_counts'],
        # Story 2.4: the locked-in skip/import/excluded partition, carried
        # byte-for-byte so Story 2.5's apply step reads it from here -- never
        # re-derived -- matching the AC's "this partition is final ...
        # including during the apply step".
        'date_scope_match': preview['date_scope_match'],
        'digest': preview['digest'],
        'snapshot_version': SNAPSHOT_VERSION,
    }


def confirm_upload(upload_id, user, submitted_digest, acknowledged):
    """
    Confirm the preview of `upload_id` (the caller has already established
    that `user` owns it). Refused, with nothing recorded, unless the upload is
    still `validated`, the acknowledgement was given, nothing blocks it, and
    the digest recomputed now equals `submitted_digest`.

    One conditional write records `status`, `confirmed_by`, `confirmed_at` and
    `confirmed_snapshot` together; it matches only a still-`validated` row, so
    a double submit confirms at most once. Creates no job and touches no
    domain data.
    """
    from backup.models import RestoreUpload

    with transaction.atomic():
        upload = RestoreUpload.objects.select_for_update().filter(pk=upload_id, uploaded_by=user).first()
        if upload is None or upload.status != RestoreUploadStatus.VALIDATED:
            security_logger.warning(
                "Restore confirm refused (not validated): user=%s upload=%s", user.username, upload_id,
            )
            return Outcome(False, NOT_VALIDATED, "This upload is not awaiting confirmation.")

        preview = build_preview(upload)

        if not acknowledged:
            return Outcome(False, NOT_ACKNOWLEDGED, "You must tick the acknowledgement to confirm.")

        if preview['blocked']:
            security_logger.warning(
                "Restore confirm blocked: user=%s upload=%s digest=%s reasons=%r",
                user.username, upload.id, preview['digest'], " | ".join(preview['block_reasons']),
            )
            return Outcome(False, BLOCKED, "This restore cannot be confirmed: " + " ".join(preview['block_reasons']))

        if not hmac.compare_digest(str(submitted_digest or '').encode('utf-8'), preview['digest'].encode('ascii')):
            security_logger.warning(
                "Restore confirm refused (preview changed): user=%s upload=%s submitted=%r current=%s",
                user.username, upload.id, restore_validation._clip(submitted_digest or '', 80), preview['digest'],
            )
            return Outcome(False, DIGEST_MISMATCH, "The preview changed since you opened it. Review it again.")

        now = timezone.now()
        updated = RestoreUpload.objects.filter(
            pk=upload.pk, status=RestoreUploadStatus.VALIDATED,
        ).update(
            status=RestoreUploadStatus.CONFIRMED,
            confirmed_by=user,
            confirmed_at=now,
            confirmed_snapshot=_snapshot(preview),
            last_edit_by=user,
            updated_at=now,
        )
        if updated != 1:
            security_logger.warning(
                "Restore confirm refused (lost race): user=%s upload=%s", user.username, upload.id,
            )
            return Outcome(False, NOT_VALIDATED, "This upload is not awaiting confirmation.")

    security_logger.info(
        "Restore confirmed (not applied): user=%s upload=%s digest=%s", user.username, upload.id, preview['digest'],
    )
    return Outcome(True)


def cancel_upload(upload_id, user):
    """
    Discard `upload_id`'s staged files and its row (the caller has already
    established that `user` owns it). Allowed for a `validated`, `confirmed`,
    `rejected` or `failed` upload, and for a `validating` one only when stale.
    The row is deleted only once its files are really gone.
    """
    from backup.models import RestoreUpload

    with transaction.atomic():
        upload = RestoreUpload.objects.select_for_update().filter(pk=upload_id, uploaded_by=user).first()
        if upload is None:
            return Outcome(False, GONE, "This upload no longer exists.")

        if not can_cancel(upload):
            security_logger.warning(
                "Restore cancel refused (validation in progress): user=%s upload=%s", user.username, upload.id,
            )
            return Outcome(
                False, LIVE_VALIDATION,
                "This upload is still being validated and cannot be cancelled yet.",
            )

        status = upload.status
        restore_validation.delete_upload_files(upload)
        if restore_validation.get_upload_dir(upload).exists():
            logger.warning(
                "Could not remove staged files for RestoreUpload %s; keeping its row.", upload.id,
            )
            security_logger.warning(
                "Restore cancel refused (files not removed): user=%s upload=%s", user.username, upload.id,
            )
            return Outcome(
                False, FILES_NOT_REMOVED,
                "The staged files could not be removed (they may be in use). Try again shortly.",
            )
        upload_pk = upload.pk
        digest = (upload.confirmed_snapshot or {}).get('digest', '') if status == RestoreUploadStatus.CONFIRMED else ''
        upload.delete()

    security_logger.info(
        "Restore upload cancelled: user=%s upload=%s status=%s digest=%s", user.username, upload_pk, status, digest,
    )
    return Outcome(True)
