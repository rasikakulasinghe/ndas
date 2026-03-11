# NDAS Data Models

Last Updated: 2026-03-09

All models inherit from `TimeStampedModel` and `UserTrackingMixin` unless noted otherwise. This provides: `created_at`, `updated_at`, `added_by` (FK → CustomUser), `last_edit_by` (FK → CustomUser).

---

## App: patients

### Patient

The core patient record.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `bht` | CharField(20) | unique, null, blank, db_index | Bed Head Ticket number |
| `nnc_no` | CharField(20) | unique, null, blank, db_index | National Neonatal Care number |
| `ptc_no` | CharField(20) | unique, null, blank, db_index | Perinatal Transport Card number |
| `pc_no` | CharField(20) | unique, null, blank, db_index | Patient Card number |
| `pin` | CharField(20) | unique, null, blank, db_index | Patient Identification Number |
| `disk_no` | CharField(20) | null, blank | Physical disk/file number |
| `baby_name` | CharField(100) | db_index | Full name of the infant |
| `mother_name` | CharField(100) | db_index | Full name of the mother |
| `pog_wks` | PositiveSmallIntegerField | choices=POG_WKS, default=40, validator=validate_pog_weeks | Gestational age in completed weeks (20–44) |
| `pog_days` | PositiveSmallIntegerField | choices=POG_DAYS, default=0, validator=validate_pog_days | Additional days (0–6) |
| `gender` | CharField(8) | choices=GENDER, db_index | Male/Female/Undefine |
| `dob_tob` | DateTimeField | db_index | Date and time of birth |
| `mo_delivery` | CharField(35) | choices=MODE_OF_DELIVERY, default="NVD" | Mode of delivery |
| `apgar_1` | PositiveSmallIntegerField | choices=APGAR, default=10, validator=validate_apgar_score | APGAR at 1 minute (0–10) |
| `apgar_5` | PositiveSmallIntegerField | choices=APGAR, default=10, validator=validate_apgar_score | APGAR at 5 minutes (0–10) |
| `apgar_10` | PositiveSmallIntegerField | choices=APGAR, default=10, validator=validate_apgar_score | APGAR at 10 minutes (0–10) |
| `resuscitated` | BooleanField | default=False, db_index | Whether resuscitation was needed |
| `resustn_note` | TextField | null, blank | Notes on resuscitation |
| `birth_weight` | PositiveSmallIntegerField | validator=validate_birth_weight (300–8000g) | Birth weight in grams |
| `length` | PositiveSmallIntegerField | null, blank, validators=[20–70] | Length in cm |
| `ofc` | PositiveSmallIntegerField | validators=[20–50] | Occipital Frontal Circumference in cm |
| `address` | TextField | null, blank | Residential address |
| `tp_mobile` | CharField(15) | validator=validate_phone_number | Primary mobile number |
| `tp_lan` | CharField(15) | null, blank, validator=validate_phone_number | Landline number |
| `moh_area` | CharField(255) | null, blank, db_index | MOH administrative area |
| `phm_area` | CharField(255) | null, blank, db_index | PHM coverage area |
| `problems` | TextField | null, blank | Medical problems narrative |
| `indecation_for_gma` | ManyToManyField → IndicationsForGMA | blank | GMA indications |
| `indecation_for_gma_other` | TextField | null, blank | Other GMA indication details |
| `antenatal_hx` | TextField | null, blank | Antenatal history |
| `intranatal_hx` | TextField | null, blank | Intranatal history |
| `postnatal_hx` | TextField | null, blank | Postnatal history |
| `do_admission` | DateTimeField | null, blank, db_index | Date of admission |
| `do_discharge` | DateTimeField | null, blank, db_index | Date of discharge |
| `other_relavent_details` | TextField | null, blank | Other relevant details |
| `institution` | ForeignKey → Institution | on_delete=PROTECT, null, blank, db_index | Phase 2 institution scoping |

**Manager:** `InstitutionScopedManager` (`.for_institution(institution)`)

**Meta:** ordering = `["-created_at", "baby_name"]`; composite indexes on names, birth data, location, risk fields

