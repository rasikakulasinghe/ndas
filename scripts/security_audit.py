"""
Comprehensive security audit script for NDAS application.

Runs multiple security checks and generates a consolidated report.
"""

import os
import sys
import json
import subprocess
from datetime import datetime

# Setup paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SECURITY_DIR = os.path.join(BASE_DIR, 'security')

# Ensure security directory exists
os.makedirs(SECURITY_DIR, exist_ok=True)


def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def run_command(command, description):
    """
    Run a shell command and return the result.

    Args:
        command: Command to run (string or list)
        description: Description of what the command does

    Returns:
        tuple: (success, output, error)
    """
    print(f"🔍 {description}...")

    try:
        if isinstance(command, str):
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=BASE_DIR
            )
        else:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=BASE_DIR
            )

        if result.returncode == 0:
            print(f"   ✅ {description} - PASSED\n")
            return True, result.stdout, result.stderr
        else:
            print(f"   ⚠️  {description} - WARNINGS\n")
            return False, result.stdout, result.stderr

    except Exception as e:
        print(f"   ❌ {description} - FAILED: {str(e)}\n")
        return False, "", str(e)


def check_django_deployment():
    """Run Django deployment check."""
    print_header("DJANGO DEPLOYMENT CHECK")

    success, output, error = run_command(
        f'cd "{BASE_DIR}" && python manage.py check --deploy',
        "Running Django deployment security checks"
    )

    # Save output
    output_file = os.path.join(SECURITY_DIR, 'django_deployment_check.txt')
    with open(output_file, 'w') as f:
        f.write(f"Django Deployment Check - {datetime.now().isoformat()}\n")
        f.write("=" * 70 + "\n\n")
        f.write(output)
        if error:
            f.write("\n\nErrors:\n")
            f.write(error)

    print(f"📄 Results saved to: {output_file}")

    # Analyze results
    issues = []
    if "WARNING" in output or "ERROR" in output:
        for line in output.split('\n'):
            if "WARNING" in line or "ERROR" in line:
                issues.append(line.strip())

    return {
        'name': 'Django Deployment Check',
        'status': 'PASSED' if success else 'WARNINGS',
        'issues_found': len(issues),
        'issues': issues,
        'output_file': output_file
    }


def run_security_tests():
    """Run security test suite."""
    print_header("SECURITY TEST SUITE")

    success, output, error = run_command(
        f'cd "{BASE_DIR}" && python manage.py test tests.test_security --verbosity=2',
        "Running comprehensive security tests"
    )

    # Save output
    output_file = os.path.join(SECURITY_DIR, 'security_tests_results.txt')
    with open(output_file, 'w') as f:
        f.write(f"Security Tests Results - {datetime.now().isoformat()}\n")
        f.write("=" * 70 + "\n\n")
        f.write(output)
        if error:
            f.write("\n\nErrors:\n")
            f.write(error)

    print(f"📄 Results saved to: {output_file}")

    # Parse test results
    test_count = output.count('test_')
    failures = output.count('FAIL')
    errors = output.count('ERROR')

    return {
        'name': 'Security Test Suite',
        'status': 'PASSED' if success else 'FAILED',
        'tests_run': test_count,
        'failures': failures,
        'errors': errors,
        'output_file': output_file
    }


def check_file_permissions():
    """Check critical file permissions."""
    print_header("FILE PERMISSIONS CHECK")

    critical_files = [
        '.env',
        'ndas/settings.py',
        'db.sqlite3',
    ]

    issues = []

    for file_path in critical_files:
        full_path = os.path.join(BASE_DIR, file_path)
        if os.path.exists(full_path):
            # Check if file is readable by others (on Unix-like systems)
            try:
                stat_info = os.stat(full_path)
                mode = stat_info.st_mode

                # Check if file has world-readable permissions
                if mode & 0o004:
                    issues.append(f"{file_path} is world-readable")
                    print(f"   ⚠️  {file_path} is world-readable")
                else:
                    print(f"   ✅ {file_path} permissions OK")
            except Exception as e:
                print(f"   ⚠️  Could not check {file_path}: {e}")
        else:
            print(f"   ℹ️  {file_path} not found (may be OK)")

    return {
        'name': 'File Permissions Check',
        'status': 'PASSED' if len(issues) == 0 else 'WARNINGS',
        'issues_found': len(issues),
        'issues': issues
    }


