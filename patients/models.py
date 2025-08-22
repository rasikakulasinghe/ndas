from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import re, os, mimetypes
from djrichtextfield.models import RichTextField

from ndas.custom_codes.choice import (
    MODE_OF_DELIVERY,
    GENDER,
    LEVEL_OF_INDICATION,
    POG_DAYS,
    POG_WKS,
    APGAR,
    BOOKMARK_TYPE,
    ATTACHMENT_TYPE,
    DX_CONCLUTION,
    VIDEO_FORMATS,
    QUALITY_CHOICES,
    PROCESSING_STATUS,
    ACCESS_LEVEL_CHOICES,
    ATTACHMENT_TYPE_CHOICES,
    ATTACHMENT_ACCESS_LEVEL_CHOICES,
    SCAN_RESULT_CHOICES,
    FILE_SIZE_LIMITS,
    ALLOWED_EXTENSIONS,
)
from ndas.custom_codes.custom_methods import (
    getCountZeroIfNone,
    get_video_path_file_name,
    get_compressed_video_path,
    get_video_thumbnail_path,
    get_attachment_path_file_name,
    getCurrentDateTime,
    checkRCState,
)
from ndas.custom_codes.validators import (
    validate_birth_weight,
    validate_apgar_score,
    validate_phone_number,
    validate_video_file,
    validate_recording_date,
    validate_pog_weeks,
    validate_pog_days,
    validate_attachment_file,
)
from ndas.custom_codes.Custom_abstract_class import (
    TimeStampedModel,
    UserTrackingMixin,
)


# Abstract base class for audit fields



