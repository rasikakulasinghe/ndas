"""
Django management command to extract and populate video duration metadata for existing videos.

Usage:
    python manage.py fix_video_durations
    python manage.py fix_video_durations --dry-run
    python manage.py fix_video_durations --verbose
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from video.models import Video
from ndas.custom_codes.custom_methods import extract_video_metadata, simple_video_duration_estimate
import os
import logging


class Command(BaseCommand):
    help = 'Extract and populate video duration metadata for existing videos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each video processed',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-extract metadata even for videos that already have duration',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        force = options['force']

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        # Get videos that need duration extraction
        if force:
            videos = Video.objects.filter(video_file__isnull=False)
            self.stdout.write(f"Processing all {videos.count()} videos (force mode)")
        else:
            videos = Video.objects.filter(
                video_file__isnull=False,
                duration_seconds__isnull=True
            )
            self.stdout.write(f"Processing {videos.count()} videos without duration data")

        if not videos.exists():
            self.stdout.write(
                self.style.SUCCESS("No videos need duration extraction!")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        updated_count = 0
        error_count = 0
        skipped_count = 0

        for video in videos:
            try:
                # Check if video file exists
                if not video.video_file:
                    if verbose:
                        self.stdout.write(f"Skipping video {video.id}: No video file")
                    skipped_count += 1
                    continue

                try:
                    video_path = video.video_file.path
                except (ValueError, OSError):
                    if verbose:
                        self.stdout.write(f"Skipping video {video.id}: File path not accessible")
                    skipped_count += 1
                    continue

                if not os.path.exists(video_path):
                    if verbose:
                        self.stdout.write(f"Skipping video {video.id}: File does not exist at {video_path}")
                    skipped_count += 1
                    continue

                # Extract metadata
                metadata = extract_video_metadata(video_path)

                # If primary extraction fails, try estimation
                if not metadata:
                    if verbose:
                        self.stdout.write(f"Primary extraction failed for video {video.id}, trying estimation...")
                    metadata = simple_video_duration_estimate(video_path)

                if not metadata:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to extract or estimate metadata for video {video.id}: {video.title}")
                    )
                    error_count += 1
                    continue

                # Prepare update data
                update_fields = []
                changes = []

                if metadata.get('duration_seconds') and (force or not video.duration_seconds):
                    if not dry_run:
                        video.duration_seconds = metadata['duration_seconds']
                    update_fields.append('duration_seconds')
                    changes.append(f"duration: {metadata['duration_seconds']}s")

                if metadata.get('resolution') and (force or not video.resolution):
                    if not dry_run:
                        video.resolution = metadata['resolution']
                    update_fields.append('resolution')
                    changes.append(f"resolution: {metadata['resolution']}")

                if update_fields:
                    if not dry_run:
                        # Use update_fields to avoid triggering save logic again
                        video.save(update_fields=update_fields)

                    updated_count += 1
                    status = "Would update" if dry_run else "Updated"

                    if verbose or dry_run:
                        self.stdout.write(
                            f"{status} video {video.id} ({video.title}): {', '.join(changes)}"
                        )
                else:
                    if verbose:
                        self.stdout.write(f"No updates needed for video {video.id}: {video.title}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing video {video.id}: {str(e)}")
                )
                error_count += 1

        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write("SUMMARY:")

        if dry_run:
            self.stdout.write(f"Videos that would be updated: {updated_count}")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully updated: {updated_count} videos")
            )

        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f"Errors encountered: {error_count} videos")
            )

        if skipped_count > 0:
            self.stdout.write(f"Skipped (file issues): {skipped_count} videos")

        if not dry_run and updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"\nDuration extraction completed! {updated_count} videos updated.")
            )
        elif dry_run and updated_count > 0:
            self.stdout.write(
                self.style.WARNING(f"\nRun without --dry-run to apply these {updated_count} updates.")
            )