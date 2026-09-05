"""
Automated regression tests for scripts/switch_env.py.

Stdlib `unittest` only -- no new dependency, matching switch_env.py's own
dependency-free style. Every test points switch_env's module-level path
constants (BASE_DIR, TARGET_ENV, BACKUP_DIR, ENV_FILES_DIR) at a throwaway
temp directory before calling into the script, and restores the originals
afterward, so nothing here ever touches the real repo `.env` or
`env files/`.

Run directly:
    python scripts/tests/test_switch_env.py
    python -m unittest scripts.tests.test_switch_env -v
"""

import contextlib
import importlib
import io
import os
import shutil
import sys
import tempfile
import unittest

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import switch_env  # noqa: E402  (import after sys.path setup, by design)


class SwitchEnvTestCase(unittest.TestCase):
    """Base case that sandboxes switch_env's module-level path constants."""

    def setUp(self):
        # Reload so each test starts from the script's real defaults before
        # we override them, in case an earlier test left globals mutated.
        importlib.reload(switch_env)

        self._orig_base_dir = switch_env.BASE_DIR
        self._orig_env_files_dir = switch_env.ENV_FILES_DIR
        self._orig_backup_dir = switch_env.BACKUP_DIR
        self._orig_target_env = switch_env.TARGET_ENV
        self._orig_passenger_template = switch_env.PASSENGER_WSGI_TEMPLATE
        self._orig_target_passenger = switch_env.TARGET_PASSENGER_WSGI

        self.tmpdir = tempfile.mkdtemp(prefix='switch_env_test_')
        self.env_files_dir = os.path.join(self.tmpdir, 'env files')
        self.backup_dir = os.path.join(self.tmpdir, '.env_backups')
        self.target_env = os.path.join(self.tmpdir, '.env')
        self.passenger_template = os.path.join(self.tmpdir, 'passenger_wsgi.py.example')
        self.target_passenger = os.path.join(self.tmpdir, 'passenger_wsgi.py')
        os.makedirs(self.env_files_dir, exist_ok=True)

        switch_env.BASE_DIR = self.tmpdir
        switch_env.ENV_FILES_DIR = self.env_files_dir
        switch_env.BACKUP_DIR = self.backup_dir
        switch_env.TARGET_ENV = self.target_env
        switch_env.PASSENGER_WSGI_TEMPLATE = self.passenger_template
        switch_env.TARGET_PASSENGER_WSGI = self.target_passenger

        # Fake templates, one per real mode, each with distinguishable
        # content so a mismatch is obvious.
        self.template_contents = {}
        for mode, filename in switch_env.MODE_TEMPLATES.items():
            content = f'# fake template for {mode}\nMODE={mode}\n'
            self.template_contents[mode] = content
            with open(os.path.join(self.env_files_dir, filename), 'w') as fh:
                fh.write(content)

        # Fake passenger_wsgi.py.example, using the real placeholder line so
        # render_passenger_wsgi()/switch_passenger_wsgi() can be exercised.
        with open(self.passenger_template, 'w') as fh:
            fh.write(
                'import sys\nimport os\n\n'
                f'{switch_env.INTERP_PLACEHOLDER_LINE}\n'
                'if sys.executable != INTERP:\n'
                '    os.execl(INTERP, INTERP, *sys.argv)\n'
            )

    def tearDown(self):
        switch_env.BASE_DIR = self._orig_base_dir
        switch_env.ENV_FILES_DIR = self._orig_env_files_dir
        switch_env.BACKUP_DIR = self._orig_backup_dir
        switch_env.TARGET_ENV = self._orig_target_env
        switch_env.PASSENGER_WSGI_TEMPLATE = self._orig_passenger_template
        switch_env.TARGET_PASSENGER_WSGI = self._orig_target_passenger
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # -- helpers ----------------------------------------------------------

    def _write_target_env(self, content):
        with open(self.target_env, 'w') as fh:
            fh.write(content)

    def _read_target_env(self):
        with open(self.target_env) as fh:
            return fh.read()

    def _backup_files(self):
        if not os.path.isdir(self.backup_dir):
            return []
        return sorted(os.listdir(self.backup_dir))

    @staticmethod
    def _run_main(argv):
        """Run switch_env.main(argv), capturing stdout/stderr and the
        return code (main() itself returns an int; argparse errors raise
        SystemExit instead -- both paths are normalized to (code, out, err))."""
        out, err = io.StringIO(), io.StringIO()
        code = None
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = switch_env.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()


