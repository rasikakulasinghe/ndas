from django.db import models
from ndas.custom_codes.choice import MODE_OF_DELIVERY, GENDER, LEVEL_OF_INDICATION, POG_DAYS, POG_WKS, APGAR, BOOKMARK_TYPE, ATTACHMENT_TYPE, DX_CONCLUTION
from ndas.custom_codes.custom_methods import getCountZeroIfNone, get_video_path_file_name, get_attachment_path_file_name, getCurrentDateTime, checkRCState
from datetime import datetime, timedelta
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.core.validators import MaxValueValidator, MinValueValidator
from djrichtextfield.models import RichTextField


class Patient(models.Model):
    bht         = models.CharField(max_length=20, unique=True, null=True, blank=True, default=None)
    nnc_no      = models.CharField(max_length=20, unique=True, null=True, blank=True, default=None)
    ptc_no      = models.CharField(max_length=20, unique=True, null=True, blank=True, default=None)
    pc_no       = models.CharField(max_length=20, unique=True, null=True, blank=True, default=None)
    pin         = models.CharField(max_length=20, unique=True, null=True, blank=True, default=None)
    disk_no     = models.CharField(max_length=20, null=True, blank=True, default=None)
    baby_name   = models.CharField(verbose_name="Name of the baby", max_length=100, null=False, blank=False)
    mother_name = models.CharField(verbose_name="Name of the mother",max_length=100, null=False, blank=False)
    pog_wks     = models.SmallIntegerField(choices=POG_WKS, default='40', null=False, blank=False)
    pog_days    = models.SmallIntegerField(choices=POG_DAYS, default='0', null=False, blank=False)
    gender      = models.CharField(max_length= 8, choices=GENDER, default='', null=False)
    dob_tob     = models.DateTimeField(null=False, blank=False)
    mo_delivery = models.CharField(max_length= 35, choices=MODE_OF_DELIVERY, default='NVD', null=False)
    apgar_1     = models.SmallIntegerField(choices=APGAR, default='10', null=False, blank=False)
    apgar_5     = models.SmallIntegerField(choices=APGAR, default='10', null=False, blank=False)
    apgar_10    = models.SmallIntegerField(choices=APGAR, default='10', null=False, blank=False)
    resuscitated= models.BooleanField(default=False)
    resustn_note= models.TextField(null=True, blank=True)
    birth_weight= models.SmallIntegerField(verbose_name="Birth weight", null=False, blank=False)
    length      = models.SmallIntegerField(null=True, blank=True)
    ofc         = models.SmallIntegerField(verbose_name=u"OFC", null=False, blank=False)
    address     = models.TextField(null=True, blank=True)
    tp_mobile   = models.CharField(max_length=15, null=False, blank=False)
    tp_lan      = models.CharField(max_length=15, null=True, blank=True)
    moh_area    = models.CharField(max_length=255, null=True, blank=True, default=None)
    phm_area    = models.CharField(max_length=255, null=True, blank=True, default=None)
    problems    = models.TextField(null=True, blank=True, default=None)
    indecation_for_gma      = models.ManyToManyField('IndicationsForGMA', verbose_name=u"Indications for GMA")
    antenatal_hx            = models.TextField(null=True, blank=True)
    intranatal_hx           = models.TextField(null=True, blank=True)
    postnatal_hx            = models.TextField(null=True, blank=True)
    do_admission            = models.DateTimeField(blank=True, null=True)
    do_discharge            = models.DateTimeField(blank=True, null=True)
    other_relavent_details  = models.TextField(null=True, blank=True)
    added_by                = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='pt_added_user', null=True)
    added_on                = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by            = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='pt_created_user', null=True)
    last_edit_on            = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        pass

    def __str__(self):
        return self.baby_name + " | " + str(self.pin)

    @property
    def isNewPatient(self):
        file_exist = Video.objects.filter(patient=self.id).exists()
        return False if file_exist else True
    
    @property
    def isDischarged(self):
        return CDICRecord.objects.all().order_by('-id').first().is_discharged

    @property
    def getAPGAR(self):
        # access to this discharge status in assessment model
        return str(self.apgar_1) + " - " + str(self.apgar_5) + " - " + str(self.apgar_10)
    
    @property
    def isScreeningPositive(self):
        var_gma_record = self.gmassessment_set.order_by('-id').first()
        if var_gma_record is not None:
            latest_gma_assessment = self.gmassessment_set.order_by('-id').first().isDiagnosisNormal
        else:
            latest_gma_assessment = True
            
        hine_records = HINEAssessment.objects.filter(patient=self.id)
        hine_record_count = getCountZeroIfNone(hine_records)

        if hine_record_count == 0 and latest_gma_assessment == True:
            return False
        if hine_record_count > 0:
            
            last_hine_score = hine_records.order_by('-id').first().score
            
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
        return str(self.pog_wks) + " Weeks and " + str(self.pog_days) + " Days"
    
    @property
    def getResuscitationState(self):
        return str(self.resustn_note) if self.resuscitated else 'Not resuscitated'
    
    @property
    def isLastGMANormal(self):
        #check assessment is there
        if GMAssessment.objects.filter(patient=self.id).exists():
            try:
                return GMAssessment.objects.filter(patient=self.id).order_by('-id').first().diagnosis.all().filter(title='Normal').exists()
            except:
                return False
        else:
            return True
    
    @property
    def isLastHINENormal(self):
        return self.hineassessment_set.order_by('-id').first().isNormal
    
    @property
    def isLastDANormal(self):
        
        return 
    
    @property
    def isBookmarked(self):
        return Bookmark.objects.get(bookmark_type='Patient', object_id=self.id)
    
    @property
    def getGMAIndicationsList(self):
        return ', '.join(map(str, list(self.indecation_for_gma.all().values_list('title', flat=True))))

    @property
    def getDiagnosisList(self):
        
        try:
            var_gma_dx_list =  ', '.join(map(str, list(self.gmassessment_set.order_by('-id').first().diagnosis.all().values_list('title', flat=True))))
        except:
            var_gma_dx_list =  'No GM assessments'
        
        var_dx_hine = self.hineassessment_set.order_by('-id').first()
        var_dx_da = self.developmentalassessment_set.order_by('-id').first()
        
        dx_gma = var_gma_dx_list
        dx_hine = 'Score - ' + str(var_dx_hine.score) if var_dx_hine is not None else 'No HINE records'
        dx_da = var_dx_da.isDxNormal if var_dx_da is not None else 'No DA records'

        return dx_gma, dx_hine, dx_da

    @property
    def getCurrentAge(self):
        var_results = relativedelta(timezone.now().date(), self.dob_tob.date())
        age_yrs = var_results.years
        age_mnths = var_results.months
        age_days = var_results.days
        return f'{age_yrs} Years {age_mnths} Months {age_days} Days'
    
    @property
    def getCorrectedAge(self):
        gestational_age = self.pog_wks * 7 + self.pog_days  # Calculate gestational age in days
        term_age = 40 * 7  # Term age in days
        
        if gestational_age < term_age:
            days_till_term = term_age - gestational_age
            var_results = relativedelta((timezone.now().date() - timedelta(days = days_till_term)), self.dob_tob.date())
        else:
            var_results = relativedelta(timezone.now().date(), self.dob_tob.date())
        age_yrs = var_results.years
        age_mnths = var_results.months
        age_days = var_results.days
        return f'{age_yrs} Years {age_mnths} Months {age_days} Days'

    @property
    def getCorrectedGestationalAge(self):
        final_corr_age_wks = 0
        final_corr_age_ds = 0
        
        born = self.dob_tob.date()
        today = timezone.now().date()
        ageindays = (today - born).days
        
        #get current age in wks and days
        ageindays_wks, ageindays_days = divmod(ageindays, 7)

        corr_age_wks = self.pog_wks + ageindays_wks
        corr_age_days = self.pog_days + ageindays_days

        if corr_age_days < 7:
            final_corr_age_wks = corr_age_wks
            final_corr_age_ds = corr_age_days
        elif corr_age_days > 7:
            final_corr_age_wks = corr_age_wks + int(corr_age_days/7)
            final_corr_age_ds = corr_age_days % 7
        elif corr_age_days == 7:
            final_corr_age_wks = corr_age_wks + int(corr_age_days/7) + 1
            final_corr_age_ds = 0

        #returning final values
        if final_corr_age_wks < 40:
            return f'{final_corr_age_wks} + {final_corr_age_ds}'
        else:
            return f'Term +'

    @property
    def getRC(self):
        
        gma_count = GMAssessment.objects.filter(patient=self.id).count()
        current_age = int((timezone.now().date() - self.dob_tob.date()).days / 30)
        
        try:
            last_hine_score = HINEAssessment.objects.filter(patient=self.id).last().score
        except AttributeError:
            last_hine_score = 0
            
        rc_state = False
        
        # check 1st GMA assessment
        if gma_count == 0 and current_age <= 2:
            check_1st_gma_wm = {'msg': 'Please perform the initial General Movement Assessment (GMA) to assess writhing movements.', 'display': True}
        else:
            check_1st_gma_wm = {'msg': '', 'display': False}
            
        # check 1st GMA assessment
        if gma_count == 0 and current_age > 2:
            check_1st_gma_fm = {'msg': 'Please perform the initial General Movement Assessment (GMA) to assess and identify fidget movements.', 'display': True}
        else:
            check_1st_gma_fm = {'msg': '', 'display': False}
            
        # check 2nd GMA assessment
        if gma_count == 1 and current_age > 2:
            check_2nd_gma = {'msg': 'Please perform the second (2nd) General Movement Assessment (GMA) to assess and identify fidget movements.', 'display': True}
        else:
            check_2nd_gma = {'msg': '', 'display': False}
                    
        # check HINE time
        if 4 <= current_age <= 6 and current_age > 2 and gma_count == 2:
            check_HINE_time = {'msg': 'It is time to perform the HINE (Hammersmith Infant Neurological Examination).', 'display': True}
        else:
            check_HINE_time = {'msg': '', 'display': False}
            
        # check physiotheraphy indication
        if self.isLastGMANormal == False and last_hine_score < 73:
            is_pt_indicated = {'msg': 'Screening positive. Please refer baby to the Multidisciplinary Team (MDT) at the Child Development and Intervention Center/ Clinic (CDIC)', 'display': True}
        else:
            is_pt_indicated = {'msg': '', 'display': False}
            
        if checkRCState(check_1st_gma_wm) or checkRCState(check_1st_gma_fm) or checkRCState(check_2nd_gma) or checkRCState(check_HINE_time) or checkRCState(is_pt_indicated):
            rc_state = True
        else:
            rc_state = False
        
        # check discharge state
        cdic_record = CDICRecord.objects.filter(patient=self.id).order_by('-id').first()
        
        if cdic_record is not None:
            discharge_state = CDICRecord.objects.filter(patient=self.id).order_by('-id').first().is_discharged
        else:
            discharge_state = False
            
        if discharge_state:
            return False
        else:
            return [rc_state, check_1st_gma_wm, check_1st_gma_fm, check_2nd_gma, check_HINE_time, is_pt_indicated]

