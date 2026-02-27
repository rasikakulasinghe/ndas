"""
referral/views.py

Referral system views.
"""
import logging
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_GET
from django_ratelimit.decorators import ratelimit
from ndas.custom_codes.error_handlers import handle_view_errors

logger = logging.getLogger(__name__)


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='manage-patients', error_message='Failed to create referral.')
def referral_initiate(request, patient_id):
    """
    Initiate a cross-institution referral (FR60, FR61, NFR22).

    GET:  Render referral form for the given patient.
    POST: Validate, build snapshot, create ReferralSent + ReferralReceived atomically.
    """
    from patients.models import Patient
    from referral.models import ReferralSent, ReferralReceived
    from referral.forms import ReferralInitiateForm
    from referral.utils import build_patient_snapshot
    from django.db import transaction as db_transaction

    institution = getattr(request, 'institution', None) or getattr(request.user, 'institution', None)

    patient = get_object_or_404(
        Patient.objects.for_institution(institution),
        id=patient_id,
    )

    if request.method == 'POST':
        form = ReferralInitiateForm(
            request.POST,
            sending_institution=institution,
        )
        if form.is_valid():
            to_institution  = form.cleaned_data['to_institution']
            to_clinician    = form.cleaned_data['to_clinician']
            initial_message = form.cleaned_data['initial_message']

            # Build snapshot BEFORE atomic block (captures current state)
            snapshot = build_patient_snapshot(patient)
            shared_uuid = uuid.uuid4()

            # NFR22: Atomic — either both records created or neither
            with db_transaction.atomic():
                ReferralSent.objects.create(
                    from_institution=institution,
                    to_institution=to_institution,
                    institution=institution,
                    patient=patient,
                    from_clinician=request.user,
                    to_clinician=to_clinician,
                    referral_uuid=shared_uuid,
                    initial_message=initial_message,
                    snapshot_data=snapshot,
                    added_by=request.user,
                    last_edit_by=request.user,
                )
                ReferralReceived.objects.create(
                    to_institution=to_institution,
                    from_institution=institution,
                    institution=to_institution,
                    patient_name=patient.baby_name or '',
                    from_clinician_name=request.user.get_full_name() or request.user.username,
                    to_clinician=to_clinician,
                    referral_uuid=shared_uuid,
                    initial_message=initial_message,
                    snapshot_data=snapshot,
                    added_by=request.user,
                    last_edit_by=request.user,
                )

            logger.info(
                "Clinician '%s' created referral %s → inst: %s, clinician: %s",
                request.user.username,
                shared_uuid,
                to_institution.name,
                to_clinician.username,
            )
            from django.contrib import messages as django_messages
            django_messages.success(
                request,
                f"Referral sent to {to_clinician.get_full_name()} at {to_institution.name}."
            )
            return redirect('referral:referral-inbox')
    else:
        form = ReferralInitiateForm(sending_institution=institution)

    return render(request, 'referral/initiate.html', {
        'form': form,
        'patient': patient,
    })


@login_required(login_url="user-login")
@require_GET
def get_institution_clinicians(request, institution_id):
    """
    HTMX endpoint: Return <option> tags for active clinicians at a given institution.
    Used by referral initiate form to populate the to_clinician dropdown dynamically.
    """
    from django.http import HttpResponse
    from users.models import CustomUser
    from ndas.custom_codes.choice import UserType

    institution = getattr(request, 'institution', None)

    # Exclude own institution for safety (AC #5)
    if institution and institution_id == institution.pk:
        return HttpResponse('<option value="">Self-referral not permitted</option>')

    clinicians = CustomUser.objects.filter(
        institution_id=institution_id,
        is_active=True,
        user_type=UserType.USER,
    ).order_by('last_name', 'first_name')

    options = ['<option value="">— Select clinician —</option>']
    for c in clinicians:
        options.append(f'<option value="{c.pk}">{c.get_full_name() or c.username}</option>')

    return HttpResponse('\n'.join(options))


