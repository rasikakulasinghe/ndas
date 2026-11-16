from django.db import migrations


def sync_superuser_user_type(apps, schema_editor):
    """Backfill user_type=SUPERADMIN for all existing is_superuser=True rows.

    Covers superuser accounts created or re-saved between migration 0009
    (which did a one-time backfill at that point in time) and the
    CustomUser.save() override that now keeps this in sync going forward.
    """
    CustomUser = apps.get_model('users', 'CustomUser')
    CustomUser.objects.filter(is_superuser=True).exclude(user_type='SUPERADMIN').update(
        user_type='SUPERADMIN'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_alter_customuser_institution_and_more'),
    ]

    operations = [
        migrations.RunPython(
            sync_superuser_user_type,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
