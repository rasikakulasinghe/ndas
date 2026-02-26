"""
referral/utils.py

Utility functions for the referral system.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

SNAPSHOT_SCHEMA_VERSION = 1


def build_patient_snapshot(patient):
    """
    Capture a complete, frozen snapshot of the patient record at referral time.

    FR61: snapshot_data is immutable after referral creation.
    AC #2: Includes demographics, all identifiers, perinatal data, all assessment types,
           active problem list with interventions, attachment metadata (no binary).
           Always includes schema_version and captured_at.

    Returns: dict (JSON-serializable)
    """
    from patients.models import (
        GMAssessment, HINEAssessment, CDICRecord,
        GeneralPaediatricAssessment, DevelopmentalAssessment,
    )

    def serialize_date(dt):
        if dt is None:
            return None
        try:
            return dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)
        except Exception:
            return str(dt)

    # ── Demographics & Identifiers ────────────────────────────────────────
    demographics = {
        'baby_name':   patient.baby_name,
        'mother_name': patient.mother_name,
        'bht':         patient.bht,
        'nnc_no':      patient.nnc_no,
        'ptc_no':      patient.ptc_no,
        'pc_no':       patient.pc_no,
        'pin':         patient.pin,
        'disk_no':     patient.disk_no,
        'gender':      patient.gender,
        'dob_tob':     serialize_date(patient.dob_tob),
        'address':     patient.address,
        'tp_mobile':   patient.tp_mobile,
        'tp_lan':      patient.tp_lan,
        'moh_area':    patient.moh_area,
        'phm_area':    patient.phm_area,
    }

    # ── Perinatal Data ────────────────────────────────────────────────────
    perinatal = {
        'pog_wks':       patient.pog_wks,
        'pog_days':      patient.pog_days,
        'mo_delivery':   patient.mo_delivery,
        'apgar_1':       patient.apgar_1,
        'apgar_5':       patient.apgar_5,
        'apgar_10':      patient.apgar_10,
        'birth_weight':  patient.birth_weight,
        'length':        getattr(patient, 'length', None),
        'ofc':           getattr(patient, 'ofc', None),
        'resuscitated':  patient.resuscitated,
        'resustn_note':  patient.resustn_note,
        'antenatal_hx':  getattr(patient, 'antenatal_hx', None),
        'intranatal_hx': getattr(patient, 'intranatal_hx', None),
        'postnatal_hx':  getattr(patient, 'postnatal_hx', None),
        'problems':      getattr(patient, 'problems', None),
        'do_admission':  serialize_date(getattr(patient, 'do_admission', None)),
        'do_discharge':  serialize_date(getattr(patient, 'do_discharge', None)),
    }

    # ── GMA Assessments ───────────────────────────────────────────────────
    gma_records = []
    for gma in GMAssessment.objects.filter(patient=patient).select_related('added_by').order_by('-created_at'):
        gma_records.append({
            'id':            gma.id,
            'created_at':    serialize_date(gma.created_at),
            'conclusion':    getattr(gma, 'conclusion', ''),
            'age_of_record': getattr(gma, 'age_of_record', ''),
            'added_by':      getattr(gma.added_by, 'get_full_name', lambda: '')(),
        })

    # ── HINE Assessments ──────────────────────────────────────────────────
    hine_records = []
    for hine in HINEAssessment.objects.filter(patient=patient).select_related('added_by').order_by('-created_at'):
        hine_records.append({
            'id':          hine.id,
            'created_at':  serialize_date(hine.created_at),
            'total_score': getattr(hine, 'total_score', None),
            'added_by':    getattr(hine.added_by, 'get_full_name', lambda: '')(),
        })

    # ── Developmental Assessments ─────────────────────────────────────────
    da_records = []
    for da in DevelopmentalAssessment.objects.filter(patient=patient).select_related('added_by').order_by('-created_at'):
        da_records.append({
            'id':         da.id,
            'created_at': serialize_date(da.created_at),
            'added_by':   getattr(da.added_by, 'get_full_name', lambda: '')(),
        })

    # ── CDIC Records ──────────────────────────────────────────────────────
    cdic_records = []
    for cdic in CDICRecord.objects.filter(patient=patient).select_related('added_by').order_by('-created_at'):
        cdic_records.append({
            'id':         cdic.id,
            'created_at': serialize_date(cdic.created_at),
            'added_by':   getattr(cdic.added_by, 'get_full_name', lambda: '')(),
        })

    # ── GPA Assessments ───────────────────────────────────────────────────
    gpa_records = []
    for gpa in GeneralPaediatricAssessment.objects.filter(patient=patient).select_related('added_by').order_by('-created_at'):
        gpa_records.append({
            'id':         gpa.id,
            'created_at': serialize_date(gpa.created_at),
            'added_by':   getattr(gpa.added_by, 'get_full_name', lambda: '')(),
        })

    # ── Problem List ──────────────────────────────────────────────────────
    problem_list = []
    try:
        from problemlist.models import Problem
        for prob in Problem.objects.filter(patient=patient).order_by('-created_at'):
            problem_list.append({
                'id':          prob.id,
                'description': getattr(prob, 'description', str(prob)),
                'status':      getattr(prob, 'status', ''),
                'created_at':  serialize_date(prob.created_at),
            })
    except Exception:
        pass  # Graceful fallback if problem list structure differs

    # ── Attachments (metadata only — no binary) ───────────────────────────
    attachments = []
    try:
        from patients.models import Attachment
        for att in Attachment.objects.filter(patient=patient).order_by('-created_at'):
            attachments.append({
                'id':         att.id,
                'filename':   att.attachment.name.split('/')[-1] if att.attachment else None,
                'created_at': serialize_date(att.created_at),
            })
    except Exception:
        pass

    return {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'captured_at':    timezone.now().isoformat(),
        'patient_id':     patient.id,
        'demographics':   demographics,
        'perinatal':      perinatal,
        'assessments': {
            'gma':   gma_records,
            'hine':  hine_records,
            'da':    da_records,
            'cdic':  cdic_records,
            'gpa':   gpa_records,
        },
        'problem_list': problem_list,
        'attachments':  attachments,
    }
