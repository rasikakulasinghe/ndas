from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from problemlist.models import Problem, ProblemAction
from patients.models import Patient

User = get_user_model()


class ProblemModelTest(TestCase):
    """Test Problem model functionality"""

    def setUp(self):
        """Set up test user and patient"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.patient = Patient.objects.create(
            baby_name='Test Baby',
            mother_name='Test Mother',
            bht='BHT001',
            gender='Male',
            dob_tob=timezone.now(),
            mo_delivery='Normal vaginal delivery (NVD)',
            birth_weight=3000,
            ofc=34.0,
            tp_mobile='0771234567',
            pog_wks=38,
            pog_days=0
        )

    def test_problem_creation(self):
        """Test creating a problem record"""
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            description='Test description',
            status='active',
            severity='moderate',
            added_by=self.user
        )
        self.assertEqual(problem.name, 'Test Problem')
        self.assertEqual(problem.status, 'active')
        self.assertEqual(problem.severity, 'moderate')
        self.assertEqual(problem.patient, self.patient)

    def test_problem_str_method(self):
        """Test __str__ method"""
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            added_by=self.user
        )
        expected = f"{self.patient.baby_name} - Test Problem"
        self.assertEqual(str(problem), expected)

    def test_problem_badge_classes(self):
        """Test status and severity badge class methods"""
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            status='active',
            severity='severe',
            added_by=self.user
        )
        self.assertEqual(problem.get_status_badge_class(), 'warning')
        self.assertEqual(problem.get_severity_badge_class(), 'danger')

    def test_problem_cascade_deletion(self):
        """Test cascade deletion when patient is deleted"""
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            added_by=self.user
        )
        patient_id = self.patient.pk
        self.patient.delete()
        # Problem should be deleted via cascade
        self.assertFalse(Problem.objects.filter(pk=problem.pk).exists())


class ProblemActionModelTest(TestCase):
    """Test ProblemAction model functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.patient = Patient.objects.create(
            baby_name='Test Baby',
            mother_name='Test Mother',
            bht='BHT001',
            gender='Male',
            dob_tob=timezone.now(),
            mo_delivery='Normal vaginal delivery (NVD)',
            birth_weight=3000,
            ofc=34.0,
            tp_mobile='0771234567',
            pog_wks=38,
            pog_days=0
        )
        self.problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            added_by=self.user
        )

    def test_problem_action_creation(self):
        """Test creating a problem action log entry"""
        action = ProblemAction.objects.create(
            problem=self.problem,
            action='Test action taken',
            performed_by=self.user
        )
        self.assertEqual(action.action, 'Test action taken')
        self.assertEqual(action.problem, self.problem)
        self.assertEqual(action.performed_by, self.user)

    def test_problem_action_ordering(self):
        """Test actions are ordered by date descending"""
        action1 = ProblemAction.objects.create(
            problem=self.problem,
            action='First action',
            performed_by=self.user
        )
        # Create second action slightly later
        action2 = ProblemAction.objects.create(
            problem=self.problem,
            action='Second action',
            performed_by=self.user
        )
        actions = self.problem.actions.all()
        self.assertEqual(actions[0], action2)  # Most recent first