class Patient(TimeStampedModel, UserTrackingMixin):
    """
    Enhanced Patient model for NDAS system with comprehensive medical data tracking
    """

    # Medical record identifiers - indexed for fast lookups
    bht = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("BHT Number"),
        help_text=_("Bed Head Ticket number - unique hospital identifier"),
    )
    nnc_no = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("NNC Number"),
        help_text=_("National Neonatal Care number"),
    )
    ptc_no = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("PTC Number"),
        help_text=_("Perinatal Transport Card number"),
    )
    pc_no = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("PC Number"),
        help_text=_("Patient Card number"),
    )
    pin = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("PIN"),
        help_text=_("Patient Identification Number"),
    )
    disk_no = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_("Disk Number"),
        help_text=_("Physical disk/file number for record storage"),
    )

    # Patient identification - indexed for searches
    baby_name = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_("Baby's Name"),
        help_text=_("Full name of the infant"),
    )
    mother_name = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_("Mother's Name"),
        help_text=_("Full name of the mother"),
    )

    # Birth details with proper validation
    pog_wks = models.PositiveSmallIntegerField(
        choices=POG_WKS,
        default=40,
        validators=[validate_pog_weeks],
        verbose_name=_("Period of Gestation (Weeks)"),
        help_text=_("Gestational age in completed weeks (20-44)"),
    )
    pog_days = models.PositiveSmallIntegerField(
        choices=POG_DAYS,
        default=0,
        validators=[validate_pog_days],
        verbose_name=_("Period of Gestation (Days)"),
        help_text=_("Additional days beyond completed weeks (0-6)"),
    )

    gender = models.CharField(
        max_length=8,
        choices=GENDER,
        db_index=True,
        verbose_name=_("Gender"),
        help_text=_("Biological sex of the infant"),
    )

    dob_tob = models.DateTimeField(
        db_index=True,
        verbose_name=_("Date and Time of Birth"),
        help_text=_("Exact date and time when the baby was born"),
    )

    mo_delivery = models.CharField(
        max_length=35,
        choices=MODE_OF_DELIVERY,
        default="NVD",
        verbose_name=_("Mode of Delivery"),
        help_text=_("Method by which the baby was delivered"),
    )

    # APGAR scores with validation
    apgar_1 = models.PositiveSmallIntegerField(
        choices=APGAR,
        default=10,
        validators=[validate_apgar_score],
        verbose_name=_("APGAR Score at 1 minute"),
        help_text=_("APGAR score assessed at 1 minute after birth (0-10)"),
    )
    apgar_5 = models.PositiveSmallIntegerField(
        choices=APGAR,
        default=10,
        validators=[validate_apgar_score],
        verbose_name=_("APGAR Score at 5 minutes"),
        help_text=_("APGAR score assessed at 5 minutes after birth (0-10)"),
    )
    apgar_10 = models.PositiveSmallIntegerField(
        choices=APGAR,
        default=10,
        validators=[validate_apgar_score],
        verbose_name=_("APGAR Score at 10 minutes"),
        help_text=_("APGAR score assessed at 10 minutes after birth (0-10)"),
    )

    # Resuscitation details
    resuscitated = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Required Resuscitation"),
        help_text=_("Whether the baby required resuscitation at birth"),
    )
    resustn_note = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Resuscitation Notes"),
        help_text=_("Detailed notes about resuscitation procedures performed"),
    )

    # Physical measurements with validation
    birth_weight = models.PositiveSmallIntegerField(
        validators=[validate_birth_weight],
        verbose_name=_("Birth Weight (grams)"),
        help_text=_("Weight of the baby at birth in grams (300-8000g)"),
    )
    length = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(20), MaxValueValidator(70)],
        verbose_name=_("Length (cm)"),
        help_text=_("Length of the baby at birth in centimeters"),
    )
    ofc = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(20), MaxValueValidator(50)],
        verbose_name=_("Occipital Frontal Circumference (cm)"),
        help_text=_("Head circumference measurement in centimeters"),
    )

    # Contact and location information
    address = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Address"),
        help_text=_("Complete residential address"),
    )
    tp_mobile = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        verbose_name=_("Primary Mobile Number"),
        help_text=_("Primary contact mobile number"),
    )
    tp_lan = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        validators=[validate_phone_number],
        verbose_name=_("Landline Number"),
        help_text=_("Landline/secondary contact number"),
    )
    moh_area = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("MOH Area"),
        help_text=_("Medical Officer of Health administrative area"),
    )
    phm_area = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("PHM Area"),
        help_text=_("Public Health Midwife coverage area"),
    )

    # Medical history and problems
    problems = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Medical Problems"),
        help_text=_("Current medical problems or concerns"),
    )

    # Related assessments
    indecation_for_gma = models.ManyToManyField(
        "IndicationsForGMA",
        blank=True,
        verbose_name=_("Indications for GMA"),
        help_text=_("Medical indications for General Movement Assessment"),
    )

    # Medical history fields
    antenatal_hx = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Antenatal History"),
        help_text=_("Medical history during pregnancy"),
    )
    intranatal_hx = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Intranatal History"),
        help_text=_("Medical events during labor and delivery"),
    )
    postnatal_hx = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Postnatal History"),
        help_text=_("Medical events and care after birth"),
    )

    # Admission and discharge tracking
    do_admission = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Date of Admission"),
        help_text=_("When the patient was admitted to the facility"),
    )
    do_discharge = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Date of Discharge"),
        help_text=_("When the patient was discharged from the facility"),
    )

    # Additional relevant medical details
    other_relavent_details = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Other Relevant Details"),
        help_text=_("Any additional medical or social information"),
    )

    class Meta:
        verbose_name = _("Patient")
        verbose_name_plural = _("Patients")
        ordering = ["-created_at", "baby_name"]

        # Database indexes for performance optimization
        indexes = [
            models.Index(fields=["baby_name", "mother_name"], name="patient_names_idx"),
            models.Index(fields=["dob_tob", "gender"], name="patient_birth_idx"),
            models.Index(
                fields=["created_at", "moh_area"], name="patient_location_idx"
            ),
            models.Index(
                fields=["resuscitated", "birth_weight"], name="patient_risk_idx"
            ),
        ]

        # Database constraints
        constraints = [
            models.CheckConstraint(
                check=models.Q(birth_weight__gte=300)
                & models.Q(birth_weight__lte=8000),
                name="valid_birth_weight",
            ),
            models.CheckConstraint(
                check=models.Q(pog_wks__gte=20) & models.Q(pog_wks__lte=44),
                name="valid_pog_weeks",
            ),
            models.CheckConstraint(
                check=models.Q(pog_days__gte=0) & models.Q(pog_days__lte=6),
                name="valid_pog_days",
            ),
        ]

    def __str__(self):
        return f"{self.baby_name} | {self.pin or 'No PIN'}"

    def clean(self):
        """Model-wide validation"""
        super().clean()

        # Validate birth date is not in the future
        if self.dob_tob and self.dob_tob > timezone.now():
            raise ValidationError({"dob_tob": _("Birth date cannot be in the future")})

        # Validate discharge date is after admission date
        if self.do_admission and self.do_discharge:
            if self.do_discharge <= self.do_admission:
                raise ValidationError(
                    {"do_discharge": _("Discharge date must be after admission date")}
                )

        # Validate birth weight consistency with gestational age
        if self.birth_weight and self.pog_wks:
            if self.pog_wks < 28 and self.birth_weight > 2000:
                raise ValidationError(
                    {"birth_weight": _("Birth weight seems high for gestational age")}
                )

    def save(self, *args, **kwargs):
        """Override save to perform additional validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    # Optimized properties with caching where appropriate
    @property
    def isNewPatient(self):
        """Check if patient has any video records"""
        if hasattr(self, "pk") and self.pk:
            return not Video.objects.filter(patient=self.pk).exists()
        return True

    @property
    def isDischarged(self):
        """Check if patient is discharged"""
        latest_record = CDICRecord.objects.filter(patient=self).order_by("-id").first()
        return latest_record.is_discharged if latest_record else False

    @property
    def getAPGAR(self):
        """Return formatted APGAR scores"""
        return f"{self.apgar_1} - {self.apgar_5} - {self.apgar_10}"

    @property
    def isScreeningPositive(self):
        """Check if patient has positive screening results"""
        if not hasattr(self, "pk") or not self.pk:
            return False

        var_gma_record = (
            GMAssessment.objects.filter(patient=self).order_by("-id").first()
        )
        if var_gma_record is not None:
            latest_gma_assessment = var_gma_record.is_diagnosis_normal
        else:
            latest_gma_assessment = True

        hine_records = HINEAssessment.objects.filter(patient=self)
        hine_record_count = getCountZeroIfNone(hine_records)

        if hine_record_count == 0 and latest_gma_assessment == True:
            return False
        if hine_record_count > 0:

            last_hine_record = hine_records.order_by("-id").first()
            last_hine_score = last_hine_record.score if last_hine_record else 0

            if latest_gma_assessment == True and last_hine_score > 73:
                return False
            if latest_gma_assessment == True and last_hine_score < 73:
                return True
            if latest_gma_assessment == False and last_hine_score < 73:
                return True
            if latest_gma_assessment == False and last_hine_score > 73:
                return True

    @property
    def getPOG(self):
        """Display gestational age in readable format"""
        return f"{self.pog_wks} Weeks and {self.pog_days} Days"

    @property
    def getResuscitationState(self):
        """Return resuscitation status with notes"""
        if self.resuscitated:
            return f"Resuscitated: {self.resustn_note or 'No details provided'}"
        return "Not resuscitated"

    @property
    def isLastGMANormal(self):
        """Check if last GMA assessment is normal"""
        if not hasattr(self, "pk") or not self.pk:
            return True

        if GMAssessment.objects.filter(patient=self).exists():
            try:
                latest = (
                    GMAssessment.objects.filter(patient=self).order_by("-id").first()
                )
                return latest.is_diagnosis_normal if latest else False
            except:
                return False
        else:
            return True

    @property
    def isLastHINENormal(self):
        """Check if last HINE assessment is normal"""
        if not hasattr(self, "pk") or not self.pk:
            return True
        latest = HINEAssessment.objects.filter(patient=self).order_by("-id").first()
        return latest.isNormal if latest else True

    @property
    def isLastDANormal(self):
        """Check if last DA assessment is normal"""
        if not hasattr(self, "pk") or not self.pk:
            return True
        latest = (
            DevelopmentalAssessment.objects.filter(patient=self).order_by("-id").first()
        )
        return latest.isDxNormal if latest else True

    @property
    def isBookmarked(self):
        """Check if patient is bookmarked"""
        if not hasattr(self, "pk") or not self.pk:
            return None
        try:
            return Bookmark.objects.get(bookmark_type="Patient", object_id=self.pk)
        except Bookmark.DoesNotExist:
            return None

    @property
    def getGMAIndicationsList(self):
        """Get list of GMA indications"""
        return ", ".join(
            map(
                str, list(self.indecation_for_gma.all().values_list("title", flat=True))
            )
        )

    @property
    def getDiagnosisList(self):
        """Get comprehensive diagnosis list from all assessments"""
        if not hasattr(self, "pk") or not self.pk:
            return "No assessments", "No assessments", "No assessments"

        try:
            latest_gma = (
                GMAssessment.objects.filter(patient=self).order_by("-id").first()
            )
            var_gma_dx_list = (
                ", ".join(
                    map(
                        str,
                        list(
                            latest_gma.diagnosis.all().values_list("title", flat=True)
                        ),
                    )
                )
                if latest_gma
                else "No GM assessments"
            )
        except:
            var_gma_dx_list = "No GM assessments"

        var_dx_hine = (
            HINEAssessment.objects.filter(patient=self).order_by("-id").first()
        )
        var_dx_da = (
            DevelopmentalAssessment.objects.filter(patient=self).order_by("-id").first()
        )

        dx_gma = var_gma_dx_list
        dx_hine = (
            f"Score - {var_dx_hine.score}"
            if var_dx_hine is not None
            else "No HINE records"
        )
        dx_da = var_dx_da.isDxNormal if var_dx_da is not None else "No DA records"

        return dx_gma, dx_hine, dx_da

    @property
    def getCurrentAge(self):
        """Calculate current age from birth date"""
        if not self.dob_tob:
            return "Unknown"

        var_results = relativedelta(timezone.now().date(), self.dob_tob.date())
        return f"{var_results.years} Years {var_results.months} Months {var_results.days} Days"

    @property
    def getCorrectedAge(self):
        """Calculate corrected age based on gestational age"""
        if not self.dob_tob:
            return "Unknown"

        gestational_age = (
            self.pog_wks * 7 + self.pog_days
        )  # Calculate gestational age in days
        term_age = 40 * 7  # Term age in days

        if gestational_age < term_age:
            days_till_term = term_age - gestational_age
            var_results = relativedelta(
                (timezone.now().date() - timedelta(days=days_till_term)),
                self.dob_tob.date(),
            )
        else:
            var_results = relativedelta(timezone.now().date(), self.dob_tob.date())
        age_yrs = var_results.years
        age_mnths = var_results.months
        age_days = var_results.days
        return f"{age_yrs} Years {age_mnths} Months {age_days} Days"

    @property
    def getCorrectedGestationalAge(self):
        """Calculate corrected gestational age"""
        if not self.dob_tob:
            return "Unknown"

        final_corr_age_wks = 0
        final_corr_age_ds = 0

        born = self.dob_tob.date()
        today = timezone.now().date()
        ageindays = (today - born).days

        # get current age in wks and days
        ageindays_wks, ageindays_days = divmod(ageindays, 7)

        corr_age_wks = self.pog_wks + ageindays_wks
        corr_age_days = self.pog_days + ageindays_days

        if corr_age_days < 7:
            final_corr_age_wks = corr_age_wks
            final_corr_age_ds = corr_age_days
        elif corr_age_days > 7:
            final_corr_age_wks = corr_age_wks + int(corr_age_days / 7)
            final_corr_age_ds = corr_age_days % 7
        elif corr_age_days == 7:
            final_corr_age_wks = corr_age_wks + int(corr_age_days / 7) + 1
            final_corr_age_ds = 0

        # returning final values
        if final_corr_age_wks < 40:
            return f"{final_corr_age_wks} + {final_corr_age_ds}"
        else:
            return f"Term +"

    @property
    def getRC(self):
        """Get recommendation and care status"""
        if not hasattr(self, "pk") or not self.pk:
            return False

        gma_count = GMAssessment.objects.filter(patient=self).count()
        current_age = int((timezone.now().date() - self.dob_tob.date()).days / 30)

        try:
            last_hine_record = HINEAssessment.objects.filter(patient=self).last()
            last_hine_score = last_hine_record.score if last_hine_record else 0
        except AttributeError:
            last_hine_score = 0

        rc_state = False

        # check 1st GMA assessment
        if gma_count == 0 and current_age <= 2:
            check_1st_gma_wm = {
                "msg": "Please perform the initial General Movement Assessment (GMA) to assess writhing movements.",
                "display": True,
            }
        else:
            check_1st_gma_wm = {"msg": "", "display": False}

        # check 1st GMA assessment
        if gma_count == 0 and current_age > 2:
            check_1st_gma_fm = {
                "msg": "Please perform the initial General Movement Assessment (GMA) to assess and identify fidget movements.",
                "display": True,
            }
        else:
            check_1st_gma_fm = {"msg": "", "display": False}

        # check 2nd GMA assessment
        if gma_count == 1 and current_age > 2:
            check_2nd_gma = {
                "msg": "Please perform the second (2nd) General Movement Assessment (GMA) to assess and identify fidget movements.",
                "display": True,
            }
        else:
            check_2nd_gma = {"msg": "", "display": False}

        # check HINE time
        if 4 <= current_age <= 6 and current_age > 2 and gma_count == 2:
            check_HINE_time = {
                "msg": "It is time to perform the HINE (Hammersmith Infant Neurological Examination).",
                "display": True,
            }
        else:
            check_HINE_time = {"msg": "", "display": False}

        # check physiotheraphy indication
        if self.isLastGMANormal == False and last_hine_score < 73:
            is_pt_indicated = {
                "msg": "Screening positive. Please refer baby to the Multidisciplinary Team (MDT) at the Child Development and Intervention Center/ Clinic (CDIC)",
                "display": True,
            }
        else:
            is_pt_indicated = {"msg": "", "display": False}

        if (
            checkRCState(check_1st_gma_wm)
            or checkRCState(check_1st_gma_fm)
            or checkRCState(check_2nd_gma)
            or checkRCState(check_HINE_time)
            or checkRCState(is_pt_indicated)
        ):
            rc_state = True
        else:
            rc_state = False

        # check discharge state
        cdic_record = CDICRecord.objects.filter(patient=self).order_by("-id").first()

        if cdic_record is not None:
            discharge_state = cdic_record.is_discharged
        else:
            discharge_state = False

        if discharge_state:
            return False
        else:
            return [
                rc_state,
                check_1st_gma_wm,
                check_1st_gma_fm,
                check_2nd_gma,
                check_HINE_time,
                is_pt_indicated,
            ]

    # Method to get related assessments efficiently
    def get_latest_gma_assessment(self):
        """Get the most recent GMA assessment"""
        if not hasattr(self, "pk") or not self.pk:
            return None
        return (
            GMAssessment.objects.filter(patient=self)
            .select_related("video_file")
            .order_by("-date_of_assessment")
            .first()
        )

    def get_latest_hine_assessment(self):
        """Get the most recent HINE assessment"""
        if not hasattr(self, "pk") or not self.pk:
            return None
        return (
            HINEAssessment.objects.filter(patient=self)
            .order_by("-date_of_assessment")
            .first()
        )

    def get_latest_da_assessment(self):
        """Get the most recent Developmental assessment"""
        if not hasattr(self, "pk") or not self.pk:
            return None
        return (
            DevelopmentalAssessment.objects.filter(patient=self)
            .order_by("-date_of_assessment")
            .first()
        )


class GMAssessment(TimeStampedModel, UserTrackingMixin):
    """
    General Movement Assessment model for tracking infant movement assessments
    with optimized performance and Django best practices
    """

    # Core assessment fields with proper validation and indexing
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name=_("Patient"),
        help_text=_("Patient this assessment belongs to"),
    )
    video_file = models.OneToOneField(
        "Video",
        on_delete=models.CASCADE,
        verbose_name=_("Video File"),
        help_text=_("Associated video file for this assessment"),
    )
    date_of_assessment = models.DateTimeField(
        db_index=True,
        verbose_name=_("Date of Assessment"),
        help_text=_("When this assessment was performed"),
    )

    # Diagnosis fields with proper validation
    diagnosis = models.ManyToManyField(
        "DiagnosisList",
        blank=True,
        verbose_name=_("Diagnosis"),
        help_text=_("Selected diagnoses for this assessment"),
    )
    diagnosis_other = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Other Diagnosis"),
        help_text=_("Additional diagnosis notes not covered by standard list"),
    )
    diagnosis_conclusion = models.CharField(
        max_length=8,
        choices=DX_CONCLUTION,
        default="NORMAL",
        db_index=True,
        verbose_name=_("Diagnosis Conclusion"),
        help_text=_("Overall assessment conclusion"),
    )

    # Assessment planning and follow-up
    management_plan = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Management Plan"),
        help_text=_("Recommended treatment and intervention plan"),
    )
    next_assessment_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Next Assessment Date"),
        help_text=_("Scheduled date for follow-up assessment"),
    )
    parent_informed = models.BooleanField(
        default=False,
        verbose_name=_("Parent Informed"),
        help_text=_("Whether the parent has been informed of the results"),
    )

    class Meta:
        verbose_name = _("GM Assessment")
        verbose_name_plural = _("GM Assessments")
        ordering = ["-date_of_assessment", "-created_at"]

        # Database indexes for performance optimization
        indexes = [
            models.Index(
                fields=["patient", "date_of_assessment"], name="gma_patient_date_idx"
            ),
            models.Index(
                fields=["diagnosis_conclusion", "date_of_assessment"],
                name="gma_conclusion_date_idx",
            ),
            models.Index(
                fields=["next_assessment_date", "parent_informed"],
                name="gma_followup_idx",
            ),
        ]

        # Database constraints
        constraints = [
            models.CheckConstraint(
                check=models.Q(date_of_assessment__lte=timezone.now()),
                name="gma_valid_assessment_date",
            ),
            models.CheckConstraint(
                check=models.Q(
                    next_assessment_date__gte=models.F("date_of_assessment__date")
                ),
                name="gma_valid_next_assessment_date",
            ),
        ]

    def __str__(self):
        return (
            f"{self.date_of_assessment.strftime('%Y-%m-%d')} | {self.patient.baby_name}"
        )

    def clean(self):
        """Model-wide validation"""
        super().clean()

        # Validate assessment date is not in the future
        if self.date_of_assessment and self.date_of_assessment > timezone.now():
            raise ValidationError(
                {"date_of_assessment": _("Assessment date cannot be in the future")}
            )

        # Validate next assessment date is after current assessment
        if (
            self.next_assessment_date
            and self.date_of_assessment
            and self.next_assessment_date <= self.date_of_assessment.date()
        ):
            raise ValidationError(
                {
                    "next_assessment_date": _(
                        "Next assessment date must be after current assessment date"
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Override save to perform validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    # Optimized properties with efficient database queries
    @property
    def assessment_age(self):
        """Get the age at time of assessment"""
        if self.video_file:
            return self.video_file.getAgeOnRecord
        return "Unknown"

    @property
    def is_bookmarked(self):
        """Check if assessment is bookmarked - optimized version"""
        if not self.pk:
            return None

        # Use select_related to avoid additional queries
        try:
            return Bookmark.objects.select_related("owner").get(
                bookmark_type="GMA", object_id=self.pk
            )
        except Bookmark.DoesNotExist:
            return None

    @property
    def is_diagnosis_normal(self):
        """Check if diagnosis conclusion is normal"""
        return self.diagnosis_conclusion == "NORMAL"

    @property
    def diagnosis_display(self):
        """Get formatted diagnosis string - optimized version"""
        if not self.pk:
            return "No diagnosis available"

        # Use values_list to fetch only needed fields and reduce memory usage
        diagnosis_items = self.diagnosis.values_list("title", "abr", flat=False)

        if not diagnosis_items:
            return self.diagnosis_other or "No specific diagnosis"

        # Check for normal diagnosis first
        for title, abr in diagnosis_items:
            if abr == "Normal":
                return "Normal"

        # Return comma-separated list of diagnoses
        titles = [title for title, abr in diagnosis_items]
        result = ", ".join(titles)

        # Append other diagnosis if available
        if self.diagnosis_other:
            result += f" | {self.diagnosis_other}"

        return result

    @property
    def is_follow_up_due(self):
        """Check if follow-up assessment is due"""
        if not self.next_assessment_date:
            return False
        return timezone.now().date() >= self.next_assessment_date

    @property
    def days_until_follow_up(self):
        """Calculate days until next assessment"""
        if not self.next_assessment_date:
            return None
        delta = self.next_assessment_date - timezone.now().date()
        return delta.days

    # Class methods for efficient queries
    @classmethod
    def get_latest_for_patient(cls, patient):
        """Get the most recent assessment for a patient"""
        return (
            cls.objects.filter(patient=patient)
            .select_related("patient", "video_file", "added_by", "last_edit_by")
            .prefetch_related("diagnosis")
            .first()
        )

    @classmethod
    def get_normal_assessments(cls):
        """Get all assessments with normal conclusions"""
        return cls.objects.filter(diagnosis_conclusion="NORMAL").select_related(
            "patient"
        )

    @classmethod
    def get_pending_follow_ups(cls):
        """Get assessments with pending follow-ups"""
        return cls.objects.filter(
            next_assessment_date__lte=timezone.now().date(), parent_informed=True
        ).select_related("patient")

    @classmethod
    def get_assessments_by_date_range(cls, start_date, end_date):
        """Get assessments within a date range"""
        return (
            cls.objects.filter(date_of_assessment__date__range=[start_date, end_date])
            .select_related("patient", "video_file")
            .prefetch_related("diagnosis")
        )


class CDICRecord(TimeStampedModel, UserTrackingMixin):
    """
    Child Development and Intervention Center (CDIC) Record model
    for tracking patient assessments, interventions, and discharge planning
    with optimized performance and Django best practices
    """

    # Core fields with proper validation and indexing
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name=_("Patient"),
        help_text=_("Patient this CDIC record belongs to"),
    )
    assessment_date = models.DateField(
        db_index=True,
        verbose_name=_("Assessment Date"),
        help_text=_("Date when the assessment was performed"),
    )

    # Assessment details
    assessment = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Assessment Details"),
        help_text=_("Detailed assessment findings and observations"),
    )
    assessment_done_by = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Assessment Done By"),
        help_text=_(
            "Name or ID of the healthcare professional who performed the assessment"
        ),
    )

    # Intervention details
    today_interventions = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Today's Interventions"),
        help_text=_("Interventions and treatments provided during this visit"),
    )

    # Follow-up planning
    next_appointment_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Next Appointment Date"),
        help_text=_("Scheduled date and time for next appointment"),
    )
    next_appointment_plan = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Next Appointment Plan"),
        help_text=_("Planned activities and goals for next appointment"),
    )

    # Discharge tracking with proper validation
    is_discharged = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Discharged"),
        help_text=_("Whether the patient has been discharged from CDIC care"),
    )
    discharged_by = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Discharged By"),
        help_text=_(
            "Name or ID of the healthcare professional who authorized discharge"
        ),
    )
    discharge_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Discharge Date"),
        help_text=_("Date when the patient was discharged from CDIC care"),
    )
    discharge_plan = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Discharge Plan"),
        help_text=_("Discharge planning and follow-up instructions"),
    )

    class Meta:
        verbose_name = _("CDIC Record")
        verbose_name_plural = _("CDIC Records")
        ordering = ["-assessment_date", "-created_at"]

        # Database indexes for performance optimization
        indexes = [
            models.Index(
                fields=["patient", "assessment_date"], name="cdic_patient_date_idx"
            ),
            models.Index(
                fields=["is_discharged", "assessment_date"], name="cdic_discharge_idx"
            ),
            models.Index(
                fields=["next_appointment_date", "is_discharged"],
                name="cdic_followup_idx",
            ),
            models.Index(
                fields=["assessment_done_by", "assessment_date"],
                name="cdic_assessor_idx",
            ),
        ]

        # Database constraints for data integrity
        constraints = [
            models.CheckConstraint(
                check=models.Q(assessment_date__lte=timezone.now().date()),
                name="cdic_valid_assessment_date",
            ),
            models.CheckConstraint(
                check=models.Q(next_appointment_date__gte=models.F("assessment_date"))
                | models.Q(next_appointment_date__isnull=True),
                name="cdic_valid_next_appointment_date",
            ),
            models.CheckConstraint(
                check=models.Q(discharge_date__gte=models.F("assessment_date"))
                | models.Q(discharge_date__isnull=True),
                name="cdic_valid_discharge_date",
            ),
            models.CheckConstraint(
                check=models.Q(is_discharged=False)
                | (
                    models.Q(is_discharged=True)
                    & models.Q(discharge_date__isnull=False)
                    & models.Q(discharged_by__isnull=False)
                ),
                name="cdic_discharge_completeness",
            ),
        ]

    def __str__(self):
        return f"{self.assessment_date.strftime('%Y-%m-%d')} | {self.patient.baby_name}"

    def clean(self):
        """Model-wide validation"""
        super().clean()

        # Validate assessment date is not in the future
        if self.assessment_date and self.assessment_date > timezone.now().date():
            raise ValidationError(
                {"assessment_date": _("Assessment date cannot be in the future")}
            )

        # Validate next appointment date
        if self.next_appointment_date and self.assessment_date:
            if self.next_appointment_date.date() <= self.assessment_date:
                raise ValidationError(
                    {
                        "next_appointment_date": _(
                            "Next appointment date must be after assessment date"
                        )
                    }
                )

        # Validate discharge information consistency
        if self.is_discharged:
            if not self.discharge_date:
                raise ValidationError(
                    {
                        "discharge_date": _(
                            "Discharge date is required when patient is marked as discharged"
                        )
                    }
                )
            if not self.discharged_by:
                raise ValidationError(
                    {
                        "discharged_by": _(
                            "Discharge authorizer is required when patient is marked as discharged"
                        )
                    }
                )
            if self.discharge_date < self.assessment_date:
                raise ValidationError(
                    {
                        "discharge_date": _(
                            "Discharge date cannot be before assessment date"
                        )
                    }
                )

        # Validate discharge date is not in the future
        if self.discharge_date and self.discharge_date > timezone.now().date():
            raise ValidationError(
                {"discharge_date": _("Discharge date cannot be in the future")}
            )

    def save(self, *args, **kwargs):
        """Override save to perform validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    # Optimized properties with efficient database queries
    @property
    def is_bookmarked(self):
        """Check if CDIC record is bookmarked - optimized version"""
        if not self.pk:
            return None

        try:
            return Bookmark.objects.select_related("owner").get(
                bookmark_type="CDICR", object_id=self.pk
            )
        except Bookmark.DoesNotExist:
            return None

    @property
    def days_since_assessment(self):
        """Calculate days since assessment was performed"""
        if not self.assessment_date:
            return None
        return (timezone.now().date() - self.assessment_date).days

    @property
    def is_follow_up_due(self):
        """Check if follow-up appointment is due"""
        if not self.next_appointment_date or self.is_discharged:
            return False
        return timezone.now() >= self.next_appointment_date

    @property
    def days_until_next_appointment(self):
        """Calculate days until next appointment"""
        if not self.next_appointment_date or self.is_discharged:
            return None
        delta = self.next_appointment_date.date() - timezone.now().date()
        return delta.days

    @property
    def days_since_discharge(self):
        """Calculate days since discharge"""
        if not self.is_discharged or not self.discharge_date:
            return None
        return (timezone.now().date() - self.discharge_date).days

    @property
    def assessment_age(self):
        """Get patient's age at time of assessment"""
        if not self.assessment_date or not self.patient.dob_tob:
            return "Unknown"

        age_delta = relativedelta(self.assessment_date, self.patient.dob_tob.date())
        return (
            f"{age_delta.years} Years {age_delta.months} Months {age_delta.days} Days"
        )

    # Class methods for efficient queries
    @classmethod
    def get_active_records(cls):
        """Get all non-discharged CDIC records"""
        return cls.objects.filter(is_discharged=False).select_related("patient")

    @classmethod
    def get_discharged_records(cls):
        """Get all discharged CDIC records"""
        return cls.objects.filter(is_discharged=True).select_related("patient")

    @classmethod
    def get_due_follow_ups(cls):
        """Get records with due follow-up appointments"""
        return cls.objects.filter(
            next_appointment_date__lte=timezone.now(), is_discharged=False
        ).select_related("patient")

    @classmethod
    def get_records_by_date_range(cls, start_date, end_date):
        """Get CDIC records within a date range"""
        return cls.objects.filter(
            assessment_date__range=[start_date, end_date]
        ).select_related("patient")

    @classmethod
    def get_records_by_assessor(cls, assessor_name):
        """Get records by specific assessor"""
        return cls.objects.filter(
            assessment_done_by__icontains=assessor_name
        ).select_related("patient")


