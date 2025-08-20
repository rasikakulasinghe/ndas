"""
Management command to cleanup old user data for privacy compliance.
Run this command periodically to maintain GDPR compliance and keep the database clean.

Usage:
    python manage.py cleanup_user_data
    python manage.py cleanup_user_data --days 60  # Custom retention period
    python manage.py cleanup_user_data --dry-run  # Show what would be deleted
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from users.models import UserActivityLog, UserSession
from users.utils import cleanup_user_data


class Command(BaseCommand):
    help = 'Cleanup old user activity data for privacy compliance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to retain data (default: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--activity-only',
            action='store_true',
            help='Only cleanup activity logs, not sessions',
        )
        parser.add_argument(
            '--sessions-only',
            action='store_true',
            help='Only cleanup sessions, not activity logs',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        activity_only = options['activity_only']
        sessions_only = options['sessions_only']

        self.stdout.write(
            self.style.SUCCESS(f'Starting cleanup process for data older than {days} days...')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will actually be deleted')
            )

        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Cleanup activity logs
        if not sessions_only:
            old_activities = UserActivityLog.objects.filter(
                login_timestamp__lt=cutoff_date
            )
            activity_count = old_activities.count()
            
            if activity_count > 0:
                self.stdout.write(f'Found {activity_count} old activity records to delete')
                
                if not dry_run:
                    deleted_count = old_activities.delete()[0]
                    self.stdout.write(
                        self.style.SUCCESS(f'Deleted {deleted_count} activity records')
                    )
            else:
                self.stdout.write('No old activity records found')

        # Cleanup sessions
        if not activity_only:
            session_cutoff = timezone.now() - timedelta(days=30)  # Shorter retention for sessions
            old_sessions = UserSession.objects.filter(
                last_activity__lt=session_cutoff
            )
            session_count = old_sessions.count()
            
            if session_count > 0:
                self.stdout.write(f'Found {session_count} old session records to delete')
                
                if not dry_run:
                    deleted_count = old_sessions.delete()[0]
                    self.stdout.write(
                        self.style.SUCCESS(f'Deleted {deleted_count} session records')
                    )
            else:
                self.stdout.write('No old session records found')

        # Additional cleanup tasks
        if not dry_run and not activity_only and not sessions_only:
            # Clean up expired email verification tokens
            from users.models import CustomUser
            expired_tokens = CustomUser.objects.filter(
                email_verification_sent_at__lt=timezone.now() - timedelta(hours=48),
                is_email_verified=False
            ).exclude(email_verification_token='')
            
            if expired_tokens.exists():
                token_count = expired_tokens.count()
                expired_tokens.update(
                    email_verification_token='',
                    email_verification_sent_at=None
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Cleaned up {token_count} expired verification tokens')
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN COMPLETED - No data was actually deleted')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Cleanup completed successfully!')
            )

        # Show statistics
        self.show_statistics()

    def show_statistics(self):
        """Show current database statistics."""
        total_activities = UserActivityLog.objects.count()
        total_sessions = UserSession.objects.count()
        active_sessions = UserSession.objects.filter(is_active=True).count()
        
        recent_activities = UserActivityLog.objects.filter(
            login_timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write('DATABASE STATISTICS:')
        self.stdout.write('='*50)
        self.stdout.write(f'Total Activity Records: {total_activities}')
        self.stdout.write(f'Recent Activities (30 days): {recent_activities}')
        self.stdout.write(f'Total Session Records: {total_sessions}')
        self.stdout.write(f'Active Sessions: {active_sessions}')
        self.stdout.write('='*50)