class GMAssessment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=False)
    video_file = models.OneToOneField('Video', on_delete=models.CASCADE, null=False, default=0)
    date_of_assessment = models.DateTimeField(auto_now_add=False, blank=False, null=False)
    diagnosis = models.ManyToManyField('DiagnosisList')
    diagnosis_other = models.TextField(null=True, blank=True)
    diagnosis_conclution = models.CharField(max_length= 8, choices=DX_CONCLUTION, default='NORMAL', null=True)
    managment_plan = models.TextField(null=True, blank=True)
    next_assessment_date = models.DateField(auto_now_add=False, blank=True, null=True)
    parant_informed = models.BooleanField(default=False)
    created_by = models.ForeignKey('users.CustomUser', related_name='gm_assmnt_created_user', on_delete=models.CASCADE, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    edit_by = models.ForeignKey('users.CustomUser', related_name='gm_assmnt_edited_user', on_delete=models.CASCADE, null=True, blank=True)
    edit_on = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        pass

    def __str__(self):
        return str(self.date_of_assessment) + ' | ' + str(self.patient.baby_name)

    @property
    def getAssessmentAge(self):
        return self.video_file.getAgeOnRecord
    
    @property
    def isBookmarked(self):
        return Bookmark.objects.get(bookmark_type='GMA', object_id=self.id)
    
    @property
    def isDiagnosisNormal(self):
        if self.diagnosis_conclution=='NORMAL':
            return True
        else:
            return False
        
    @property
    def getDiagnosis(self):
        d_list_obj = self.diagnosis.all()
        d_list_abr = []
        
        for item in d_list_obj.iterator():
            d_list_abr.append(item.abr)
        
        if 'Normal' in d_list_abr:
            return 'Normal'
        else:
            return ', '.join(str(element.title) for element in d_list_obj)

class CDICRecord(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=False)
    assessment_date = models.DateField(auto_now_add=False, blank=False, null=False)
    assessment = models.TextField(null=True, blank=True)
    assessment_done_by = models.TextField(null=True, blank=True)
    today_interventions = models.TextField(null=True, blank=True)
    next_appoinment_date = models.DateTimeField(auto_now_add=False, blank=True, null=True)
    next_appoinment_plan = models.TextField(null=True, blank=True)
    is_discharged = models.BooleanField(default=False, blank=False, null=False)
    dishcharged_by = models.TextField(null=True, blank=True)
    dischaged_date = models.DateField(auto_now_add=False, blank=True, null=True)
    discharge_plan = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey('users.CustomUser', related_name='cdic_assmnt_created_user', on_delete=models.CASCADE, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    edit_by = models.ForeignKey('users.CustomUser', related_name='cdic_assmnt_edited_user', on_delete=models.CASCADE, null=True, blank=True)
    edit_on = models.DateTimeField(auto_now=True, blank=True, null=True)
    
    class Meta:
        pass

    def __str__(self):
        return str(self.assessment_date) + ' | ' + str(self.patient.baby_name)
    
    @property
    def isBookmarked(self):
        return Bookmark.objects.get(bookmark_type='CDICR', object_id=self.id)
    
class Video(models.Model):
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, null=True)
    caption = models.CharField(max_length=75, null=False, blank=False)
    video = models.FileField(upload_to=get_video_path_file_name, blank=True, null=True)
    recorded_on = models.DateField(blank=False, null=False, default=datetime.now)
    description = models.TextField(null=True, blank=True)
    uploaded_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, null=True, blank=True)
    uploaded_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='video_last_edit_by', null=True, blank=True)
    last_edit_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        pass

    def __str__(self):
        return str(self.caption + " | " + self.video.name)

    @property
    def getAgeOnRecord(self):
        # return self.patient.dob_tob - self.recorded_on
        x = (self.recorded_on - self.patient.dob_tob.date())
        
        var_age = x.days
        if var_age < 7:
            return f'{var_age}  Days'
        elif var_age == 7:
            return f'1 Week'
        elif var_age > 7 and var_age < 30:
            ageindays_wks, ageindays_days = divmod(var_age, 7)
            return f'{ageindays_wks} Weeks and {ageindays_days} Days'
        elif var_age == 30:
            return f'1 Month'
        elif var_age > 30 and var_age < 365:
            ageindays_mnths, ageindays_days = divmod(var_age, 30)
            return f'{ageindays_mnths} Months and {ageindays_days} Days'
        elif var_age == 365:
            return f'1 Year'
        elif var_age > 365:
            ageindays_yrs, ageindays_days = divmod(var_age, 365)
            return f'{ageindays_yrs} Years and {ageindays_days} Days'
    
    @property
    def isNewFile(self):
        var_new = GMAssessment.objects.filter(video_file=self.pk).exists()
        return False if var_new else True
    
    @property
    def isBookmarked(self):
        return Bookmark.objects.filter(bookmark_type='File', object_id=self.id).first()

