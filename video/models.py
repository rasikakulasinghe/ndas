from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.validators import validate_video_file, validate_recording_date
from patients.models import GMAssessment, Bookmark


class Video(TimeStampedModel, UserTrackingMixin):

    video_file = models.FileField(
        upload_to="videos/%Y/",
        verbose_name=_("Video File"),
        help_text=_("Upload the video file here"),
        validators=[validate_video_file],
        db_index=True,
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Video Title"),
        help_text=_("Descriptive title for the video (max 200 characters)"),
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z0-9\s\-_\.]+$",
                message=_(
                    "Title can only contain letters, numbers, spaces, hyphens, underscores, and dots."
                ),
            )
        ],
        db_index=True,  # Index for faster search
    )

    # Patient relationship
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="video_files",  # Unique related_name
        verbose_name=_("Patient"),
        help_text=_("Patient associated with this video"),
        db_index=True,  # Index for faster lookup
    )

    recorded_on = models.DateTimeField(
        verbose_name=_("Recorded On"),
        help_text=_("Date and time when the video was recorded"),
        validators=[validate_recording_date],
        db_index=True,  # Index for filtering/sorting
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Detailed description of the video content"),
    )

    class Meta:
        verbose_name = _("Video")
        verbose_name_plural = _("Videos")
        ordering = ["-recorded_on"]  # Default ordering by newest first

    def __str__(self):
        return f"{self.title} ({self.patient}) - {self.recorded_on:%Y-%m-%d}"  # Useful for admin/debug

    @property
    def getAgeOnRecord(self):
        # return self.patient.dob_tob - self.recorded_on
        x = self.recorded_on - self.patient.dob_tob.date()

        var_age = x.days
        if var_age < 7:
            return f"{var_age}  Days"
        elif var_age == 7:
            return f"1 Week"
        elif var_age > 7 and var_age < 30:
            ageindays_wks, ageindays_days = divmod(var_age, 7)
            return f"{ageindays_wks} Weeks and {ageindays_days} Days"
        elif var_age == 30:
            return f"1 Month"
        elif var_age > 30 and var_age < 365:
            ageindays_mnths, ageindays_days = divmod(var_age, 30)
            return f"{ageindays_mnths} Months and {ageindays_days} Days"
        elif var_age == 365:
            return f"1 Year"
        elif var_age > 365:
            ageindays_yrs, ageindays_days = divmod(var_age, 365)
            return f"{ageindays_yrs} Years and {ageindays_days} Days"


    @property
    def isNewFile(self):
        var_new = GMAssessment.objects.filter(video_file=self).exists()
        return not var_new


    @property
    def isBookmarked(self):
        return Bookmark.objects.filter(bookmark_type="File", object_id=self.pk).first()
