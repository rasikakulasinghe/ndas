from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_ratelimit.decorators import ratelimit
from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from io import BytesIO
import openpyxl
import json
import logging

from patients.models import Patient
from problemlist.models import Problem, ProblemAction
from problemlist.forms import ProblemForm, ProblemActionForm
from ndas.custom_codes.custom_methods import getCountZeroIfNone, institution_scope
from ndas.custom_codes.delete_helpers import (
    has_delete_permission,
    get_redirect_url,
)

logger = logging.getLogger(__name__)


@login_required(login_url="user-login")
def problem_manager(request, pid):
    """
    Display all problems for a specific patient.

    Active problems appear first, followed by resolved problems (greyed out).
    Implements core design principle: active problems prioritized.

    Args:
        request: HTTP request object
        pid: Patient primary key

    Returns:
        Rendered template with patient problems
    """
    patient = get_object_or_404(Patient.objects.for_institution(getattr(request, 'institution', None)), pk=pid)

    # Active problems first, then resolved (core design principle)
    problems = Problem.objects.filter(patient=patient).annotate(
        priority=Case(
            When(status__in=['active', 'chronic'], then=Value(1)),
            When(status__in=['resolved', 'inactive'], then=Value(2)),
            default=Value(3),
            output_field=IntegerField()
        )
    ).order_by('priority', '-date_identified')

    count = getCountZeroIfNone(problems)

    context = {
        "patient": patient,
        "problems": problems,
        "count": count,
    }
    return render(request, "problemlist/manager.html", context)


