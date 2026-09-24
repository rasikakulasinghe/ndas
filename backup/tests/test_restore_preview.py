"""
backup/tests/test_restore_preview.py -- Story 2.2

Service tests (`backup.restore_preview`: counts, actions, digest stability and
sensitivity, block reasons, confirm/cancel rules) and view tests for every row
of the spec's I/O matrix: the preview, confirm, cancel, the confirmed-upload
protection, and the access gates.
"""
import copy
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from backup import restore_preview, restore_validation
from backup.models import BackupJob, RestoreUpload
from backup.restore_validation import get_upload_dir, get_upload_path
from backup.services import _model_export_plan
from backup.tests.test_restore_views import SECURITY_LOGGER, RestoreViewTestBase
from institution.models import Institution
from ndas.custom_codes.choice import RestoreAuthenticity, RestoreUploadStatus
from patients.models import Patient

SHA = 'a' * 64


def make_patient(institution, user, bht='BHT-001'):
    return Patient.objects.create(
        bht=bht, baby_name='Baby One', mother_name='Test Mother', dob_tob=timezone.now(), gender='Male',
        pog_wks=38, pog_days=2, birth_weight=3000, ofc=33, mo_delivery='Normal vaginal delivery (NVD)',
        tp_mobile='0711234567', institution=institution, added_by=user,
    )


STAGED_SIZE = len(b"staged")  # what RestoreViewTestBase.make_upload writes


class PreviewTestBase(RestoreViewTestBase):
    def make_upload(self, *args, **kwargs):
        # A confirmed upload always carries its confirmation time and snapshot
        # (DB check constraint).
        if kwargs.get('status') == RestoreUploadStatus.CONFIRMED:
            kwargs.setdefault('confirmed_at', timezone.now())
            kwargs.setdefault('confirmed_snapshot', {'digest': 'd' * 64})
        return super().make_upload(*args, **kwargs)

    def csrf_client(self, user):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        session = client.session
        session['active_institution_id'] = self.inst.id
        session.save()
        return client

    def summary(self, **overrides):
        base = {
            'source_job_id': 5, 'manifest_version': 1, 'schema_version': 'f' * 64, 'scope_type': 'single',
            'institutions': [self.inst.slug],
            'record_counts': {'patients.patient': 3, 'video.video': 1, 'referral.referralsent': 2},
            'date_filter': {'applied': False, 'start': None, 'end': None},
            'generated_at': '2026-09-20T10:00:00+00:00', 'generated_by': 'someone',
        }
        base.update(overrides)
        return base

    def validated(self, authenticity=RestoreAuthenticity.VERIFIED, user=None, summary=None, match_summary=None,
                  **overrides):
        return self.make_upload(
            user=user, status=RestoreUploadStatus.VALIDATED, progress_pct=100, authenticity=authenticity,
            source_job_id=5, archive_sha256=SHA, size_bytes=STAGED_SIZE,
            manifest_summary=summary if summary is not None else self.summary(**overrides),
            match_summary=match_summary,
        )

    def match_summary(self, **overrides):
        base = {
            'institution_slug': self.inst.slug, 'target_institution_id': self.inst.id,
            'skip': [{
                'archive_pk': 1, 'matched_fields': ['bht'], 'identifiers': {'bht': 'BHT-SKIP-1'},
                'existing_patient_ids': [999],
            }],
            'import': [{'archive_pk': 2, 'matched_fields': [], 'identifiers': {'nnc_no': 'NNC-IMPORT-2'}}],
            'excluded': [
                {'archive_pk': 3, 'matched_fields': ['pin'], 'identifiers': {'pin': 'PIN-EXCL-3'},
                 'reason': 'ambiguous-conflict', 'existing_patient_ids': [998, 997]},
            ],
        }
        base.update(overrides)
        return base

    def age(self, upload, minutes):
        RestoreUpload.objects.filter(pk=upload.pk).update(updated_at=timezone.now() - timedelta(minutes=minutes))
        upload.refresh_from_db()


# --------------------------------------------------------------------------
# Service: build_preview
# --------------------------------------------------------------------------

class ExportModelKeysTest(PreviewTestBase):
    def test_keys_match_the_export_plan_in_order(self):
        plan_keys = [key for key, _qs in _model_export_plan([self.inst])]
        self.assertEqual(list(restore_preview.EXPORT_MODEL_KEYS), plan_keys)
        self.assertEqual(len(plan_keys), 13)


