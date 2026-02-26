from django.test import TestCase
from django.core.exceptions import ValidationError
from django.conf import settings
from institution.models import Institution
from ndas.custom_codes.choice import SubscriptionStatus


class InstitutionModelTest(TestCase):

    def test_institution_saves_with_timestampedmodel_fields(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        self.assertIsNotNone(inst.created_at)
        self.assertIsNotNone(inst.updated_at)

    def test_institution_saves_with_usertracking_fields(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        # added_by and last_edit_by are auto-populated by middleware; here they are null
        self.assertIsNone(inst.added_by)   # acceptable in tests — middleware not active
        self.assertIsNone(inst.last_edit_by)

    def test_subscription_status_choices_exist(self):
        self.assertEqual(SubscriptionStatus.ACTIVE, 'ACTIVE')
        self.assertEqual(SubscriptionStatus.GRACE, 'GRACE')
        self.assertEqual(SubscriptionStatus.EXPIRED, 'EXPIRED')

    def test_slug_immutable_on_update(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        inst.slug = 'different-slug'
        with self.assertRaises(ValidationError):
            inst.save()

    def test_slug_unchanged_on_update_is_allowed(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        inst.name = 'Test Hospital Updated'
        inst.save()  # Should not raise — slug unchanged
        inst.refresh_from_db()
        self.assertEqual(inst.slug, 'test-hospital')

    def test_new_institution_creation_with_slug_works(self):
        inst = Institution.objects.create(name='New Hospital', slug='new-hospital')
        self.assertEqual(inst.slug, 'new-hospital')

    def test_multi_institution_enabled_is_false_by_default(self):
        self.assertFalse(settings.MULTI_INSTITUTION_ENABLED)

    def test_institution_str(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        self.assertEqual(str(inst), 'Test Hospital')