@ratelimit(key='user', rate='10/m', method='POST')
@ratelimit(key='ip', rate='20/m', method='POST')
@login_required(login_url="user-login")
def problem_add(request, pid):
    """
    Create a new problem entry for a patient.

    Args:
        request: HTTP request object
        pid: Patient primary key

    Returns:
        Rendered add form or redirect to manager on success
    """
    patient = get_object_or_404(Patient.objects.for_institution(getattr(request, 'institution', None)), pk=pid)

    if request.method == "POST":
        form = ProblemForm(request.POST)
        if form.is_valid():
            problem = form.save(commit=False)
            problem.patient = patient
            problem.save()
            messages.success(
                request,
                f"Problem '{problem.name}' added successfully for {patient.baby_name}."
            )
            return redirect("problem-manager", pid=patient.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProblemForm()

    context = {
        "patient": patient,
        "form": form,
    }
    return render(request, "problemlist/add.html", context)


@login_required(login_url="user-login")
def problem_view(request, pk):
    """
    View detailed information about a specific problem.

    Args:
        request: HTTP request object
        pk: Problem primary key

    Returns:
        Rendered problem detail template
    """
    problem = get_object_or_404(Problem, pk=pk, **institution_scope(request))
    patient = problem.patient
    actions = problem.actions.select_related('performed_by', 'added_by', 'last_edit_by').all()[:10]  # Latest 10 actions for inline timeline
    action_count = getCountZeroIfNone(problem.actions.all())

    context = {
        "problem": problem,
        "patient": patient,
        "actions": actions,
        "action_count": action_count,
    }
    return render(request, "problemlist/view.html", context)


@ratelimit(key='user', rate='10/m', method='POST')
@ratelimit(key='ip', rate='20/m', method='POST')
@login_required(login_url="user-login")
def problem_edit(request, pk):
    """
    Edit an existing problem entry.

    Args:
        request: HTTP request object
        pk: Problem primary key

    Returns:
        Rendered edit form or redirect to view on success
    """
    problem = get_object_or_404(Problem, pk=pk, **institution_scope(request))
    patient = problem.patient

    if request.method == "POST":
        form = ProblemForm(request.POST, instance=problem)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Problem '{problem.name}' updated successfully."
            )
            return redirect("problem-view", pk=problem.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProblemForm(instance=problem)

    context = {
        "problem": problem,
        "patient": patient,
        "form": form,
    }
    return render(request, "problemlist/edit.html", context)


@ratelimit(key='user', rate='5/m', method=['DELETE', 'POST'])
@ratelimit(key='ip', rate='10/m', method=['DELETE', 'POST'])
@login_required(login_url="user-login")
def problem_delete(request, pk):
    """
    Unified problem deletion endpoint with password verification and audit logging
    Supports both DELETE (AJAX modal) and POST (legacy form) methods

    Accepts:
        - DELETE method with JSON payload {password: str}
        - POST method with form data (backward compatibility)
    Returns:
        - DELETE: JSON {success: bool, message: str, redirect_url: str}
        - POST: Redirect to problem manager
        - GET: Render confirmation page (legacy)
    """
    from ndas.custom_codes.delete_helpers import (
        validate_can_delete,
        get_entity_display_name,
        get_entity_warning_items,
        get_entity_detail_items,
    )

    problem = get_object_or_404(Problem, pk=pk, **institution_scope(request))
    patient_id = problem.patient.pk

    # Check permission using delete helper
    if not has_delete_permission(request.user, problem):
        if request.method == "DELETE":
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=Problem, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this problem."
            }, status=403)
        else:
            messages.error(
                request,
                "You do not have permission to delete this problem."
            )
            return redirect("problem-manager", pid=patient_id)

    # Handle DELETE request (AJAX modal)
    if request.method == "DELETE":
        try:
            # 1. Parse JSON payload
            try:
                data = json.loads(request.body)
                password = data.get('password', '')
            except json.JSONDecodeError:
                return JsonResponse({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Invalid request format."
                }, status=400)

            # 2. Verify password presence
            if not password:
                return JsonResponse({
                    "success": False,
                    "error": "Password required",
                    "message": "Password is required to confirm deletion."
                }, status=400)

            # 3. Verify password correctness
            if not request.user.check_password(password):
                logger.warning(
                    f"Invalid password for deletion: user={request.user.username}, "
                    f"entity=Problem, id={pk}"
                )
                return JsonResponse({
                    "success": False,
                    "error": "Invalid password",
                    "message": "Incorrect password. Please try again."
                }, status=401)

            # 4. Check business rules
            validation_result = validate_can_delete(problem)
            if not validation_result['can_delete']:
                return JsonResponse({
                    "success": False,
                    "error": "Cannot delete",
                    "message": validation_result['reason']
                }, status=400)

            # 5. Store info for logging and response
            problem_name = get_entity_display_name(problem)
            problem_info = {
                "id": problem.id,
                "name": problem.name,
                "patient_id": patient_id,
                "deleted_by": request.user.username,
                "deleted_at": timezone.now().isoformat(),
            }

            # 6. Perform deletion
            problem.delete()

            # 7. Audit log
            logger.info(
                f"Deletion successful: user={request.user.username}, "
                f"entity=Problem, name={problem_name}, id={pk}, "
                f"details={problem_info}"
            )

            # 8. Return success
            return JsonResponse({
                "success": True,
                "message": f"Problem '{problem_name}' and all associated actions have been deleted successfully.",
                "redirect_url": get_redirect_url('Problem', patient_id=patient_id)
            })

        except Exception as e:
            logger.error(
                f"Deletion error: user={request.user.username}, "
                f"entity=Problem, id={pk}, error={str(e)}"
            )
            return JsonResponse({
                "success": False,
                "error": "Server error",
                "message": f"An error occurred during deletion: {str(e)}"
            }, status=500)

    # Handle POST request (legacy form submission - backward compatibility)
    if request.method == "POST":
        from django.contrib.auth import authenticate

        password = request.POST.get('password')

        # Verify password
        user = authenticate(username=request.user.username, password=password)
        if user is None:
            messages.error(request, "Incorrect password. Deletion cancelled.")
            return redirect("problem-manager", pid=patient_id)

        # Check if entity can be deleted (business rules)
        validation_result = validate_can_delete(problem)
        if not validation_result['can_delete']:
            messages.error(request, validation_result['reason'])
            return redirect("problem-manager", pid=patient_id)

        # Perform deletion
        problem_name = problem.name
        problem.delete()
        messages.success(
            request,
            f"Problem '{problem_name}' and all associated actions have been deleted successfully."
        )
        return redirect("problem-manager", pid=patient_id)

    # GET request - render confirmation page (legacy)
    context = {
        'problem': problem,
        'patient': problem.patient,
        'entity_name': get_entity_display_name(problem),
        'warnings': get_entity_warning_items(problem),
        'details': get_entity_detail_items(problem),
    }
    return render(request, 'problemlist/delete_confirm.html', context)