class BuildPreviewTest(PreviewTestBase):
    def test_rows_cover_all_13_models_with_counts_and_actions(self):
        make_patient(self.inst, self.superadmin)
        other = Institution.objects.create(name='Other', slug='other', created_by=self.superadmin)
        make_patient(other, self.superadmin, bht='BHT-002')

        preview = restore_preview.build_preview(self.validated())
        rows = {row['key']: row for row in preview['models']}

        self.assertEqual([row['key'] for row in preview['models']], list(restore_preview.EXPORT_MODEL_KEYS))
        self.assertEqual(rows['patients.patient']['archive_count'], 3)
        self.assertEqual(rows['patients.patient']['current_count'], 1)  # only the archive's institution
        self.assertEqual(rows['video.video']['archive_count'], 1)
        self.assertEqual(rows['problemlist.problem']['archive_count'], 0)  # absent from the manifest
        for key, row in rows.items():
            expected = 'not_restored' if key.startswith('referral.') else 'replaced'
            self.assertEqual(row['action'], expected, key)
        self.assertEqual(rows['patients.patient']['label'], 'Patient')

    def test_counts_only_cover_institutions_that_exist_here(self):
        make_patient(self.inst, self.superadmin)
        preview = restore_preview.build_preview(self.validated(institutions=[self.inst.slug, 'ghost']))
        self.assertEqual(preview['live_counts']['patients.patient'], 1)
        self.assertEqual(
            preview['institutions'],
            [
                {'slug': 'ghost', 'name': '', 'exists': False},
                {'slug': self.inst.slug, 'name': self.inst.name, 'exists': True},
            ],
        )

    def test_no_institution_exists_gives_zero_counts_never_unfiltered(self):
        make_patient(self.inst, self.superadmin)
        preview = restore_preview.build_preview(self.validated(institutions=['ghost']))
        self.assertEqual(set(preview['live_counts'].values()), {0})
        self.assertTrue(preview['blocked'])

    def test_full_scope_all_present_is_not_blocked(self):
        preview = restore_preview.build_preview(self.validated())
        self.assertEqual(preview['block_reasons'], [])
        self.assertFalse(preview['blocked'])

    def test_block_reasons(self):
        missing = restore_preview.build_preview(self.validated(institutions=[self.inst.slug, 'ghost']))
        self.assertEqual(len(missing['block_reasons']), 1)
        self.assertIn('ghost', missing['block_reasons'][0])

        dated = restore_preview.build_preview(
            self.validated(date_filter={'applied': True, 'start': '2026-01-01', 'end': None}),
        )
        self.assertEqual(len(dated['block_reasons']), 1)
        self.assertIn('date-scoped', dated['block_reasons'][0])

        not_validated = self.make_upload(status=RestoreUploadStatus.CONFIRMED, manifest_summary=self.summary())
        reasons = restore_preview.build_preview(not_validated)['block_reasons']
        self.assertEqual(len(reasons), 1)
        self.assertIn('not validated', reasons[0])

    def test_date_bound_without_applied_flag_is_date_scoped(self):
        for date_filter in (
            {'applied': False, 'start': '2026-01-01', 'end': None},
            {'applied': False, 'start': None, 'end': '2026-02-01'},
        ):
            with self.subTest(date_filter=date_filter):
                preview = restore_preview.build_preview(self.validated(date_filter=date_filter))
                self.assertTrue(preview['date_filter']['applied'])
                self.assertTrue(preview['facts']['date_filter']['applied'])
                self.assertEqual(len(preview['block_reasons']), 1)
                self.assertIn('date-scoped', preview['block_reasons'][0])
        plain = restore_preview.build_preview(self.validated())
        self.assertFalse(plain['date_filter']['applied'])

    def test_archive_naming_no_institutions_is_blocked(self):
        preview = restore_preview.build_preview(self.validated(institutions=[]))
        self.assertIn("The archive names no institutions.", preview['block_reasons'])

    def test_unknown_scope_type_is_blocked(self):
        for scope in ('galaxy', '', None):
            with self.subTest(scope=scope):
                preview = restore_preview.build_preview(self.validated(scope_type=scope))
                self.assertEqual(len(preview['block_reasons']), 1)
                self.assertIn('scope type', preview['block_reasons'][0])
        for scope in ('single', 'multi', 'system'):
            self.assertFalse(restore_preview.build_preview(self.validated(scope_type=scope))['blocked'])

    def test_missing_or_short_staged_archive_is_blocked(self):
        upload = self.validated()
        get_upload_path(upload).write_bytes(b"sta")  # shorter than the uploaded size
        preview = restore_preview.build_preview(upload)
        self.assertEqual(len(preview['block_reasons']), 1)
        self.assertIn('size does not match', preview['block_reasons'][0])

        get_upload_path(upload).unlink()
        preview = restore_preview.build_preview(upload)
        self.assertEqual(len(preview['block_reasons']), 1)
        self.assertIn('missing', preview['block_reasons'][0])

    def test_staged_archive_check_does_not_change_the_digest(self):
        upload = self.validated()
        before = restore_preview.build_preview(upload)['digest']
        get_upload_path(upload).unlink()
        self.assertEqual(restore_preview.build_preview(upload)['digest'], before)

    def test_malformed_summary_does_not_crash(self):
        upload = self.validated(summary={'institutions': 'nope', 'record_counts': [], 'date_filter': 3})
        preview = restore_preview.build_preview(upload)
        self.assertEqual(preview['institutions'], [])
        self.assertEqual(set(m['archive_count'] for m in preview['models']), {0})


class DateScopeMatchPreviewTest(PreviewTestBase):
    def test_match_summary_present_lifts_the_date_scoped_block(self):
        upload = self.validated(
            date_filter={'applied': True, 'start': '2026-01-01', 'end': None},
            match_summary=self.match_summary(),
        )
        preview = restore_preview.build_preview(upload)
        self.assertEqual(preview['block_reasons'], [])
        self.assertFalse(preview['blocked'])
        self.assertEqual(preview['date_scope_match'], self.match_summary())

    def test_multi_scope_date_scoped_without_match_summary_uses_single_institution_wording(self):
        upload = self.validated(
            scope_type='multi', date_filter={'applied': True, 'start': '2026-01-01', 'end': None},
        )
        preview = restore_preview.build_preview(upload)
        self.assertIsNone(preview['date_scope_match'])
        self.assertEqual(len(preview['block_reasons']), 1)
        self.assertIn('only supported for a single-institution archive yet', preview['block_reasons'][0])

    def test_system_scope_date_scoped_without_match_summary_uses_single_institution_wording(self):
        upload = self.validated(
            scope_type='system', date_filter={'applied': True, 'start': '2026-01-01', 'end': None},
        )
        preview = restore_preview.build_preview(upload)
        self.assertIsNone(preview['date_scope_match'])
        self.assertIn('only supported for a single-institution archive yet', preview['block_reasons'][0])

    def test_single_scope_date_scoped_without_match_summary_says_to_cancel_and_upload_again(self):
        # e.g. an archive validated before Story 2.4 shipped -- still blocked, not crashed.
        upload = self.validated(date_filter={'applied': True, 'start': '2026-01-01', 'end': None})
        preview = restore_preview.build_preview(upload)
        self.assertIsNone(preview['date_scope_match'])
        self.assertEqual(len(preview['block_reasons']), 1)
        reason = preview['block_reasons'][0]
        self.assertIn('validated before date-scoped matching existed', reason)
        self.assertIn('no computed match', reason)
        self.assertIn('Cancel this upload and upload the archive again', reason)
        self.assertNotIn('not available yet', reason)
        self.assertNotIn('only supported for a single-institution archive', reason)

    def test_missing_institution_still_blocks_even_with_a_computed_match(self):
        upload = self.validated(
            institutions=['ghost'],
            date_filter={'applied': True, 'start': '2026-01-01', 'end': None},
            match_summary=self.match_summary(institution_slug='ghost', target_institution_id=None),
        )
        preview = restore_preview.build_preview(upload)
        self.assertIsNotNone(preview['date_scope_match'])
        self.assertTrue(preview['blocked'])
        self.assertEqual(preview['block_reasons'], [
            "These institutions named by the archive do not exist on this system: ghost. "
            "A restore never creates institutions and never restores only part of an archive.",
        ])

    def test_non_date_scoped_upload_ignores_a_stray_match_summary(self):
        upload = self.validated(match_summary=self.match_summary())
        preview = restore_preview.build_preview(upload)
        self.assertIsNone(preview['date_scope_match'])

    def date_scoped(self, match_summary, **overrides):
        overrides.setdefault('date_filter', {'applied': True, 'start': '2026-01-01', 'end': None})
        return self.validated(match_summary=match_summary, **overrides)

    def test_incomplete_match_summary_does_not_lift_the_block(self):
        base = self.match_summary()
        unusable = {
            'empty dict': {},
            'missing skip': {k: v for k, v in base.items() if k != 'skip'},
            'missing import': {k: v for k, v in base.items() if k != 'import'},
            'missing excluded': {k: v for k, v in base.items() if k != 'excluded'},
            'skip not a list': {**base, 'skip': {'archive_pk': 1}},
            'import is None': {**base, 'import': None},
            'excluded is a string': {**base, 'excluded': 'none'},
            'no institution slug': {k: v for k, v in base.items() if k != 'institution_slug'},
        }
        for label, match_summary in unusable.items():
            with self.subTest(label):
                preview = restore_preview.build_preview(self.date_scoped(match_summary))
                self.assertIsNone(preview['date_scope_match'])
                self.assertTrue(preview['blocked'])
                self.assertEqual(len(preview['block_reasons']), 1)
                self.assertIn('Cancel this upload and upload the archive again', preview['block_reasons'][0])
                self.assertIsNone(restore_preview._snapshot(preview)['date_scope_match'])

    def test_match_summary_for_a_different_institution_slug_does_not_lift_the_block(self):
        preview = restore_preview.build_preview(
            self.date_scoped(self.match_summary(institution_slug='some-other-hosp')),
        )
        self.assertIsNone(preview['date_scope_match'])
        self.assertTrue(preview['blocked'])
        self.assertIn('Cancel this upload and upload the archive again', preview['block_reasons'][0])

    def test_stray_match_summary_on_a_multi_or_system_scope_archive_is_ignored(self):
        for scope in ('multi', 'system'):
            with self.subTest(scope=scope):
                preview = restore_preview.build_preview(self.date_scoped(self.match_summary(), scope_type=scope))
                self.assertIsNone(preview['date_scope_match'])
                self.assertEqual(len(preview['block_reasons']), 1)
                self.assertIn('only supported for a single-institution archive yet', preview['block_reasons'][0])
                self.assertIsNone(restore_preview._snapshot(preview)['date_scope_match'])

    def test_single_scope_naming_two_institutions_needs_exactly_one(self):
        other = Institution.objects.create(name='Other', slug='other', created_by=self.superadmin)
        upload = self.date_scoped(
            self.match_summary(), scope_type='single', institutions=[self.inst.slug, other.slug],
        )
        preview = restore_preview.build_preview(upload)
        self.assertIsNone(preview['date_scope_match'])
        self.assertEqual(len(preview['block_reasons']), 1)
        self.assertIn('must name exactly one institution', preview['block_reasons'][0])
        self.assertTrue(preview['blocked'])

    def test_malformed_match_summary_does_not_crash(self):
        upload = self.make_upload(
            status=RestoreUploadStatus.VALIDATED, progress_pct=100, authenticity=RestoreAuthenticity.VERIFIED,
            source_job_id=5, archive_sha256=SHA, size_bytes=STAGED_SIZE,
            manifest_summary=self.summary(date_filter={'applied': True, 'start': '2026-01-01', 'end': None}),
            match_summary=['not', 'a', 'dict'],
        )
        preview = restore_preview.build_preview(upload)
        self.assertIsNone(preview['date_scope_match'])
        self.assertTrue(preview['blocked'])


