# 📦 NDAS Table Backup & Restore - Complete Package

## ✅ Status: Backup Completed Successfully

**Date:** November 10, 2025  
**Tables:** `patients_diagnosislist`, `patients_indicationsforgma`  
**Total Records:** 34 (8 + 26)

---

## 📁 Files Included

### 🔧 Scripts
| File | Purpose |
|------|---------|
| `backup_tables.py` | Export tables to JSON |
| `restore_tables.py` | Import tables from JSON |
| `verify_restore.py` | Verify restored data |

### 📊 Data Backups
| File | Records | Description |
|------|---------|-------------|
| `backup_diagnosislist_20251110_175115.json` | 8 | Diagnosis codes & descriptions |
| `backup_indicationsforgma_20251110_175115.json` | 26 | GMA indication criteria |

### 📖 Documentation
| File | Content |
|------|---------|
| `TABLE_BACKUP_RESTORE_README.md` | Complete instructions |
| `BACKUP_SUMMARY.md` | Quick reference guide |
| `BACKUP_RESTORE_QUICKSTART.md` | This file |

---

## 🚀 Quick Start

### Option 1: Simple Restore (Recommended)

1. **Copy files to new host:**
   - `restore_tables.py`
   - `backup_diagnosislist_20251110_175115.json`
   - `backup_indicationsforgma_20251110_175115.json`
   - `verify_restore.py`

2. **Run restore:**
   ```powershell
   python restore_tables.py
   ```

3. **Verify:**
   ```powershell
   python verify_restore.py
   ```

### Option 2: Specify Files Explicitly

```powershell
python restore_tables.py --diagnosis backup_diagnosislist_20251110_175115.json --indications backup_indicationsforgma_20251110_175115.json
```

---

## 📋 Checklist

### Before Restore
- [ ] Django project set up on new host
- [ ] Database migrations completed (`python manage.py migrate`)
- [ ] At least one superuser created (`python manage.py createsuperuser`)
- [ ] Backup files copied to project root

### After Restore
- [ ] Run verification script
- [ ] Check Django admin interface
- [ ] Test data access in application

---

## 🎯 Expected Results

### DiagnosisList (8 records)
```
✅ Normal
✅ Fidgety movements (FMs)
✅ Hypokinesis (H)
✅ Poor repertoire (PR)
✅ Cramped synchronized (CS)
✅ Chaotic (CH)
✅ Absent Fidgety Movements (AF)
✅ Abnormal Fidgety Movements (AxF)
```

### IndicationsForGMA (26 records)
```
✅ High level: 16 records
✅ Medium level: 9 records
✅ Low level: 1 record
```

---

## 💡 Key Features

✨ **Smart Restore**
- Detects and updates existing records
- Won't create duplicates
- Auto-assigns user tracking fields

✨ **Error Handling**
- Continues on errors
- Detailed summary report
- Clear error messages

✨ **Flexible**
- Restore both tables together
- Restore single table
- Auto-detect latest backups

---

## 🔍 Verification Commands

### Quick Check
```powershell
python verify_restore.py
```

### Django Shell Check
```powershell
python manage.py shell
```

```python
from patients.models import DiagnosisList, IndicationsForGMA

# Count records
print(f"DiagnosisList: {DiagnosisList.objects.count()}")
print(f"IndicationsForGMA: {IndicationsForGMA.objects.count()}")

# View samples
for d in DiagnosisList.objects.all()[:3]:
    print(f"  {d.abr}: {d.title}")
```

---

## ⚠️ Important Notes

1. **Test First**: Always restore to development database first
2. **Backup Current**: Create backup of new host database before restore
3. **Superuser Required**: Ensure at least one superuser exists
4. **Location**: Run scripts from project root (where `manage.py` is)

---

## 📞 Troubleshooting

### "File not found"
- Ensure JSON files are in same directory as scripts
- Check file names match exactly

### "No module named 'patients'"
- Run from project root directory
- Verify Django settings are correct

### "No superuser found"
```powershell
python manage.py createsuperuser
```

### "Settings error"
- Check `DJANGO_SETTINGS_MODULE` in scripts
- Should be: `ndas.settings`

---

## 🔄 Creating New Backups

Anytime you need a fresh backup:

```powershell
python backup_tables.py
```

New timestamped files will be created without overwriting old ones.

---

## 📚 Additional Resources

For detailed information, see:
- **TABLE_BACKUP_RESTORE_README.md** - Full documentation
- **BACKUP_SUMMARY.md** - Backup details and data contents

---

## ✅ Success Indicators

After running `verify_restore.py`, you should see:

```
✅ Data verification PASSED - All tables contain data
✅ All counts match expected values from backup
✅ Verification completed successfully!
```

If you see these messages, your restore was successful! 🎉

---

**Ready to restore?** Start with copying the files to your new host and running `python restore_tables.py`
