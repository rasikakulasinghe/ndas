from django.db import models
from django.core.exceptions import ValidationError
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import SubscriptionStatus


class Institution(TimeStampedModel, UserTrackingMixin):
    name = models.CharField(max_length=255, unique=True, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    logo = models.ImageField(
        upload_to='institution_logos/',  # temporary path; Story 1.5 adds institution-aware paths
        null=True, blank=True
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE
    )
    subscription_start = models.DateField(null=True, blank=True)
    grace_period_end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='institutions_created',
        help_text="SUPERADMIN who onboarded this institution"
    )

    def save(self, *args, **kwargs):
        if self.pk:
            original = Institution.objects.get(pk=self.pk)
            if original.slug != self.slug:
                raise ValidationError("Institution slug is immutable and cannot be changed after creation.")
        super().save(*args, **kwargs)

    def clean(self):
        if self.pk:
            try:
                original = Institution.objects.get(pk=self.pk)
                if original.slug != self.slug:
                    raise ValidationError({'slug': 'Institution slug is immutable and cannot be changed after creation.'})
            except Institution.DoesNotExist:
                pass

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