class DigestTest(PreviewTestBase):
    def digest(self, upload):
        return restore_preview.build_preview(upload)['digest']

    def test_stable_across_calls(self):
        upload = self.validated()
        self.assertEqual(self.digest(upload), self.digest(upload))

    def test_ignores_live_counts(self):
        upload = self.validated()
        before = self.digest(upload)
        make_patient(self.inst, self.superadmin)
        self.assertEqual(self.digest(upload), before)

    def test_ignores_institution_and_archive_order(self):
        other = Institution.objects.create(name='Other', slug='other', created_by=self.superadmin)
        a = self.validated(institutions=[self.inst.slug, other.slug])
        b_summary = self.summary(institutions=[other.slug, self.inst.slug])
        self.assertEqual(self.digest(a), self.digest(self.validated(summary=b_summary, user=self.other_superadmin)))

    def test_sensitive_to_each_decision_relevant_fact(self):
        upload = self.validated()
        base = self.digest(upload)

        def changed(mutate):
            clone = copy.deepcopy(upload.manifest_summary)
            mutate(clone)
            other = RestoreUpload(
                archive_sha256=upload.archive_sha256, authenticity=upload.authenticity,
                status=RestoreUploadStatus.VALIDATED, manifest_summary=clone,
            )
            return self.digest(other)

        self.assertNotEqual(changed(lambda s: s.update(scope_type='multi')), base)
        self.assertNotEqual(changed(lambda s: s['record_counts'].update({'patients.patient': 4})), base)
        self.assertNotEqual(changed(lambda s: s['date_filter'].update(applied=True)), base)
        self.assertNotEqual(changed(lambda s: s['institutions'].append('ghost')), base)
        self.assertNotEqual(changed(lambda s: s['institutions'].clear()), base)

        upload.archive_sha256 = 'b' * 64
        self.assertNotEqual(self.digest(upload), base)
        upload.archive_sha256 = SHA
        upload.authenticity = RestoreAuthenticity.UNVERIFIED
        self.assertNotEqual(self.digest(upload), base)

    def test_sensitive_to_an_institution_appearing_or_disappearing_here(self):
        ghost_upload = self.validated(institutions=[self.inst.slug, 'ghost'])
        before = self.digest(ghost_upload)
        Institution.objects.create(name='Ghost', slug='ghost', created_by=self.superadmin)
        self.assertNotEqual(self.digest(ghost_upload), before)

    def test_sensitive_to_a_changed_match_summary(self):
        date_filter = {'applied': True, 'start': '2026-01-01', 'end': None}
        base_upload = self.validated(date_filter=date_filter, match_summary=self.match_summary())
        base = self.digest(base_upload)

        changed_upload = self.validated(date_filter=date_filter, match_summary=self.match_summary(skip=[]))
        self.assertNotEqual(self.digest(changed_upload), base)

        none_upload = self.validated(date_filter=date_filter)
        self.assertNotEqual(self.digest(none_upload), base)


# --------------------------------------------------------------------------
# Service: confirm / cancel
# --------------------------------------------------------------------------