class Attachment(models.Model):
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=75, null=False, blank=False)
    attachment = models.FileField(upload_to=get_attachment_path_file_name, blank=False, null=False)
    attachment_type = models.CharField(max_length= 5, choices=ATTACHMENT_TYPE, default='Image', null=False)
    description = models.TextField(null=True, blank=True)
    uploaded_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, null=True, blank=True)
    uploaded_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='attachment_last_edit_by', null=True, blank=True)
    last_edit_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        pass
    
    def __str__(self):
        return str(self.title + " | " + self.attachment_type)
    
    @property
    def isBookmarked(self):
        return Bookmark.objects.get(bookmark_type='Attachment', object_id=self.id)

class Bookmark(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    bookmark_type = models.CharField(max_length= 10, choices=BOOKMARK_TYPE, default='Video', null=False)
    object_id = models.PositiveIntegerField(null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='bm_last_edit_by', null=True, blank=True)
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
    level = models.CharField(max_length= 6, choices=LEVEL_OF_INDICATION, null=False)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='gmai_created_by', null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='gmai_last_edit_by', null=True, blank=True)
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
    video_1 =  models.FileField(upload_to='tutorials/', blank=True, null=True)
    video_2 = models.FileField(upload_to='tutorials/', blank=True, null=True)
    
    class Meta:
        pass

    def __str__(self):
        return self.title

