"""
Verification script to check restored data
Run this after restoring tables to verify data integrity
"""
import os
import sys
import django

# Add the project directory to the Python path
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_path)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ndas.settings')
django.setup()

from patients.models import DiagnosisList, IndicationsForGMA


def verify_data():
    """Verify the restored data"""
    
    print("="*60)
    print("Data Verification Report")
    print("="*60)
    
    # Check DiagnosisList
    print("\n1. DiagnosisList Table")
    print("-" * 60)
    diagnosis_count = DiagnosisList.objects.count()
    print(f"   Total records: {diagnosis_count}")
    
    if diagnosis_count > 0:
        print(f"\n   Sample records (first 5):")
        for i, item in enumerate(DiagnosisList.objects.all()[:5], 1):
            print(f"   {i}. [{item.abr}] {item.title}")
    else:
        print("   ⚠ WARNING: No records found!")
    
    # Check IndicationsForGMA
    print("\n2. IndicationsForGMA Table")
    print("-" * 60)
    indications_count = IndicationsForGMA.objects.count()
    print(f"   Total records: {indications_count}")
    
    if indications_count > 0:
        # Count by level
        levels = IndicationsForGMA.objects.values_list('level', flat=True).distinct()
        print(f"\n   Breakdown by level:")
        for level in levels:
            count = IndicationsForGMA.objects.filter(level=level).count()
            print(f"   - {level}: {count} records")
        
        print(f"\n   Sample records (first 5):")
        for i, item in enumerate(IndicationsForGMA.objects.all()[:5], 1):
            title_preview = item.title[:50] + '...' if len(item.title) > 50 else item.title
            print(f"   {i}. [{item.level}] {title_preview}")
    else:
        print("   ⚠ WARNING: No records found!")
    
    # Summary
    print("\n" + "="*60)
    print("Verification Summary")
    print("="*60)
    print(f"DiagnosisList records: {diagnosis_count}")
    print(f"IndicationsForGMA records: {indications_count}")
    
    if diagnosis_count > 0 and indications_count > 0:
        print("\n✅ Data verification PASSED - All tables contain data")
        return True
    else:
        print("\n❌ Data verification FAILED - Some tables are empty")
        return False


def verify_expected_counts(expected_diagnosis=8, expected_indications=26):
    """Verify against expected record counts from backup"""
    
    print("\n" + "="*60)
    print("Expected Count Verification")
    print("="*60)
    
    diagnosis_count = DiagnosisList.objects.count()
    indications_count = IndicationsForGMA.objects.count()
    
    diagnosis_match = diagnosis_count == expected_diagnosis
    indications_match = indications_count == expected_indications
    
    status = "✅" if diagnosis_match else "⚠"
    print(f"{status} DiagnosisList: Expected {expected_diagnosis}, Found {diagnosis_count}")
    
    status = "✅" if indications_match else "⚠"
    print(f"{status} IndicationsForGMA: Expected {expected_indications}, Found {indications_count}")
    
    if diagnosis_match and indications_match:
        print("\n✅ All counts match expected values from backup")
        return True
    else:
        print("\n⚠ Warning: Record counts don't match backup")
        print("  This may be expected if you had existing records")
        return False


if __name__ == '__main__':
    try:
        print("\nRunning data verification...\n")
        
        # Basic verification
        basic_check = verify_data()
        
        # Expected count verification
        count_check = verify_expected_counts()
        
        print("\n" + "="*60)
        if basic_check:
            print("Verification completed successfully!")
        else:
            print("Verification found issues - please review above")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\nError during verification: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