class ConfirmServiceTest(PreviewTestBase):
    def confirm(self, upload, digest=None, ack=True, user=None):
        digest = restore_preview.build_preview(upload)['digest'] if digest is None else digest
        return restore_preview.confirm_upload(upload.id, user or self.superadmin, digest, ack)

    def test_confirm_records_snapshot_and_status_only(self):
        make_patient(self.inst, self.superadmin)
        upload = self.validated()
        patients_before = list(Patient.objects.all_institutions().values_list('pk', flat=True))

        outcome = self.confirm(upload)

        self.assertTrue(outcome.ok)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertEqual(upload.confirmed_by, self.superadmin)
        self.assertIsNotNone(upload.confirmed_at)
        snapshot = upload.confirmed_snapshot
        preview = restore_preview.build_preview(upload)
        self.assertEqual(snapshot['digest'], preview['digest'])
        self.assertEqual(snapshot['archive_sha256'], SHA)
        self.assertEqual(snapshot['archive_counts']['patients.patient'], 3)
        self.assertEqual(snapshot['live_counts_at_confirmation']['patients.patient'], 1)
        self.assertEqual(snapshot['institutions'], [{'slug': self.inst.slug, 'exists': True}])
        self.assertEqual(snapshot['actions']['referral.referralsent'], 'not_restored')
        self.assertEqual(snapshot['source_job_id'], 5)
        self.assertEqual(BackupJob.objects.count(), 0)
        self.assertEqual(list(Patient.objects.all_institutions().values_list('pk', flat=True)), patients_before)
        self.assertTrue(get_upload_path(upload).exists())  # the archive stays staged

    def assertRefused(self, upload, outcome, code):
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, code)
        upload.refresh_from_db()
        self.assertNotEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertIsNone(upload.confirmed_snapshot)
        self.assertIsNone(upload.confirmed_at)
        self.assertIsNone(upload.confirmed_by)

    def test_snapshot_carries_the_locked_in_date_scope_match_partition(self):
        summary = self.match_summary()
        upload = self.validated(
            date_filter={'applied': True, 'start': '2026-01-01', 'end': None}, match_summary=summary,
        )
        self.assertTrue(self.confirm(upload).ok)
        upload.refresh_from_db()
        self.assertEqual(upload.confirmed_snapshot['date_scope_match'], summary)

    def test_snapshot_records_versioned_hand_off_contract(self):
        upload = self.validated()
        self.assertTrue(self.confirm(upload).ok)
        upload.refresh_from_db()
        snapshot = upload.confirmed_snapshot
        self.assertEqual(snapshot['snapshot_version'], 1)
        self.assertIn('live_counts_at_confirmation', snapshot)
        self.assertNotIn('live_counts', snapshot)

    def test_confirming_an_unverified_upload_works(self):
        upload = self.validated(authenticity=RestoreAuthenticity.UNVERIFIED)
        self.assertTrue(self.confirm(upload).ok)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertEqual(upload.confirmed_snapshot['authenticity'], RestoreAuthenticity.UNVERIFIED)

    def test_non_ascii_digest_is_a_clean_mismatch(self):
        upload = self.validated()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = self.confirm(upload, digest='caf\u00e9-\u2603-' + 'x' * 40)
        self.assertRefused(upload, outcome, restore_preview.DIGEST_MISMATCH)

    def test_control_characters_in_the_digest_cannot_forge_log_lines(self):
        upload = self.validated()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            self.confirm(upload, digest='abc\nFORGED LOG LINE')
        for line in logs.output:
            self.assertNotIn('\nFORGED', line)

    def test_missing_staged_archive_blocks_confirm(self):
        upload = self.validated()
        get_upload_path(upload).unlink()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = self.confirm(upload)
        self.assertRefused(upload, outcome, restore_preview.BLOCKED)

    def test_short_staged_archive_blocks_confirm(self):
        upload = self.validated()
        get_upload_path(upload).write_bytes(b"x")
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = self.confirm(upload)
        self.assertRefused(upload, outcome, restore_preview.BLOCKED)

    def test_lost_race_at_the_conditional_write_records_nothing(self):
        upload = self.validated()
        digest = restore_preview.build_preview(upload)['digest']
        real_build = restore_preview.build_preview

        def build_then_lose_the_row(u):
            result = real_build(u)
            # Another request moves the row out of `validated` before our write.
            RestoreUpload.objects.filter(pk=u.pk).update(status=RestoreUploadStatus.REJECTED)
            return result

        with mock.patch.object(restore_preview, 'build_preview', side_effect=build_then_lose_the_row), \
                self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = restore_preview.confirm_upload(upload.id, self.superadmin, digest, True)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_preview.NOT_VALIDATED)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.REJECTED)
        self.assertIsNone(upload.confirmed_snapshot)

    def test_no_acknowledgement(self):
        upload = self.validated()
        self.assertRefused(upload, self.confirm(upload, ack=False), restore_preview.NOT_ACKNOWLEDGED)

    def test_digest_mismatch_is_refused_and_logged(self):
        upload = self.validated()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            outcome = self.confirm(upload, digest='0' * 64)
        self.assertRefused(upload, outcome, restore_preview.DIGEST_MISMATCH)
        self.assertTrue(any(str(upload.id) in line and 'sa_rs' in line for line in logs.output))

    def test_empty_digest_is_refused(self):
        upload = self.validated()
        self.assertRefused(upload, self.confirm(upload, digest=''), restore_preview.DIGEST_MISMATCH)

    def test_preview_changed_since_page_load(self):
        upload = self.validated(institutions=[self.inst.slug, 'ghost'])
        # A page that once showed 'ghost' as missing... then the institution appears.
        stale_digest = restore_preview.build_preview(upload)['digest']
        Institution.objects.create(name='Ghost', slug='ghost', created_by=self.superadmin)
        self.assertRefused(upload, self.confirm(upload, digest=stale_digest), restore_preview.DIGEST_MISMATCH)

    def test_missing_institution_blocks_even_with_the_right_digest(self):
        upload = self.validated(institutions=[self.inst.slug, 'ghost'])
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = self.confirm(upload)
        self.assertRefused(upload, outcome, restore_preview.BLOCKED)

    def test_date_scoped_archive_blocks(self):
        upload = self.validated(date_filter={'applied': True, 'start': '2026-01-01', 'end': '2026-02-01'})
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = self.confirm(upload)
        self.assertRefused(upload, outcome, restore_preview.BLOCKED)

    def test_replay_is_refused_and_changes_nothing(self):
        upload = self.validated()
        self.assertTrue(self.confirm(upload).ok)
        upload.refresh_from_db()
        first = (upload.confirmed_at, upload.confirmed_snapshot)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = restore_preview.confirm_upload(upload.id, self.superadmin, first[1]['digest'], True)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_preview.NOT_VALIDATED)
        upload.refresh_from_db()
        self.assertEqual((upload.confirmed_at, upload.confirmed_snapshot), first)

    def test_non_validated_statuses_are_refused(self):
        for status in (
            RestoreUploadStatus.VALIDATING, RestoreUploadStatus.REJECTED, RestoreUploadStatus.FAILED,
        ):
            with self.subTest(status=status):
                upload = self.make_upload(
                    user=self.other_superadmin if status == RestoreUploadStatus.REJECTED else None,
                    status=status, manifest_summary=self.summary(), archive_sha256=SHA,
                )
                with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
                    outcome = restore_preview.confirm_upload(
                        upload.id, upload.uploaded_by, restore_preview.build_preview(upload)['digest'], True,
                    )
                self.assertFalse(outcome.ok)

    def test_another_users_upload_cannot_be_confirmed(self):
        upload = self.validated(user=self.other_superadmin)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = self.confirm(upload, user=self.superadmin)
        self.assertFalse(outcome.ok)