**Key Properties:**
- `isNewPatient` — True if no videos linked
- `isDischarged` — True if latest CDICRecord.is_discharged
- `getAPGAR` — formatted "1-5-10"
- `isScreeningPositive` — True if GMA abnormal or HINE ≤ 73
- `getPOG` — formatted gestational age
- `isLastGMANormal`, `isLastHINENormal`, `isLastDANormal` — last assessment normal checks
- `isDiagnosisNormal` — all three latest assessments normal
- `getCurrentAge`, `getCorrectedAge`, `getCorrectedGestationalAge` — age calculations
- `getRC` — recommendation and care status list (6 items: state + 5 check results)
- `isBookmarked` — returns Bookmark object or None

---

### GMAssessment (General Movement Assessment)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `patient` | ForeignKey → Patient | CASCADE, db_index | |
| `video_file` | OneToOneField → Video | CASCADE | One assessment per video |
| `date_of_assessment` | DateTimeField | db_index | |
| `diagnosis` | ManyToManyField → DiagnosisList | blank | Multiple diagnoses |
| `diagnosis_other` | TextField | null, blank | Free-text additional diagnosis |
| `diagnosis_conclusion` | CharField(8) | choices=DX_CONCLUTION, default="NORMAL", db_index | NORMAL or ABNORMAL |
| `management_plan` | TextField | null, blank | Treatment plan |
| `next_assessment_date` | DateField | null, blank, db_index | Follow-up date |
| `parent_informed` | BooleanField | default=False | Parent informed of results |

**Meta:** ordering = `["-date_of_assessment", "-created_at"]`

**Key Properties:**
- `is_diagnosis_normal` — True if `diagnosis_conclusion == "NORMAL"`
- `assessment_age` — age string at time of assessment (from video)
- `is_bookmarked` — returns Bookmark object for GMA type
- `is_follow_up_due`, `days_until_follow_up`

---

### CDICRecord (Child Development and Intervention Centre)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `patient` | ForeignKey → Patient | CASCADE, db_index | |
| `assessment_date` | DateField | db_index | |
| `assessment` | TextField | null, blank | Assessment details |
| `assessment_done_by` | CharField(200) | null, blank, db_index | Assessor name/ID |
| `today_interventions` | TextField | null, blank | Interventions this visit |
| `next_appointment_date` | DateTimeField | null, blank, db_index | |
| `next_appointment_plan` | TextField | null, blank | |
| `is_discharged` | BooleanField | default=False, db_index | Discharge flag |
| `discharged_by` | CharField(200) | null, blank, db_index | Discharge authorizer |
| `discharge_date` | DateField | null, blank, db_index | |
| `discharge_plan` | TextField | null, blank | |

**Meta:** ordering = `["-assessment_date", "-created_at"]`

---

### GeneralPaediatricAssessment (GPA)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `patient` | ForeignKey → Patient | CASCADE, db_index | |
| `assessment_date` | DateTimeField | db_index | |
| `healthcare_provider` | CharField(200) | db_index | |
| `current_problems` | TextField | required | |
| `physical_examination` | TextField | required | |
| `investigation_summary` | TextField | required | |
| `prescribed_medications` | TextField | required | |
| `next_plan` | TextField | required | |
| `next_assessment_date` | DateTimeField | null, blank, db_index | |
| `is_discharged` | BooleanField | default=False, db_index | |
| `discharged_authorized_by` | ForeignKey → CustomUser | SET_NULL, null, blank | |
| `discharge_plan` | TextField | null, blank | |

**Meta:** ordering = `["-assessment_date", "-created_at"]`

---

### HINEAssessment (Hammersmith Infant Neurological Examination)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `patient` | ForeignKey → Patient | CASCADE, db_index | |
| `date_of_assessment` | DateTimeField | db_index | |
| `score` | PositiveSmallIntegerField | validators=[0–78], db_index | Total HINE score |
| `assessment_done_by` | CharField(200) | db_index | |
| `comment` | TextField | null, blank | |

**Meta:** ordering = `["-date_of_assessment"]`

**Key Properties:**
- `is_normal` — True if `score > 73`
- `severity_category` — Normal / Mild / Moderate / Severe Abnormality

---

### DevelopmentalAssessment (DA)

Four developmental domains, each with from/to age range (months, 0–72) and details text.

