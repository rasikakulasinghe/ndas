# Generated manually to rename subscription type from 'paid' to 'commercial'

from django.db import migrations


def rename_paid_to_commercial(apps, schema_editor):
    """
    Update all subscription records with type 'paid' to 'commercial'
    """
    Subscription = apps.get_model('users', 'Subscription')
    Subscription.objects.filter(subscription_type='paid').update(subscription_type='commercial')


def rename_commercial_to_paid(apps, schema_editor):
    """
    Reverse migration: Update all subscription records with type 'commercial' back to 'paid'
    """
    Subscription = apps.get_model('users', 'Subscription')
    Subscription.objects.filter(subscription_type='commercial').update(subscription_type='paid')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_alter_subscription_options_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_paid_to_commercial, rename_commercial_to_paid),
    ]