class CancelServiceTest(PreviewTestBase):
    def test_cancellable_statuses_delete_files_and_row(self):
        for status in (
            RestoreUploadStatus.VALIDATED, RestoreUploadStatus.CONFIRMED,
            RestoreUploadStatus.REJECTED, RestoreUploadStatus.FAILED,
        ):
            with self.subTest(status=status):
                upload = self.make_upload(status=status)
                directory = get_upload_dir(upload)
                self.assertTrue(directory.exists())
                outcome = restore_preview.cancel_upload(upload.id, self.superadmin)
                self.assertTrue(outcome.ok)
                self.assertFalse(RestoreUpload.objects.filter(pk=upload.pk).exists())
                self.assertFalse(directory.exists())

    def test_cancel_removes_a_row_whose_files_are_already_gone(self):
        upload = self.make_upload(status=RestoreUploadStatus.REJECTED, staged=False)
        self.assertTrue(restore_preview.cancel_upload(upload.id, self.superadmin).ok)
        self.assertFalse(RestoreUpload.objects.filter(pk=upload.pk).exists())

    def test_fresh_validating_upload_cannot_be_cancelled(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATING)
        self.age(upload, 29)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = restore_preview.cancel_upload(upload.id, self.superadmin)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_preview.LIVE_VALIDATION)
        self.assertTrue(RestoreUpload.objects.filter(pk=upload.pk).exists())
        self.assertTrue(get_upload_path(upload).exists())

    def test_stale_validating_upload_can_be_cancelled_and_frees_the_slot(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATING)
        self.age(upload, 31)
        self.assertTrue(restore_preview.cancel_upload(upload.id, self.superadmin).ok)
        self.assertFalse(RestoreUpload.objects.filter(pk=upload.pk).exists())
        self.assertFalse(get_upload_dir(upload).exists())
        # The one-validating-upload slot is free again.
        self.make_upload(status=RestoreUploadStatus.VALIDATING)

    def test_row_is_kept_when_files_cannot_be_removed(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        with mock.patch.object(restore_validation, 'delete_upload_files'), \
                self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            outcome = restore_preview.cancel_upload(upload.id, self.superadmin)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_preview.FILES_NOT_REMOVED)
        self.assertTrue(RestoreUpload.objects.filter(pk=upload.pk).exists())

    def test_cancel_of_a_row_that_no_longer_exists_is_a_distinct_outcome(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        upload_id = upload.id
        upload.delete()
        outcome = restore_preview.cancel_upload(upload_id, self.superadmin)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_preview.GONE)

    def test_cannot_cancel_another_users_upload(self):
        upload = self.make_upload(user=self.other_superadmin, status=RestoreUploadStatus.VALIDATED)
        self.assertFalse(restore_preview.cancel_upload(upload.id, self.superadmin).ok)
        self.assertTrue(RestoreUpload.objects.filter(pk=upload.pk).exists())


