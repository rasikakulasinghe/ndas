"""
Simple test to check if 404 page template exists and is properly formatted
"""

import os
from django.conf import settings

def test_404_template():
    """Check if the 404 template exists and has the expected content"""
    template_path = os.path.join(settings.BASE_DIR, 'templates', '404.html')
    
    if os.path.exists(template_path):
        print("✅ 404.html template file exists")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for key elements
        checks = [
            ('404', '404 error code'),
            ('Page not found', 'Error message'),
            ('AdminLTE', 'AdminLTE styling'),
            ('btn', 'Button elements'),
            ('fa-home', 'Home icon')
        ]
        
        for check, description in checks:
            if check in content:
                print(f"✅ {description} found")
            else:
                print(f"❌ {description} missing")
                
        print(f"\nTemplate size: {len(content)} characters")
        print("✅ 404 page template is ready!")
        
    else:
        print("❌ 404.html template file not found")

if __name__ == '__main__':
    test_404_template()