def check_security_settings():
    """Check security-related Django settings."""
    print_header("SECURITY SETTINGS CHECK")

    # Import Django settings
    sys.path.insert(0, BASE_DIR)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ndas.settings')

    try:
        from django.conf import settings

        checks = []

        # Check CSRF protection
        checks.append({
            'name': 'CSRF_COOKIE_SECURE',
            'value': getattr(settings, 'CSRF_COOKIE_SECURE', False),
            'expected': 'True in production',
            'status': '✅' if not settings.DEBUG or getattr(settings, 'CSRF_COOKIE_SECURE', False) else '⚠️'
        })

        checks.append({
            'name': 'SESSION_COOKIE_SECURE',
            'value': getattr(settings, 'SESSION_COOKIE_SECURE', False),
            'expected': 'True in production',
            'status': '✅' if not settings.DEBUG or getattr(settings, 'SESSION_COOKIE_SECURE', False) else '⚠️'
        })

        checks.append({
            'name': 'SECURE_HSTS_SECONDS',
            'value': getattr(settings, 'SECURE_HSTS_SECONDS', 0),
            'expected': '> 0',
            'status': '✅' if getattr(settings, 'SECURE_HSTS_SECONDS', 0) > 0 else '⚠️'
        })

        checks.append({
            'name': 'SECURE_CONTENT_TYPE_NOSNIFF',
            'value': getattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF', False),
            'expected': 'True',
            'status': '✅' if getattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF', False) else '❌'
        })

        checks.append({
            'name': 'SECURE_BROWSER_XSS_FILTER',
            'value': getattr(settings, 'SECURE_BROWSER_XSS_FILTER', False),
            'expected': 'True',
            'status': '✅' if getattr(settings, 'SECURE_BROWSER_XSS_FILTER', False) else '❌'
        })

        checks.append({
            'name': 'DEBUG',
            'value': settings.DEBUG,
            'expected': 'False in production',
            'status': '✅' if not settings.DEBUG else '⚠️ (development mode)'
        })

        # Print results
        for check in checks:
            print(f"   {check['status']} {check['name']}: {check['value']} (expected: {check['expected']})")

        # Count issues
        issues = [c for c in checks if c['status'] != '✅']

        return {
            'name': 'Security Settings Check',
            'status': 'PASSED' if len(issues) == 0 else 'WARNINGS',
            'checks': checks,
            'issues_found': len(issues)
        }

    except Exception as e:
        print(f"   ❌ Error checking settings: {e}")
        return {
            'name': 'Security Settings Check',
            'status': 'ERROR',
            'error': str(e)
        }


def generate_audit_report(results):
    """Generate comprehensive audit report."""
    print_header("SECURITY AUDIT REPORT")

    # Create report
    report = {
        'audit_date': datetime.now().isoformat(),
        'project': 'NDAS - Neurodevelopmental Assessment System',
        'audit_type': 'Comprehensive Security Audit',
        'results': results
    }

    # Save JSON report
    json_file = os.path.join(SECURITY_DIR, 'security_audit_report.json')
    with open(json_file, 'w') as f:
        json.dump(report, f, indent=2)

    # Create markdown report
    md_file = os.path.join(SECURITY_DIR, 'security_audit_report.md')
    with open(md_file, 'w') as f:
        f.write(f"# NDAS Security Audit Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Project:** Neurodevelopmental Assessment System (NDAS)\n")
        f.write(f"**Audit Type:** Comprehensive Security Audit\n\n")
        f.write(f"---\n\n")

        f.write(f"## Executive Summary\n\n")

        # Count statuses
        passed = sum(1 for r in results if r.get('status') == 'PASSED')
        warnings = sum(1 for r in results if r.get('status') == 'WARNINGS')
        failed = sum(1 for r in results if r.get('status') == 'FAILED')

        f.write(f"- **Total Checks:** {len(results)}\n")
        f.write(f"- **Passed:** {passed} ✅\n")
        f.write(f"- **Warnings:** {warnings} ⚠️\n")
        f.write(f"- **Failed:** {failed} ❌\n\n")

        # Overall status
        if failed > 0:
            f.write(f"**Overall Status:** ❌ FAILED (Critical issues found)\n\n")
        elif warnings > 0:
            f.write(f"**Overall Status:** ⚠️ WARNINGS (Issues need attention)\n\n")
        else:
            f.write(f"**Overall Status:** ✅ PASSED (No critical issues)\n\n")

        f.write(f"---\n\n")
        f.write(f"## Detailed Results\n\n")

        # Write each result
        for result in results:
            f.write(f"### {result['name']}\n\n")
            f.write(f"**Status:** {result['status']}\n\n")

            if 'issues_found' in result:
                f.write(f"**Issues Found:** {result['issues_found']}\n\n")

            if 'issues' in result and result['issues']:
                f.write(f"**Issues:**\n\n")
                for issue in result['issues']:
                    f.write(f"- {issue}\n")
                f.write(f"\n")

            if 'output_file' in result:
                f.write(f"**Detailed Output:** `{result['output_file']}`\n\n")

            f.write(f"---\n\n")

    print(f"✅ Security audit report generated:")
    print(f"   📄 JSON: {json_file}")
    print(f"   📄 Markdown: {md_file}")

    # Print summary
    print(f"\n{'='*70}")
    print(f"  AUDIT SUMMARY")
    print(f"{'='*70}")
    print(f"  Total Checks:  {len(results)}")
    print(f"  Passed:        {passed} ✅")
    print(f"  Warnings:      {warnings} ⚠️")
    print(f"  Failed:        {failed} ❌")
    print(f"{'='*70}\n")

    return report


def main():
    """Main security audit function."""
    print("\n" + "=" * 70)
    print("  NDAS SECURITY AUDIT")
    print("=" * 70)
    print(f"\n📅 Audit Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Base Directory: {BASE_DIR}")
    print(f"📁 Security Reports: {SECURITY_DIR}\n")

    results = []

    # Run all checks
    try:
        results.append(check_security_settings())
        results.append(check_file_permissions())
        results.append(check_django_deployment())
        results.append(run_security_tests())

    except KeyboardInterrupt:
        print("\n\n⚠️  Security audit interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Security audit failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Generate report
    report = generate_audit_report(results)

    # Determine exit code
    failed_count = sum(1 for r in results if r.get('status') == 'FAILED')

    if failed_count > 0:
        print("❌ Security audit completed with FAILURES\n")
        return 1
    else:
        print("✅ Security audit completed successfully\n")
        return 0


if __name__ == '__main__':
    sys.exit(main())