class Video(TimeStampedModel, UserTrackingMixin):
    """
    Enhanced Video model with compression, validation, and optimization features
    """

    # Core fields
    patient = models.ForeignKey(
        "Patient",
        on_delete=models.CASCADE,
        related_name="videos",
        verbose_name=_("Patient"),
        help_text=_("Patient associated with this video"),
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
    )

    # Video file fields
    original_video = models.FileField(
        upload_to=get_video_path_file_name,
        verbose_name=_("Original Video File"),
        help_text=_("Original uploaded video file"),
        validators=[validate_video_file],
    )

    compressed_video = models.FileField(
        upload_to=get_compressed_video_path,
        blank=True,
        null=True,
        verbose_name=_("Compressed Video"),
        help_text=_("Compressed version of the video for web playback"),
    )

    thumbnail = models.ImageField(
        upload_to=get_video_thumbnail_path,
        blank=True,
        null=True,
        verbose_name=_("Video Thumbnail"),
        help_text=_("Auto-generated thumbnail from video"),
    )

    # Video metadata
    recorded_on = models.DateTimeField(
        verbose_name=_("Recorded On"),
        help_text=_("Date and time when the video was recorded"),
        validators=[validate_recording_date],
    )

    duration = models.DurationField(
        blank=True,
        null=True,
        verbose_name=_("Duration"),
        help_text=_("Video duration in seconds (auto-detected)"),
    )

    file_size = models.PositiveBigIntegerField(
        blank=True,
        null=True,
        verbose_name=_("File Size"),
        help_text=_("Original file size in bytes"),
    )

    compressed_file_size = models.PositiveBigIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Compressed File Size"),
        help_text=_("Compressed file size in bytes"),
    )

    format = models.CharField(
        max_length=10,
        choices=VIDEO_FORMATS,
        blank=True,
        verbose_name=_("Video Format"),
        help_text=_("Original video format"),
    )

    resolution = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Resolution"),
        help_text=_("Video resolution (e.g., 1920x1080)"),
    )

    frame_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Frame Rate"),
        help_text=_("Video frame rate in FPS"),
    )

    bitrate = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Bitrate"),
        help_text=_("Video bitrate in kbps"),
    )

    # Processing fields
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS,
        default="pending",
        verbose_name=_("Processing Status"),
        help_text=_("Current processing status of the video"),
    )

    target_quality = models.CharField(
        max_length=20,
        choices=QUALITY_CHOICES,
        default="medium",
        verbose_name=_("Target Quality"),
        help_text=_("Desired compression quality"),
    )

    processing_started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Processing Started"),
        help_text=_("When video processing began"),
    )

    processing_completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Processing Completed"),
        help_text=_("When video processing completed"),
    )

    processing_error = models.TextField(
        blank=True,
        verbose_name=_("Processing Error"),
        help_text=_("Error message if processing failed"),
    )

    # Content fields
    description = models.TextField(
        blank=True,
        max_length=2000,
        verbose_name=_("Description"),
        help_text=_("Detailed description of the video content (max 2000 characters)"),
    )

    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Tags"),
        help_text=_("Comma-separated tags for categorization and search"),
    )

    is_sensitive = models.BooleanField(
        default=False,
        verbose_name=_("Contains Sensitive Content"),
        help_text=_("Mark if video contains sensitive medical content"),
    )

    # Access control
    is_public = models.BooleanField(
        default=False,
        verbose_name=_("Public Access"),
        help_text=_("Allow public access to this video"),
    )

    access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default="restricted",
        verbose_name=_("Access Level"),
        help_text=_("Who can access this video"),
    )

    # Legacy fields for backward compatibility
    uploaded_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        related_name="uploaded_videos",
        null=True,
        blank=True,
        verbose_name=_("Uploaded By"),
        help_text=_("User who uploaded this video"),
    )

    uploaded_on = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Uploaded On"),
        help_text=_("When this video was uploaded"),
    )

    last_edit_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        related_name="edited_videos",
        null=True,
        blank=True,
        verbose_name=_("Last Edited By"),
        help_text=_("User who last modified this video"),
    )

    last_edit_on = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Last Edited On"),
        help_text=_("When this video was last modified"),
    )

    class Meta:
        verbose_name = _("Video")
        verbose_name_plural = _("Videos")
        ordering = ["-uploaded_on", "-recorded_on"]
        indexes = [
            models.Index(fields=["patient", "-uploaded_on"]),
            models.Index(fields=["processing_status"]),
            models.Index(fields=["uploaded_by", "-uploaded_on"]),
            models.Index(fields=["recorded_on"]),
            models.Index(fields=["is_public", "access_level"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(file_size__gte=0), name="positive_file_size"
            ),
            models.CheckConstraint(
                check=models.Q(compressed_file_size__gte=0),
                name="positive_compressed_file_size",
            ),
        ]

    def __str__(self):
        return (
            f"{self.title} - {self.patient.baby_name if self.patient else 'No Patient'}"
        )

    def clean(self):
        """Model validation"""
        super().clean()

        # Validate that recorded_on is not in the future
        from django.utils import timezone

        if self.recorded_on and self.recorded_on > timezone.now():
            raise ValidationError(
                {"recorded_on": _("Recording date cannot be in the future.")}
            )

        # Validate file size consistency
        if self.original_video and self.file_size:
            if (
                abs(self.original_video.size - self.file_size) > 1024
            ):  # Allow 1KB difference
                self.file_size = self.original_video.size

    def save(self, *args, **kwargs):
        """Override save to handle metadata extraction and processing"""
        is_new = self.pk is None

        # Set file size if not already set
        if self.original_video and not self.file_size:
            self.file_size = self.original_video.size

        # Extract format from filename if not set
        if self.original_video and not self.format:
            import os

            ext = os.path.splitext(self.original_video.name)[1].lower().lstrip(".")
            if ext in dict(VIDEO_FORMATS):
                self.format = ext

        # Set processing status
        if is_new and self.original_video:
            self.processing_status = "pending"

        super().save(*args, **kwargs)

        # Trigger background processing for new videos
        if is_new and self.original_video:
            self.start_video_processing()

    def start_video_processing(self):
        """
        Start background video processing
        This would typically use Celery or similar for async processing
        """
        from django.utils import timezone

        self.processing_status = "processing"
        self.processing_started_at = timezone.now()
        self.save(update_fields=["processing_status", "processing_started_at"])

        # TODO: Implement actual video processing with Celery
        # process_video_task.delay(self.pk)

    def extract_video_metadata(self):
        """
        Extract metadata from video file
        This would use ffmpeg-python or similar library
        """
        if not self.original_video:
            return

        try:
            # TODO: Implement with ffmpeg-python
            # import ffmpeg
            # probe = ffmpeg.probe(self.original_video.path)
            # video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            #
            # self.duration = float(video_stream.get('duration', 0))
            # self.resolution = f"{video_stream['width']}x{video_stream['height']}"
            # self.frame_rate = eval(video_stream.get('r_frame_rate', '0/1'))
            # self.bitrate = int(video_stream.get('bit_rate', 0)) // 1000  # Convert to kbps

            # For now, set placeholder values
            self.resolution = "1920x1080"  # Placeholder
            self.frame_rate = 30.0  # Placeholder

        except Exception as e:
            # Log error but don't fail
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to extract metadata for video {self.pk}: {e}")

    @property
    def file_size_mb(self):
        """Get file size in megabytes"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0

    @property
    def compressed_file_size_mb(self):
        """Get compressed file size in megabytes"""
        if self.compressed_file_size:
            return round(self.compressed_file_size / (1024 * 1024), 2)
        return 0

    @property
    def compression_ratio(self):
        """Calculate compression ratio"""
        if self.file_size and self.compressed_file_size:
            return round((1 - self.compressed_file_size / self.file_size) * 100, 1)
        return 0

    @property
    def duration_display(self):
        """Get human-readable duration"""
        if not self.duration:
            return "Unknown"

        total_seconds = int(self.duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    @property
    def processing_time(self):
        """Get processing time duration"""
        if self.processing_started_at and self.processing_completed_at:
            return self.processing_completed_at - self.processing_started_at
        return None

    @property
    def age_on_recording(self):
        """Get patient age when video was recorded"""
        if not self.patient or not self.recorded_on:
            return "Unknown"

        recorded_date = (
            self.recorded_on.date()
            if hasattr(self.recorded_on, "date")
            else self.recorded_on
        )
        birth_date = (
            self.patient.dob_tob.date()
            if hasattr(self.patient.dob_tob, "date")
            else self.patient.dob_tob
        )

        age_delta = recorded_date - birth_date
        days = age_delta.days

        if days < 7:
            return f"{days} Days"
        elif days == 7:
            return "1 Week"
        elif days < 30:
            weeks, remaining_days = divmod(days, 7)
            return f"{weeks} Weeks and {remaining_days} Days"
        elif days == 30:
            return "1 Month"
        elif days < 365:
            months, remaining_days = divmod(days, 30)
            return f"{months} Months and {remaining_days} Days"
        elif days == 365:
            return "1 Year"
        else:
            years, remaining_days = divmod(days, 365)
            return f"{years} Years and {remaining_days} Days"

    @property
    def is_new_file(self):
        """Check if video has associated assessments"""
        # Maintain backward compatibility
        return (
            not hasattr(self, "gmassessment_set") or not self.gmassessment_set.exists()
        )

    @property
    def is_bookmarked(self):
        """Check if video is bookmarked (backward compatibility)"""
        try:
            from patients.models import Bookmark

            return Bookmark.objects.filter(
                bookmark_type="Video", object_id=self.pk
            ).exists()
        except:
            return False

    @property
    def playback_url(self):
        """Get the best URL for video playback"""
        if self.compressed_video:
            return self.compressed_video.url
        elif self.original_video:
            return self.original_video.url
        return None

    @property
    def thumbnail_url(self):
        """Get thumbnail URL with fallback"""
        if self.thumbnail:
            return self.thumbnail.url
        # Return a default video thumbnail
        return "/static/images/default-video-thumbnail.jpg"

    def get_tags_list(self):
        """Get tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
        return []

    def can_be_accessed_by(self, user):
        """Check if user can access this video"""
        if not user or not user.is_authenticated:
            return self.is_public

        # Superusers can access everything
        if user.is_superuser:
            return True

        # Uploaded by user
        if self.uploaded_by == user:
            return True

        # Access level checks
        if self.access_level == "public":
            return True
        elif self.access_level == "department":
            # TODO: Implement department-based access
            return True
        elif self.access_level == "team":
            # TODO: Implement team-based access
            return True

        return False

    def mark_processing_completed(self):
        """Mark video processing as completed"""
        from django.utils import timezone

        self.processing_status = "completed"
        self.processing_completed_at = timezone.now()
        self.save(update_fields=["processing_status", "processing_completed_at"])

    def mark_processing_failed(self, error_message=""):
        """Mark video processing as failed"""
        self.processing_status = "failed"
        self.processing_error = error_message
        self.save(update_fields=["processing_status", "processing_error"])

    # Legacy property for backward compatibility
    @property
    def caption(self):
        """Legacy property mapping to title"""
        return self.title

    @property
    def video(self):
        """Legacy property mapping to original_video"""
        return self.original_video

    @property
    def getAgeOnRecord(self):
        """Legacy property for backward compatibility"""
        return self.age_on_recording

    @property
    def isNewFile(self):
        """Legacy property for backward compatibility"""
        return self.is_new_file

    @property
    def isBookmarked(self):
        """Legacy property for backward compatibility"""
        return self.is_bookmarked


class Attachment(TimeStampedModel, UserTrackingMixin):
    """
    Enhanced Attachment model for managing patient file attachments
    with comprehensive validation, performance optimization, and security features
    """

    # Core fields with proper validation and indexing
    patient = models.ForeignKey(
        "Patient",
        on_delete=models.CASCADE,
        related_name="attachments",
        db_index=True,
        verbose_name=_("Patient"),
        help_text=_("Patient this attachment belongs to"),
    )

    title = models.CharField(
        max_length=200,  # Increased from 75 for better descriptions
        db_index=True,
        verbose_name=_("Title"),
        help_text=_("Descriptive title for the attachment (max 200 characters)"),
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z0-9\s\-_\.(),]+$",
                message=_(
                    "Title can only contain letters, numbers, spaces, hyphens, underscores, dots, commas, and parentheses."
                ),
            )
        ],
    )

    attachment = models.FileField(
        upload_to=get_attachment_path_file_name,
        verbose_name=_("Attachment File"),
        help_text=_(
            "Upload file (Images: 10MB max, Videos: 2GB max, Others: 100MB max)"
        ),
        validators=[validate_attachment_file],
    )

    attachment_type = models.CharField(
        max_length=10,
        choices=ATTACHMENT_TYPE_CHOICES,
        db_index=True,
        verbose_name=_("Attachment Type"),
        help_text=_("Type of file being uploaded"),
    )

    description = models.TextField(
        blank=True,
        max_length=1000,  # Added max length for better performance
        verbose_name=_("Description"),
        help_text=_(
            "Detailed description of the attachment content (max 1000 characters)"
        ),
    )

    # File metadata fields
    file_size = models.PositiveBigIntegerField(
        blank=True,
        null=True,
        verbose_name=_("File Size"),
        help_text=_("File size in bytes (auto-detected)"),
    )

    mime_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("MIME Type"),
        help_text=_("File MIME type (auto-detected)"),
    )

    original_filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Original Filename"),
        help_text=_("Original name of the uploaded file"),
    )

    # Access control and security
    is_sensitive = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Contains Sensitive Content"),
        help_text=_("Mark if attachment contains sensitive medical information"),
    )

    access_level = models.CharField(
        max_length=20,
        choices=ATTACHMENT_ACCESS_LEVEL_CHOICES,
        default="restricted",
        db_index=True,
        verbose_name=_("Access Level"),
        help_text=_("Who can access this attachment"),
    )

    # Virus scan and validation status
    is_scanned = models.BooleanField(
        default=False,
        verbose_name=_("Virus Scanned"),
        help_text=_("Whether the file has been scanned for viruses"),
    )

    scan_result = models.CharField(
        max_length=20,
        choices=SCAN_RESULT_CHOICES,
        default="pending",
        verbose_name=_("Scan Result"),
        help_text=_("Result of virus scan"),
    )

    # Legacy fields for backward compatibility (updated field names)
    uploaded_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        related_name="uploaded_attachments",
        null=True,
        blank=True,
        verbose_name=_("Uploaded By"),
        help_text=_("User who uploaded this attachment"),
    )

    uploaded_on = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Uploaded On"),
        help_text=_("When this attachment was uploaded"),
    )

    last_edit_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        related_name="edited_attachments",
        null=True,
        blank=True,
        verbose_name=_("Last Edited By"),
        help_text=_("User who last modified this attachment"),
    )

    last_edit_on = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Last Edited On"),
        help_text=_("When this attachment was last modified"),
    )

    class Meta:
        verbose_name = _("Attachment")
        verbose_name_plural = _("Attachments")
        ordering = ["-uploaded_on", "-created_at"]

        # Database indexes for performance optimization
        indexes = [
            models.Index(
                fields=["patient", "-uploaded_on"], name="attachment_patient_date_idx"
            ),
            models.Index(
                fields=["attachment_type", "-uploaded_on"],
                name="attachment_type_date_idx",
            ),
            models.Index(
                fields=["uploaded_by", "-uploaded_on"], name="attachment_user_date_idx"
            ),
            models.Index(
                fields=["is_sensitive", "access_level"], name="attachment_access_idx"
            ),
            models.Index(
                fields=["scan_result", "is_scanned"], name="attachment_security_idx"
            ),
        ]

        # Database constraints for data integrity
        constraints = [
            models.CheckConstraint(
                check=models.Q(file_size__gte=0),
                name="attachment_positive_file_size",
            ),
            models.CheckConstraint(
                check=models.Q(title__length__gte=1),
                name="attachment_title_not_empty",
            ),
        ]

    def __str__(self):
        patient_name = self.patient.baby_name if self.patient else "No Patient"
        attachment_type_display = dict(ATTACHMENT_TYPE_CHOICES).get(
            self.attachment_type, self.attachment_type
        )
        return f"{self.title} | {attachment_type_display} | {patient_name}"

    def clean(self):
        """Model-wide validation"""
        super().clean()

        # Validate file type matches attachment_type
        if self.attachment and self.attachment_type:
            self._validate_file_type_consistency()

        # Validate file size based on type
        if self.attachment:
            self._validate_file_size()

    def save(self, *args, **kwargs):
        """Override save to handle metadata extraction and validation"""
        is_new = self.pk is None

        # Extract metadata if new file
        if self.attachment and (
            is_new or "attachment" in kwargs.get("update_fields", [])
        ):
            self._extract_file_metadata()
            self._determine_attachment_type()

        # Perform validation
        self.full_clean()
        super().save(*args, **kwargs)

        # Trigger virus scan for new files
        if is_new and self.attachment:
            self._schedule_virus_scan()

    def _extract_file_metadata(self):
        """Extract metadata from the uploaded file"""
        if not self.attachment:
            return

        try:
            # Set file size
            self.file_size = self.attachment.size

            # Set original filename
            self.original_filename = self.attachment.name

            # Detect MIME type
            import mimetypes

            mime_type, _ = mimetypes.guess_type(self.attachment.name)
            self.mime_type = mime_type or "application/octet-stream"

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to extract metadata for attachment {self.pk}: {e}")

    def _determine_attachment_type(self):
        """Auto-determine attachment type based on file extension"""
        if not self.attachment or self.attachment_type:
            return

        import os

        ext = os.path.splitext(self.attachment.name)[1].lower()

        for att_type, extensions in ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                self.attachment_type = att_type
                break
        else:
            self.attachment_type = "other"

    def _validate_file_type_consistency(self):
        """Validate that file extension matches declared attachment type"""
        import os

        ext = os.path.splitext(self.attachment.name)[1].lower()

        allowed_exts = ALLOWED_EXTENSIONS.get(self.attachment_type, [])
        if allowed_exts and ext not in allowed_exts:
            attachment_type_display = dict(ATTACHMENT_TYPE_CHOICES).get(
                self.attachment_type, self.attachment_type
            )
            raise ValidationError(
                {
                    "attachment": _(
                        f"File extension '{ext}' is not allowed for {attachment_type_display}. "
                        f"Allowed extensions: {', '.join(allowed_exts)}"
                    )
                }
            )

    def _validate_file_size(self):
        """Validate file size based on attachment type"""
        max_size = FILE_SIZE_LIMITS["MAX_FILE_SIZE"]

        if self.attachment_type == "image":
            max_size = FILE_SIZE_LIMITS["MAX_IMAGE_SIZE"]
        elif self.attachment_type == "video":
            max_size = FILE_SIZE_LIMITS["MAX_VIDEO_SIZE"]

        if self.attachment.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            attachment_type_display = dict(ATTACHMENT_TYPE_CHOICES).get(
                self.attachment_type, self.attachment_type
            )
            raise ValidationError(
                {
                    "attachment": _(
                        f"File size too large. Maximum allowed size for {attachment_type_display} is {max_size_mb:.1f} MB."
                    )
                }
            )

    def _schedule_virus_scan(self):
        """Schedule virus scan for the uploaded file"""
        # TODO: Implement actual virus scanning with ClamAV or similar
        # For now, mark as clean (in production, this should be async)
        self.is_scanned = True
        self.scan_result = "clean"
        self.save(update_fields=["is_scanned", "scan_result"])

    # Properties for better data access
    @property
    def file_size_mb(self):
        """Get file size in megabytes"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0

    @property
    def file_size_display(self):
        """Get human-readable file size"""
        if not self.file_size:
            return "Unknown"

        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def is_image(self):
        """Check if attachment is an image"""
        return self.attachment_type == "image"

    @property
    def is_video(self):
        """Check if attachment is a video"""
        return self.attachment_type == "video"

    @property
    def is_pdf(self):
        """Check if attachment is a PDF"""
        return self.attachment_type == "pdf"

    @property
    def is_safe_to_view(self):
        """Check if file is safe to view (virus-free)"""
        return self.is_scanned and self.scan_result == "clean"

    @property
    def can_be_previewed(self):
        """Check if file can be previewed in browser"""
        return self.is_safe_to_view and self.attachment_type in ["image", "pdf"]

    @property
    def is_bookmarked(self):
        """Check if attachment is bookmarked - optimized version"""
        if not self.pk:
            return None

        try:
            return Bookmark.objects.select_related("owner").get(
                bookmark_type="Attachment", object_id=self.pk
            )
        except Bookmark.DoesNotExist:
            return None

    # Legacy property for backward compatibility
    @property
    def isBookmarked(self):
        """Legacy property mapping to is_bookmarked"""
        return self.is_bookmarked

    def can_be_accessed_by(self, user):
        """Check if user can access this attachment"""
        if not user or not user.is_authenticated:
            return False

        # Superusers can access everything
        if user.is_superuser:
            return True

        # Uploaded by user
        if self.uploaded_by == user:
            return True

        # Access level checks
        if self.access_level == "general":
            return True
        elif self.access_level == "department":
            # TODO: Implement department-based access
            return True
        elif self.access_level == "team":
            # TODO: Implement team-based access
            return True

        return False

    def get_download_url(self):
        """Get secure download URL"""
        if self.attachment and self.is_safe_to_view:
            return self.attachment.url
        return None

    def get_preview_url(self):
        """Get preview URL for supported file types"""
        if self.can_be_previewed:
            return self.attachment.url
        return None

    # Class methods for efficient queries
    @classmethod
    def get_by_patient(cls, patient, attachment_type=None):
        """Get attachments for a specific patient"""
        queryset = cls.objects.filter(patient=patient).select_related(
            "patient", "uploaded_by", "last_edit_by"
        )

        if attachment_type:
            queryset = queryset.filter(attachment_type=attachment_type)

        return queryset.order_by("-uploaded_on")

    @classmethod
    def get_recent_uploads(cls, days=7):
        """Get recently uploaded attachments"""
        from django.utils import timezone

        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        return cls.objects.filter(uploaded_on__gte=cutoff_date).select_related(
            "patient", "uploaded_by"
        )

    @classmethod
    def get_large_files(cls, size_mb=50):
        """Get files larger than specified size"""
        size_bytes = size_mb * 1024 * 1024
        return cls.objects.filter(file_size__gte=size_bytes).select_related("patient")

    @classmethod
    def get_pending_scans(cls):
        """Get files pending virus scan"""
        return cls.objects.filter(
            scan_result="pending", is_scanned=False
        ).select_related("patient")

    @classmethod
    def get_infected_files(cls):
        """Get files marked as infected"""
        return cls.objects.filter(scan_result="infected").select_related("patient")


class Bookmark(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    bookmark_type = models.CharField(
        max_length=10, choices=BOOKMARK_TYPE, default="Video", null=False
    )
    object_id = models.PositiveIntegerField(null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(
        "users.CustomUser", on_delete=models.CASCADE, null=True, blank=True
    )
    created_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="bm_last_edit_by",
        null=True,
        blank=True,
    )
    last_edit_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        pass

    def __str__(self):
        return str(self.title + " | " + self.owner.username)

    # @property
    # def getAgeOnRecord(self):
    #     return self.patient.dob_tob - self.recorded_on


class IndicationsForGMA(models.Model):
    title = models.CharField(max_length=75, null=False, blank=False)
    level = models.CharField(max_length=6, choices=LEVEL_OF_INDICATION, null=False)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="gmai_created_by",
        null=True,
        blank=True,
    )
    created_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="gmai_last_edit_by",
        null=True,
        blank=True,
    )
    last_edit_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        pass

    def __str__(self):
        return str(self.title + " | " + self.level)

    @property
    def getIndicationList(self):
        return IndicationsForGMA.objects.all().title


class DiagnosisList(models.Model):
    abr = models.CharField(max_length=6, null=False, blank=False)
    title = models.TextField()
    description = models.TextField()

    class Meta:
        pass

    def __str__(self):
        return str(self.title + " (" + self.title + ")")


class Help(models.Model):
    title = models.CharField(max_length=200, null=False, blank=False)
    description = RichTextField(null=True, blank=True)
    video_1 = models.FileField(upload_to="tutorials/", blank=True, null=True)
    video_2 = models.FileField(upload_to="tutorials/", blank=True, null=True)

    class Meta:
        pass

    def __str__(self):
        return self.title


class HINEAssessment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=False)
    date_of_assessment = models.DateTimeField(
        auto_now_add=False, blank=False, null=False
    )
    score = models.SmallIntegerField(
        verbose_name="HINE Score",
        validators=[MinValueValidator(0), MaxValueValidator(78)],
        null=False,
        blank=False,
    )
    assessment_done_by = models.CharField(max_length=200, null=False, blank=False)
    comment = models.TextField(null=True, blank=True)
    added_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="hine_added_user",
        null=True,
    )
    added_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="hine_created_user",
        null=True,
    )
    last_edit_on = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        pass

    def __str__(self):
        return f"{{self.score}} - {{str(self.date_of_assessment)}}"

    @property
    def getAssessmentAgeInMonths(self):
        ageindays_months, ageindays_days = divmod(
            (self.date_of_assessment - self.patient.dob_tob).days, 30
        )
        return f" {ageindays_months} Months and {ageindays_days} Days"

    @property
    def isBookmarked(self):
        return Bookmark.objects.get(bookmark_type="HINE", object_id=self.id)

    @property
    def isNormal(self):
        if self.score > 73:
            return True
        else:
            return False


class DevelopmentalAssessment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=False)
    date_of_assessment = models.DateTimeField(
        auto_now_add=False, blank=False, null=False
    )
    gm_age_from = models.SmallIntegerField(null=True, blank=True)
    gm_age_to = models.SmallIntegerField(null=True, blank=True)
    gm_details = models.TextField(null=True, blank=True)
    fmv_age_from = models.SmallIntegerField(null=True, blank=True)
    fmv_age_to = models.SmallIntegerField(null=True, blank=True)
    fmv_details = models.TextField(null=True, blank=True)
    hsl_age_from = models.SmallIntegerField(null=True, blank=True)
    hsl_age_to = models.SmallIntegerField(null=True, blank=True)
    hsl_details = models.TextField(null=True, blank=True)
    seb_age_from = models.SmallIntegerField(null=True, blank=True)
    seb_age_to = models.SmallIntegerField(null=True, blank=True)
    seb_details = models.TextField(null=True, blank=True)
    assessment_done_by = models.CharField(max_length=200, null=False, blank=False)
    comment = models.TextField(null=True, blank=True)
    added_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="da_added_user",
        null=True,
    )
    added_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="da_created_user",
        null=True,
    )
    last_edit_on = models.DateTimeField(auto_now=True, blank=True, null=True)
    isDxNormal = models.BooleanField(default=False)

    class Meta:
        pass

    def __str__(self):
        return f"{{self.patient.baby_name}} - {{str(self.date_of_assessment)}}"

    @property
    def getAssessmentAgeInMonths(self):
        ageindays_months, ageindays_days = divmod(
            (self.date_of_assessment - self.patient.dob_tob).days, 30
        )
        return f" {ageindays_months} Months and {ageindays_days} Days"

    @property
    def isNormal(self):
        ageindays_months, xx = divmod(
            (self.date_of_assessment - self.patient.dob_tob).days, 30
        )
        var_gm = (
            ageindays_months <= self.gm_age_to and ageindays_months >= self.gm_age_from
        )
        var_fv = (
            ageindays_months <= self.fmv_age_to
            and ageindays_months >= self.fmv_age_from
        )
        var_hsl = (
            ageindays_months <= self.hsl_age_to
            and ageindays_months >= self.hsl_age_from
        )
        var_seb = (
            ageindays_months <= self.seb_age_to
            and ageindays_months >= self.seb_age_from
        )

        return var_gm and var_fv and var_hsl and var_seb

    @property
    def isBookmarked(self):
        return Bookmark.objects.get(bookmark_type="DA", object_id=self.id)

    def save(self, *args, **kwargs):
        self.isDxNormal = self.isNormal
        super().save(*args, **kwargs)
