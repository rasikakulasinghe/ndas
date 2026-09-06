"""
One-command switcher between NDAS environment configurations.

Backs up the current root `.env` (if any), then copies the template that
matches the requested mode from `env files/` over it.

Usage:
    python scripts\\switch_env.py <mode>
    python scripts/switch_env.py <mode>

Modes (CLI arg uses hyphens; template filenames use dots -- mapping below):

    development            -> env files/.env.development.example
    production             -> env files/.env.production.example
    production-postgresql  -> env files/.env.production.postgresql.example
    production-demo        -> env files/.env.production.demo.example (demo.ndas.lk)
    production-live        -> env files/.env.production.live.example (ndas.lk)

production-demo and production-live are separate profiles for two domains
hosted under the same shared-hosting account but in SEPARATE application
roots (separate checkouts/venvs) -- run this script from within each app
root to switch that root's own .env.

For production-demo and production-live specifically, this also
(re)generates this app root's `passenger_wsgi.py` from
`passenger_wsgi.py.example`, filling in that domain's known cPanel venv
name/Python version (see PASSENGER_WSGI_INTERP below). This exists because
a hand-edited passenger_wsgi.py on demo.ndas.lk shipped with the INTERP
placeholder never replaced *and* two statements accidentally joined onto
one line -- both are silent Passenger-startup failures with nothing in
django.log. Generating the file removes that manual-editing step entirely.

This is a plain stdlib script, not a Django management command: settings.py
reads SECRET_KEY (and, when DB_ENGINE is set, the DB_* vars) via
decouple.config() with no default, so `python manage.py <anything>` crashes
before any command body runs if `.env` is missing or broken. This script has
no such bootstrap dependency, so it can repair a broken `.env`.
"""

import argparse
import os
import shutil
import sys
from datetime import datetime

# Setup paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_FILES_DIR = os.path.join(BASE_DIR, 'env files')
BACKUP_DIR = os.path.join(BASE_DIR, '.env_backups')
TARGET_ENV = os.path.join(BASE_DIR, '.env')
PASSENGER_WSGI_TEMPLATE = os.path.join(BASE_DIR, 'passenger_wsgi.py.example')
TARGET_PASSENGER_WSGI = os.path.join(BASE_DIR, 'passenger_wsgi.py')

# CLI mode -> template filename under `env files/`
MODE_TEMPLATES = {
    'development': '.env.development.example',
    'production': '.env.production.example',
    'production-postgresql': '.env.production.postgresql.example',
    'production-demo': '.env.production.demo.example',
    'production-live': '.env.production.live.example',
}

# Modes that point at a real production deployment (as opposed to
# development). Used to decide when to print the production review/reminder
# banners below -- keep in sync with MODE_TEMPLATES.
PRODUCTION_MODES = (
    'production',
    'production-postgresql',
    'production-demo',
    'production-live',
)

# Values the templates deliberately leave as placeholders/defaults, and that
# this script must never auto-fill. Not all of these are secrets (e.g.
# ALLOWED_HOSTS) -- the reminder heading below is worded accordingly.
PRODUCTION_REVIEW_ITEMS = (
    'SECRET_KEY',
    'DB_PASSWORD',
    'EMAIL_HOST_PASSWORD',
    'ALLOWED_HOSTS',
)

# cPanel "Setup Python App" venv name + Python version, per mode, for the
# modes that map to one specific known app root. This account's Python
# selector tops out at 3.11.15 (no 3.12+ offered), so both apps were
# recreated on 3.11 as of 2026-09-06 -- confirmed for demo.ndas.lk; verify
# ndas.lk's "Setup Python App" was also created under 3.11 before relying on
# this for production-live. requirements.txt is pinned to Django~=5.2.0 to
# match (Django 6.0 needs Python >=3.12, which this host doesn't offer).
# Only modes listed here get passenger_wsgi.py generated; modes without a
# fixed, known app root (development, production, production-postgresql)
# leave passenger_wsgi.py untouched.
PASSENGER_WSGI_INTERP = {
    'production-demo': ('www.demo.ndas.lk', '3.11'),
    'production-live': ('www.ndas.lk', '3.11'),
}

