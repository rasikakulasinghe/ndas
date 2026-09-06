"""
Passenger WSGI entry point for cPanel shared hosting.

Copy this file to `passenger_wsgi.py` in the application root cPanel's
"Setup Python App" created for this domain (one app root per domain --
demo.ndas.lk and ndas.lk each need their own copy). cPanel's "Setup Python
App" page already launches this file with the correct interpreter for the
venv/Python version configured for that specific app -- do not try to
re-exec a different interpreter here (see the incident note below).

A 500 error with nothing useful in django.log is often this file being
missing, or (per the 2026-09-06 demo.ndas.lk incident) this file trying to
manually re-exec a specific venv's Python via os.execl. That re-exec fought
Passenger's own interpreter selection and killed the app before Python ever
ran, with nothing but a stray "tput: No value for $TERM" line in the
Passenger log and no traceback anywhere -- removing the re-exec and just
importing the WSGI application directly fixed it. Keep this file this
simple; let cPanel's "Setup Python App" own the interpreter choice.
"""

import sys
import os

# Ensure this app root is importable regardless of Passenger's cwd.
sys.path.insert(0, os.path.dirname(__file__))

from ndas.wsgi import application  # noqa: E402  (import after sys.path setup, by design)