@login_required(login_url="user-login")
@require_GET
@handle_view_errors(redirect_url='home', error_message='Failed to load referral inbox.')
def referral_inbox(request):
    """
    Unified referral inbox — shows sent and received referral threads (FR63).

    Split panel: thread list left, thread detail right (HTMX-loaded).
    """
    from referral.models import ReferralSent, ReferralReceived

    institution = getattr(request, 'institution', None) or getattr(request.user, 'institution', None)

    sent_referrals = (
        ReferralSent.objects
        .for_institution(institution)
        .filter(from_clinician=request.user)
        .select_related('to_institution', 'to_clinician', 'patient')
        .order_by('-created_at')
    ) if institution else ReferralSent.objects.none()

    received_referrals = (
        ReferralReceived.objects
        .for_institution(institution)
        .filter(to_clinician=request.user)
        .select_related('from_institution', 'to_clinician')
        .order_by('-created_at')
    ) if institution else ReferralReceived.objects.none()

    threads = []
    for ref in sent_referrals:
        threads.append({
            'direction':         'sent',
            'referral_uuid':     ref.referral_uuid,
            'status':            ref.status,
            'patient_name':      ref.patient.baby_name if ref.patient else ref.snapshot_data.get('demographics', {}).get('baby_name', 'Unknown'),
            'other_institution': ref.to_institution,
            'other_clinician':   ref.to_clinician,
            'created_at':        ref.created_at,
            'is_unread':         False,
            'obj':               ref,
        })
    for ref in received_referrals:
        threads.append({
            'direction':         'received',
            'referral_uuid':     ref.referral_uuid,
            'status':            ref.status,
            'patient_name':      ref.patient_name,
            'other_institution': ref.from_institution,
            'other_clinician':   ref.from_clinician_name,
            'created_at':        ref.created_at,
            'is_unread':         not ref.is_read,
            'obj':               ref,
        })

    threads.sort(key=lambda t: t['created_at'], reverse=True)

    return render(request, 'referral/inbox.html', {
        'threads': threads,
        'thread_count': len(threads),
    })


def _thread_panel_response(request, referral_uuid):
    """
    Internal helper: builds the thread panel response without decorators.
    Called by referral_thread_panel (GET) and referral_reply (POST).
    """
    from referral.models import ReferralSent, ReferralReceived, ReferralMessage
    from referral.forms import ReferralReplyForm

    institution = getattr(request, 'institution', None) or getattr(request.user, 'institution', None)

    sent = ReferralSent.objects.filter(
        referral_uuid=referral_uuid,
        institution=institution,
    ).first()

    received = ReferralReceived.objects.filter(
        referral_uuid=referral_uuid,
        institution=institution,
    ).first()

    if not sent and not received:
        from django.http import HttpResponse
        return HttpResponse(
            '<p class="text-center text-danger p-3">Thread not found.</p>',
            status=404,
        )

    if received and not received.is_read and received.to_clinician == request.user:
        received.is_read = True
        received.save(update_fields=['is_read', 'updated_at'])

    messages_qs = ReferralMessage.objects.filter(
        referral_uuid=referral_uuid
    ).select_related('sender', 'sender_institution').order_by('created_at')

    current_record = sent or received
    status = current_record.status
    snapshot_data = current_record.snapshot_data
    is_closed = status == 'CLOSED'
    is_sender = sent is not None

    # AC #1: Patient header from frozen snapshot
    demographics = snapshot_data.get('demographics', {})
    patient_header = {
        'baby_name': demographics.get('baby_name', 'Unknown'),
        'bht':       demographics.get('bht', '—'),
        'nnc_no':    demographics.get('nnc_no', '—'),
    }

    reply_form = None if is_closed else ReferralReplyForm()

    return render(request, 'referral/thread_panel.html', {
        'referral_uuid':  referral_uuid,
        'sent':           sent,
        'received':       received,
        'messages':       messages_qs,
        'status':         status,
        'snapshot_data':  snapshot_data,
        'patient_header': patient_header,
        'is_sender':      is_sender,
        'is_closed':      is_closed,
        'reply_form':     reply_form,
    })


@login_required(login_url="user-login")
@require_GET
@handle_view_errors(redirect_url='referral:referral-inbox', error_message='Failed to load referral thread.')
def referral_thread_panel(request, referral_uuid):
    """
    HTMX partial: full referral thread with frozen snapshot + reply form (FR62).

    AC #3: Called via hx-get from thread list item. Returns thread_panel.html partial.
    Marks ReferralReceived as read on first open.
    """
    return _thread_panel_response(request, referral_uuid)


