from django.db import migrations, models


def populate_short_name(apps, schema_editor):
    Institution = apps.get_model('institution', 'Institution')
    for inst in Institution.objects.filter(short_name=''):
        inst.short_name = inst.name[:10].upper()
        inst.save(update_fields=['short_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('institution', '0004_institution_logo_path_callable'),
    ]

    operations = [
        migrations.AddField(
            model_name='institution',
            name='short_name',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.RunPython(populate_short_name, migrations.RunPython.noop),
    ]
