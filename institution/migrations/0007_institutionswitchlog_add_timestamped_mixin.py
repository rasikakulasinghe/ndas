# Manually written migration for F2 adversarial fix.
# Upgrades InstitutionSwitchLog to inherit TimeStampedModel + UserTrackingMixin:
#   - Removes switched_at (replaced by created_at from TimeStampedModel)
#   - Adds created_at, updated_at (TimeStampedModel)
#   - Adds added_by, last_edit_by (UserTrackingMixin)
#   - Updates Meta.ordering and Meta.indexes to use created_at

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("institution", "0006_institutionswitchlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add created_at with a one-off default of timezone.now for existing rows
        migrations.AddField(
            model_name="institutionswitchlog",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="Created At",
            ),
            preserve_default=False,
        ),
        # Add updated_at
        migrations.AddField(
            model_name="institutionswitchlog",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                verbose_name="Updated At",
            ),
        ),
        # Add added_by FK
        migrations.AddField(
            model_name="institutionswitchlog",
            name="added_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="institutionswitchlog_added",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Added By",
            ),
        ),
        # Add last_edit_by FK
        migrations.AddField(
            model_name="institutionswitchlog",
            name="last_edit_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="institutionswitchlog_last_edited",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Last Edited By",
            ),
        ),
        # Remove old index on (user, switched_at) BEFORE dropping switched_at column
        migrations.RemoveIndex(
            model_name="institutionswitchlog",
            name="institution_user_id_88b3ef_idx",
        ),
        # Remove switched_at (replaced by created_at)
        migrations.RemoveField(
            model_name="institutionswitchlog",
            name="switched_at",
        ),
        # Update Meta ordering to use created_at
        migrations.AlterModelOptions(
            name="institutionswitchlog",
            options={"ordering": ["-created_at"]},
        ),
        # Add new index on (user, created_at)
        migrations.AddIndex(
            model_name="institutionswitchlog",
            index=models.Index(
                fields=["user", "created_at"],
                name="institution_switch_user_created_idx",
            ),
        ),
    ]
