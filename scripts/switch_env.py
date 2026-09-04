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

# CLI mode -> template filename under `env files/`
MODE_TEMPLATES = {
    'development': '.env.development.example',
    'production': '.env.production.example',
    'production-postgresql': '.env.production.postgresql.example',
}

# Values the templates deliberately leave as placeholders/defaults, and that
# this script must never auto-fill. Not all of these are secrets (e.g.
# ALLOWED_HOSTS) -- the reminder heading below is worded accordingly.
PRODUCTION_REVIEW_ITEMS = (
    'SECRET_KEY',
    'DB_PASSWORD',
    'EMAIL_HOST_PASSWORD',
    'ALLOWED_HOSTS',
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
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'mode',
        choices=sorted(MODE_TEMPLATES.keys()),
        help='Environment mode to switch to.',
    )
    return parser


def _unique_backup_path():
    """Compute a collision-safe backup path under BACKUP_DIR.

    The timestamp has only second-level granularity, so two switches within
    the same second would otherwise collide and one backup would silently
    clobber another -- violating the "never silently discarded" guarantee.
    Append an incrementing disambiguator suffix until the path is free.
    """
    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    candidate = os.path.join(BACKUP_DIR, f'.env.{timestamp}.bak')
    suffix = 1
    while os.path.exists(candidate):
        candidate = os.path.join(BACKUP_DIR, f'.env.{timestamp}-{suffix}.bak')
        suffix += 1
    return candidate


def backup_existing_env():
    """Back up the current root .env (if present) to .env_backups/.

    Returns the backup path, or None if there was no .env to back up.
    Raises SwitchEnvError if the backup directory can't be created or the
    backup copy fails -- .env itself is never touched by this function.
    """
    if not os.path.exists(TARGET_ENV):
        return None

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except OSError as exc:
        raise SwitchEnvError(
            f'could not create backup directory {BACKUP_DIR}: {exc}'
        ) from exc

    backup_path = _unique_backup_path()

    try:
        shutil.copyfile(TARGET_ENV, backup_path)
    except OSError as exc:
        raise SwitchEnvError(
            f'could not write backup file {backup_path}: {exc}'
        ) from exc

    return backup_path


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

    if mode in ('production', 'production-postgresql'):
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

    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return switch_env(args.mode)


if __name__ == '__main__':
    sys.exit(main())