class HINEAssessment(models.Model):
    patient             = models.ForeignKey(Patient, on_delete=models.CASCADE, null=False)
    date_of_assessment  = models.DateTimeField(auto_now_add=False, blank=False, null=False)
    score               = models.SmallIntegerField(verbose_name=u"HINE Score", validators=[MinValueValidator(0), MaxValueValidator(78)],null=False, blank=False)
    assessment_done_by  = models.CharField(max_length=200, null=False, blank=False)
    comment             = models.TextField(null=True, blank=True)
    added_by            = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='hine_added_user', null=True)
    added_on            = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by        = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='hine_created_user', null=True)
    last_edit_on        = models.DateTimeField(auto_now=True, blank=True, null=True)
    
    class Meta:
        pass

    def __str__(self):
        return f'{{self.score}} - {{str(self.date_of_assessment)}}'
    
    @property
    def getAssessmentAgeInMonths(self):
        ageindays_months, ageindays_days = divmod((self.date_of_assessment - self.patient.dob_tob).days, 30)
        return f' {ageindays_months} Months and {ageindays_days} Days'
    
    @property
    def isBookmarked(self):
        return Bookmark.objects.get(bookmark_type='HINE', object_id=self.id)
    
    @property
    def isNormal(self):
        if self.score > 73:
            return True
        else:
            return False

