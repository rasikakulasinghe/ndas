"""
Story 3.3 — Update Institution.logo upload_to to use institution-aware callable.
This migration captures the change from 'institution_logos/' string to
get_institution_logo_path callable. No database schema change occurs.
"""
import ndas.custom_codes.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('institution', '0003_patientmovelog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='institution',
            name='logo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=ndas.custom_codes.validators.get_institution_logo_path,
            ),
        ),
    ]
