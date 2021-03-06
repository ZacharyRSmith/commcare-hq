from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _

PRODUCTION_DOMAIN = 'm4change'
TEST_DOMAIN = 'test-pathfinder'
M4CHANGE_DOMAINS = (PRODUCTION_DOMAIN, TEST_DOMAIN)

NUMBER_OF_MONTHS_FOR_FIXTURES = 6

MOTHER_CASE_TYPE = "pregnant_mother"
CHILD_CASE_TYPE = "child"

M4CHANGE2_FOLLOW_UP_FORM_XMLNS = 'http://openrosa.org/formdesigner/56189892f7d8b3087d98b7599e0574f8e2031da6'
M4CHANGE2_BOOKING_FORM_XMLNS = 'http://openrosa.org/formdesigner/b9d9f943e63d5de8a6ea3a40a314bc5dafd2ef50'
M4CHANGE2_LAB_RESULT_UPDATE_FORM_XMLNS = 'http://openrosa.org/formdesigner/c313dc769f447de3224fe13102c75b299e1e6ab3'
M4CHANGE2_BOOKED_DELIVERY_FORM_XMLNS = 'http://openrosa.org/formdesigner/e951a60e291a2867a95d206441d876fbf204949d'
M4CHANGE2_UNBOOKED_DELIVERY_FORM_XMLNS = 'http://openrosa.org/formdesigner/3b48e25bab6e7bd0967336b81b1e008c9ab5e6f9'

M4CHANGE2R_FOLLOW_UP_FORM_XMLNS = 'http://openrosa.org/formdesigner/a336db2836b54b2c301a79ef531d30d00618577c'
M4CHANGE2R_BOOKED_DELIVERY_FORM_XMLNS = 'http://openrosa.org/formdesigner/dffcbe5c125f3b0c6859265b0f08abec9f4d23f0'

PNC_CHILD_IMMUNIZATION_FORM_XMLNS = 'http://openrosa.org/formdesigner/4dc380eadd46dfa9915f374934af30b5596edc92'
REG_HOME_DELIVERED_INFANT_FORM_XMLNS = 'http://openrosa.org/formdesigner/7fea595525157a9edd81b731d6b10f0b65a44ae2'

PMTCT_CLIENTS_FORM = 'http://openrosa.org/formdesigner/E671459B-7402-4B68-9020-7F49F0D94ED5'

BOOKING_FORMS = [
    M4CHANGE2_BOOKING_FORM_XMLNS,
]

FOLLOW_UP_FORMS = [
    M4CHANGE2_FOLLOW_UP_FORM_XMLNS,
    M4CHANGE2R_FOLLOW_UP_FORM_XMLNS,
]

LAB_RESULTS_FORMS = [
    M4CHANGE2_LAB_RESULT_UPDATE_FORM_XMLNS
]

IMMUNIZATION_FORMS = [
    PNC_CHILD_IMMUNIZATION_FORM_XMLNS
]

BOOKED_DELIVERY_FORMS = [
    M4CHANGE2_BOOKED_DELIVERY_FORM_XMLNS,
    M4CHANGE2R_BOOKED_DELIVERY_FORM_XMLNS
]

UNBOOKED_DELIVERY_FORMS = [
    M4CHANGE2_UNBOOKED_DELIVERY_FORM_XMLNS,
]

BOOKED_AND_UNBOOKED_DELIVERY_FORMS = BOOKED_DELIVERY_FORMS + UNBOOKED_DELIVERY_FORMS
BOOKING_AND_FOLLOW_UP_FORMS = BOOKING_FORMS + FOLLOW_UP_FORMS
BOOKING_FOLLOW_UP_AND_LAB_RESULTS_FORMS = BOOKING_AND_FOLLOW_UP_FORMS + LAB_RESULTS_FORMS
PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS = PNC_CHILD_IMMUNIZATION_FORM_XMLNS +\
                                                      REG_HOME_DELIVERED_INFANT_FORM_XMLNS

EMPTY_FIELD = "---"

REJECTION_REASON_DISPLAY_NAMES = {
    "none": _("None"),
    "phone_number": _("Incorrect phone number"),
    "double": _("Double entry"),
    "other": _("Other errors")
}

ALL_M4CHANGE_FORMS = [
    M4CHANGE2_FOLLOW_UP_FORM_XMLNS,
    M4CHANGE2_BOOKING_FORM_XMLNS,
    M4CHANGE2_LAB_RESULT_UPDATE_FORM_XMLNS,
    M4CHANGE2_BOOKED_DELIVERY_FORM_XMLNS,
    M4CHANGE2_UNBOOKED_DELIVERY_FORM_XMLNS,
    M4CHANGE2R_FOLLOW_UP_FORM_XMLNS,
    M4CHANGE2R_BOOKED_DELIVERY_FORM_XMLNS,
    PNC_CHILD_IMMUNIZATION_FORM_XMLNS,
    REG_HOME_DELIVERED_INFANT_FORM_XMLNS,
    PMTCT_CLIENTS_FORM
]

MCCT_SERVICE_TYPES = {
    "all": BOOKING_FORMS + FOLLOW_UP_FORMS + BOOKED_AND_UNBOOKED_DELIVERY_FORMS + IMMUNIZATION_FORMS,
    "registration": BOOKING_FORMS,
    "antenatal": FOLLOW_UP_FORMS,
    "delivery": BOOKED_AND_UNBOOKED_DELIVERY_FORMS,
    "immunization": IMMUNIZATION_FORMS
}

REDIS_FIXTURE_KEYS = dict([(domain, '%s-fixture-locations' % domain) for domain in M4CHANGE_DOMAINS])
REDIS_FIXTURE_LOCK_KEYS = dict([(domain, '%s-fixture-locations-lock' % domain) for domain in M4CHANGE_DOMAINS])
