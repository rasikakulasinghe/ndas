"""
ndas/tests/test_logging_settings.py -- deferred-work ledger triage (batch 3)

Pins the LOGGING dict's security-log wiring: `security_file` is never
DEBUG-gated (the bug this batch fixed -- it used to drop every
django.security.* line whenever DEBUG=True), and `django.security`/
`users.middleware` share one handler list that includes `console` exactly
when DEBUG is on.

`LOGGING` is built once at settings-import time, from the real DEBUG value
in the environment -- NOT from `settings.DEBUG`, which Django's test runner
(`setup_test_environment`) force-overrides to `False` for the whole test
run regardless of the real value (a test-runner quirk, not an application
behavior). Comparing against `settings.DEBUG` here would therefore fail
under `manage.py test` even when LOGGING was built correctly, so the real
environment value is re-read directly via decouple, exactly as
`ndas/settings.py` itself reads it.
"""
from decouple import config
from django.conf import settings
from django.test import SimpleTestCase

REAL_DEBUG = config('DEBUG', default=False, cast=bool)


class SecurityLogHandlerTest(SimpleTestCase):
    def test_security_file_has_no_debug_gate(self):
        security_file = settings.LOGGING['handlers']['security_file']
        self.assertNotIn(
            'filters', security_file,
            "security_file must write regardless of DEBUG -- a 'filters' entry here "
            "(e.g. require_debug_false) would silently drop it in local dev again.",
        )

    def test_security_loggers_console_handler_matches_debug(self):
        for logger_name in ('django.security', 'users.middleware'):
            with self.subTest(logger=logger_name):
                handlers = settings.LOGGING['loggers'][logger_name]['handlers']
                self.assertIn('security_file', handlers)
                self.assertEqual(
                    'console' in handlers, REAL_DEBUG,
                    "console should be present iff DEBUG is on",
                )

    def test_security_and_middleware_loggers_share_the_same_handler_list(self):
        self.assertEqual(
            settings.LOGGING['loggers']['django.security']['handlers'],
            settings.LOGGING['loggers']['users.middleware']['handlers'],
        )

    def test_security_file_writes_to_the_expected_path(self):
        security_file = settings.LOGGING['handlers']['security_file']
        self.assertTrue(str(security_file['filename']).endswith('security.log'))