class ConfirmedProtectionTest(PreviewTestBase):
    def test_confirmed_is_not_a_finished_status(self):
        self.assertNotIn(RestoreUploadStatus.CONFIRMED, restore_validation.FINISHED_STATUSES)

    def test_delete_finished_uploads_keeps_a_confirmed_upload(self):
        confirmed = self.make_upload(status=RestoreUploadStatus.CONFIRMED)
        finished = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        restore_validation.delete_finished_uploads(self.superadmin)
        self.assertTrue(RestoreUpload.objects.filter(pk=confirmed.pk).exists())
        self.assertTrue(get_upload_path(confirmed).exists())
        self.assertFalse(RestoreUpload.objects.filter(pk=finished.pk).exists())

    def test_a_row_that_turns_confirmed_after_listing_survives_replacement(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        real_atomic = transaction.atomic

        def confirm_then_enter(*args, **kwargs):
            RestoreUpload.objects.filter(pk=upload.pk).update(
                status=RestoreUploadStatus.CONFIRMED, confirmed_at=timezone.now(),
                confirmed_snapshot={'digest': 'd' * 64},
            )
            return real_atomic(*args, **kwargs)

        with mock.patch('backup.restore_validation.transaction.atomic', side_effect=confirm_then_enter):
            restore_validation.delete_finished_uploads(self.superadmin)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertTrue(get_upload_path(upload).exists())

    def test_confirmed_upload_must_carry_a_snapshot_and_time(self):
        for extra in ({}, {'confirmed_at': timezone.now()}, {'confirmed_snapshot': {'digest': 'x'}}):
            with self.subTest(extra=extra):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    RestoreUpload.objects.create(
                        uploaded_by=self.superadmin, status=RestoreUploadStatus.CONFIRMED, **extra,
                    )
        # confirmed_by may be null (SET_NULL)
        RestoreUpload.objects.create(
            uploaded_by=self.superadmin, status=RestoreUploadStatus.CONFIRMED,
            confirmed_at=timezone.now(), confirmed_snapshot={'digest': 'x'}, confirmed_by=None,
        )

    def test_refusal_is_written_to_the_security_log(self):
        self.make_upload(status=RestoreUploadStatus.CONFIRMED)
        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            self.client_for(self.superadmin).post(self.url, {})
        self.assertTrue(any('confirmed upload exists' in line and 'sa_rs' in line for line in logs.output))

    @mock.patch('backup.views.subprocess.Popen')
    def test_new_upload_refused_while_a_confirmed_one_exists(self, mock_popen):
        confirmed = self.make_upload(status=RestoreUploadStatus.CONFIRMED)
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        follow = self.client_for(self.superadmin).get(self.url)
        self.assertEqual(RestoreUpload.objects.count(), 1)
        self.assertTrue(RestoreUpload.objects.filter(pk=confirmed.pk).exists())
        self.assertTrue(get_upload_path(confirmed).exists())
        mock_popen.assert_not_called()
        self.assertEqual(follow.status_code, 200)

    @mock.patch('backup.views.subprocess.Popen')
    def test_refusal_message_says_cancel_it_first(self, mock_popen):
        self.make_upload(status=RestoreUploadStatus.CONFIRMED)
        client = self.client_for(self.superadmin)
        response = client.post(self.url, {}, follow=True)
        self.assertContains(response, 'Cancel it first')

    @mock.patch('backup.views.subprocess.Popen')
    def test_another_users_confirmed_upload_does_not_block(self, mock_popen):
        self.make_upload(user=self.other_superadmin, status=RestoreUploadStatus.CONFIRMED)
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertEqual(RestoreUpload.objects.filter(uploaded_by=self.superadmin).count(), 1)
        self.assertEqual(response.status_code, 302)


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

class PreviewViewTest(PreviewTestBase):
    def url_for(self, name, upload):
        return reverse(f'backup:restore-{name}', args=[upload.id])

    def get_preview(self, upload, client=None):
        return (client or self.client_for(self.superadmin)).get(self.url_for('preview', upload))

    def test_full_scope_preview_renders_scope_institutions_and_counts(self):
        make_patient(self.inst, self.superadmin)
        upload = self.validated()
        response = self.get_preview(upload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'read-only preview')
        self.assertContains(response, 'verified against backup job 5')
        self.assertContains(response, self.inst.slug)
        self.assertContains(response, 'Exists')
        self.assertContains(response, 'Replaced')
        self.assertContains(response, 'Not restored')
        self.assertContains(response, 'Bookmark')
        for key in restore_preview.EXPORT_MODEL_KEYS:
            self.assertContains(response, key)
        self.assertContains(response, 'Confirm restore')
        self.assertNotContains(response, 'This archive cannot be confirmed')
        self.assertContains(response, restore_preview.build_preview(upload)['digest'])
        self.assertContains(response, self.url_for('confirm', upload))
        self.assertContains(response, self.url_for('cancel', upload))

    def test_get_preview_writes_nothing(self):
        upload = self.validated()
        client = self.client_for(self.superadmin)
        before = list(RestoreUpload.objects.values())
        files_before = sorted(p.name for p in get_upload_dir(upload).iterdir())
        staged_before = get_upload_path(upload).read_bytes()
        session_tables = ('django_session', 'users_usersession', 'users_useractivitylog')

        with CaptureQueriesContext(connection) as queries:
            response = self.get_preview(upload, client)

        self.assertEqual(response.status_code, 200)
        writes = [
            q['sql'] for q in queries
            if not q['sql'].lstrip().upper().startswith(('SELECT', 'SAVEPOINT', 'RELEASE'))
            and not any(table in q['sql'] for table in session_tables)
        ]
        self.assertEqual(writes, [])
        self.assertEqual(list(RestoreUpload.objects.values()), before)
        self.assertEqual(sorted(p.name for p in get_upload_dir(upload).iterdir()), files_before)
        self.assertEqual(get_upload_path(upload).read_bytes(), staged_before)
        self.assertEqual(BackupJob.objects.count(), 0)

    def test_preview_never_opens_the_archive(self):
        upload = self.validated()
        with mock.patch('backup.restore_validation.zipfile.ZipFile') as zip_file, \
                mock.patch('zipfile.ZipFile') as zip_file_2:
            self.get_preview(upload)
        zip_file.assert_not_called()
        zip_file_2.assert_not_called()

    def test_unverified_preview_keeps_the_warning_and_labels_claims(self):
        upload = self.validated(authenticity=RestoreAuthenticity.UNVERIFIED)
        response = self.get_preview(upload)
        self.assertContains(response, 'Origin unverified')
        self.assertContains(response, 'claimed by the archive')
        self.assertContains(response, 'Confirm restore')
        self.assertNotContains(response, 'This archive cannot be confirmed')

    def test_missing_institution_lists_it_and_disables_confirm(self):
        upload = self.validated(institutions=[self.inst.slug, 'ghost-hosp'])
        response = self.get_preview(upload)
        self.assertContains(response, 'ghost-hosp')
        self.assertContains(response, 'This archive cannot be confirmed')
        self.assertContains(response, 'do not exist on this system')
        self.assertNotContains(response, self.url_for('confirm', upload))
        self.assertNotContains(response, 'name="acknowledge"')
        self.assertNotContains(response, 'name="digest"')

    def test_missing_staged_archive_does_not_offer_confirm(self):
        upload = self.validated()
        get_upload_path(upload).unlink()
        response = self.get_preview(upload)
        self.assertContains(response, 'staged archive file is missing')
        self.assertNotContains(response, self.url_for('confirm', upload))

    def test_date_scoped_archive_does_not_offer_confirm(self):
        upload = self.validated(date_filter={'applied': True, 'start': '2026-01-01', 'end': None})
        response = self.get_preview(upload)
        self.assertContains(response, '2026-01-01')
        self.assertContains(response, 'date-scoped')
        self.assertNotContains(response, self.url_for('confirm', upload))

    def test_multi_scope_date_scoped_archive_shows_the_single_institution_wording(self):
        upload = self.validated(
            scope_type='multi', date_filter={'applied': True, 'start': '2026-01-01', 'end': None},
        )
        response = self.get_preview(upload)
        self.assertContains(response, 'only supported for a single-institution archive yet')
        self.assertNotContains(response, self.url_for('confirm', upload))

    def test_date_scoped_archive_with_a_computed_match_renders_the_partition_and_offers_confirm(self):
        upload = self.validated(
            date_filter={'applied': True, 'start': '2026-01-01', 'end': None},
            match_summary=self.match_summary(),
        )
        response = self.get_preview(upload)
        self.assertContains(response, 'Date-scoped match preview')
        self.assertContains(response, 'Import: 1')
        self.assertContains(response, 'Skip: 1')
        self.assertContains(response, 'Excluded: 1')
        self.assertContains(response, '#1')  # skip entry
        self.assertContains(response, '#2')  # import entry
        self.assertContains(response, '#3')  # excluded entry
        # identifier values for every entry
        self.assertContains(response, 'BHT-SKIP-1')
        self.assertContains(response, 'NNC-IMPORT-2')
        self.assertContains(response, 'PIN-EXCL-3')
        # readable reason text, never the raw code, and no project-management reference
        self.assertContains(
            response,
            'Ambiguous: matches more than one existing patient, or another archived patient matches the same one',
        )
        self.assertNotContains(response, 'ambiguous-conflict')
        self.assertNotContains(response, 'Story 2.5')
        self.assertContains(response, 'applied in a later step')
        self.assertContains(response, 'Confirm restore')
        self.assertNotContains(response, 'This archive cannot be confirmed')
        self.assertContains(response, self.url_for('confirm', upload))

    def test_missing_institution_partition_shows_readable_reason(self):
        excluded = [
            {'archive_pk': 7, 'matched_fields': [], 'identifiers': {'bht': 'BHT-GHOST-7'},
             'reason': 'missing-institution', 'existing_patient_ids': []},
        ]
        upload = self.validated(
            institutions=['ghost-hosp'], date_filter={'applied': True, 'start': '2026-01-01', 'end': None},
            match_summary=self.match_summary(
                institution_slug='ghost-hosp', target_institution_id=None, skip=[], excluded=excluded,
                **{'import': []},
            ),
        )
        response = self.get_preview(upload)
        self.assertContains(response, 'BHT-GHOST-7')
        self.assertContains(response, "This archive's institution does not exist on this system")
        self.assertNotContains(response, 'missing-institution')
        self.assertNotContains(response, self.url_for('confirm', upload))

    def test_long_lists_are_capped_at_200_rows_with_an_and_n_more_row(self):
        def entries(prefix, count, **extra):
            return [
                {'archive_pk': 1000 + i, 'matched_fields': [], 'identifiers': {'bht': f'{prefix}-{i:04d}'}, **extra}
                for i in range(count)
            ]
        upload = self.validated(
            date_filter={'applied': True, 'start': '2026-01-01', 'end': None},
            match_summary=self.match_summary(
                skip=entries('SKIPPED', 205, existing_patient_ids=[1]),
                excluded=entries('EXCLUDED', 201, reason='ambiguous-conflict', existing_patient_ids=[1, 2]),
                **{'import': entries('IMPORTED', 200)},
            ),
        )
        response = self.get_preview(upload)
        self.assertContains(response, 'Import: 200')
        self.assertContains(response, 'Skip: 205')
        self.assertContains(response, 'Excluded: 201')
        # skip: first 200 shown, the 201st (index 200) is not; "... and 5 more"
        self.assertContains(response, 'SKIPPED-0199')
        self.assertNotContains(response, 'SKIPPED-0200')
        self.assertContains(response, '... and 5 more to skip')
        self.assertContains(response, 'EXCLUDED-0199')
        self.assertNotContains(response, 'EXCLUDED-0200')
        self.assertContains(response, '... and 1 more excluded')
        # exactly 200 imports: all shown, no "more" row
        self.assertContains(response, 'IMPORTED-0199')
        self.assertNotContains(response, 'more to import')

    def test_not_previewable_statuses_redirect_to_status_with_a_message(self):
        for status in (
            RestoreUploadStatus.VALIDATING, RestoreUploadStatus.REJECTED,
            RestoreUploadStatus.FAILED, RestoreUploadStatus.CONFIRMED,
        ):
            with self.subTest(status=status):
                upload = self.make_upload(status=status, manifest_summary=self.summary())
                response = self.get_preview(upload)
                self.assertRedirects(response, self.url_for('status', upload), fetch_redirect_response=False)
                RestoreUpload.objects.filter(pk=upload.pk).delete()

    def test_walking_away_leaves_the_upload_validated_and_previewable(self):
        upload = self.validated()
        client = self.client_for(self.superadmin)
        self.assertEqual(self.get_preview(upload, client).status_code, 200)
        client.get(self.url_for('status', upload))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertEqual(self.get_preview(upload, client).status_code, 200)

    def test_untrusted_institution_text_is_escaped(self):
        upload = self.validated(institutions=["<script>alert('x')</script>"])
        response = self.get_preview(upload)
        self.assertNotContains(response, "<script>alert('x')</script>")


class ConfirmViewTest(PreviewTestBase):
    def confirm_url(self, upload):
        return reverse('backup:restore-confirm', args=[upload.id])

    def post_confirm(self, upload, client=None, digest=None, ack=True, **extra):
        data = {'digest': digest if digest is not None else restore_preview.build_preview(upload)['digest']}
        if ack:
            data['acknowledge'] = 'on'
        data.update(extra)
        return (client or self.client_for(self.superadmin)).post(self.confirm_url(upload), data)

    def test_confirm_succeeds_and_says_not_applied(self):
        upload = self.validated()
        client = self.client_for(self.superadmin)
        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            response = self.post_confirm(upload, client)
        self.assertRedirects(
            response, reverse('backup:restore-status', args=[upload.id]), fetch_redirect_response=False,
        )
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertEqual(BackupJob.objects.count(), 0)
        self.assertTrue(any('confirmed' in line.lower() and str(upload.id) in line for line in logs.output))

        page = client.get(reverse('backup:restore-status', args=[upload.id]))
        self.assertContains(page, 'not applied yet')
        self.assertContains(page, 'has not been applied')
        self.assertNotContains(page, 'Review restore preview')
        self.assertContains(page, 'Cancel the confirmed restore')

    def test_confirm_does_not_modify_domain_data(self):
        patient = make_patient(self.inst, self.superadmin)
        upload = self.validated()
        institutions_before = Institution.objects.count()
        self.post_confirm(upload)
        self.assertEqual(Patient.objects.all_institutions().count(), 1)
        patient.refresh_from_db()
        self.assertEqual(patient.baby_name, 'Baby One')
        self.assertEqual(BackupJob.objects.count(), 0)
        self.assertEqual(Institution.objects.count(), institutions_before)

    def test_missing_acknowledgement_shows_a_form_error_and_records_nothing(self):
        upload = self.validated()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.post_confirm(upload, ack=False)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tick the acknowledgement')
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertIsNone(upload.confirmed_snapshot)

    def test_confirming_an_unverified_upload_through_the_view(self):
        upload = self.validated(authenticity=RestoreAuthenticity.UNVERIFIED)
        response = self.post_confirm(upload)
        self.assertEqual(response.status_code, 302)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_non_ascii_digest_is_refused_cleanly_not_a_500(self):
        upload = self.validated()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.post_confirm(upload, digest='caf\u00e9\u2603')
        self.assertRedirects(
            response, reverse('backup:restore-preview', args=[upload.id]), fetch_redirect_response=False,
        )
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)

    def test_forced_post_with_a_missing_staged_archive_is_refused(self):
        upload = self.validated()
        digest = restore_preview.build_preview(upload)['digest']
        get_upload_path(upload).unlink()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            self.post_confirm(upload, digest=digest)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertIsNone(upload.confirmed_snapshot)

    def test_form_errors_are_visible_on_a_blocked_preview(self):
        upload = self.validated(institutions=[self.inst.slug, 'ghost'])
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.post_confirm(upload, ack=False)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tick the acknowledgement')
        self.assertContains(response, 'This archive cannot be confirmed')
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)

    def test_acknowledgement_checkbox_is_required_in_html(self):
        upload = self.validated()
        response = self.client_for(self.superadmin).get(reverse('backup:restore-preview', args=[upload.id]))
        self.assertContains(response, 'name="acknowledge" required')

    def test_missing_digest_is_refused(self):
        upload = self.validated()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.client_for(self.superadmin).post(self.confirm_url(upload), {'acknowledge': 'on'})
        self.assertEqual(response.status_code, 200)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)

    def test_digest_mismatch_is_refused_with_review_again(self):
        upload = self.validated()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.post_confirm(upload, digest='f' * 64)
        self.assertRedirects(
            response, reverse('backup:restore-preview', args=[upload.id]), fetch_redirect_response=False,
        )
        page = self.client_for(self.superadmin).get(reverse('backup:restore-preview', args=[upload.id]))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertIsNone(upload.confirmed_snapshot)
        self.assertEqual(page.status_code, 200)

    def test_digest_mismatch_message_reaches_the_user(self):
        upload = self.validated()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.client_for(self.superadmin).post(
                self.confirm_url(upload), {'digest': 'f' * 64, 'acknowledge': 'on'}, follow=True,
            )
        self.assertContains(response, 'Review it again')

    def test_forced_post_for_a_missing_institution_is_refused(self):
        upload = self.validated(institutions=[self.inst.slug, 'ghost'])
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.post_confirm(upload)
        self.assertEqual(response.status_code, 302)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertIsNone(upload.confirmed_snapshot)

    def test_forced_post_for_a_date_scoped_archive_is_refused(self):
        upload = self.validated(date_filter={'applied': True, 'start': '2026-01-01', 'end': None})
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            self.post_confirm(upload)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)

    def test_replay_is_refused_and_changes_nothing(self):
        upload = self.validated()
        digest = restore_preview.build_preview(upload)['digest']
        client = self.client_for(self.superadmin)
        self.post_confirm(upload, client, digest=digest)
        upload.refresh_from_db()
        first = (upload.confirmed_at, upload.confirmed_snapshot)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.post_confirm(upload, client, digest=digest)
        self.assertRedirects(
            response, reverse('backup:restore-status', args=[upload.id]), fetch_redirect_response=False,
        )
        upload.refresh_from_db()
        self.assertEqual((upload.confirmed_at, upload.confirmed_snapshot), first)

    def test_non_validated_upload_cannot_be_confirmed(self):
        for status in (
            RestoreUploadStatus.VALIDATING, RestoreUploadStatus.REJECTED, RestoreUploadStatus.FAILED,
        ):
            with self.subTest(status=status):
                upload = self.make_upload(status=status, manifest_summary=self.summary())
                with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
                    response = self.post_confirm(upload, digest='0' * 64)
                self.assertEqual(response.status_code, 302)
                upload.refresh_from_db()
                self.assertEqual(upload.status, status)
                RestoreUpload.objects.filter(pk=upload.pk).delete()

    def test_get_is_not_allowed(self):
        upload = self.validated()
        response = self.client_for(self.superadmin).get(self.confirm_url(upload))
        self.assertEqual(response.status_code, 405)

    def test_csrf_is_enforced(self):
        upload = self.validated()
        before = list(RestoreUpload.objects.values())
        client = self.csrf_client(self.superadmin)
        response = client.post(self.confirm_url(upload), {
            'digest': restore_preview.build_preview(upload)['digest'], 'acknowledge': 'on',
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(list(RestoreUpload.objects.values()), before)


class CancelViewTest(PreviewTestBase):
    def cancel_url(self, upload):
        return reverse('backup:restore-cancel', args=[upload.id])

    def test_cancel_removes_files_and_row(self):
        for status in (
            RestoreUploadStatus.VALIDATED, RestoreUploadStatus.CONFIRMED,
            RestoreUploadStatus.REJECTED, RestoreUploadStatus.FAILED,
        ):
            with self.subTest(status=status):
                upload = self.make_upload(status=status)
                directory = get_upload_dir(upload)
                with self.assertLogs(SECURITY_LOGGER, level='INFO'):
                    response = self.client_for(self.superadmin).post(self.cancel_url(upload))
                self.assertRedirects(response, self.url, fetch_redirect_response=False)
                self.assertFalse(RestoreUpload.objects.filter(pk=upload.pk).exists())
                self.assertFalse(directory.exists())

    def test_cancel_modifies_no_domain_data(self):
        make_patient(self.inst, self.superadmin)
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        self.client_for(self.superadmin).post(self.cancel_url(upload))
        self.assertEqual(Patient.objects.all_institutions().count(), 1)
        self.assertEqual(BackupJob.objects.count(), 0)

    def test_live_validating_upload_cannot_be_cancelled(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATING)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.client_for(self.superadmin).post(self.cancel_url(upload))
        self.assertRedirects(
            response, reverse('backup:restore-status', args=[upload.id]), fetch_redirect_response=False,
        )
        self.assertTrue(RestoreUpload.objects.filter(pk=upload.pk).exists())
        self.assertTrue(get_upload_path(upload).exists())

    def test_stale_validating_upload_can_be_cancelled_then_uploaded_again(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATING)
        self.age(upload, 45)
        client = self.client_for(self.superadmin)

        page = client.get(reverse('backup:restore-status', args=[upload.id]))
        self.assertContains(page, self.cancel_url(upload))

        response = client.post(self.cancel_url(upload))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertFalse(RestoreUpload.objects.filter(pk=upload.pk).exists())

        with mock.patch('backup.views.subprocess.Popen'):
            again = self.post_archive(client)
        self.assertEqual(again.status_code, 302)
        self.assertEqual(RestoreUpload.objects.filter(uploaded_by=self.superadmin).count(), 1)

    def test_fresh_validating_status_page_offers_no_cancel(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATING)
        page = self.client_for(self.superadmin).get(reverse('backup:restore-status', args=[upload.id]))
        self.assertNotContains(page, self.cancel_url(upload))

    def test_row_kept_when_files_cannot_be_removed(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        with mock.patch.object(restore_validation, 'delete_upload_files'), \
                self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = self.client_for(self.superadmin).post(self.cancel_url(upload))
        self.assertRedirects(
            response, reverse('backup:restore-status', args=[upload.id]), fetch_redirect_response=False,
        )
        self.assertTrue(RestoreUpload.objects.filter(pk=upload.pk).exists())

    def test_csrf_is_enforced(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        response = self.csrf_client(self.superadmin).post(self.cancel_url(upload))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(RestoreUpload.objects.filter(pk=upload.pk).exists())
        self.assertTrue(get_upload_path(upload).exists())

    def test_cancel_of_a_row_that_vanished_mid_request_redirects_to_the_upload_page(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        gone = restore_preview.Outcome(False, restore_preview.GONE, "This upload no longer exists.")
        with mock.patch.object(restore_preview, 'cancel_upload', return_value=gone):
            response = self.client_for(self.superadmin).post(self.cancel_url(upload), follow=True)
        self.assertRedirects(response, self.url)
        self.assertContains(response, 'already cancelled')

    def test_get_is_not_allowed(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        self.assertEqual(self.client_for(self.superadmin).get(self.cancel_url(upload)).status_code, 405)
        self.assertTrue(RestoreUpload.objects.filter(pk=upload.pk).exists())


class StatusPageActionsTest(PreviewTestBase):
    def test_validated_status_page_links_to_the_preview_and_offers_cancel(self):
        upload = self.validated()
        page = self.client_for(self.superadmin).get(reverse('backup:restore-status', args=[upload.id]))
        self.assertContains(page, 'Review restore preview')
        self.assertContains(page, reverse('backup:restore-preview', args=[upload.id]))
        self.assertContains(page, reverse('backup:restore-cancel', args=[upload.id]))

    def test_unverified_status_page_wording_is_unchanged(self):
        upload = self.validated(authenticity=RestoreAuthenticity.UNVERIFIED)
        page = self.client_for(self.superadmin).get(reverse('backup:restore-status', args=[upload.id]))
        self.assertContains(page, 'Origin unverified')
        self.assertContains(page, 'Allow unverified origin')

    def test_rejected_and_failed_pages_offer_cancel(self):
        for status in (RestoreUploadStatus.REJECTED, RestoreUploadStatus.FAILED):
            upload = self.make_upload(status=status)
            page = self.client_for(self.superadmin).get(reverse('backup:restore-status', args=[upload.id]))
            self.assertContains(page, reverse('backup:restore-cancel', args=[upload.id]))


class AccessTest(PreviewTestBase):
    NAMES = ('preview', 'confirm', 'cancel')

    def request(self, client, name, upload):
        url = reverse(f'backup:restore-{name}', args=[upload.id])
        if name == 'preview':
            return client.get(url)
        return client.post(url, {'digest': restore_preview.build_preview(upload)['digest'], 'acknowledge': 'on'})

    def test_anonymous_goes_to_login(self):
        upload = self.validated()
        for name in self.NAMES:
            with self.subTest(view=name):
                response = self.request(Client(), name, upload)
                self.assertEqual(response.status_code, 302)
                self.assertIn('login', response['Location'])
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)

    def test_non_superadmins_are_denied_and_logged(self):
        upload = self.validated()
        for user in (self.admin, self.user):
            for name in self.NAMES:
                with self.subTest(user=user.username, view=name):
                    with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
                        response = self.request(self.client_for(user), name, upload)
                    self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
                    self.assertTrue(any(user.username in line for line in logs.output))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertTrue(get_upload_path(upload).exists())

    def test_another_super_admins_upload_is_404(self):
        upload = self.validated(user=self.other_superadmin)
        client = self.client_for(self.superadmin)
        for name in self.NAMES:
            with self.subTest(view=name):
                self.assertEqual(self.request(client, name, upload).status_code, 404)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertTrue(get_upload_path(upload).exists())

    def test_unknown_upload_is_404(self):
        client = self.client_for(self.superadmin)
        self.assertEqual(client.get(reverse('backup:restore-preview', args=[999999])).status_code, 404)