class ProblemViewTest(TestCase):
    """Test problem views"""

    def setUp(self):
        """Set up test client, user, and data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.patient = Patient.objects.create(
            baby_name='Test Baby',
            mother_name='Test Mother',
            bht='BHT001',
            gender='Male',
            dob_tob=timezone.now(),
            mo_delivery='Normal vaginal delivery (NVD)',
            birth_weight=3000,
            ofc=34.0,
            tp_mobile='0771234567',
            pog_wks=38,
            pog_days=0
        )
        self.client.login(username='testuser', password='testpass123')

    def test_problem_manager_view(self):
        """Test problem manager view renders correctly"""
        url = reverse('problem-manager', kwargs={'pid': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Patient Problems')

    def test_problem_add_view_get(self):
        """Test problem add view GET request"""
        url = reverse('problem-add', kwargs={'pid': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Problem')

    def test_problem_add_view_post(self):
        """Test problem add view POST request"""
        url = reverse('problem-add', kwargs={'pid': self.patient.pk})
        data = {
            'name': 'Test Problem',
            'description': 'Test description',
            'date_identified': timezone.now().date(),
            'status': 'active',
            'severity': 'moderate',
        }
        response = self.client.post(url, data)
        # Should redirect to problem manager
        self.assertEqual(response.status_code, 302)
        # Verify problem was created
        self.assertTrue(Problem.objects.filter(name='Test Problem').exists())

    def test_problem_view_detail(self):
        """Test problem detail view"""
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            added_by=self.user
        )
        url = reverse('problem-view', kwargs={'pk': problem.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Problem')

    def test_problem_edit_view(self):
        """Test problem edit view"""
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            added_by=self.user
        )
        url = reverse('problem-edit', kwargs={'pk': problem.pk})
        data = {
            'name': 'Updated Problem',
            'description': 'Updated description',
            'date_identified': timezone.now().date(),
            'status': 'resolved',
        }
        response = self.client.post(url, data)
        # Should redirect to problem view
        self.assertEqual(response.status_code, 302)
        # Verify problem was updated
        problem.refresh_from_db()
        self.assertEqual(problem.name, 'Updated Problem')
        self.assertEqual(problem.status, 'resolved')

    def test_problem_delete_permission_superuser(self):
        """Test superuser can delete any problem"""
        superuser = User.objects.create_superuser(
            username='admin',
            password='adminpass123'
        )
        self.client.login(username='admin', password='adminpass123')
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            added_by=self.user  # Different user
        )
        url = reverse('problem-delete', kwargs={'pk': problem.pk})
        response = self.client.get(url)
        # Should delete and redirect
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Problem.objects.filter(pk=problem.pk).exists())

    def test_problem_delete_permission_own_record(self):
        """Test staff can delete their own records"""
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            added_by=self.user  # Same user logged in
        )
        url = reverse('problem-delete', kwargs={'pk': problem.pk})
        response = self.client.get(url)
        # Should delete and redirect
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Problem.objects.filter(pk=problem.pk).exists())

    def test_unauthenticated_access(self):
        """Test unauthenticated users are redirected to login"""
        self.client.logout()
        url = reverse('problem-manager', kwargs={'pid': self.patient.pk})
        response = self.client.get(url)
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('user-login', response.url)


class ProblemFormValidationTest(TestCase):
    """Test problem form validation"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.patient = Patient.objects.create(
            baby_name='Test Baby',
            mother_name='Test Mother',
            bht='BHT001',
            gender='Male',
            dob_tob=timezone.now(),
            mo_delivery='Normal vaginal delivery (NVD)',
            birth_weight=3000,
            ofc=34.0,
            tp_mobile='0771234567',
            pog_wks=38,
            pog_days=0
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_future_date_validation(self):
        """Test that future dates are rejected"""
        url = reverse('problem-add', kwargs={'pid': self.patient.pk})
        future_date = (timezone.now() + timezone.timedelta(days=30)).date()
        data = {
            'name': 'Test Problem',
            'date_identified': future_date,
            'status': 'active',
        }
        response = self.client.post(url, data)
        # Should show form with errors (not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cannot be in the future')

    def test_auto_populate_date_resolved(self):
        """Test that date_resolved is auto-populated when status is resolved"""
        problem = Problem.objects.create(
            patient=self.patient,
            name='Test Problem',
            status='active',
            added_by=self.user
        )
        url = reverse('problem-edit', kwargs={'pk': problem.pk})
        data = {
            'name': 'Test Problem',
            'date_identified': timezone.now().date(),
            'status': 'resolved',  # Changing to resolved
            # Not providing date_resolved
        }
        response = self.client.post(url, data)
        problem.refresh_from_db()
        # date_resolved should be auto-populated
        self.assertIsNotNone(problem.date_resolved)


