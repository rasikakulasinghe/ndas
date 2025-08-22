from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """
    Abstract base class that provides self-updating 'created_at' and 'updated_at' fields
    """

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("When this record was created"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
        help_text=_("When this record was last updated"),
    )

    class Meta:
        abstract = True


class UserTrackingMixin(models.Model):
    """
    Abstract base class for user tracking fields
    """

    added_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        related_name="%(class)s_added",
        null=True,
        blank=True,
        verbose_name=_("Added By"),
        help_text=_("User who created this record"),
    )
    last_edit_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        related_name="%(class)s_last_edited",
        null=True,
        blank=True,
        verbose_name=_("Last Edited By"),
        help_text=_("User who last modified this record"),
    )

    class Meta:
        abstract = True