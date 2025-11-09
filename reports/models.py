import json
from django.db import models
from djrichtextfield.models import RichTextField
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import ConfigValueTypes


class ReportTemplate(TimeStampedModel, UserTrackingMixin):
    """Configurable report header/footer templates for professional PDF/Excel reports"""

    name = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Template name (e.g., 'Default Medical Report', 'Hospital Logo Template')"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of when to use this template"
    )
    header_text = RichTextField(
        blank=True,
        help_text="Header text for reports (supports rich text formatting)"
    )
    footer_text = RichTextField(
        blank=True,
        help_text="Footer text for reports (supports rich text formatting)"
    )
    logo = models.ImageField(
        upload_to="reports/logos/%Y/%m/",
        blank=True,
        null=True,
        help_text="Logo image for report header (PNG/JPG, max 5MB)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is available for use"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default template for reports"
    )

    class Meta:
        verbose_name = "Report Template"
        verbose_name_plural = "Report Templates"
        ordering = ['-is_default', '-is_active', 'name']

    def __str__(self):
        default_tag = " (Default)" if self.is_default else ""
        active_tag = "" if self.is_active else " (Inactive)"
        return f"{self.name}{default_tag}{active_tag}"

    def save(self, *args, **kwargs):
        """Ensure only one default template exists (atomic operation)"""
        from django.db import transaction

        if self.is_default:
            # Use atomic transaction to prevent race conditions
            with transaction.atomic():
                # Lock the table and unset any other default templates
                ReportTemplate.objects.select_for_update().filter(
                    is_default=True
                ).exclude(pk=self.pk).update(is_default=False)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class ReportConfig(TimeStampedModel, UserTrackingMixin):
    """System-wide configuration settings for report generation"""

    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Configuration key (e.g., 'temp_file_retention_hours', 'pdf_page_size')"
    )
    value = models.TextField(
        help_text="Configuration value (stored as string, deserialized based on value_type)"
    )
    value_type = models.CharField(
        max_length=20,
        choices=ConfigValueTypes.choices,
        default=ConfigValueTypes.STRING,
        help_text="Data type for proper deserialization"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this configuration controls"
    )

    class Meta:
        verbose_name = "Report Configuration"
        verbose_name_plural = "Report Configurations"
        ordering = ['key']

    def __str__(self):
        return f"{self.key} = {self.value} ({self.value_type})"

    def get_value(self):
        """Deserialize value based on value_type"""
        if self.value_type == ConfigValueTypes.INTEGER:
            return int(self.value)
        elif self.value_type == ConfigValueTypes.BOOLEAN:
            return self.value.lower() in ('true', '1', 'yes')
        elif self.value_type == ConfigValueTypes.JSON:
            return json.loads(self.value)
        else:  # STRING
            return self.value

    def set_value(self, new_value):
        """Serialize value and auto-detect value_type"""
        if isinstance(new_value, bool):
            self.value = str(new_value)
            self.value_type = ConfigValueTypes.BOOLEAN
        elif isinstance(new_value, int):
            self.value = str(new_value)
            self.value_type = ConfigValueTypes.INTEGER
        elif isinstance(new_value, (dict, list)):
            self.value = json.dumps(new_value)
            self.value_type = ConfigValueTypes.JSON
        else:
            self.value = str(new_value)
            self.value_type = ConfigValueTypes.STRING
