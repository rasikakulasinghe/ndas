import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('institution', '0004_institution_logo_path_callable'),
        ('patients', '0010_alter_patient_institution'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReferralSent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this record was created', verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='When this record was last updated', verbose_name='Updated At')),
                ('referral_uuid', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Shared with ReferralReceived. Generated once at creation; never regenerated.', unique=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('REPLIED', 'Replied'), ('CLOSED', 'Closed')], default='PENDING', max_length=20)),
                ('initial_message', models.TextField(help_text='The referral message from the sending clinician.')),
                ('snapshot_data', models.JSONField(default=dict, help_text='Frozen patient record snapshot at referral submission time. Do not modify after creation.')),
                ('outcome', models.TextField(blank=True, help_text='Clinical outcome note, added at closure.')),
                ('added_by', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referralsent_added', to=settings.AUTH_USER_MODEL, verbose_name='Added By')),
                ('last_edit_by', models.ForeignKey(blank=True, help_text='User who last modified this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referralsent_last_edited', to=settings.AUTH_USER_MODEL, verbose_name='Last Edited By')),
                ('from_institution', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_sent', to='institution.institution')),
                ('to_institution', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_received_at', to='institution.institution')),
                ('patient', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_sent', to='patients.patient')),
                ('from_clinician', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_sent_by', to=settings.AUTH_USER_MODEL)),
                ('to_clinician', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_received_by', to=settings.AUTH_USER_MODEL)),
                ('institution', models.ForeignKey(db_index=True, help_text='Owning institution for scoping. Same as from_institution.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_owned_sent', to='institution.institution')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ReferralReceived',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this record was created', verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='When this record was last updated', verbose_name='Updated At')),
                ('patient_name', models.CharField(help_text='Denormalized patient name from snapshot, for display without patient FK lookup.', max_length=200)),
                ('from_clinician_name', models.CharField(help_text='Denormalized sending clinician name.', max_length=200)),
                ('referral_uuid', models.UUIDField(editable=False, help_text='Copied from ReferralSent.referral_uuid. Never regenerated.')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('REPLIED', 'Replied'), ('CLOSED', 'Closed')], default='PENDING', max_length=20)),
                ('initial_message', models.TextField(help_text='Copy of the referral message from the sending clinician.')),
                ('snapshot_data', models.JSONField(default=dict, help_text='Own copy of patient snapshot. Self-contained regardless of ReferralSent state.')),
                ('outcome', models.TextField(blank=True)),
                ('is_read', models.BooleanField(default=False, help_text='True once the receiving clinician has opened the referral thread.')),
                ('added_by', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referralreceived_added', to=settings.AUTH_USER_MODEL, verbose_name='Added By')),
                ('last_edit_by', models.ForeignKey(blank=True, help_text='User who last modified this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referralreceived_last_edited', to=settings.AUTH_USER_MODEL, verbose_name='Last Edited By')),
                ('to_institution', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_received', to='institution.institution')),
                ('from_institution', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_sent_from', to='institution.institution')),
                ('to_clinician', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_received_as_clinician', to=settings.AUTH_USER_MODEL)),
                ('institution', models.ForeignKey(db_index=True, help_text='Owning institution for scoping. Same as to_institution.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals_owned_received', to='institution.institution')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ReferralMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this record was created', verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='When this record was last updated', verbose_name='Updated At')),
                ('referral_uuid', models.UUIDField(db_index=True, help_text='Shared referral_uuid — links to both ReferralSent and ReferralReceived.')),
                ('body', models.TextField()),
                ('message_type', models.CharField(choices=[('OPINION', 'Clinical Opinion')], default='OPINION', max_length=20)),
                ('added_by', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referralmessage_added', to=settings.AUTH_USER_MODEL, verbose_name='Added By')),
                ('last_edit_by', models.ForeignKey(blank=True, help_text='User who last modified this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referralmessage_last_edited', to=settings.AUTH_USER_MODEL, verbose_name='Last Edited By')),
                ('sender', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referral_messages_sent', to=settings.AUTH_USER_MODEL)),
                ('sender_institution', models.ForeignKey(db_index=True, help_text='Institution of the sender at the time of the message (for display badge).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referral_messages', to='institution.institution')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='referralsent',
            index=models.Index(fields=['referral_uuid'], name='referral_re_referra_idx'),
        ),
        migrations.AddIndex(
            model_name='referralsent',
            index=models.Index(fields=['from_institution', 'status'], name='referral_re_from_in_idx'),
        ),
        migrations.AddIndex(
            model_name='referralsent',
            index=models.Index(fields=['to_institution', 'status'], name='referral_re_to_inst_idx'),
        ),
        migrations.AddIndex(
            model_name='referralreceived',
            index=models.Index(fields=['referral_uuid'], name='referral_re_referra_rec_idx'),
        ),
        migrations.AddIndex(
            model_name='referralreceived',
            index=models.Index(fields=['to_institution', 'status'], name='referral_re_to_inst_rec_idx'),
        ),
    ]
