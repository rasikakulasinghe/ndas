# Table Backup and Restore Guide

This guide explains how to backup and restore the `patients_diagnosislist` and `patients_indicationsforgma` tables for migration to a new host.

## Files Created

1. **backup_tables.py** - Script to export tables to JSON
2. **restore_tables.py** - Script to import tables from JSON
3. **backup_diagnosislist_[timestamp].json** - DiagnosisList data backup
4. **backup_indicationsforgma_[timestamp].json** - IndicationsForGMA data backup

---

## Backup Process (Current Host)

### Step 1: Run the Backup Script

```powershell
python backup_tables.py
```

This will create two timestamped JSON files:
- `backup_diagnosislist_YYYYMMDD_HHMMSS.json`
- `backup_indicationsforgma_YYYYMMDD_HHMMSS.json`

### Step 2: Transfer Files to New Host

Copy the following files to the new host:
1. `backup_tables.py` (optional, for future backups)
2. `restore_tables.py`
3. `backup_diagnosislist_[timestamp].json`
4. `backup_indicationsforgma_[timestamp].json`
5. This README file

---

## Restore Process (New Host)

### Prerequisites

1. Django project must be fully set up on the new host
2. Database migrations must be completed (`python manage.py migrate`)
3. At least one superuser must exist (for tracking fields)

### Method 1: Auto-detect Latest Backups

Place the backup JSON files in the project root directory and run:

```powershell
python restore_tables.py
```

The script will automatically find and use the most recent backup files.

### Method 2: Specify Backup Files

Explicitly specify which backup files to restore:

```powershell
python restore_tables.py --diagnosis backup_diagnosislist_20251110_175115.json --indications backup_indicationsforgma_20251110_175115.json
```

### Method 3: Restore Individual Tables

Restore only DiagnosisList:
```powershell
python restore_tables.py --diagnosis backup_diagnosislist_20251110_175115.json
```

Restore only IndicationsForGMA:
```powershell
python restore_tables.py --indications backup_indicationsforgma_20251110_175115.json
```

---

## How the Restore Works

### Smart Duplicate Detection

The restore script intelligently handles existing data:

**DiagnosisList:**
- First tries to match by ID
- If not found, matches by abbreviation (abr)
- Updates existing records or creates new ones

**IndicationsForGMA:**
- First tries to match by ID
- If not found, matches by title
- Updates existing records or creates new ones

### User Tracking

The script automatically:
- Uses the first superuser account for `added_by` and `last_edit_by` fields
- Maintains data integrity with proper user tracking

### Summary Output

After completion, you'll see:
```
DiagnosisList restore summary:
  Created: X
  Updated: Y
  Skipped: Z
  Total processed: N

IndicationsForGMA restore summary:
  Created: X
  Updated: Y
  Skipped: Z
  Total processed: N
```

---

## Troubleshooting

### Issue: "File not found"
**Solution:** Ensure the JSON backup files are in the same directory as `restore_tables.py`

### Issue: "No superuser found"
**Solution:** Create a superuser first:
```powershell
python manage.py createsuperuser
```

### Issue: "Module not found"
**Solution:** Ensure you're running from the project root directory where `manage.py` is located

### Issue: Django settings error
**Solution:** Verify the `DJANGO_SETTINGS_MODULE` path in the script matches your project structure (default: `ndas.settings`)

---

## Data Structure

### DiagnosisList Fields
- `id` - Primary key
- `abr` - Abbreviation (unique identifier)
- `title` - Full diagnosis title
- `description` - Detailed description
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

### IndicationsForGMA Fields
- `id` - Primary key
- `title` - Indication title
- `level` - Indication level (from LEVEL_OF_INDICATION choices)
- `description` - Detailed description
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

---

## Best Practices

1. **Always test restore on a development database first**
2. **Create a database backup before running restore**
3. **Keep backup files with timestamps for version tracking**
4. **Verify data after restore using Django admin or database queries**

### Verification Commands

After restore, verify the data:

```powershell
# Check record counts
python manage.py shell
```

Then in the Django shell:
```python
from patients.models import DiagnosisList, IndicationsForGMA

print(f"DiagnosisList count: {DiagnosisList.objects.count()}")
print(f"IndicationsForGMA count: {IndicationsForGMA.objects.count()}")

# View first few records
print("\nDiagnosisList samples:")
for item in DiagnosisList.objects.all()[:3]:
    print(f"  - {item.abr}: {item.title}")

print("\nIndicationsForGMA samples:")
for item in IndicationsForGMA.objects.all()[:3]:
    print(f"  - {item.title} ({item.level})")
```

---

## Quick Reference

### Backup Commands
```powershell
# Create backup
python backup_tables.py
```

### Restore Commands
```powershell
# Auto-detect and restore
python restore_tables.py

# Specify files
python restore_tables.py --diagnosis FILE1.json --indications FILE2.json

# Restore single table
python restore_tables.py --diagnosis FILE1.json
python restore_tables.py --indications FILE2.json
```

---

## Support

For issues or questions, refer to the main project documentation or contact the development team.

**Created:** November 10, 2025  
**Project:** NDAS - Neurodevelopmental Assessment System
