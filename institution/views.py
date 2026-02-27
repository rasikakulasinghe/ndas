"""
institution/views.py

Institution management views for Phase 2 Multi-Institution expansion.
Implements superadmin network operations (Epic 2) and institution admin self-management (Epic 3).
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.db.models import Count, Max
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.static import serve as django_serve_static
from django_ratelimit.decorators import ratelimit

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus
from ndas.custom_codes.error_handlers import handle_view_errors

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Story 2.1 — Institution Selector Screen
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url="user-login")
@require_GET
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='manage-patients', error_message='Unable to load institution network.')
def institution_selector(request):
    """
    SUPERADMIN god-view: shows all institutions as cards with aggregate metrics.
    Destination for InstitutionContextMiddleware redirect when SUPERADMIN has no active context.

    AC: FR50 — superadmin network overview dashboard.
    """
    user_type = getattr(request.user, 'user_type', None)

    # Access guard: only SUPERADMIN can see the network selector
    if user_type != UserType.SUPERADMIN:
        # TODO (Story 3.1): ADMIN → redirect to 'institution:institution-admin-dashboard' once implemented
        return redirect('manage-patients')

    # Clear active institution context — being on the selector means no institution is selected
    request.session.pop('active_institution_id', None)

    # Aggregate all institutions with user count, patient count, last activity
    # CustomUser.institution related_name='users' → Count('users')
    # Patient.institution related_name='patients' → Count('patients')
    institutions = Institution.objects.annotate(
        user_count=Count('users', distinct=True),
        patient_count=Count('patients', distinct=True),
        last_activity=Max('patients__created_at'),
    ).select_related('created_by').order_by('name')

    return render(request, 'institution/selector.html', {
        'institutions': institutions,
        'page_title': 'Institution Network',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Story 2.2 — Institution Context Switching (full implementation)
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url="user-login")
@require_POST
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='institution:institution-selector', error_message='Context switch failed.')
def institution_switch(request, institution_id):
    """
    SUPERADMIN context switch — sets session['active_institution_id'].
    POSTed from selector.html cards AND from the superadmin_overlay dropdown.
    After switching, redirects to manage-patients (full page reload, new institution context).

    AC: FR51 — persistent on-screen institution context switching.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    institution = get_object_or_404(Institution, pk=institution_id, is_active=True)

    # Log context switch for audit trail
    previous_id = request.session.get('active_institution_id')
    previous_name = '(none)'
    if previous_id:
        try:
            previous_name = Institution.objects.get(pk=previous_id).name
        except Institution.DoesNotExist:
            previous_name = f'(id={previous_id}, deleted)'

    request.session['active_institution_id'] = institution.pk

    logger.info(
        "SUPERADMIN %s switched institution context: '%s' → '%s' (id=%d)",
        request.user.username, previous_name, institution.name, institution.pk,
    )

    messages.success(request, f"Viewing as: {institution.name}")
    return redirect('manage-patients')