| Domain | Fields |
|--------|--------|
| Gross Motor | `gm_age_from`, `gm_age_to`, `gm_details` |
| Fine Motor & Vision | `fmv_age_from`, `fmv_age_to`, `fmv_details` |
| Hearing, Speech & Language | `hsl_age_from`, `hsl_age_to`, `hsl_details` |
| Social, Emotional & Behavioural | `seb_age_from`, `seb_age_to`, `seb_details` |

Additional fields:

| Field | Type | Constraints |
|-------|------|-------------|
| `patient` | ForeignKey → Patient | CASCADE, db_index |
| `date_of_assessment` | DateTimeField | db_index |
| `assessment_done_by` | CharField(200) | db_index |
| `comment` | TextField | null, blank |
| `is_dx_normal` | BooleanField | default=False, db_index, db_column="isDxNormal" |

**`is_dx_normal`** is automatically recalculated on every save: True if all domain age ranges contain the patient's actual age at assessment time.

**Meta:** ordering = `["-date_of_assessment"]`

---

### Attachment

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `patient` | ForeignKey → Patient | CASCADE, db_index | |
| `title` | CharField(200) | db_index, regex validator | |
| `attachment` | FileField | upload_to=get_institution_attachment_path, validator=validate_attachment_file | |
| `attachment_type` | CharField(10) | choices=ATTACHMENT_TYPE_CHOICES, db_index | image/pdf/video/document/other |
| `description` | TextField | blank, max_length=1000 | |
| `file_size` | PositiveBigIntegerField | null, blank | Bytes, auto-populated |
| `mime_type` | CharField(100) | blank | Auto-detected |
| `original_filename` | CharField(255) | blank | |
| `is_sensitive` | BooleanField | default=False, db_index | Sensitive content flag |
| `access_level` | CharField(20) | choices=ATTACHMENT_ACCESS_LEVEL_CHOICES, default="restricted", db_index | |
| `is_scanned` | BooleanField | default=False | Virus scan done flag |
| `scan_result` | CharField(20) | choices=SCAN_RESULT_CHOICES, default="pending" | pending/clean/infected/error |

---

### Bookmark

Generic bookmark system for any content type.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `title` | CharField(200) | db_index, regex validator | |
| `bookmark_type` | CharField(20) | choices=BOOKMARK_TYPE, default="Video", db_index | Patient/Video/GMA/HINE/Attachment/DA/CDICR/GPA |
| `object_id` | PositiveIntegerField | db_index | PK of the bookmarked object |
| `description` | TextField | blank, null, max_length=1000 | |
| `owner` | ForeignKey → CustomUser | CASCADE, db_index, null, blank | |
| `is_public` | BooleanField | default=False, db_index | |
| `tags` | CharField(500) | blank | Comma-separated tags |
| `priority` | CharField(10) | choices=[low/normal/high/urgent], default="normal", db_index | |

---

### IndicationsForGMA

| Field | Type | Constraints |
|-------|------|-------------|
| `title` | CharField(75) | unique, db_index |
| `level` | CharField(6) | choices=LEVEL_OF_INDICATION (High/Medium/Low), db_index |
| `description` | TextField | null, blank |

**Meta:** ordering = `['level', 'title']`

---

### DiagnosisList

| Field | Type | Constraints |
|-------|------|-------------|
| `abr` | CharField(6) | unique, db_index |
| `title` | CharField(255) | db_index |
| `description` | TextField | |

---

### Help

| Field | Type | Constraints |
|-------|------|-------------|
| `title` | CharField(200) | unique, db_index |
| `description` | RichTextField | null, blank |
| `video_1` | FileField | upload_to="tutorials/%Y/%m/", blank, null |
| `video_2` | FileField | upload_to="tutorials/%Y/%m/", blank, null |
| `is_active` | BooleanField | default=True, db_index |
| `display_order` | PositiveIntegerField | default=0, db_index |

---

## App: users

### CustomUser

