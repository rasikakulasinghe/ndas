import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from patients.models import Patient
from users.models import CustomUser

class PatientDeletionTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create a superuser for testing deletion
        self.superuser = CustomUser.objects.create_user(
            username='testadmin',
            email='admin@test.com',
            password='testpass123',
            is_superuser=True,
            is_staff=True
        )
        
        # Create a regular user
        self.regular_user = CustomUser.objects.create_user(
            username='testuser',
            email='user@test.com',
            password='testpass123',
            is_superuser=False
        )
        
        # Create a test patient
        self.patient = Patient.objects.create(
            bht='TEST001',
            baby_name='Test Baby',
            mother_name='Test Mother',
            gender='Male',
            dob_tob=timezone.now().date(),
            birth_weight=3500,  # Changed to grams (3.5 kg = 3500g)
            ofc=35.0,
            tp_mobile='0771234567',
            mo_delivery='Normal vaginal delivery (NVD)',  # Use valid choice
            added_by=self.superuser
        )
    
    def test_patient_delete_superuser_success(self):
        """Test successful patient deletion by superuser"""
        self.client.login(username='testadmin', password='testpass123')
        
        url = reverse('delete-patient', kwargs={'pk': self.patient.id})
        response = self.client.delete(
            url,
            data=json.dumps({'password': 'testpass123'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN='test-token'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('deleted successfully', response_data['message'])
        
        # Verify patient is actually deleted
        with self.assertRaises(Patient.DoesNotExist):
            Patient.objects.get(id=self.patient.id)
    
    def test_patient_delete_wrong_password(self):
        """Test patient deletion with wrong password"""
        self.client.login(username='testadmin', password='testpass123')
        
        url = reverse('delete-patient', kwargs={'pk': self.patient.id})
        response = self.client.delete(
            url,
            data=json.dumps({'password': 'wrongpassword'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN='test-token'
        )
        
        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Wrong password', response_data['message'])
        
        # Verify patient still exists
        Patient.objects.get(id=self.patient.id)
    
    def test_patient_delete_regular_user_denied(self):
        """Test patient deletion denied for regular user"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('delete-patient', kwargs={'pk': self.patient.id})
        response = self.client.delete(
            url,
            data=json.dumps({'password': 'testpass123'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN='test-token'
        )
        
        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('permission', response_data['message'])
        
        # Verify patient still exists
        Patient.objects.get(id=self.patient.id)
    
    def test_patient_delete_not_found(self):
        """Test patient deletion with non-existent patient ID"""
        self.client.login(username='testadmin', password='testpass123')
        
        url = reverse('delete-patient', kwargs={'pk': 99999})
        response = self.client.delete(
            url,
            data=json.dumps({'password': 'testpass123'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN='test-token'
        )
        
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('does not exist', response_data['message'])
    
    def test_patient_delete_unauthenticated(self):
        """Test patient deletion without authentication"""
        url = reverse('delete-patient', kwargs={'pk': self.patient.id})
        response = self.client.delete(
            url,
            data=json.dumps({'password': 'testpass123'}),
            content_type='application/json'
        )
        
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
        
        # Verify patient still exists
        Patient.objects.get(id=self.patient.id)
    
    def test_patient_delete_confirm_view_superuser(self):
        """Test patient delete confirmation view for superuser"""
        self.client.login(username='testadmin', password='testpass123')
        
        url = reverse('delete-confirm-patient', kwargs={'pk': self.patient.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.patient.baby_name)
        self.assertContains(response, self.patient.bht)
        self.assertNotContains(response, 'hide')
    
    def test_patient_delete_confirm_view_regular_user(self):
        """Test patient delete confirmation view for regular user"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('delete-confirm-patient', kwargs={'pk': self.patient.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dont have permission')
        self.assertContains(response, 'hide')

# Create your tests here.
