"""
backup/tests/test_job_lock.py -- Story 2.3

`backup/job_lock.py`: the overlap rule extracted from `backup_create` so a
`backup` job and a `restore` job are held to the same lock. Covers
`resolved_institution_ids` and `create_job_unless_overlapping` directly (the
view-level exercise of the same rule -- `backup_create` refusing an
overlapping restore and `restore_start` refusing an overlapping backup --
lives in `test_views.py` / `test_restore_views.py`).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from backup.job_lock import create_job_unless_overlapping, resolved_institution_ids
from backup.models import BackupJob
from institution.models import Institution
from ndas.custom_codes.choice import BackupJobScopeType, BackupJobStatus, BackupJobType

User = get_user_model()


class JobLockTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='jl_sa', password='x', position='Administrator', mobile_primary='0770000701',
        )
        self.inst_a = Institution.objects.create(name='JL Hosp A', slug='jl-hosp-a', created_by=self.user)
        self.inst_b = Institution.objects.create(name='JL Hosp B', slug='jl-hosp-b', created_by=self.user)
        self.inst_c = Institution.objects.create(name='JL Hosp C', slug='jl-hosp-c', created_by=self.user)

    def make_job(self, scope_type, institutions=(), status=BackupJobStatus.PENDING, job_type=BackupJobType.BACKUP):
        if scope_type == BackupJobScopeType.SINGLE:
            job = BackupJob.objects.create(
                job_type=job_type, status=status, scope_type=scope_type,
                scope=institutions[0], triggered_by=self.user,
            )
        elif scope_type == BackupJobScopeType.MULTI:
            job = BackupJob.objects.create(
                job_type=job_type, status=status, scope_type=scope_type, triggered_by=self.user,
            )
            job.scopes.set(institutions)
        else:
            job = BackupJob.objects.create(
                job_type=job_type, status=status, scope_type=scope_type, triggered_by=self.user,
            )
        return job


class ResolvedInstitutionIdsTest(JobLockTestBase):
    def test_single_scope_returns_its_id(self):
        job = self.make_job(BackupJobScopeType.SINGLE, [self.inst_a])
        self.assertEqual(resolved_institution_ids(job), {self.inst_a.id})

    def test_multi_scope_returns_all_ids_via_prefetch(self):
        job = self.make_job(BackupJobScopeType.MULTI, [self.inst_a, self.inst_b])
        job = BackupJob.objects.prefetch_related('scopes').get(pk=job.pk)
        self.assertEqual(resolved_institution_ids(job), {self.inst_a.id, self.inst_b.id})

    def test_system_scope_returns_empty_set(self):
        job = self.make_job(BackupJobScopeType.SYSTEM)
        self.assertEqual(resolved_institution_ids(job), set())

    def test_single_scope_with_deleted_institution_returns_empty_set(self):
        job = self.make_job(BackupJobScopeType.SINGLE, [self.inst_a])
        self.inst_a.delete()
        job.refresh_from_db()
        self.assertIsNone(job.scope_id)
        self.assertEqual(resolved_institution_ids(job), set())


class CreateJobUnlessOverlappingTest(JobLockTestBase):
    def create(self, scope_type, institutions=(), **fields):
        defaults = dict(job_type=BackupJobType.BACKUP, status=BackupJobStatus.PENDING, triggered_by=self.user)
        defaults.update(fields)
        return create_job_unless_overlapping(scope_type, list(institutions), **defaults)

    def test_creates_a_single_scope_job_when_nothing_conflicts(self):
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_a])
        self.assertIsNotNone(job)
        self.assertEqual(job.scope_type, BackupJobScopeType.SINGLE)
        self.assertEqual(job.scope, self.inst_a)
        self.assertEqual(BackupJob.objects.count(), 1)

    def test_creates_a_multi_scope_job_and_sets_scopes_m2m(self):
        job = self.create(BackupJobScopeType.MULTI, [self.inst_a, self.inst_b])
        self.assertIsNotNone(job)
        self.assertIsNone(job.scope)
        self.assertEqual(set(job.scopes.values_list('id', flat=True)), {self.inst_a.id, self.inst_b.id})

    def test_creates_a_system_scope_job(self):
        job = self.create(BackupJobScopeType.SYSTEM)
        self.assertIsNotNone(job)
        self.assertEqual(job.scope_type, BackupJobScopeType.SYSTEM)
        self.assertIsNone(job.scope)

    def test_job_fields_are_passed_through(self):
        job = self.create(
            BackupJobScopeType.SINGLE, [self.inst_a],
            job_type=BackupJobType.RESTORE, trigger_institution=self.inst_a,
        )
        self.assertEqual(job.job_type, BackupJobType.RESTORE)
        self.assertEqual(job.trigger_institution, self.inst_a)
        self.assertEqual(job.triggered_by, self.user)

    def test_same_institution_single_vs_single_conflicts(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a])
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_a])
        self.assertIsNone(job)
        self.assertEqual(BackupJob.objects.count(), 1)  # nothing created on conflict

    def test_disjoint_single_vs_single_does_not_conflict(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a])
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_b])
        self.assertIsNotNone(job)
        self.assertEqual(BackupJob.objects.count(), 2)

    def test_multi_overlapping_single_conflicts(self):
        self.make_job(BackupJobScopeType.MULTI, [self.inst_a, self.inst_b])
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_b])
        self.assertIsNone(job)

    def test_multi_disjoint_from_single_does_not_conflict(self):
        self.make_job(BackupJobScopeType.MULTI, [self.inst_a, self.inst_b])
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_c])
        self.assertIsNotNone(job)

    def test_existing_system_job_blocks_every_new_job(self):
        self.make_job(BackupJobScopeType.SYSTEM)
        self.assertIsNone(self.create(BackupJobScopeType.SINGLE, [self.inst_a]))
        self.assertIsNone(self.create(BackupJobScopeType.MULTI, [self.inst_a, self.inst_b]))

    def test_new_system_job_is_blocked_by_any_existing_job(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a])
        self.assertIsNone(self.create(BackupJobScopeType.SYSTEM))

    def test_new_system_job_conflicts_even_with_no_existing_jobs_at_all_is_created(self):
        job = self.create(BackupJobScopeType.SYSTEM)
        self.assertIsNotNone(job)

    def test_completed_and_failed_jobs_never_conflict(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a], status=BackupJobStatus.COMPLETED)
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a], status=BackupJobStatus.FAILED)
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_a])
        self.assertIsNotNone(job)

    def test_running_job_conflicts_same_as_pending(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a], status=BackupJobStatus.RUNNING)
        self.assertIsNone(self.create(BackupJobScopeType.SINGLE, [self.inst_a]))

    def test_conflict_check_is_type_agnostic_backup_blocks_restore(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a], job_type=BackupJobType.BACKUP)
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_a], job_type=BackupJobType.RESTORE)
        self.assertIsNone(job)

    def test_conflict_check_is_type_agnostic_restore_blocks_backup(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a], job_type=BackupJobType.RESTORE)
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_a], job_type=BackupJobType.BACKUP)
        self.assertIsNone(job)

    def test_disjoint_backup_and_restore_both_allowed(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a], job_type=BackupJobType.RESTORE)
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_b], job_type=BackupJobType.BACKUP)
        self.assertIsNotNone(job)

    def test_pre_restore_snapshot_jobs_also_count_toward_the_lock(self):
        self.make_job(BackupJobScopeType.SINGLE, [self.inst_a], job_type=BackupJobType.PRE_RESTORE_SNAPSHOT)
        job = self.create(BackupJobScopeType.SINGLE, [self.inst_a])
        self.assertIsNone(job)