class TestSwitchEachMode(SwitchEnvTestCase):
    """Existing .env gets backed up (original content preserved) and the
    new .env exactly matches that mode's template, for every mode."""

    def test_each_mode_backs_up_and_switches(self):
        for mode in switch_env.MODE_TEMPLATES:
            with self.subTest(mode=mode):
                original_content = f'# original .env before switching to {mode}\nMODE=previous\n'
                self._write_target_env(original_content)
                before_backups = set(self._backup_files())
                # A prior iteration (production-demo, earlier in dict order)
                # may have already created passenger_wsgi.py -- this run then
                # backs that up too, on top of the .env backup.
                expected_new_backups = 2 if (
                    mode in switch_env.PASSENGER_WSGI_INTERP and os.path.exists(self.target_passenger)
                ) else 1

                code, out, err = self._run_main([mode])

                self.assertEqual(code, 0, msg=f'stderr was: {err}')
                self.assertEqual(self._read_target_env(), self.template_contents[mode])

                new_backups = set(self._backup_files()) - before_backups
                self.assertEqual(
                    len(new_backups), expected_new_backups,
                    msg=f'expected {expected_new_backups} new backup file(s), got {new_backups}',
                )
                env_backup_name = next(name for name in new_backups if name.startswith('.env.'))
                with open(os.path.join(self.backup_dir, env_backup_name)) as fh:
                    self.assertEqual(fh.read(), original_content)

                if mode in switch_env.PASSENGER_WSGI_INTERP:
                    venv_name, python_version = switch_env.PASSENGER_WSGI_INTERP[mode]
                    self.assertTrue(os.path.isfile(self.target_passenger))
                    with open(self.target_passenger) as fh:
                        generated = fh.read()
                    self.assertNotIn('ndas-CHANGE-ME', generated)
                    self.assertIn(f"'{venv_name}', '{python_version}', 'bin', 'python3'", generated)
                else:
                    self.assertFalse(
                        os.path.exists(self.target_passenger),
                        msg=f'mode {mode!r} should not touch passenger_wsgi.py',
                    )

                # Clean up this iteration's .env for the next mode.
                os.remove(self.target_env)


class TestNoExistingEnv(SwitchEnvTestCase):
    def test_no_existing_env_creates_from_template_no_backup(self):
        self.assertFalse(os.path.exists(self.target_env))

        code, out, err = self._run_main(['development'])

        self.assertEqual(code, 0, msg=f'stderr was: {err}')
        self.assertTrue(os.path.exists(self.target_env))
        self.assertEqual(self._read_target_env(), self.template_contents['development'])
        self.assertEqual(self._backup_files(), [], 'no backup should be created when .env did not exist')


class TestUnknownOrMissingMode(SwitchEnvTestCase):
    def test_unknown_mode_leaves_env_untouched_and_exits_nonzero(self):
        original_content = 'MODE=untouched\n'
        self._write_target_env(original_content)

        code, out, err = self._run_main(['bogus-mode'])

        self.assertNotEqual(code, 0)
        self.assertEqual(self._read_target_env(), original_content)
        self.assertEqual(self._backup_files(), [])

    def test_missing_mode_argument_leaves_env_untouched_and_exits_nonzero(self):
        original_content = 'MODE=untouched\n'
        self._write_target_env(original_content)

        code, out, err = self._run_main([])

        self.assertNotEqual(code, 0)
        self.assertEqual(self._read_target_env(), original_content)
        self.assertEqual(self._backup_files(), [])

    def test_unknown_mode_with_no_env_leaves_it_absent(self):
        self.assertFalse(os.path.exists(self.target_env))

        code, out, err = self._run_main(['bogus-mode'])

        self.assertNotEqual(code, 0)
        self.assertFalse(os.path.exists(self.target_env))