Extends `AbstractUser` and `TimeStampedModel` (no `UserTrackingMixin`).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `position` | CharField(30) | choices=POSSITION, default="Medical Officer" | Professional role |
| `mobile_primary` | CharField(15) | validator=validate_phone_number, db_index | Required |
| `mobile_secondary` | CharField(15) | blank | |
| `landline_primary` | CharField(15) | blank | |
| `landline_secondary` | CharField(15) | blank | |
| `home_address` | TextField | blank | |
| `station_address` | TextField | blank | |
| `last_login_device` | CharField(255) | blank | |
| `is_email_verified` | BooleanField | default=False | |
| `email_verification_token` | CharField(64) | blank | |
| `email_verification_sent_at` | DateTimeField | null, blank | |
| `email_verified_at` | DateTimeField | null, blank | |
| `profile_picture` | ImageField | upload_to="profile_pictures/%Y/%m/", blank | |
| `additional_notes` | TextField | blank | |
| `institution` | ForeignKey → Institution | SET_NULL, null, blank | Phase 2 |
| `user_type` | CharField(20) | choices=UserType, default=USER, db_index | Phase 2: USER/ADMIN/SUPERADMIN |

**USERNAME_FIELD:** `username`
**REQUIRED_FIELDS:** `["email", "first_name", "position", "mobile_primary"]`

**Meta:** ordering = `["first_name", "last_name"]`

---

### UserActivityLog

Tracks login/logout events and device details.

| Field | Type | Notes |
|-------|------|-------|
| `user` | ForeignKey → CustomUser | CASCADE, null/blank (for failed attempts) |
| `login_status` | CharField(20) | choices: success/failed/logout |
| `attempted_username` | CharField(150) | For failed logins |
| `ip_address` | GenericIPAddressField | |
| `user_agent` | TextField | Full UA string |
| `browser_name`, `browser_version` | CharField | |
| `operating_system` | CharField(100) | |
| `device_type`, `device_brand`, `device_model` | CharField | |
| `is_mobile`, `is_tablet`, `is_touch_capable`, `is_pc`, `is_bot` | BooleanField | |
| `country`, `city` | CharField | Optional geolocation |
| `latitude`, `longitude` | FloatField | null, blank |
| `session_key` | CharField(40) | |
| `login_timestamp` | DateTimeField | auto_now_add |
| `logout_timestamp` | DateTimeField | null, blank |
| `session_duration` | DurationField | null, blank |
| `failed_login_reason` | CharField(200) | blank |
| `data_retention_date` | DateTimeField | null, blank; GDPR compliance |

---

### UserSession

Tracks active sessions.

| Field | Type | Notes |
|-------|------|-------|
| `user` | ForeignKey → CustomUser | CASCADE |
| `session_key` | CharField(40) | unique |
| `ip_address` | GenericIPAddressField | |
| `user_agent` | TextField | |
| `device_summary` | CharField(200) | |
| `last_activity` | DateTimeField | auto_now |
| `is_active` | BooleanField | default=True |

---

### DeveloperContacts

Contact information for the application developer/owner.

| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(100) | |
| `logo` | ImageField | |
| `qualifications` | CharField(500) | |
| `email` | EmailField(45) | |
| `mobile_phone`, `landline_phone` | CharField(15) | |
| `facebook_url`, `twitter_url`, `linkedin_url`, `youtube_url`, `website_url` | URLField | |
| `whatsapp_number` | CharField(15) | |

---

### Subscription

Singleton model (always PK=1). Global subscription status affecting all non-superuser access.

| Field | Type | Notes |
|-------|------|-------|
| `subscription_type` | CharField(10) | choices: free/commercial |
| `start_date` | DateField | db_index |
| `duration_days` | PositiveIntegerField | default=30 |
| `billing_amount` | DecimalField(10, 2) | default=0.00 |
| `status` | CharField(15) | choices: active/expired/grace_period; db_index |
| `grace_period_days` | PositiveIntegerField | default=7 |
| `notes` | TextField | blank |

**Key Properties:** `expiration_date`, `grace_period_end_date`, `remaining_days`, `is_active`, `is_expired`, `is_grace_period` — all cached (60s) for performance

**Class Method:** `Subscription.get_global_subscription()` — get-or-create PK=1

---

## App: video

