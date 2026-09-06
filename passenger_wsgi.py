"""
Passenger WSGI entry point for cPanel shared hosting.

Copy this file to `passenger_wsgi.py` in the application root cPanel's
"Setup Python App" created for this domain (one app root per domain --
demo.ndas.lk and ndas.lk each need their own copy, with INTERP pointing at
THAT app's own virtualenv). A 500 error with nothing useful in the site's
own logs is often this file being missing, or INTERP pointing at the wrong
(or a nonexistent) virtualenv path.
"""

import sys
import os

# Point this at the virtualenv cPanel created for THIS app (Setup Python App
# page shows the exact path -- it differs per domain/app root).
INTERP = os.path.join(os.environ['HOME'], 'virtualenv', 'www.demo.ndas.lk', '3.11', 'bin', 'python3')
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Setup paths
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'ndas.settings'

# Import Django application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