@login_required(login_url="user-login")
def problem_status_change(request, pk):
    """
    HTMX endpoint for inline status changes.

    Handles quick status updates without full page reload.
    Auto-populates date_resolved when status changes to 'resolved'.

    Args:
        request: HTTP request object (POST)
        pk: Problem primary key

    Returns:
        Rendered problem row HTML for HTMX swap
    """
    problem = get_object_or_404(Problem, pk=pk, **institution_scope(request))
    new_status = request.POST.get('status')

    if new_status in ['active', 'resolved', 'chronic', 'inactive']:
        old_status = problem.status
        problem.status = new_status

        # Auto-populate date_resolved when status becomes 'resolved'
        if new_status == 'resolved' and not problem.date_resolved:
            problem.date_resolved = timezone.now().date()

        # Clear date_resolved if status is not 'resolved'
        if new_status != 'resolved':
            problem.date_resolved = None

        problem.save()

        # Log action
        ProblemAction.objects.create(
            problem=problem,
            action=f"Status changed from {old_status} to {new_status}",
            performed_by=request.user
        )

        messages.success(
            request,
            f"Problem status updated to {new_status}."
        )

    # Return updated row HTML (HTMX will swap it)
    return render(request, "problemlist/_problem_row.html", {"problem": problem})


@login_required(login_url="user-login")
def problem_timeline(request, pk):
    """
    Expanded timeline view showing all actions for a problem.

    Displays full chronological history of all interventions and status changes.

    Args:
        request: HTTP request object
        pk: Problem primary key

    Returns:
        Rendered timeline template
    """
    problem = get_object_or_404(Problem, pk=pk, **institution_scope(request))
    patient = problem.patient
    actions = problem.actions.select_related('performed_by', 'added_by', 'last_edit_by').all()  # Already ordered by -date

    context = {
        "problem": problem,
        "patient": patient,
        "actions": actions,
        "action_count": getCountZeroIfNone(actions),
    }
    return render(request, "problemlist/timeline.html", context)