### Video

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `video_file` | FileField | upload_to=get_institution_video_path, validator=validate_video_file, db_index | |
| `title` | CharField(200) | regex validator, db_index | |
| `patient` | ForeignKey → Patient | CASCADE, db_index | |
| `recorded_on` | DateTimeField | validator=validate_recording_date, db_index | Cannot be in future or >10 years ago |
| `description` | TextField | blank | |
| `duration_seconds` | PositiveIntegerField | null, blank, max=14400 | Auto-extracted via moviepy/ffprobe |
| `file_size_bytes` | PositiveBigIntegerField | null, blank | Auto-populated on save |
| `processing_status` | CharField(20) | choices=PROCESSING_STATUS, default="pending", db_index | pending/uploading/processing/completed/failed |
| `resolution` | CharField(20) | null, blank | e.g. "1920x1080" |

**Manager:** `VideoManager` with custom `VideoQuerySet`

**QuerySet methods:**
- `.with_assessment_status()` — annotates `is_assessed` (avoids N+1 on lists)
- `.with_bookmark_status(user)` — annotates `user_bookmarked`
- `.new_videos_only()` — videos not used in any GMAssessment
- `.assessed_videos_only()` — videos used in a GMAssessment

**Meta:** ordering = `["-recorded_on", "-created_at"]`; unique constraint on `(patient, recorded_on, title)`

**Key Properties:**
- `age_on_recording` — patient age string at recording date
- `duration_formatted` — "HH:MM:SS"
- `file_size_mb`
- `file_extension`

---

## App: reports

### ReportTemplate

| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(200) | unique, db_index |
| `description` | TextField | blank |
| `header_text` | RichTextField | blank; CKEditor rich text |
| `footer_text` | RichTextField | blank |
| `logo` | ImageField | upload_to="reports/logos/%Y/%m/" |
| `is_active` | BooleanField | default=True |
| `is_default` | BooleanField | default=False; only one default enforced atomically |

---

### ReportConfig

| Field | Type | Notes |
|-------|------|-------|
| `key` | CharField(100) | unique, db_index |
| `value` | TextField | |
| `value_type` | CharField(20) | choices=ConfigValueTypes (STRING/INTEGER/BOOLEAN/JSON) |
| `description` | TextField | blank |

---

## App: problemlist

### Problem

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `patient` | ForeignKey → Patient | CASCADE, related_name="problem_list" | |
| `name` | CharField(255) | db_index | Short clinical name |
| `description` | TextField | blank | |
| `date_of_onset` | DateField | null, blank | |
| `date_identified` | DateField | default=timezone.now, db_index | |
| `status` | CharField(20) | choices=PROBLEM_STATUS, default=ACTIVE, db_index | active/resolved/chronic/inactive |
| `severity` | CharField(20) | choices=SEVERITY_CHOICES, null, blank | mild/moderate/severe/life_threatening |
| `date_resolved` | DateField | null, blank | |
| `action_taken` | TextField | blank | |
| `outcome` | TextField | blank | |
| `comments` | TextField | blank | |

**Meta:** ordering = `["-date_identified"]`; composite index on `(patient, status)`

---

### ProblemAction

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `problem` | ForeignKey → Problem | CASCADE, related_name="actions" | |
| `action` | TextField | | Description of action |
| `date` | DateTimeField | default=timezone.now | When action was performed |
| `performed_by` | ForeignKey → CustomUser | SET_NULL, null | Who performed it |

**Meta:** ordering = `["-date"]`

---

## App: institution

### Institution

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `name` | CharField(255) | unique, db_index | |
| `slug` | SlugField(100) | unique, db_index; IMMUTABLE after creation | Used in file storage paths |
| `short_name` | CharField(10) | blank, default='' | |
| `logo` | ImageField | upload_to=get_institution_logo_path, null, blank | |
| `subscription_status` | CharField(20) | choices=SubscriptionStatus, default=ACTIVE | ACTIVE/GRACE/EXPIRED |
| `subscription_start` | DateField | null, blank | |
| `grace_period_end` | DateField | null, blank | |
| `is_active` | BooleanField | default=True, db_index | |
| `created_by` | ForeignKey → CustomUser | SET_NULL, null, blank, related_name="institutions_created" | SUPERADMIN who onboarded |

**Meta:** ordering = `['name']`

**Validation:** `clean()` and `save()` enforce slug immutability after creation.

---

### PatientMoveLog