class DevelopmentalAssessment(models.Model):
    patient             = models.ForeignKey(Patient, on_delete=models.CASCADE, null=False)
    date_of_assessment  = models.DateTimeField(auto_now_add=False, blank=False, null=False)
    gm_age_from         = models.SmallIntegerField(null=True, blank=True)
    gm_age_to           = models.SmallIntegerField(null=True, blank=True)
    gm_details          = models.TextField(null=True, blank=True)
    fmv_age_from        = models.SmallIntegerField(null=True, blank=True)
    fmv_age_to          = models.SmallIntegerField(null=True, blank=True)
    fmv_details         = models.TextField(null=True, blank=True)
    hsl_age_from        = models.SmallIntegerField(null=True, blank=True)
    hsl_age_to          = models.SmallIntegerField(null=True, blank=True)
    hsl_details         = models.TextField(null=True, blank=True)
    seb_age_from        = models.SmallIntegerField(null=True, blank=True)
    seb_age_to          = models.SmallIntegerField(null=True, blank=True)
    seb_details         = models.TextField(null=True, blank=True)
    assessment_done_by  = models.CharField(max_length=200, null=False, blank=False)
    comment             = models.TextField(null=True, blank=True)
    added_by            = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='da_added_user', null=True)
    added_on            = models.DateTimeField(auto_now_add=True, blank=False, null=False)
    last_edit_by        = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='da_created_user', null=True)
    last_edit_on        = models.DateTimeField(auto_now=True, blank=True, null=True)
    isDxNormal          = models.BooleanField(default=False)
    
    class Meta:
        pass

    def __str__(self):
        return f'{{self.patient.baby_name}} - {{str(self.date_of_assessment)}}'
    
    @property
    def getAssessmentAgeInMonths(self):
        ageindays_months, ageindays_days = divmod((self.date_of_assessment - self.patient.dob_tob).days, 30)
        return f' {ageindays_months} Months and {ageindays_days} Days'
    
    @property
    def isNormal(self):
        ageindays_months, xx = divmod((self.date_of_assessment - self.patient.dob_tob).days, 30)
        var_gm = ageindays_months <= self.gm_age_to and ageindays_months >= self.gm_age_from
        var_fv = ageindays_months <= self.fmv_age_to and ageindays_months >= self.fmv_age_from
        var_hsl = ageindays_months <= self.hsl_age_to and ageindays_months >= self.hsl_age_from
        var_seb = ageindays_months <= self.seb_age_to and ageindays_months >= self.seb_age_from
        
        return var_gm and var_fv and var_hsl and var_seb

    @property
    def isBookmarked(self):
        return Bookmark.objects.get(bookmark_type='DA', object_id=self.id)
    
    def save(self, *args, **kwargs):
        self.isDxNormal = self.isNormal
        super().save(*args, **kwargs)