class ProblemAnalysisViewTest(TestCase):
    """Test problem analysis view with filters"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.patient1 = Patient.objects.create(
            baby_name='Patient One',
            mother_name='Mother One',
            bht='BHT001',
            gender='Male',
            dob_tob=timezone.now(),
            mo_delivery='Normal vaginal delivery (NVD)',
            birth_weight=3000,
            ofc=34.0,
            tp_mobile='0771234567',
            pog_wks=38,
            pog_days=0
        )
        self.patient2 = Patient.objects.create(
            baby_name='Patient Two',
            mother_name='Mother Two',
            bht='BHT002',
            gender='Female',
            dob_tob=timezone.now(),
            mo_delivery='Normal vaginal delivery (NVD)',
            birth_weight=2800,
            ofc=33.0,
            tp_mobile='0779876543',
            pog_wks=37,
            pog_days=5
        )
        # Create various problems for filtering
        Problem.objects.create(
            patient=self.patient1,
            name='Problem 1',
            status='active',
            severity='severe',
            added_by=self.user
        )
        Problem.objects.create(
            patient=self.patient2,
            name='Problem 2',
            status='resolved',
            severity='mild',
            added_by=self.user
        )
        self.client.login(username='testuser', password='testpass123')

    def test_analysis_view_loads(self):
        """Test analysis view renders"""
        url = reverse('problem-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Problem Analysis')

    def test_analysis_filter_by_status(self):
        """Test filtering by status"""
        url = reverse('problem-analysis')
        response = self.client.get(url, {'status': ['active']})
        self.assertEqual(response.status_code, 200)
        # Should only show active problems
        self.assertContains(response, 'Problem 1')
        self.assertNotContains(response, 'Problem 2')

    def test_analysis_summary_statistics(self):
        """Test that summary statistics are correctly calculated"""
        # Create additional problems with different statuses
        Problem.objects.create(
            patient=self.patient1,
            name='Chronic Problem',
            status='chronic',
            added_by=self.user
        )
        Problem.objects.create(
            patient=self.patient1,
            name='Inactive Problem',
            status='inactive',
            added_by=self.user
        )

        url = reverse('problem-analysis')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check that stats are in context
        self.assertIn('stats', response.context)
        stats = response.context['stats']

        # Verify counts
        self.assertEqual(stats['active'], 1)
        self.assertEqual(stats['chronic'], 1)
        self.assertEqual(stats['resolved'], 1)
        self.assertEqual(stats['inactive'], 1)

        # Verify the stats are displayed in the template
        self.assertContains(response, 'Summary Statistics')
        self.assertContains(response, 'Active Problems')
        self.assertContains(response, 'Chronic Problems')
        self.assertContains(response, 'Resolved Problems')
        self.assertContains(response, 'Inactive Problems')


class ProblemXSSPreventionTest(TestCase):
    """Test XSS prevention in problem forms and data sanitization"""

    def setUp(self):
        """Set up test user and patient"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.patient = Patient.objects.create(
            baby_name='Test Baby',
            mother_name='Test Mother',
            bht='BHT001',
            gender='Male',
            dob_tob=timezone.now(),
            mo_delivery='Normal vaginal delivery (NVD)',
            birth_weight=3000,
            ofc=34.0,
            tp_mobile='0771234567',
            pog_wks=38,
            pog_days=0
        )
        self.client.login(username='testuser', password='testpass123')

    def test_problem_name_sanitization(self):
        """Test that problem name is sanitized to prevent XSS"""
        from problemlist.forms import ProblemForm

        # Test with malicious script tag
        form_data = {
            'name': '<script>alert("xss")</script>Test Problem',
            'description': 'Test description',
            'date_identified': timezone.now().date(),
            'status': 'active',
        }
        form = ProblemForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Verify sanitization removed script tags AND their content
        cleaned_name = form.cleaned_data['name']
        self.assertNotIn('<script>', cleaned_name)
        self.assertNotIn('</script>', cleaned_name)
        self.assertNotIn('alert', cleaned_name)  # Script content removed for security
        self.assertIn('Test Problem', cleaned_name)  # Safe content preserved

    def test_problem_description_sanitization(self):
        """Test that problem description is sanitized"""
        from problemlist.forms import ProblemForm

        # Test with HTML tags and event handlers
        form_data = {
            'name': 'Test Problem',
            'description': '<img src=x onerror="alert(1)">BP < 120/80 mmHg',
            'date_identified': timezone.now().date(),
            'status': 'active',
        }
        form = ProblemForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Verify sanitization
        cleaned_description = form.cleaned_data['description']
        self.assertNotIn('onerror', cleaned_description)
        self.assertNotIn('<img', cleaned_description)
        # Medical notation should be preserved
        self.assertIn('BP < 120/80 mmHg', cleaned_description)

    def test_medical_notation_preserved(self):
        """Test that legitimate medical notation is preserved"""
        from problemlist.forms import ProblemForm

        # Test medical notation preservation
        form_data = {
            'name': 'Hypoglycemia',
            'description': 'Blood glucose < 50 mg/dL, temperature > 38°C',
            'action_taken': 'Administered IV glucose, repeat labs in 2-4 hours',
            'outcome': 'Glucose increased to > 70 mg/dL',
            'comments': 'Monitor for signs: lethargy, poor feeding, etc.',
            'date_identified': timezone.now().date(),
            'status': 'active',
        }
        form = ProblemForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Verify medical notation is preserved
        self.assertIn('< 50 mg/dL', form.cleaned_data['description'])
        self.assertIn('> 38°C', form.cleaned_data['description'])
        self.assertIn('2-4 hours', form.cleaned_data['action_taken'])
        self.assertIn('> 70 mg/dL', form.cleaned_data['outcome'])

    def test_action_sanitization(self):
        """Test that action_taken field is sanitized"""
        from problemlist.forms import ProblemForm

        form_data = {
            'name': 'Test Problem',
            'action_taken': '<a href="javascript:void(0)">Click here</a>',
            'date_identified': timezone.now().date(),
            'status': 'active',
        }
        form = ProblemForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Verify sanitization removed dangerous protocol
        cleaned_action = form.cleaned_data['action_taken']
        self.assertNotIn('javascript:', cleaned_action)
        self.assertNotIn('<a', cleaned_action)
        self.assertIn('Click here', cleaned_action)

    def test_problem_action_form_sanitization(self):
        """Test that ProblemActionForm sanitizes action field"""
        from problemlist.forms import ProblemActionForm

        # Test with malicious input
        form_data = {
            'action': '<style>body{display:none}</style>Administered medication',
        }
        form = ProblemActionForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Verify sanitization
        cleaned_action = form.cleaned_data['action']
        self.assertNotIn('<style>', cleaned_action)
        self.assertNotIn('</style>', cleaned_action)
        self.assertIn('Administered medication', cleaned_action)

    def test_whitespace_normalization(self):
        """Test that excessive whitespace is normalized"""
        from problemlist.forms import ProblemForm

        form_data = {
            'name': 'Test    Problem    With    Spaces',
            'description': 'Line1\n\n\n\nLine2',
            'date_identified': timezone.now().date(),
            'status': 'active',
        }
        form = ProblemForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Verify whitespace normalization
        cleaned_name = form.cleaned_data['name']
        self.assertEqual('Test Problem With Spaces', cleaned_name)

        # Multiple newlines should be normalized to double newline
        cleaned_description = form.cleaned_data['description']
        self.assertIn('Line1', cleaned_description)
        self.assertIn('Line2', cleaned_description)

    def test_xss_in_database_save(self):
        """Test that XSS is prevented when saving to database"""
        # Create problem with malicious input via form
        form_data = {
            'name': '<script>alert("xss")</script>Seizure Disorder',
            'description': '<img src=x onerror="alert(1)">Patient presents with seizures',
            'action_taken': 'Started on <b>anti-epileptics</b>',
            'outcome': 'Seizure free for > 24 hours',
            'comments': '<a href="javascript:alert(1)">Follow-up</a> in 2 weeks',
            'date_identified': timezone.now().date(),
            'status': 'active',
        }

        from problemlist.forms import ProblemForm
        form = ProblemForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Save to database
        problem = form.save(commit=False)
        problem.patient = self.patient
        problem.added_by = self.user
        problem.save()

        # Retrieve from database and verify
        saved_problem = Problem.objects.get(id=problem.id)
        self.assertNotIn('<script>', saved_problem.name)
        self.assertNotIn('onerror', saved_problem.description)
        self.assertNotIn('<b>', saved_problem.action_taken)
        self.assertNotIn('javascript:', saved_problem.comments)

        # Verify medical notation is preserved
        self.assertIn('> 24 hours', saved_problem.outcome)