@login_required(login_url="user-login")
@require_http_methods(["POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='referral:referral-inbox', error_message='Failed to submit reply.')
def referral_reply(request, referral_uuid):
    """
    Submit a clinical opinion reply to a referral thread (FR62, FR64).

    Creates ReferralMessage, updates status to REPLIED on both ReferralSent + ReferralReceived.
    Rejects if thread is CLOSED (AC #5).
    """
    from referral.models import ReferralSent, ReferralReceived, ReferralMessage
    from referral.forms import ReferralReplyForm
    from ndas.custom_codes.choice import ReferralStatus

    institution = getattr(request, 'institution', None) or getattr(request.user, 'institution', None)

    sent = ReferralSent.objects.filter(
        referral_uuid=referral_uuid,
        institution=institution,
    ).first()

    received = ReferralReceived.objects.filter(
        referral_uuid=referral_uuid,
        institution=institution,
    ).first()

    if not sent and not received:
        from django.http import HttpResponse
        return HttpResponse('<p class="text-danger p-3">Referral not found.</p>', status=404)

    current_record = sent or received

    # AC #5: Reject reply to CLOSED thread
    if current_record.status == ReferralStatus.CLOSED:
        from django.http import HttpResponse
        return HttpResponse(
            '<div class="alert alert-danger m-2">This referral is closed. No further replies are permitted.</div>',
            status=403,
        )

    form = ReferralReplyForm(request.POST)
    if form.is_valid():
        body = form.cleaned_data['body']

        ReferralMessage.objects.create(
            referral_uuid=referral_uuid,
            sender=request.user,
            sender_institution=institution,
            body=body,
            message_type=ReferralMessage.OPINION,
            added_by=request.user,
            last_edit_by=request.user,
        )

        # Update status to REPLIED at BOTH institutions (intentional cross-institution write — NFR22)
        # H1: include updated_at explicitly — queryset .update() bypasses auto_now=True
        from django.utils import timezone as tz
        now = tz.now()
        ReferralSent.objects.filter(referral_uuid=referral_uuid).update(
            status=ReferralStatus.REPLIED, updated_at=now)
        ReferralReceived.objects.filter(referral_uuid=referral_uuid).update(
            status=ReferralStatus.REPLIED, updated_at=now)

        logger.info(
            "Clinician '%s' replied to referral %s",
            request.user.username, referral_uuid,
        )

    return _thread_panel_response(request, referral_uuid)


@login_required(login_url="user-login")
@require_http_methods(["POST"])
@ratelimit(key='user_or_ip', rate='5/m')
@handle_view_errors(redirect_url='referral:referral-inbox', error_message='Failed to close referral.')
def referral_close(request, referral_uuid):
    """
    Close a referral thread (FR64).

    Sets CLOSED status on both ReferralSent and ReferralReceived via referral_uuid.
    Only the sending clinician (or their institution ADMIN) can close.
    GRACE subscription exemption: active referrals can be closed regardless of subscription status
    (exempted by InstitutionContextMiddleware for /referral/ paths — FR48).
    """
    from referral.models import ReferralSent, ReferralReceived
    from ndas.custom_codes.choice import ReferralStatus, UserType
    from django.db import transaction as db_transaction

    institution = getattr(request, 'institution', None) or getattr(request.user, 'institution', None)

    # Only the sender institution can close
    sent = ReferralSent.objects.filter(
        referral_uuid=referral_uuid,
        institution=institution,
    ).first()

    if not sent:
        from django.http import HttpResponse
        return HttpResponse(
            '<div class="alert alert-danger m-2">Only the sending institution can close a referral.</div>',
            status=403,
        )

    # Permission: only from_clinician or institution ADMIN can close
    user_type = getattr(request.user, 'user_type', None)
    is_from_clinician = (sent.from_clinician == request.user)
    is_inst_admin = (user_type == UserType.ADMIN and request.user.institution == institution)

    if not is_from_clinician and not is_inst_admin:
        from django.http import HttpResponse
        return HttpResponse(
            '<div class="alert alert-danger m-2">Only the referring clinician or institution admin can close this referral.</div>',
            status=403,
        )

    # Already closed — idempotent response
    if sent.status == ReferralStatus.CLOSED:
        return _thread_panel_response(request, referral_uuid)

    # Atomically close both records (intentional cross-institution write)
    # H1: include updated_at explicitly — queryset .update() bypasses auto_now=True
    from django.utils import timezone as tz
    now = tz.now()
    with db_transaction.atomic():
        ReferralSent.objects.filter(referral_uuid=referral_uuid).update(
            status=ReferralStatus.CLOSED, updated_at=now)
        ReferralReceived.objects.filter(referral_uuid=referral_uuid).update(
            status=ReferralStatus.CLOSED, updated_at=now)

    logger.info(
        "Clinician '%s' (inst: %s) closed referral %s",
        request.user.username,
        getattr(institution, 'name', 'unknown'),
        referral_uuid,
    )

    # Dispatch custom signal so signals.py can create closure notifications (FR69).
    # NOTE: bulk update() skips post_save, so we use a custom signal here.
    from referral.signals import referral_status_changed
    referral_status_changed.send(
        sender=ReferralSent,
        referral_uuid=referral_uuid,
        new_status=ReferralStatus.CLOSED,
        changed_by=request.user,
    )

    return _thread_panel_response(request, referral_uuid)


@login_required(login_url="user-login")
@require_GET
@handle_view_errors(redirect_url='home', error_message='Failed to load referral tab.')
def patient_referrals_tab(request, patient_id):
    """
    Referrals tab partial for patient detail view (FR65).

    Shows all outgoing (ReferralSent) and incoming (ReferralReceived) referrals
    for this patient scoped to the current institution (FR66 — no cross-institution leak).
    """
    from patients.models import Patient
    from referral.models import ReferralSent, ReferralReceived

    institution = getattr(request, 'institution', None) or getattr(request.user, 'institution', None)

    patient = get_object_or_404(
        Patient.objects.for_institution(institution),
        id=patient_id,
    )

    # Outgoing referrals — patient belongs to this institution
    sent_referrals = (
        ReferralSent.objects
        .filter(patient=patient, from_institution=institution)
        .select_related('from_institution', 'to_institution', 'from_clinician', 'to_clinician')
        .order_by('-created_at')
    )

    # Incoming referrals received by this institution for this patient
    # (patient_name match — ReferralReceived has no direct patient FK)
    received_referrals = (
        ReferralReceived.objects
        .filter(to_institution=institution, patient_name=patient.baby_name or '')
        .select_related('from_institution', 'to_institution', 'to_clinician')
        .order_by('-created_at')
    )

    timeline = []
    for ref in sent_referrals:
        timeline.append({
            'direction':        'sent',
            'referral_uuid':    ref.referral_uuid,
            'from_institution': ref.from_institution,
            'to_institution':   ref.to_institution,
            'from_clinician':   ref.from_clinician,
            'to_clinician':     ref.to_clinician,
            'status':           ref.status,
            'outcome':          ref.outcome,
            'created_at':       ref.created_at,
        })
    for ref in received_referrals:
        timeline.append({
            'direction':        'received',
            'referral_uuid':    ref.referral_uuid,
            'from_institution': ref.from_institution,
            'to_institution':   ref.to_institution,
            'from_clinician':   ref.from_clinician_name,
            'to_clinician':     ref.to_clinician,
            'status':           ref.status,
            'outcome':          ref.outcome,
            'created_at':       ref.created_at,
        })

    timeline.sort(key=lambda t: t['created_at'], reverse=True)

    return render(request, 'referral/patient_referrals_tab.html', {
        'patient':        patient,
        'timeline':       timeline,
        'referral_count': len(timeline),
    })


# ── Story 5.2: Notification Bell ───────────────────────────────────────────


@login_required(login_url="user-login")
@require_GET
def notification_count(request):
    """
    HTMX endpoint: returns unread notification count badge fragment (FR38, NFR23).

    Polled every 60 seconds by the navbar bell (hx-trigger="every 60s").
    Returns an empty fragment (no badge) when count is zero.
    """
    from referral.models import Notification
    count = Notification.objects.filter(
        recipient=request.user,
        institution=request.institution,
        is_read=False,
    ).count()
    return render(request, 'referral/notification_count_badge.html', {'count': count})


# ── Story 5.3: Notification Panel & Mark as Read ───────────────────────────


@login_required(login_url="user-login")
@require_GET
def notification_panel(request):
    """
    HTMX endpoint: returns rendered notification panel for dropdown (FR38, FR70).

    Limited to 20 most recent notifications for the current user+institution.
    Loaded into #notification-panel-container on bell click.
    """
    from referral.models import Notification
    notifications = Notification.objects.filter(
        recipient=request.user,
        institution=request.institution,
    ).order_by('-created_at')[:20]
    return render(request, 'referral/notification_panel.html', {
        'notifications': notifications,
    })


@login_required(login_url="user-login")
@require_GET
def notification_mark_read(request, pk):
    """
    Mark a single notification as read and redirect to its target link (FR70).

    Scoped to recipient=request.user and institution=request.institution to
    prevent cross-user reads.
    """
    from referral.models import Notification
    notif = get_object_or_404(
        Notification,
        id=pk,
        recipient=request.user,
        institution=request.institution,
    )
    if not notif.is_read:
        notif.is_read = True
        notif.last_edit_by = request.user
        notif.save(update_fields=['is_read', 'last_edit_by', 'updated_at'])

    # Redirect to the notification's target link or inbox fallback
    target = notif.link if notif.link else reverse('referral:referral-inbox')
    return redirect(target)


@login_required(login_url="user-login")
@require_http_methods(["POST"])
def notification_mark_all_read(request):
    """
    Mark all notifications for current user+institution as read (FR70).

    Returns re-rendered panel for HTMX swap into #notification-panel-container.
    """
    from referral.models import Notification
    Notification.objects.filter(
        recipient=request.user,
        institution=request.institution,
        is_read=False,
    ).update(is_read=True)

    # Re-render panel showing all-read state
    notifications = Notification.objects.filter(
        recipient=request.user,
        institution=request.institution,
    ).order_by('-created_at')[:20]
    return render(request, 'referral/notification_panel.html', {
        'notifications': notifications,
    })
