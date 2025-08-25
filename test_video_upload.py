#!/usr/bin/env python
"""
Test script for the enhanced video upload functionality in NDAS.
This script tests the video upload workflow including file validation,
size checking, and compression triggering.
"""

import os
import sys
import django
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
import tempfile

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ndas.settings')
django.setup()

from patients.models import Patient, Video
from users.models import CustomUser


class VideoUploadTestCase:
    """Test case for video upload functionality"""
    
    def __init__(self):
        self.client = Client()
        self.setup_test_data()
    
    def setup_test_data(self):
        """Create test user and patient"""
        # Create test user
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            is_staff=True
        )
        
        # Create test patient
        self.patient = Patient.objects.create(
            bht='TEST001',
            baby_name='Test Baby',
            mother_name='Test Mother',
            gender='M',
            birth_weight=3000,
            pog_wks=38,
            pog_days=0,
            added_by=self.user
        )
        
        print(f"✓ Created test user: {self.user.username}")
        print(f"✓ Created test patient: {self.patient.bht}")
    
    def create_mock_video_file(self, size_mb=1):
        """Create a mock video file for testing"""
        # Create a temporary file with specified size
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            # Write data to reach the desired size
            data = b'0' * (size_mb * 1024 * 1024)
            tmp_file.write(data)
            tmp_file.flush()
            
            # Create Django UploadedFile
            with open(tmp_file.name, 'rb') as f:
                uploaded_file = SimpleUploadedFile(
                    name=f'test_video_{size_mb}mb.mp4',
                    content=f.read(),
                    content_type='video/mp4'
                )
            
            # Clean up temp file
            os.unlink(tmp_file.name)
            
            return uploaded_file
    
    def test_small_video_upload(self):
        """Test uploading a small video file (< 25MB)"""
        print("\n🧪 Testing small video upload...")
        
        # Login
        self.client.login(username='testuser', password='testpass123')
        
        # Create small video file
        video_file = self.create_mock_video_file(size_mb=5)  # 5MB file
        
        # Prepare form data
        form_data = {
            'title_text': 'Test Small Video',
            'recorded_on': '2025-01-01T10:00',
            'description': 'Test description for small video',
            'tags': 'test, small, video',
            'target_quality': 'medium',
            'access_level': 'restricted',
            'is_sensitive': False,
        }
        
        # Upload video
        response = self.client.post(
            f'/video/add/{self.patient.id}/',
            data={**form_data, 'file': video_file},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✓ Small video uploaded successfully: {data.get('f_id')}")
                print(f"  - Needs compression: {data.get('needs_compression')}")
                print(f"  - Redirect URL: {data.get('redirect_url')}")
                return True
            else:
                print(f"✗ Upload failed: {data.get('msg')}")
        else:
            print(f"✗ HTTP error: {response.status_code}")
        
        return False
    
    def test_large_video_upload(self):
        """Test uploading a large video file (> 25MB)"""
        print("\n🧪 Testing large video upload...")
        
        # Login
        self.client.login(username='testuser', password='testpass123')
        
        # Create large video file
        video_file = self.create_mock_video_file(size_mb=30)  # 30MB file
        
        # Prepare form data
        form_data = {
            'title_text': 'Test Large Video',
            'recorded_on': '2025-01-01T10:00',
            'description': 'Test description for large video',
            'tags': 'test, large, video',
            'target_quality': 'medium',
            'access_level': 'restricted',
            'is_sensitive': False,
        }
        
        # Upload video
        response = self.client.post(
            f'/video/add/{self.patient.id}/',
            data={**form_data, 'file': video_file},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✓ Large video uploaded successfully: {data.get('f_id')}")
                print(f"  - Needs compression: {data.get('needs_compression')}")
                print(f"  - Redirect URL: {data.get('redirect_url')}")
                return True
            else:
                print(f"✗ Upload failed: {data.get('msg')}")
        else:
            print(f"✗ HTTP error: {response.status_code}")
        
        return False
    
    def test_invalid_file_upload(self):
        """Test uploading an invalid file type"""
        print("\n🧪 Testing invalid file upload...")
        
        # Login
        self.client.login(username='testuser', password='testpass123')
        
        # Create invalid file (text file)
        invalid_file = SimpleUploadedFile(
            name='test.txt',
            content=b'This is not a video file',
            content_type='text/plain'
        )
        
        # Prepare form data
        form_data = {
            'title_text': 'Test Invalid File',
            'recorded_on': '2025-01-01T10:00',
            'description': 'Test description for invalid file',
        }
        
        # Try to upload invalid file
        response = self.client.post(
            f'/video/add/{self.patient.id}/',
            data={**form_data, 'file': invalid_file},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        if response.status_code == 200:
            data = response.json()
            if not data.get('success'):
                print(f"✓ Invalid file correctly rejected: {data.get('msg')}")
                return True
            else:
                print(f"✗ Invalid file was incorrectly accepted")
        else:
            print(f"✗ HTTP error: {response.status_code}")
        
        return False
    
    def test_processing_page_access(self):
        """Test accessing the video processing page"""
        print("\n🧪 Testing processing page access...")
        
        # Login
        self.client.login(username='testuser', password='testpass123')
        
        # Create a video in processing state
        video = Video.objects.create(
            patient=self.patient,
            title='Test Processing Video',
            processing_status='processing',
            added_by=self.user
        )
        
        # Access processing page
        response = self.client.get(f'/video/processing/{video.id}/')
        
        if response.status_code == 200:
            print(f"✓ Processing page accessible")
            return True
        else:
            print(f"✗ Processing page not accessible: {response.status_code}")
        
        return False
    
    def run_all_tests(self):
        """Run all test cases"""
        print("🚀 Starting NDAS Video Upload Tests...")
        print("=" * 50)
        
        tests = [
            self.test_small_video_upload,
            self.test_large_video_upload,
            self.test_invalid_file_upload,
            self.test_processing_page_access,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
            except Exception as e:
                print(f"✗ Test failed with exception: {e}")
        
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print("⚠️  Some tests failed. Check the implementation.")
        
        return passed == total


def main():
    """Main function to run tests"""
    test_case = VideoUploadTestCase()
    success = test_case.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