# The exact placeholder line in passenger_wsgi.py.example that INTERP
# substitution replaces. A named constant so a future rewording of the
# template breaks this loudly instead of silently leaving the placeholder
# in the generated file.
INTERP_PLACEHOLDER_LINE = (
    "INTERP = os.path.join(os.environ['HOME'], 'virtualenv', "
    "'ndas-CHANGE-ME', '3.11', 'bin', 'python3')"
)


class SwitchEnvError(Exception):
    """A step in switching .env failed before completion (.env untouched)."""


def build_parser():
    parser = argparse.ArgumentParser(
        prog='switch_env.py',
        description='Switch the root .env between NDAS environment configurations.',
        epilog=(
            'Mode -> template mapping:\n'
            '  development            -> env files/.env.development.example\n'
            '  production             -> env files/.env.production.example\n'
            '  production-postgresql  -> env files/.env.production.postgresql.example\n'
            '  production-demo        -> env files/.env.production.demo.example (demo.ndas.lk)\n'
            '  production-live        -> env files/.env.production.live.example (ndas.lk)\n'
            '\n'
            'production-demo/production-live also regenerate this app root\'s\n'
            'passenger_wsgi.py from passenger_wsgi.py.example with the correct INTERP.\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'mode',
        choices=sorted(MODE_TEMPLATES.keys()),
        help='Environment mode to switch to.',
    )
    return parser


def _unique_backup_path(name_prefix):
    """Compute a collision-safe backup path under BACKUP_DIR for name_prefix.

    The timestamp has only second-level granularity, so two switches within
    the same second would otherwise collide and one backup would silently
    clobber another -- violating the "never silently discarded" guarantee.
    Append an incrementing disambiguator suffix until the path is free.
    """
    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    candidate = os.path.join(BACKUP_DIR, f'{name_prefix}.{timestamp}.bak')
    suffix = 1
    while os.path.exists(candidate):
        candidate = os.path.join(BACKUP_DIR, f'{name_prefix}.{timestamp}-{suffix}.bak')
        suffix += 1
    return candidate


def _backup_existing_file(target_path, name_prefix):
    """Back up target_path (if present) to BACKUP_DIR.

    Returns the backup path, or None if there was nothing to back up.
    Raises SwitchEnvError if the backup directory can't be created or the
    backup copy fails -- target_path itself is never touched by this
    function.
    """
    if not os.path.exists(target_path):
        return None

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except OSError as exc:
        raise SwitchEnvError(
            f'could not create backup directory {BACKUP_DIR}: {exc}'
        ) from exc

    backup_path = _unique_backup_path(name_prefix)

    try:
        shutil.copyfile(target_path, backup_path)
    except OSError as exc:
        raise SwitchEnvError(
            f'could not write backup file {backup_path}: {exc}'
        ) from exc

    return backup_path


def backup_existing_env():
    """Back up the current root .env (if present) to .env_backups/.

    Returns the backup path, or None if there was no .env to back up.
    Raises SwitchEnvError if the backup directory can't be created or the
    backup copy fails -- .env itself is never touched by this function.
    """
    return _backup_existing_file(TARGET_ENV, '.env')


def render_passenger_wsgi(venv_name, python_version):
    """Return passenger_wsgi.py.example's content with INTERP filled in
    for the given cPanel venv name/Python version.

    Raises SwitchEnvError if the template is missing, or if its placeholder
    INTERP line has drifted from INTERP_PLACEHOLDER_LINE (so this function
    fails loudly instead of silently leaving the placeholder in place --
    which is exactly the bug that broke demo.ndas.lk).
    """
    if not os.path.isfile(PASSENGER_WSGI_TEMPLATE):
        raise SwitchEnvError(f'template not found: {PASSENGER_WSGI_TEMPLATE}')

    with open(PASSENGER_WSGI_TEMPLATE) as fh:
        content = fh.read()

    if INTERP_PLACEHOLDER_LINE not in content:
        raise SwitchEnvError(
            f'{PASSENGER_WSGI_TEMPLATE} no longer contains the expected '
            'INTERP placeholder line -- update INTERP_PLACEHOLDER_LINE in '
            'switch_env.py to match it.'
        )

    real_line = (
        "INTERP = os.path.join(os.environ['HOME'], 'virtualenv', "
        f"'{venv_name}', '{python_version}', 'bin', 'python3')"
    )
    return content.replace(INTERP_PLACEHOLDER_LINE, real_line)


def switch_passenger_wsgi(mode):
    """Generate this app root's passenger_wsgi.py for mode, if mode has a
    known cPanel venv name/Python version in PASSENGER_WSGI_INTERP.

    Returns (backup_path_or_None, venv_name, python_version) on success,
    or None if mode has no entry in PASSENGER_WSGI_INTERP (passenger_wsgi.py
    is left untouched). Raises SwitchEnvError on failure -- the existing
    passenger_wsgi.py, if any, is never touched by this function.
    """
    if mode not in PASSENGER_WSGI_INTERP:
        return None

    venv_name, python_version = PASSENGER_WSGI_INTERP[mode]
    rendered = render_passenger_wsgi(venv_name, python_version)

    backup_path = _backup_existing_file(TARGET_PASSENGER_WSGI, 'passenger_wsgi.py')

    try:
        with open(TARGET_PASSENGER_WSGI, 'w') as fh:
            fh.write(rendered)
    except OSError as exc:
        raise SwitchEnvError(
            f'could not write {TARGET_PASSENGER_WSGI}: {exc}'
        ) from exc

    return backup_path, venv_name, python_version


def switch_env(mode):
    template_name = MODE_TEMPLATES[mode]
    template_path = os.path.join(ENV_FILES_DIR, template_name)

    if not os.path.isfile(template_path):
        print(f'ERROR: template not found: {template_path}', file=sys.stderr)
        print('.env was left untouched.', file=sys.stderr)
        return 1

    try:
        backup_path = backup_existing_env()
    except SwitchEnvError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        print('.env was left untouched.', file=sys.stderr)
        return 1

    try:
        shutil.copyfile(template_path, TARGET_ENV)
    except OSError as exc:
        print(f'ERROR: could not write {TARGET_ENV}: {exc}', file=sys.stderr)
        if backup_path:
            print(
                'Your previous .env was already backed up to '
                f'{os.path.relpath(backup_path, BASE_DIR)} before this failure -- '
                'copy it back over .env to recover manually.',
                file=sys.stderr,
            )
        else:
            print(
                '.env did not exist before this run, so nothing needed backing up.',
                file=sys.stderr,
            )
        return 1

    print(f'Switched .env to "{mode}" mode.')
    print(f'  Template used: env files/{template_name}')
    if backup_path:
        print(f'  Previous .env backed up to: {os.path.relpath(backup_path, BASE_DIR)}')
    else:
        print('  No existing .env found -- created a new one (no backup needed).')

    if mode in PRODUCTION_MODES:
        print('')
        print('REMINDER: review these production values before deploying --')
        print('the template leaves them as placeholders/defaults, never auto-filled by this script:')
        for key in PRODUCTION_REVIEW_ITEMS:
            print(f'  - {key}')

    if mode == 'production-postgresql':
        print('')
        print('REMINDER: this mode points at a different database (PostgreSQL, not SQLite).')
        print('Run `python manage.py migrate` against it before relying on it -- switching')
        print('.env alone does not create or update its schema.')

    if mode in PASSENGER_WSGI_INTERP:
        try:
            passenger_backup_path, venv_name, python_version = switch_passenger_wsgi(mode)
        except SwitchEnvError as exc:
            print(f'ERROR: {exc}', file=sys.stderr)
            print(
                'passenger_wsgi.py was left untouched (the .env switch above still succeeded).',
                file=sys.stderr,
            )
            return 1

        print('')
        print(f'Generated passenger_wsgi.py for INTERP -> virtualenv/{venv_name}/{python_version}/bin/python3')
        if passenger_backup_path:
            print(f'  Previous passenger_wsgi.py backed up to: {os.path.relpath(passenger_backup_path, BASE_DIR)}')
        else:
            print('  No existing passenger_wsgi.py found -- created a new one (no backup needed).')

    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return switch_env(args.mode)


if __name__ == '__main__':
    sys.exit(main())
