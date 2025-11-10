"""
Backup script for DiagnosisList and IndicationsForGMA tables
This script exports the data to JSON format for migration to another host
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


def backup_data():
    """Backup DiagnosisList and IndicationsForGMA to JSON files"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Backup DiagnosisList
    print("Backing up DiagnosisList...")
    diagnosis_list = DiagnosisList.objects.all()
    diagnosis_data = []
    
    for item in diagnosis_list:
        diagnosis_data.append({
            'id': item.id,
            'abr': item.abr,
            'title': item.title,
            'description': item.description,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'updated_at': item.updated_at.isoformat() if item.updated_at else None,
        })
    
    diagnosis_filename = f'backup_diagnosislist_{timestamp}.json'
    with open(diagnosis_filename, 'w', encoding='utf-8') as f:
        json.dump(diagnosis_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ DiagnosisList backed up to {diagnosis_filename} ({len(diagnosis_data)} records)")
    
    # Backup IndicationsForGMA
    print("\nBacking up IndicationsForGMA...")
    indications_list = IndicationsForGMA.objects.all()
    indications_data = []
    
    for item in indications_list:
        indications_data.append({
            'id': item.id,
            'title': item.title,
            'level': item.level,
            'description': item.description,
            'created_at': item.created_at.isoformat() if item.created_at else None,
            'updated_at': item.updated_at.isoformat() if item.updated_at else None,
        })
    
    indications_filename = f'backup_indicationsforgma_{timestamp}.json'
    with open(indications_filename, 'w', encoding='utf-8') as f:
        json.dump(indications_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ IndicationsForGMA backed up to {indications_filename} ({len(indications_data)} records)")
    
    print(f"\n{'='*60}")
    print("Backup completed successfully!")
    print(f"{'='*60}")
    print(f"\nBackup files created:")
    print(f"  - {diagnosis_filename}")
    print(f"  - {indications_filename}")
    
    return diagnosis_filename, indications_filename


if __name__ == '__main__':
    try:
        backup_data()
    except Exception as e:
        print(f"Error during backup: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
