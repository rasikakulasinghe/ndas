# Generated migration for standardize-model-tracking-mixins
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('problemlist', '0001_initial'),
    ]

    operations = [
        # Add created_at field (nullable first to handle existing rows)
        migrations.AddField(
            model_name='problemaction',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True,
                null=True,
                blank=True,
                verbose_name='Created At',
                help_text='When this record was created',
            ),
        ),
        # Add updated_at field (nullable first to handle existing rows)
        migrations.AddField(
            model_name='problemaction',
            name='updated_at',
            field=models.DateTimeField(
                auto_now=True,
                null=True,
                blank=True,
                verbose_name='Updated At',
                help_text='When this record was last updated',
            ),
        ),
        # Add added_by field (nullable - user tracking is optional for existing records)
        migrations.AddField(
            model_name='problemaction',
            name='added_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who created this record',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='problemaction_added',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Added By',
            ),
        ),
        # Add last_edit_by field (nullable - user tracking is optional for existing records)
        migrations.AddField(
            model_name='problemaction',
            name='last_edit_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who last modified this record',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='problemaction_last_edited',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Last Edited By',
            ),
        ),
    ]
