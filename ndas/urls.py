from django.contrib import admin
from django.urls import path, include
from . import settings, views
from django.conf import settings
from institution.views import protected_media_view

admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_INDEX_TITLE

urlpatterns = [
    path("admin/", admin.site.urls),
    path("institution/", include("institution.urls")),  # must precede the root patients catch-all
    path("referral/", include("referral.urls")),
    path("users/", include("users.urls")),
    path("reports/", include("reports.urls")),
    path("problems/", include("problemlist.urls")),
    path("", include("patients.urls")),
    path("djrichtextfield/", include("djrichtextfield.urls")),
    path("video/", include("video.urls")),
    path("debug/bootstrap/", views.debug_bootstrap, name="debug-bootstrap"),
]

# Always routed through Django, in DEBUG and in production alike — this is
# what enforces institution isolation on patient videos/attachments/logos.
# Nginx must proxy_pass /media/ here rather than aliasing it to disk; see
# institution.views.protected_media_view and DEPLOYMENT.md §2.6.
urlpatterns += [
    path('media/<path:path>', protected_media_view, name='protected-media'),
]

# Custom error handlers
handler404 = "ndas.views.handler404"
handler500 = "ndas.views.handler500"