class TestPassengerWsgiGeneration(SwitchEnvTestCase):
    """production-demo/production-live regenerate passenger_wsgi.py; other
    modes leave an existing one alone; failures are reported without
    touching the .env switch that already succeeded."""

    def test_second_switch_backs_up_previous_passenger_wsgi(self):
        self._write_target_env('MODE=previous\n')
        code, _, err = self._run_main(['production-demo'])
        self.assertEqual(code, 0, msg=f'stderr was: {err}')
        with open(self.target_passenger) as fh:
            first_generated = fh.read()

        code, _, err = self._run_main(['production-live'])
        self.assertEqual(code, 0, msg=f'stderr was: {err}')

        backups = self._backup_files()
        passenger_backups = [name for name in backups if name.startswith('passenger_wsgi.py.')]
        self.assertEqual(len(passenger_backups), 1)
        with open(os.path.join(self.backup_dir, passenger_backups[0])) as fh:
            self.assertEqual(fh.read(), first_generated)

        with open(self.target_passenger) as fh:
            second_generated = fh.read()
        self.assertIn("'www.ndas.lk', '3.8', 'bin', 'python3'", second_generated)

    def test_missing_passenger_template_fails_without_undoing_env_switch(self):
        os.remove(self.passenger_template)
        self._write_target_env('MODE=previous\n')

        code, out, err = self._run_main(['production-demo'])

        self.assertNotEqual(code, 0)
        self.assertIn('passenger_wsgi.py.example', err)
        # The .env switch itself already succeeded before the passenger step ran.
        self.assertEqual(self._read_target_env(), self.template_contents['production-demo'])
        self.assertFalse(os.path.exists(self.target_passenger))

    def test_drifted_placeholder_line_fails_loudly(self):
        with open(self.passenger_template, 'w') as fh:
            fh.write("INTERP = 'this template no longer matches the expected placeholder'\n")
        self._write_target_env('MODE=previous\n')

        code, out, err = self._run_main(['production-live'])

        self.assertNotEqual(code, 0)
        self.assertIn('INTERP_PLACEHOLDER_LINE', err)
        self.assertFalse(os.path.exists(self.target_passenger))

    def test_non_passenger_mode_leaves_existing_passenger_wsgi_untouched(self):
        with open(self.target_passenger, 'w') as fh:
            fh.write('# hand-maintained, not managed by switch_env\n')
        self._write_target_env('MODE=previous\n')

        code, _, err = self._run_main(['development'])

        self.assertEqual(code, 0, msg=f'stderr was: {err}')
        with open(self.target_passenger) as fh:
            self.assertEqual(fh.read(), '# hand-maintained, not managed by switch_env\n')
        passenger_backups = [name for name in self._backup_files() if name.startswith('passenger_wsgi.py.')]
        self.assertEqual(passenger_backups, [], 'a non-passenger mode must not touch passenger_wsgi.py at all')


class TestMissingTemplate(SwitchEnvTestCase):
    def test_missing_template_leaves_env_untouched_exit_1_names_path(self):
        original_content = 'MODE=untouched\n'
        self._write_target_env(original_content)

        missing_template_path = os.path.join(self.env_files_dir, switch_env.MODE_TEMPLATES['production'])
        os.remove(missing_template_path)

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = switch_env.switch_env('production')

        self.assertEqual(code, 1)
        self.assertEqual(self._read_target_env(), original_content)
        self.assertEqual(self._backup_files(), [], 'a failed switch must not leave a backup either')
        self.assertIn(missing_template_path, err.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
