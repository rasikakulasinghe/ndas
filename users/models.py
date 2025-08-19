from django.db import models
from django.contrib.auth.models import AbstractUser
from ndas.custom_codes.choice import POSSITION
from ndas.custom_codes.validators import image_extension_validation

# custom user
class CustomUser(AbstractUser):
    possition           = models.CharField(max_length= 17, choices=POSSITION, default='Medical Officer', null=False)
    tp_mobile_1         = models.CharField(max_length=12, null=False)
    tp_mobile_2         = models.CharField(max_length=12, null=False)
    tp_lan_1            = models.CharField(max_length=12, null=True)
    tp_lan_2            = models.CharField(max_length=12, null=True)
    address_home        = models.TextField(blank=True, null=True)
    address_station     = models.TextField(blank=True, null=True)
    last_login_device   = models.TextField(null=True)
    profile_pic         = models.ImageField(upload_to='profile_pic/',
                            height_field=None, width_field=None, max_length=100,
                            validators=[image_extension_validation], null=True, blank=True)
    other               = models.TextField(blank=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'password', 'first_name', 'possition', 'tp_mobile_1']

    def __str__(self):
        return str(self.first_name)

    @property
    def image_url(self):
        if self.profile_pic and hasattr(self.profile_pic, 'url'):
            return self.profile_pic.url

    class Meta:
        pass

class DevoloperContacts(models.Model):
    name = models.CharField(max_length=100, default='Dr. Rasika Kulasinghe')
    logo = models.ImageField(upload_to='static/image/', height_field=None, width_field=None, max_length=100, validators=[image_extension_validation], null=True, blank=True)
    qualifications = models.CharField(max_length=500, default='MBBS, HDIT, BIT')
    email = models.CharField(max_length=45, default='rasikakulasinghe@gmail.com')
    tel_mob = models.CharField(max_length=14, blank=True)
    tel_lan = models.CharField(max_length=14, blank=True)
    facebook = models.CharField(max_length=100, blank=True)
    twitter = models.CharField(max_length=100, blank=True)
    whatsapp = models.CharField(max_length=100, blank=True)
    youtube = models.CharField(max_length=100, blank=True)
    web = models.CharField(max_length=100, blank=True)

    def __str__(self):
            return self.name