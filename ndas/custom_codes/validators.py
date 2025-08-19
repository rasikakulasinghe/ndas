import os, math
from django.core.exceptions import ValidationError
from django.contrib import messages


def image_extension_validation(value):
    ext = os.path.splitext(value.name)[1]  # [0]
    valid_extensions = ['.jpg', '.jpeg', '.png']
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension, pls use .jpg, .jpeg, .png formats')

# validate BHT
def BHT_validation(request, value):
    if  value == '':
        messages.error(request, 'Please enter BHT number, field cant be empty...')
        return False
    elif not value.isnumeric():
        messages.error(request, 'Please enter valid BHT number, it cant contain any letter...')
        return False
    else:
        return True
    
# validate PHN
def PHN_validation(request, value):
    if  value == '':
        messages.error(request, 'Please enter PHN number, field cant be empty...')
        return False
    elif not value.isnumeric():
        messages.error(request, 'Please enter valid PHN number, it cant contain any letter...')
        return False
    else:
        return True
    
# validate NNC
def NNC_validation(request, value):
    if  value == '':
        messages.error(request, 'Please enter NNC number, field cant be empty...')
        return False
    elif not value.isnumeric():
        messages.error(request, 'Please enter valid NNC number, it cant contain any letter...')
        return False
    else:
        return True
    
# validate name of baby
def Name_baby_validation(request, value):
    if  value == '':
        messages.error(request, 'Please enter babies name, field cant be empty...')
    else:
        return True
    
# validate name of mother
def Name_mother_validation(request, value):
    if  value == '':
        messages.error(request, 'Please enter mothers name, field cant be empty...')
        return False
    else:
        return True

def validateVideoSize(var_uploaded_file):
    file_size_mb = math.ceil(var_uploaded_file.size / (1024 * 1024))
    if file_size_mb < 1000:
         return True
    else:
        return False

def validateVideoType(var_uploaded_file):
    extension = os.path.splitext(var_uploaded_file.name)[1].lower()
    if extension in ['.mp4', '.mov']:
        return True
    else:
        return False

def getFileType(var_uploaded_file):
    extension = os.path.splitext(var_uploaded_file.name)[1].lower()
    if extension in ['.jpg', '.jpeg',]:
        return 'Photo'
    elif extension in ['.mp4','.mov',]:
        return 'Video'
    elif extension in ['.pdf',]:
        return 'PDF'
    else:
        return 'Undefined'
    
def validateAttachmentSize(var_uploaded_file):
    file_size_mb = math.ceil(var_uploaded_file.size / (1024 * 1024))  # round up to the nearest whole number
    if file_size_mb > 100:
        return False
    else:
        return True

def validateAttachmentType(var_uploaded_file):
    extension = os.path.splitext(var_uploaded_file.name)[1].lower()
    if extension in ['.jpg', '.jpeg', '.mp4', '.mov', '.pdf']:
        return True
    else:
        return False