Audit trail for SUPERADMIN patient-move operations.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `patient` | ForeignKey → Patient | CASCADE, db_index | |
| `from_institution` | ForeignKey → Institution | SET_NULL, null, related_name="moves_out", db_index | |
| `to_institution` | ForeignKey → Institution | SET_NULL, null, related_name="moves_in", db_index | |
| `moved_by` | ForeignKey → CustomUser | SET_NULL, null | |
| `notes` | TextField | blank | |

**Meta:** ordering = `["-created_at"]`

---

## App: referral

### ReferralSent

Owned by the sending institution. Created atomically with `ReferralReceived`.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `from_institution` | ForeignKey → Institution | SET_NULL, null, related_name="referrals_sent", db_index | |
| `to_institution` | ForeignKey → Institution | SET_NULL, null, related_name="referrals_received_at", db_index | |
| `patient` | ForeignKey → Patient | SET_NULL, null, related_name="referrals_sent", db_index | |
| `from_clinician` | ForeignKey → CustomUser | SET_NULL, null, related_name="referrals_sent_by", db_index | |
| `to_clinician` | ForeignKey → CustomUser | SET_NULL, null, related_name="referrals_received_by", db_index | |
| `referral_uuid` | UUIDField | default=uuid4, unique, db_index, editable=False | Shared link with ReferralReceived |
| `status` | CharField(20) | choices=ReferralStatus, default=PENDING, db_index | PENDING/REPLIED/CLOSED |
| `initial_message` | TextField | | Referral message |
| `snapshot_data` | JSONField | default=dict | Frozen patient snapshot; immutable after creation |
| `outcome` | TextField | blank | Added at closure |
| `institution` | ForeignKey → Institution | SET_NULL, null, related_name="referrals_owned_sent", db_index | Owning institution for scoping (= from_institution) |

**Manager:** `InstitutionScopedManager`

---

### ReferralReceived

Owned by the receiving institution. No FK to `ReferralSent` (fully independent).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `to_institution` | ForeignKey → Institution | SET_NULL, null, related_name="referrals_received", db_index | |
| `from_institution` | ForeignKey → Institution | SET_NULL, null, related_name="referrals_sent_from", db_index | |
| `patient_name` | CharField(200) | | Denormalized from snapshot |
| `from_clinician_name` | CharField(200) | | Denormalized sender name |
| `to_clinician` | ForeignKey → CustomUser | SET_NULL, null, related_name="referrals_received_as_clinician", db_index | |
| `referral_uuid` | UUIDField | db_index, editable=False | Copied from ReferralSent |
| `status` | CharField(20) | choices=ReferralStatus, default=PENDING, db_index | |
| `initial_message` | TextField | | |
| `snapshot_data` | JSONField | default=dict | Own copy of patient snapshot |
| `outcome` | TextField | blank | |
| `is_read` | BooleanField | default=False, db_index | Read flag |
| `institution` | ForeignKey → Institution | SET_NULL, null, related_name="referrals_owned_received", db_index | Owning institution (= to_institution) |

**Manager:** `InstitutionScopedManager`

---

### ReferralMessage

Consultation messages within a referral thread.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `referral_uuid` | UUIDField | db_index | Links to both ReferralSent and ReferralReceived |
| `sender` | ForeignKey → CustomUser | SET_NULL, null, related_name="referral_messages_sent", db_index | |
| `sender_institution` | ForeignKey → Institution | SET_NULL, null, related_name="referral_messages", db_index | |
| `body` | TextField | | Message body |
| `message_type` | CharField(20) | choices: OPINION, default=OPINION | |

**Meta:** ordering = `['created_at']` (chronological in thread)

---

### Notification

In-app notifications for referral lifecycle events.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `recipient` | ForeignKey → CustomUser | CASCADE, related_name="referral_notifications", db_index | |
| `notification_type` | CharField(30) | choices=NotificationType, db_index | REFERRAL_RECEIVED/REFERRAL_REPLIED/REFERRAL_CLOSED |
| `title` | CharField(200) | | |
| `body` | TextField | blank | |
| `link` | CharField(500) | blank | URL to navigate to |
| `is_read` | BooleanField | default=False, db_index | |
| `institution` | ForeignKey → Institution | CASCADE, related_name="notifications" | |

**Manager:** `InstitutionScopedManager`

Created exclusively via Django signals in `referral/signals.py`.
