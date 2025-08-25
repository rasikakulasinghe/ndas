"""
Test script to verify the 404 page functionality
Run this script from the Django project directory using:
python manage.py shell < test_404_page.py
"""

from django.test import Client
from django.urls import reverse
from django.conf import settings

def test_404_page():
    """Test that our custom 404 page is working"""
    client = Client()
    
    # Test a non-existent URL
    response = client.get('/non-existent-page/')
    
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 404:
        print("✅ 404 page is working correctly!")
        print(f"Template used: {'404.html' if '404' in str(response.content) else 'Default Django 404'}")
    else:
        print(f"❌ Expected 404, got {response.status_code}")
    
    # Check if our custom content is present
    if b'Page not found' in response.content:
        print("✅ Custom 404 content is being rendered")
    else:
        print("❌ Custom 404 content not found")

if __name__ == '__main__':
    test_404_page()
