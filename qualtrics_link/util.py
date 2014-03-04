#
# util.py
import hashlib
import hmac
import base64
from Crypto.Cipher import AES
from django.conf import settings
from datetime import date
from icommons_common.models import QualtricsAccessList

BLACKLIST = set(['HBS', 'HMS', 'HSDM'])
AREA_LOOKUP = {
    'SUM'  : 'EXT',
    'EXT'  : 'EXT',
    'DCE'  : 'EXT',
    'ECS'  : 'EXT',
    'FAS'  : 'FAS',
    'EAS'  : 'FAS', 
    'COL'  : 'FAS',
    'FGS'  : 'FAS',
    'GSD'  : 'GSD',
    'DES'  : 'GSD',
    'EDU'  : 'GSE',
    'GSE'  : 'GSE',
    'HDS'  : 'HDS',
    'DIV'  : 'HDS',
    'HKS'  : 'HKS',
    'KSG'  : 'HKS',
    'HLS'  : 'HLS',
    'LAW'  : 'HLS',
    'HSPH' : 'HSPH',
    'SPH'  : 'HSPH',
    'UIS'  : 'HUIT',
    'HUIT' : 'HUIT',
    'HBS'  : 'HBS',
    'HSDM' : 'HSDM',
    'HMS'  : 'HMS',
} 

BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS) 

def getencryptedhuid(huid):
    hasher = hashlib.md5()
    hasher.update(huid)
    encid = hasher.hexdigest()
    return encid

def createencodedtoken(keyvaluepairs):
    key = settings.QUALTRICS_LINK['QUALTRICS_APP_KEY']
    secret = bytes(key)
    data = bytes(keyvaluepairs)
    encoded = base64.b64encode(hmac.new(secret, data).digest())
    token = keyvaluepairs+'&mac='+encoded 
    raw = pad(token)
    cipher = AES.new(key, AES.MODE_ECB)
    encodedtoken = base64.b64encode(cipher.encrypt(raw)) 
    return encodedtoken

def getssotesturl(keyvaluepairs):
    key = settings.QUALTRICS_LINK['QUALTRICS_APP_KEY']
    encodedtoken = createencodedtoken(keyvaluepairs)
    ssotestlink = 'https://new.qualtrics.com/ControlPanel/ssoTest.php?key='+key+'&mac=md5&ssotoken='+encodedtoken
    return ssotestlink

def getqualtricsurl(keyvaluepairs):
    encodedtoken = createencodedtoken(keyvaluepairs)
    qualtricsurl = 'https://harvard.qualtrics.com/ControlPanel/?ssotoken='+encodedtoken
    return qualtricsurl

def getclientip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ipaddress = x_forwarded_for.split(',')[0]
    else:
        ipaddress = request.META.get('REMOTE_ADDR')
    return ipaddress

def lookupunit(unit):
    if unit in AREA_LOOKUP:
        return AREA_LOOKUP[unit]
    else:
        return 'Other'

def getvalidschool(schools):
    for schoolcode in schools:
        school = lookupunit(schoolcode)
        if  school not in BLACKLIST:
            return school
    return None

def isdeptvalid(dept):
    if dept.lower() == 'not available':
        return True
    division = lookupunit(dept)
    if  division in BLACKLIST:
        return False
    return True

def isuserinwhitelist(huid):
    try:
        person = QualtricsAccessList.objects.get(user_id=huid)
        if person.expiration_date:
            expiration_date = person.expiration_date   
            if expiration_date >= date.today():
                # the user is in the whitelist and has an expiration date that is valid
                return True
            else:
                # the user is in the whitelist and has an expiration date that has expired
                return False
        else:
            # the user is in the whitelist but has no expiration date
            return True
    except QualtricsAccessList.DoesNotExist:
        # the user is not in the whitelist'
        return False

def builduserdict(data):

    userdata = {}
    
    userdata['role'] = 'generic'
    userdata['division'] = 'Other'
    
    if 'people' in data:
        person = data['people'][0]
        
        if 'firstName' in person:
            userdata['firstname'] = person['firstName']
        else:
            userdata['firstname'] = None

        if 'lastName' in person:
            userdata['lastname'] = person['lastName']
        else:
            userdata['lastname'] = None

        if 'email' in person:
            userdata['email'] = person['email']
        else:
            userdata['email'] = None

        #Person Affiliations check
        if 'personAffiliation' in person:
            personaffiliation = person['personAffiliation']
            userdata['personaffiliation'] = personaffiliation
            if personaffiliation.lower() != 'not available':
                userdata['role'] = personaffiliation
        else:
            userdata['personaffiliation'] = None

        #School Affiliations check    
        if 'schoolAffiliations' in person:
            schoolaffiliations = person['schoolAffiliations']
            userdata['schoolaffiliations'] = schoolaffiliations
            valid_school_code = getvalidschool(schoolaffiliations)
            if valid_school_code:
                userdata['validschool'] = True
                userdata['role'] = 'student'
                userdata['division'] = valid_school_code
        else:
            userdata['schoolaffiliations'] = None

        # Department Affiliations check
        if 'departmentAffiliation' in person:
            departmentaffiliation = person['departmentAffiliation']
            userdata['departmentaffiliation'] = departmentaffiliation
            valid_department = isdeptvalid(departmentaffiliation)
            if valid_department:
                userdata['role'] = 'employee'
                userdata['division'] = departmentaffiliation
        else:
            userdata['departmentaffiliation'] = None

    return userdata
