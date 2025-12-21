"""
Restore script for DiagnosisList and IndicationsForGMA tables
This script imports the data from JSON backup files
"""
import os
import sys
import django
import json
from datetime import datetime

# Add the project directory to the Python path
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_path)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ndas.settings')
django.setup()

from patients.models import DiagnosisList, IndicationsForGMA
from django.contrib.auth import get_user_model

User = get_user_model()


def restore_diagnosislist(filename):
    """Restore DiagnosisList from JSON backup"""
    
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found!")
        return False
    
    print(f"Restoring DiagnosisList from {filename}...")
    
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get first superuser as fallback for tracking fields
    try:
        fallback_user = User.objects.filter(is_superuser=True).first()
    except:
        fallback_user = None
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for item_data in data:
        item_id = item_data.get('id')
        
        # Try to find existing record by id or title
        existing = None
        if item_id:
            try:
                existing = DiagnosisList.objects.get(id=item_id)
            except DiagnosisList.DoesNotExist:
                pass
        
        if not existing:
            # Try to find by abbreviation (abr)
            try:
                existing = DiagnosisList.objects.filter(abr=item_data['abr']).first()
            except:
                pass
        
        if existing:
            # Update existing record
            existing.abr = item_data['abr']
            existing.title = item_data['title']
            existing.description = item_data['description']
            existing.save()
            updated_count += 1
            print(f"  ✓ Updated: {item_data['title'][:50]}...")
        else:
            # Create new record
            try:
                new_item = DiagnosisList(
                    abr=item_data['abr'],
                    title=item_data['title'],
                    description=item_data['description'],
                )
                # Set user tracking fields if available
                if fallback_user:
                    new_item.added_by = fallback_user
                    new_item.last_edit_by = fallback_user
                
                new_item.save()
                created_count += 1
                print(f"  ✓ Created: {item_data['title'][:50]}...")
            except Exception as e:
                print(f"  ✗ Error creating {item_data['title'][:50]}: {str(e)}")
                skipped_count += 1
    
    print(f"\nDiagnosisList restore summary:")
    print(f"  Created: {created_count}")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total processed: {len(data)}")
    
    return True


def restore_indicationsforgma(filename):
    """Restore IndicationsForGMA from JSON backup"""
    
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found!")
        return False
    
    print(f"\nRestoring IndicationsForGMA from {filename}...")
    
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get first superuser as fallback for tracking fields
    try:
        fallback_user = User.objects.filter(is_superuser=True).first()
    except:
        fallback_user = None
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for item_data in data:
        item_id = item_data.get('id')
        
        # Try to find existing record by id or title
        existing = None
        if item_id:
            try:
                existing = IndicationsForGMA.objects.get(id=item_id)
            except IndicationsForGMA.DoesNotExist:
                pass
        
        if not existing:
            # Try to find by title
            try:
                existing = IndicationsForGMA.objects.filter(title=item_data['title']).first()
            except:
                pass
        
        if existing:
            # Update existing record
            existing.title = item_data['title']
            existing.level = item_data['level']
            existing.description = item_data.get('description', '')
            existing.save()
            updated_count += 1
            print(f"  ✓ Updated: {item_data['title'][:50]}...")
        else:
            # Create new record
            try:
                new_item = IndicationsForGMA(
                    title=item_data['title'],
                    level=item_data['level'],
                    description=item_data.get('description', ''),
                )
                # Set user tracking fields if available
                if fallback_user:
                    new_item.added_by = fallback_user
                    new_item.last_edit_by = fallback_user
                
                new_item.save()
                created_count += 1
                print(f"  ✓ Created: {item_data['title'][:50]}...")
            except Exception as e:
                print(f"  ✗ Error creating {item_data['title'][:50]}: {str(e)}")
                skipped_count += 1
    
    print(f"\nIndicationsForGMA restore summary:")
    print(f"  Created: {created_count}")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total processed: {len(data)}")
    
    return True


def restore_data(diagnosis_file=None, indications_file=None):
    """Restore both tables from backup files"""
    
    print(f"{'='*60}")
    print("NDAS Table Restore Utility")
    print(f"{'='*60}\n")
    
    # If no files specified, look for most recent backup files
    if not diagnosis_file:
        import glob
        diagnosis_files = sorted(glob.glob('backup_diagnosislist_*.json'), reverse=True)
        if diagnosis_files:
            diagnosis_file = diagnosis_files[0]
            print(f"Using most recent DiagnosisList backup: {diagnosis_file}")
        else:
            print("No DiagnosisList backup files found!")
            return False
    
    if not indications_file:
        import glob
        indications_files = sorted(glob.glob('backup_indicationsforgma_*.json'), reverse=True)
        if indications_files:
            indications_file = indications_files[0]
            print(f"Using most recent IndicationsForGMA backup: {indications_file}")
        else:
            print("No IndicationsForGMA backup files found!")
            return False
    
    print("\n" + "="*60)
    
    success = True
    
    # Restore DiagnosisList
    if diagnosis_file:
        if not restore_diagnosislist(diagnosis_file):
            success = False
    
    # Restore IndicationsForGMA
    if indications_file:
        if not restore_indicationsforgma(indications_file):
            success = False
    
    print(f"\n{'='*60}")
    if success:
        print("Restore completed successfully!")
    else:
        print("Restore completed with errors!")
    print(f"{'='*60}\n")
    
    return success


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Restore DiagnosisList and IndicationsForGMA tables')
    parser.add_argument('--diagnosis', help='Path to DiagnosisList JSON backup file')
    parser.add_argument('--indications', help='Path to IndicationsForGMA JSON backup file')
    
    args = parser.parse_args()
    
    try:
        restore_data(args.diagnosis, args.indications)
    except Exception as e:
        print(f"Error during restore: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