@login_required(login_url="user-login")
def problem_action_add(request, pk):
    """
    Add a new action log entry to a problem.

    Creates timestamped audit trail entry for clinical interventions.

    Args:
        request: HTTP request object
        pk: Problem primary key

    Returns:
        Redirect to problem view or timeline
    """
    problem = get_object_or_404(Problem, pk=pk, **institution_scope(request))

    if request.method == "POST":
        form = ProblemActionForm(request.POST)
        if form.is_valid():
            action = form.save(commit=False)
            action.problem = problem
            action.performed_by = request.user
            action.save()
            messages.success(
                request,
                "Action logged successfully."
            )
            return redirect("problem-view", pk=problem.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProblemActionForm()

    context = {
        "problem": problem,
        "patient": problem.patient,
        "form": form,
    }
    return render(request, "problemlist/action_add.html", context)


@login_required(login_url="user-login")
def problem_analysis(request):
    """
    Problem analysis page with advanced filtering.

    Supports filtering by:
    - Patient (Select2 autocomplete)
    - Status (multiple selection)
    - Severity (multiple selection)
    - Date range (from/to dates)

    Args:
        request: HTTP request object

    Returns:
        Rendered analysis template with filtered results
    """
    # Get filter parameters
    patient_id = request.GET.get('patient')
    status_filter = request.GET.getlist('status')
    severity_filter = request.GET.getlist('severity')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # Start with all problems (institution-scoped)
    _inst = getattr(request, 'institution', None)
    _patients_qs = Patient.objects.for_institution(_inst)
    problems = Problem.objects.select_related('patient', 'added_by').filter(patient__in=_patients_qs)

    # Apply filters
    if patient_id:
        problems = problems.filter(patient_id=patient_id)

    if status_filter:
        problems = problems.filter(status__in=status_filter)

    if severity_filter:
        problems = problems.filter(severity__in=severity_filter)

    if date_from:
        problems = problems.filter(date_identified__gte=date_from)

    if date_to:
        problems = problems.filter(date_identified__lte=date_to)

    # Order by date
    problems = problems.order_by('-date_identified')

    # Get all patients for Select2 dropdown
    patients = Patient.objects.for_institution(getattr(request, 'institution', None)).values('pk', 'baby_name', 'bht', 'mother_name')

    count = getCountZeroIfNone(problems)

    # Calculate summary statistics
    stats = {
        'active': problems.filter(status='active').count(),
        'chronic': problems.filter(status='chronic').count(),
        'resolved': problems.filter(status='resolved').count(),
        'inactive': problems.filter(status='inactive').count(),
    }

    context = {
        "problems": problems,
        "patients": patients,
        "count": count,
        "stats": stats,
        "filters": {
            "patient_id": patient_id,
            "status_filter": status_filter,
            "severity_filter": severity_filter,
            "date_from": date_from,
            "date_to": date_to,
        }
    }
    return render(request, "problemlist/analysis.html", context)


@login_required(login_url="user-login")
def problem_analysis_export(request):
    """
    Export filtered problems to Excel.

    Uses same filter logic as analysis page to export matching records.

    Args:
        request: HTTP request object

    Returns:
        Excel file download response
    """
    # Get filter parameters (same as analysis view)
    patient_id = request.GET.get('patient')
    status_filter = request.GET.getlist('status')
    severity_filter = request.GET.getlist('severity')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # Start with all problems (institution-scoped)
    _inst = getattr(request, 'institution', None)
    _patients_qs = Patient.objects.for_institution(_inst)
    problems = Problem.objects.select_related('patient', 'added_by').filter(patient__in=_patients_qs)

    # Apply filters
    if patient_id:
        problems = problems.filter(patient_id=patient_id)

    if status_filter:
        problems = problems.filter(status__in=status_filter)

    if severity_filter:
        problems = problems.filter(severity__in=severity_filter)

    if date_from:
        problems = problems.filter(date_identified__gte=date_from)

    if date_to:
        problems = problems.filter(date_identified__lte=date_to)

    # Order by date
    problems = problems.order_by('-date_identified')

    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Problem Analysis"

    # Headers
    headers = [
        'Patient BHT',
        'Patient Name',
        'Mother Name',
        'Problem',
        'Status',
        'Severity',
        'Date Identified',
        'Date Onset',
        'Date Resolved',
        'Action Taken',
        'Outcome',
        'Added By',
        'Created At'
    ]
    ws.append(headers)

    # Data rows
    for problem in problems:
        ws.append([
            problem.patient.bht if problem.patient.bht else 'N/A',
            problem.patient.baby_name,
            problem.patient.mother_name if problem.patient.mother_name else 'N/A',
            problem.name,
            problem.get_status_display(),
            problem.get_severity_display() if problem.severity else 'N/A',
            problem.date_identified.strftime('%Y-%m-%d') if problem.date_identified else 'N/A',
            problem.date_of_onset.strftime('%Y-%m-%d') if problem.date_of_onset else 'N/A',
            problem.date_resolved.strftime('%Y-%m-%d') if problem.date_resolved else 'N/A',
            problem.action_taken if problem.action_taken else 'N/A',
            problem.outcome if problem.outcome else 'N/A',
            problem.added_by.username if problem.added_by else 'N/A',
            problem.created_at.strftime('%Y-%m-%d %H:%M') if problem.created_at else 'N/A',
        ])

    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Create response
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"problem_analysis_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'

    return response