# ─────────────────────────────────────────────────────────────────────────────
# Story 2.3 — Atomic Institution Onboarding
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='institution:institution-selector',
    error_message='Failed to load institution onboarding form.'
)
def institution_add(request):
    """
    Atomic institution onboarding: creates Institution + first ADMIN account in one transaction.
    SUPERADMIN only.

    GET:  Display blank InstitutionOnboardingForm.
    POST: Validate → transaction.atomic() → create Institution + CustomUser(ADMIN) → redirect.

    AC: FR52 — no institution without admin; NFR13 — atomic operation.
    """
    from institution.forms import InstitutionOnboardingForm

    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    form = InstitutionOnboardingForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                # ── Step 1: Create Institution ─────────────────────────────
                institution = Institution.objects.create(
                    name=form.cleaned_data['institution_name'],
                    slug=form.cleaned_data['institution_slug'],
                    subscription_status=SubscriptionStatus.ACTIVE,
                    is_active=True,
                    created_by=request.user,
                )

                # ── Step 2: Create first ADMIN account ────────────────────
                # If this step raises any exception, the transaction rolls back
                # and institution above is also undone — no orphan Institution.
                admin_user = User.objects.create_user(
                    username=form.cleaned_data['admin_username'],
                    password=form.cleaned_data['admin_password'],
                    email=form.cleaned_data['admin_email'],
                    first_name=form.cleaned_data['admin_first_name'],
                    last_name=form.cleaned_data.get('admin_last_name', ''),
                    position=form.cleaned_data['admin_position'],
                    mobile_primary=form.cleaned_data['admin_mobile'],
                    user_type=UserType.ADMIN,
                    institution=institution,
                    is_active=True,
                )

            # Transaction committed successfully — both records exist
            logger.info(
                "SUPERADMIN '%s' onboarded institution '%s' (slug=%s, admin='%s')",
                request.user.username,
                institution.name,
                institution.slug,
                admin_user.username,
            )
            messages.success(
                request,
                f"Institution '{institution.name}' successfully onboarded. "
                f"Admin account '{admin_user.username}' created."
            )
            return redirect('institution:institution-selector')

        except IntegrityError as e:
            # Catch race-condition duplicate slug/username that slipped past form validation
            logger.warning(
                "IntegrityError during institution onboarding by '%s': %s",
                request.user.username, str(e)
            )
            form.add_error(
                None,
                "Onboarding failed: a duplicate slug or username was detected. "
                "Please verify the slug and username are unique."
            )

    return render(request, 'institution/add.html', {
        'form': form,
        'page_title': 'Onboard New Institution',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Story 2.4 — Cross-Institution Aggregate Analytics Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url="user-login")
@require_GET
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='institution:institution-selector',
    error_message='Failed to load superadmin analytics dashboard.'
)
def superadmin_dashboard(request):
    """
    Cross-institution aggregate analytics dashboard (FR53).

    READ-ONLY view. Deliberately queries ALL institutions without scoping —
    this is an intentional superadmin aggregate, not an accidental data leak.

    SUPERADMIN only.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    # ── Date range for "current month" activity ───────────────────────────
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── All institutions — intentional cross-institution read (FR53) ──────
    # CustomUser.institution related_name='users' → Count('users')
    # Patient.institution related_name='patients' → Count('patients')
    institutions = Institution.objects.annotate(
        user_count=Count('users', distinct=True),
        patient_count=Count('patients', distinct=True),
    ).select_related('created_by').order_by('name')

    # ── Assessment volumes this month — grouped by institution ─────────────
    # Each dict maps {institution_id: count} using patient__institution_id path
    # O(5) queries total regardless of institution count — scalable.
    from patients.models import (
        GMAssessment, HINEAssessment, CDICRecord,
        GeneralPaediatricAssessment, DevelopmentalAssessment
    )

    def _assessment_counts(model):
        """Return {institution_id: count} dict for the current month."""
        return dict(
            model.objects.filter(created_at__gte=month_start)
            .values('patient__institution_id')
            .annotate(count=Count('id'))
            .values_list('patient__institution_id', 'count')
        )

    gma_counts  = _assessment_counts(GMAssessment)
    hine_counts = _assessment_counts(HINEAssessment)
    cdic_counts = _assessment_counts(CDICRecord)
    gpa_counts  = _assessment_counts(GeneralPaediatricAssessment)
    da_counts   = _assessment_counts(DevelopmentalAssessment)

    # ── Build per-institution card data ────────────────────────────────────
    institution_data = []
    for inst in institutions:
        inst_id = inst.pk
        a_gma  = gma_counts.get(inst_id, 0)
        a_hine = hine_counts.get(inst_id, 0)
        a_cdic = cdic_counts.get(inst_id, 0)
        a_gpa  = gpa_counts.get(inst_id, 0)
        a_da   = da_counts.get(inst_id, 0)
        total_assessments = a_gma + a_hine + a_cdic + a_gpa + a_da

        institution_data.append({
            'institution': inst,
            'user_count': inst.user_count,
            'patient_count': inst.patient_count,
            'assessment_counts': {
                'gma': a_gma,
                'hine': a_hine,
                'cdic': a_cdic,
                'gpa': a_gpa,
                'da': a_da,
                'total': total_assessments,
            },
            # STUB: ReferralSent/ReferralReceived not yet available (Story 4.1).
            'referral_counts': {
                'sent': 0,
                'received': 0,
                'pending': 0,
                'closed': 0,
            },
        })

    # ── Recent events: institution onboardings (newest first) ─────────────
    recent_institutions = Institution.objects.select_related(
        'created_by'
    ).order_by('-created_at')[:10]

    # ── Platform-wide summary totals ─────────────────────────────────────
    total_institutions = len(institution_data)
    total_patients = sum(d['patient_count'] for d in institution_data)
    total_users = sum(d['user_count'] for d in institution_data)
    total_assessments_this_month = sum(
        d['assessment_counts']['total'] for d in institution_data
    )

    logger.info(
        "SUPERADMIN '%s' viewed aggregate analytics dashboard (%d institutions)",
        request.user.username, total_institutions
    )

    return render(request, 'institution/superadmin_dashboard.html', {
        'institution_data': institution_data,
        'recent_institutions': recent_institutions,
        'month_name': now.strftime('%B %Y'),
        'total_institutions': total_institutions,
        'total_patients': total_patients,
        'total_users': total_users,
        'total_assessments_this_month': total_assessments_this_month,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Story 2.5 — Cross-Institution Aggregate Reports
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='institution:institution-selector',
    error_message='Failed to generate report. Please try again.'
)
def superadmin_reports(request):
    """
    Cross-institution aggregate report export — three scopes (FR54):
    1. per_institution  — one institution's full data (Excel)
    2. cross_institution — all institutions aggregate (Excel)

    SUPERADMIN only.

    GET:  Render scope selector form.
    POST: Generate and stream the export.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    institutions = Institution.objects.order_by('name')

    if request.method == 'POST':
        scope = request.POST.get('scope', '')
        institution_id = request.POST.get('institution_id', '')

        # ── Validate scope ─────────────────────────────────────────────
        valid_scopes = ('per_institution', 'cross_institution')
        if scope not in valid_scopes:
            messages.error(request, "Invalid report scope selected.")
            return render(request, 'institution/superadmin_reports.html', {
                'institutions': institutions,
            })

        if scope == 'per_institution' and not institution_id:
            messages.error(request, "Please select a target institution for per-institution export.")
            return render(request, 'institution/superadmin_reports.html', {
                'institutions': institutions,
            })

        from reports.utils.excel_generator import ExcelReportGenerator
        generator = ExcelReportGenerator()

        try:
            if scope == 'per_institution':
                target_institution = get_object_or_404(Institution, pk=institution_id)
                output_path, metadata = generator.per_institution_aggregate(
                    institution=target_institution,
                )
                filename = (
                    f"ndas_{target_institution.slug}_report_"
                    f"{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )

            else:  # cross_institution
                output_path, metadata = generator.cross_institution_aggregate()
                filename = (
                    f"ndas_network_report_"
                    f"{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )

            logger.info(
                "SUPERADMIN '%s' generated %s report → %s",
                request.user.username, scope, filename
            )

            response = FileResponse(
                open(output_path, 'rb'),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            logger.error(
                "Report generation failed for SUPERADMIN '%s', scope='%s': %s",
                request.user.username, scope, str(e)
            )
            messages.error(request, f"Report generation failed: {str(e)}")

    return render(request, 'institution/superadmin_reports.html', {
        'institutions': institutions,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Story 2.6 — Patient Move Between Institutions
# ─────────────────────────────────────────────────────────────────────────────

def _get_move_impact(patient):
    """Return impact preview dict for moving this patient. Lazy imports for circular safety."""
    from patients.models import (
        GMAssessment, HINEAssessment, CDICRecord,
        GeneralPaediatricAssessment, DevelopmentalAssessment,
    )
    from video.models import Video

    gma_count  = GMAssessment.objects.filter(patient=patient).count()
    hine_count = HINEAssessment.objects.filter(patient=patient).count()
    cdic_count = CDICRecord.objects.filter(patient=patient).count()
    gpa_count  = GeneralPaediatricAssessment.objects.filter(patient=patient).count()
    da_count   = DevelopmentalAssessment.objects.filter(patient=patient).count()
    video_count = Video.objects.filter(patient=patient).count()

    # Attachment — check actual model name from patients app
    attachment_count = 0
    try:
        from patients.models import Attachment
        attachment_count = Attachment.objects.filter(patient=patient).count()
    except (ImportError, AttributeError):
        pass

    # Open referrals — only if referral app exists (Story 4.1 prerequisite)
    open_referral_count = 0
    try:
        from referral.models import ReferralSent
        from ndas.custom_codes.choice import ReferralStatus
        open_referral_count = ReferralSent.objects.filter(
            patient=patient, status__in=[ReferralStatus.PENDING, ReferralStatus.REPLIED]
        ).count()
    except (ImportError, AttributeError):
        pass

    return {
        'gma_count': gma_count,
        'hine_count': hine_count,
        'cdic_count': cdic_count,
        'gpa_count': gpa_count,
        'da_count': da_count,
        'video_count': video_count,
        'attachment_count': attachment_count,
        'open_referral_count': open_referral_count,
        'total_assessments': gma_count + hine_count + cdic_count + gpa_count + da_count,
    }


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='manage-patients',
    error_message='Patient move failed. Please try again.'
)
def superadmin_patient_move(request, patient_id):
    """
    Multi-step patient move between institutions (FR55).

    Step 1 (GET):         Show impact preview + destination selector
    Step 2 (POST confirm): Show name-confirmation form
    Step 3 (POST execute): Execute atomic move

    SUPERADMIN only.
    """
    from patients.models import Patient as PatientModel
    from institution.models import PatientMoveLog

    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    # Intentional: SUPERADMIN crosses institution boundaries — no for_institution() scope.
    # This is the only view permitted to fetch patients outside their institution context.
    patient = get_object_or_404(PatientModel, id=patient_id)
    source_institution = patient.institution
    all_institutions = Institution.objects.filter(is_active=True).exclude(
        pk=source_institution.pk if source_institution else None
    ).order_by('name')

    step = request.POST.get('step', 'preview') if request.method == 'POST' else 'preview'

    # ── Step: preview (GET) ──────────────────────────────────────────────
    if request.method == 'GET' or step == 'preview':
        impact = _get_move_impact(patient)
        return render(request, 'institution/superadmin_patient_move.html', {
            'patient': patient,
            'source_institution': source_institution,
            'all_institutions': all_institutions,
            'impact': impact,
            'step': 'preview',
        })

    # ── Step: confirm (POST, step=confirm) ───────────────────────────────
    if step == 'confirm':
        destination_id = request.POST.get('destination_institution_id', '')
        destination = get_object_or_404(Institution, pk=destination_id)
        impact = _get_move_impact(patient)
        return render(request, 'institution/superadmin_patient_move.html', {
            'patient': patient,
            'source_institution': source_institution,
            'destination_institution': destination,
            'impact': impact,
            'step': 'confirm',
        })

    # ── Step: execute (POST, step=execute) ───────────────────────────────
    if step == 'execute':
        destination_id = request.POST.get('destination_institution_id', '')
        institution_name_confirm = request.POST.get('institution_name_confirm', '').strip()
        destination = get_object_or_404(Institution, pk=destination_id)

        if institution_name_confirm != destination.name:
            messages.error(
                request,
                f"Institution name does not match. Expected: '{destination.name}'. "
                "Please type the exact destination institution name."
            )
            impact = _get_move_impact(patient)
            return render(request, 'institution/superadmin_patient_move.html', {
                'patient': patient,
                'source_institution': source_institution,
                'destination_institution': destination,
                'impact': impact,
                'step': 'confirm',
                'name_mismatch_error': True,
            })

        # ── Atomic move ────────────────────────────────────────────────
        with transaction.atomic():
            patient.institution = destination
            patient.save(update_fields=['institution', 'updated_at'])

            # Create audit log record scoped to SOURCE institution
            PatientMoveLog.objects.create(
                patient=patient,
                from_institution=source_institution,
                to_institution=destination,
                moved_by=request.user,
                notes=f"Patient moved by SUPERADMIN '{request.user.username}'"
            )
            # Create audit log record scoped to DESTINATION institution
            PatientMoveLog.objects.create(
                patient=patient,
                from_institution=source_institution,
                to_institution=destination,
                moved_by=request.user,
                notes=f"Patient received from '{source_institution.name if source_institution else '?'}' by SUPERADMIN '{request.user.username}'"
            )

            # ── Notification stub (Story 5.1 prerequisite) ──────────────
            # TODO (Story 5.1): Create Notification records for both institution admins

        logger.info(
            "SUPERADMIN '%s' moved patient %d from '%s' to '%s'",
            request.user.username, patient_id,
            source_institution.name if source_institution else '?',
            destination.name,
        )
        messages.success(
            request,
            f"Patient '{patient.baby_name}' successfully moved to '{destination.name}'."
        )
        return redirect('view-patient', pk=patient.id)

    # Fallback
    return redirect('manage-patients')


# ─────────────────────────────────────────────────────────────────────────────
# Story 3.1 — Institution Admin Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url="user-login")
@require_GET
@handle_view_errors(
    redirect_url='home',
    error_message='Dashboard failed to load. Please try again.'
)
def institution_admin_dashboard(request):
    """
    Institution admin role dashboard — 4 quadrants (FR56).

    ADMIN only. Redirects:
      USER       → 'home'
      SUPERADMIN → 'institution:superadmin-dashboard'
    """
    from django.db.models import Q

    user_type = getattr(request.user, 'user_type', None)
    if user_type == UserType.SUPERADMIN:
        return redirect('institution:superadmin-dashboard')
    if user_type != UserType.ADMIN:
        return redirect('home')

    # /institution/ URLs are middleware-exempt, so fall back to user's institution
    institution = _get_admin_institution(request)
    if institution is None:
        return redirect('home')
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Quadrant 1: Patient stats ─────────────────────────────────────────
    from patients.models import Patient
    patient_qs = Patient.objects.for_institution(institution)
    total_patients = patient_qs.count()

    # ── Quadrant 2: Assessment activity (current month) ───────────────────
    from patients.models import (
        GMAssessment, HINEAssessment, CDICRecord,
        GeneralPaediatricAssessment, DevelopmentalAssessment,
    )

    def _count_this_month(model):
        return model.objects.filter(
            patient__institution=institution,
            created_at__gte=month_start,
        ).count()

    assessment_counts = {
        'gma':  _count_this_month(GMAssessment),
        'hine': _count_this_month(HINEAssessment),
        'cdic': _count_this_month(CDICRecord),
        'gpa':  _count_this_month(GeneralPaediatricAssessment),
        'da':   _count_this_month(DevelopmentalAssessment),
    }
    assessment_counts['total'] = sum(assessment_counts.values())

    # ── Quadrant 3: Referral activity (stub until Story 4.1) ──────────────
    referral_stats = {'sent': 0, 'received': 0, 'pending': 0, 'closed': 0}
    try:
        from referral.models import ReferralSent, ReferralReceived
        from ndas.custom_codes.choice import ReferralStatus
        referral_stats['sent']     = ReferralSent.objects.filter(from_institution=institution).count()
        referral_stats['received'] = ReferralReceived.objects.filter(to_institution=institution).count()
        referral_stats['pending']  = ReferralSent.objects.filter(from_institution=institution, status=ReferralStatus.PENDING).count()
        referral_stats['closed']   = ReferralSent.objects.filter(from_institution=institution, status=ReferralStatus.CLOSED).count()
    except ImportError:
        pass

    # ── Quadrant 4: Team activity ─────────────────────────────────────────
    total_users = User.objects.filter(institution=institution, is_active=True).count()
    recent_registrations = Patient.objects.for_institution(institution).order_by('-created_at')[:5]

    context = {
        'institution': institution,
        'total_patients': total_patients,
        'assessment_counts': assessment_counts,
        'referral_stats': referral_stats,
        'total_users': total_users,
        'recent_registrations': recent_registrations,
        'month_start': month_start,
    }
    return render(request, 'institution/admin_dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Story 3.2 — Clinician Account Management
# ─────────────────────────────────────────────────────────────────────────────

def _get_admin_institution(request):
    """
    Resolve institution for ADMIN views.
    /institution/ URLs are middleware-exempt, so fall back to user.institution.
    """
    return getattr(request, 'institution', None) or getattr(request.user, 'institution', None)


@login_required(login_url="user-login")
@require_GET
@handle_view_errors(redirect_url='home', error_message='Failed to load clinician list.')
def institution_clinician_list(request):
    """
    Institution admin: view all clinicians in own institution (FR57).
    ADMIN only.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.ADMIN:
        return redirect('home')

    institution = _get_admin_institution(request)
    if institution is None:
        return redirect('home')

    clinicians = (
        User.objects
        .filter(institution=institution, user_type=UserType.USER)  # H1: only USER-type; toggle_status enforces this too
        .order_by('last_name', 'first_name')
        .select_related('institution')
    )
    return render(request, 'institution/clinician_list.html', {
        'clinicians': clinicians,
        'institution': institution,
    })


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='institution:institution-clinician-list',
    error_message='Failed to create clinician.'
)
def institution_clinician_add(request):
    """
    Institution admin: create a new USER-type clinician (FR57).
    ADMIN only.
    """
    from institution.forms import InstitutionClinicianForm

    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.ADMIN:
        return redirect('home')

    institution = _get_admin_institution(request)
    if institution is None:
        return redirect('home')

    if request.method == 'POST':
        form = InstitutionClinicianForm(request.POST)
        if form.is_valid():
            new_user = form.save(institution=institution)
            logger.info(
                "ADMIN '%s' created clinician '%s' in institution '%s'",
                request.user.username, new_user.username, institution.name,
            )
            messages.success(
                request,
                f"Clinician account for '{new_user.get_full_name()}' created successfully."
            )
            return redirect('institution:institution-clinician-list')
    else:
        form = InstitutionClinicianForm()

    return render(request, 'institution/clinician_add.html', {
        'form': form,
        'institution': institution,
    })


@login_required(login_url="user-login")
@require_POST
@ratelimit(key='user_or_ip', rate='5/m')
@handle_view_errors(
    redirect_url='institution:institution-clinician-list',
    error_message='Failed to update clinician status.'
)
def institution_clinician_toggle_status(request, user_id):
    """
    Institution admin: activate or deactivate a clinician account (FR57).
    ADMIN only. Operates only on USER-type accounts within own institution.
    AC #2: deactivated clinician cannot authenticate; records remain intact.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.ADMIN:
        return redirect('home')

    institution = _get_admin_institution(request)
    if institution is None:
        return redirect('home')

    target_user = get_object_or_404(
        User,
        id=user_id,
        institution=institution,
        user_type=UserType.USER,  # AC #3: admins can only manage USER accounts
    )

    # Prevent self-deactivation
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('institution:institution-clinician-list')

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active', 'updated_at'])

    action = "activated" if target_user.is_active else "deactivated"
    logger.info(
        "ADMIN '%s' %s clinician '%s' in institution '%s'",
        request.user.username, action, target_user.username, institution.name,
    )
    messages.success(request, f"Account '{target_user.get_full_name()}' has been {action}.")
    return redirect('institution:institution-clinician-list')


# ─────────────────────────────────────────────────────────────────────────────
# Story 3.3 — Institution Branding Setup
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='home', error_message='Failed to save institution settings.')
def institution_settings(request):
    """
    Institution admin: upload logo + manage display settings (FR58).
    ADMIN only (or SUPERADMIN viewing institution context).
    """
    from institution.forms import InstitutionSettingsForm

    user_type = getattr(request.user, 'user_type', None)
    if user_type not in (UserType.ADMIN, UserType.SUPERADMIN):
        return redirect('home')

    institution = _get_admin_institution(request)
    if institution is None:
        return redirect('home')

    if request.method == 'POST':
        form = InstitutionSettingsForm(request.POST, request.FILES, instance=institution)
        if form.is_valid():
            form.save()
            logger.info(
                "User '%s' updated settings for institution '%s'",
                request.user.username, institution.name,
            )
            messages.success(request, "Institution settings saved successfully.")
            return redirect('institution:institution-settings')
    else:
        form = InstitutionSettingsForm(instance=institution)

    return render(request, 'institution/settings.html', {
        'form': form,
        'institution': institution,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Protected Media View (existing — Story 1.5)
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url="user-login")
def protected_media_view(request, path):
    """
    Serve media files with institution isolation enforcement (development only).

    Institution-partitioned paths (/{slug}/videos/ and /{slug}/attachments/) are restricted
    to the owning institution's users. SUPERADMIN can access any institution's files.

    In production: Nginx handles media serving. An X-Accel-Redirect approach with
    a Django auth endpoint is recommended for production file isolation.
    """
    user_type = getattr(request.user, 'user_type', UserType.USER)
    _inst = getattr(request, 'institution', None)

    # Check if path is institution-partitioned: format is "{slug}/videos/..." or "{slug}/attachments/..."
    parts = path.split('/')
    if len(parts) >= 2 and parts[1] in ('videos', 'attachments'):
        path_slug = parts[0]
        # SUPERADMIN can access all institution files
        if user_type != UserType.SUPERADMIN:
            # Block if institution context not set or slug mismatch
            if _inst is None or _inst.slug != path_slug:
                return HttpResponseForbidden(
                    "Access denied: this file belongs to another institution."
                )

    return django_serve_static(request, path, document_root=settings.MEDIA_ROOT)
