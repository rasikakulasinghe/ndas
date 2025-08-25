#!/usr/bin/env python
"""
Quick test script to verify URL resolution for patient management
"""
import os
import sys
import django

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ndas.settings')
django.setup()

from django.urls import reverse, resolve
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

def test_url_resolution():
    """Test that manage-patients URL resolves correctly"""
    print("Testing URL resolution for patient management...")
    
    # Test reverse resolution
    try:
        manage_patients_url = reverse('manage-patients')
        print(f"✓ reverse('manage-patients') = {manage_patients_url}")
    except Exception as e:
        print(f"✗ Error reversing 'manage-patients': {e}")
        return False
    
    # Test URL resolution
    try:
        resolved = resolve(manage_patients_url)
        print(f"✓ URL {manage_patients_url} resolves to view: {resolved.func.__name__}")
        print(f"✓ URL name: {resolved.url_name}")
    except Exception as e:
        print(f"✗ Error resolving URL {manage_patients_url}: {e}")
        return False
    
    # Test that the old problematic URL doesn't resolve
    try:
        old_url = "/patients/manager/"
        resolved = resolve(old_url)
        print(f"✗ Old URL {old_url} should not resolve but it does: {resolved}")
        return False
    except Exception as e:
        print(f"✓ Old URL {old_url} correctly fails to resolve: {type(e).__name__}")
    
    return True

if __name__ == "__main__":
    success = test_url_resolution()
    if success:
        print("\n✓ All URL tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some URL tests failed!")
        sys.exit(1)
