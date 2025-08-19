# Performance Optimization Recommendations for NDAS

# 1. Optimized Views with Query Optimization
"""
Replace existing views in patients/views.py with optimized versions:
"""

# Example: Optimized patient_view function
def patient_view_optimized(request, pk):
    """Optimized version with select_related and prefetch_related"""
    selected_patient = Patient.objects.select_related(
        'added_by', 'last_edit_by'
    ).prefetch_related(
        'indecation_for_gma',
        'video_set',
        'attachment_set',
        'gmassessment_set',
        'hineassessment_set',
        'developmentalassessment_set',
        'cdicrecord_set'
    ).get(id=pk)
    
    # Use the prefetched data instead of separate queries
    file_videos = selected_patient.video_set.all()[:5]
    file_video_count = selected_patient.video_set.count()
    
    # Continue with optimized queries...

# 2. Database Indexes
"""
Add these to your models for better query performance:
"""

class Patient(models.Model):
    bht = models.CharField(max_length=20, unique=True, null=True, blank=True, default=None, db_index=True)
    nnc_no = models.CharField(max_length=20, unique=True, null=True, blank=True, default=None, db_index=True)
    baby_name = models.CharField(verbose_name="Name of the baby", max_length=100, null=False, blank=False, db_index=True)
    mother_name = models.CharField(verbose_name="Name of the mother", max_length=100, null=False, blank=False, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['baby_name', 'mother_name']),
            models.Index(fields=['added_on']),
            models.Index(fields=['dob_tob']),
        ]

# 3. Caching Strategy
"""
Add to settings.py:
"""
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'TIMEOUT': 300,  # 5 minutes default
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache frequently accessed data
from django.core.cache import cache

def get_patient_stats():
    stats = cache.get('patient_stats')
    if stats is None:
        stats = {
            'total_patients': Patient.objects.count(),
            'diagnosed_patients': Patient.objects.filter(gmassessment__isnull=False).count(),
            # ... other stats
        }
        cache.set('patient_stats', stats, 3600)  # Cache for 1 hour
    return stats

# 4. Pagination Optimization
"""
Use Cursor Pagination for large datasets:
"""
from django.core.paginator import Paginator
from django.db.models import Q

def optimized_patient_list(request):
    # Use only() to fetch only needed fields
    patients = Patient.objects.only(
        'id', 'bht', 'baby_name', 'mother_name', 'added_on'
    ).order_by('-id')
    
    paginator = Paginator(patients, 25)  # Increase page size
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'patients/list.html', {'page_obj': page_obj})

# 5. File Upload Optimization
"""
Implement chunked file uploads for large files:
"""
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

def handle_large_file_upload(uploaded_file, patient_id):
    """Handle large file uploads in chunks"""
    chunk_size = 1024 * 1024  # 1MB chunks
    
    file_path = f"uploads/patient_{patient_id}/{uploaded_file.name}"
    
    with default_storage.open(file_path, 'wb') as destination:
        for chunk in uploaded_file.chunks(chunk_size):
            destination.write(chunk)
    
    return file_path

# 6. Query Set Optimization
"""
Replace inefficient queries:
"""

# Instead of:
patients = Patient.objects.all()
for patient in patients:
    videos = patient.video_set.all()  # N+1 query problem

# Use:
patients = Patient.objects.prefetch_related('video_set').all()
for patient in patients:
    videos = patient.video_set.all()  # Uses prefetched data

# 7. Static Files Optimization
"""
Configure static files for production:
"""
# In settings.py
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Use CDN for static files in production
if not DEBUG:
    STATIC_URL = 'https://your-cdn-domain.com/static/'

print("Performance optimization guidelines created.")
print("Implement these changes gradually and test thoroughly.")
