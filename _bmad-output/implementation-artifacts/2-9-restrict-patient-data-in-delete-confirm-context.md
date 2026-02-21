# Story 2.9: Restrict Patient Data in `patient_delete_confirm` Context

Status: done

## Story

As a security-conscious developer,
I want `patient_delete_confirm` to pass only minimal patient data when the user lacks delete permission,
so that a future template rendering bug cannot accidentally expose full patient records to unauthorised users.

## Acceptance Criteria

1. When user is not superuser, context passed to template contains only `patient_id`, `patient_name`, and `hide=True` — not the full `patient` object.
2. The `hide=True` flag remains in the non-superuser context for template rendering decisions.
3. Superuser path unchanged — full `patient` object still passed.
4. Template `patients/delete-confirm.html` continues to render correctly for both permission levels (if/when it exists).

## Tasks / Subtasks

- [x] Task 1: Fix non-superuser context in `patient_delete_confirm` (AC: #1, #2, #3) — `patients/views.py:601–607`
  - [x] Replaced `{"patient": patient, "hide": True}` with `{"patient_id": patient.id, "patient_name": patient.baby_name, "hide": True}`
- [x] Task 2: Verify view context and state (AC: #3, #4)
  - [x] Confirmed superuser branch at line 594–595 unchanged: `{"patient": patient}`
  - [x] Confirmed URL not registered in `patients/urls.py` — view is orphaned (defense-in-depth fix)
  - [x] `python manage.py test patients` — 3 story-related tests pass; pre-existing failures unchanged

## Dev Notes

### Current State — `patients/views.py:599–611`

```python
@handle_view_errors(redirect_url='manage-patients', error_message='Error loading delete confirmation')
@login_required(login_url="user-login")
def patient_delete_confirm(request, pk):
    patient = get_object_or_404(Patient, id=pk)
    user = request.user
    if user.is_superuser:
        return render(request, "patients/delete-confirm.html", {"patient": patient})
    else:
        messages.warning(
            request,
            "You dont have permission to delete this record. Please contact Administrator/ Developer",
        )
        return render(
            request, "patients/delete-confirm.html", {"patient": patient, "hide": True}  # ← FULL OBJECT LEAKED
        )
```

### Required State After Fix — Lines 609–611 Only

```python
        return render(
            request, "patients/delete-confirm.html", {
                "patient_id": patient.id,
                "patient_name": patient.baby_name,
                "hide": True,
            }
        )
```

**Only the `else` branch changes.** The `if user.is_superuser:` branch at line 603 is untouched.

### Important Context: This View Is Currently Orphaned

Two facts confirm this view is not actively reachable:

1. **No URL registered:** `grep "delete_confirm\|delete-confirm" patients/urls.py` returns nothing. The view cannot be accessed via any registered URL path.
2. **Template missing:** `templates/patients/delete-confirm.html` does not exist in the templates directory. The modern delete system uses the unified `delete_confirmation_modal.html` partial instead.

The fix is still worth making as **defense-in-depth**: if the URL or template is ever added back, the security behaviour will already be correct. Code that never executes can still reflect incorrect intent.

### Patient Model Fields for Minimal Context

The non-superuser context needs only two fields:
- `patient.id` → pass as `patient_id` (integer)
- `patient.baby_name` → pass as `patient_name` (string, per CLAUDE.md field name)

Both are non-sensitive identifiers sufficient for a "permission denied" confirmation screen.

### No Template Change Required

The template `patients/delete-confirm.html` does not currently exist, so no template update is needed. If/when the template is created, it should:
- Check `{% if hide %}` before rendering any sensitive patient details
- Use `{{ patient_id }}` and `{{ patient_name }}` for the non-superuser path
- Use `{{ patient }}` object for the superuser path

### Superuser Path Is Unchanged

Line 603 remains exactly as-is:
```python
if user.is_superuser:
    return render(request, "patients/delete-confirm.html", {"patient": patient})
```

Superusers have full delete rights — passing the full object is intentional and correct.

### No Migration Required

Single-line context dict change. No model, URL, import, or template changes.

### Project Structure Notes

- File changed: `patients/views.py:609–611` — context dict replacement in `else` branch only
- No imports, no URLs, no templates changed

### References

- [Source: _bmad-output/planning-artifacts/epic-2-security.md#Story-2.9]
- [Source: docs/code-audit-adversarial-review.md#SEC-09]
- [Source: patients/views.py:597–611 — patient_delete_confirm full view]
- [Source: patients/urls.py — confirmed no URL registered for this view]
- [Source: CLAUDE.md#Patient Model Fields — baby_name is the correct field name]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Replaced `{"patient": patient, "hide": True}` with `{"patient_id": patient.id, "patient_name": patient.baby_name, "hide": True}` in the `else` branch of `patient_delete_confirm` (`patients/views.py:601–607`). Non-superuser path now exposes only id and baby_name, not the full Patient object. AC #1 and #2 satisfied.
- Task 2 complete: Superuser branch at line 594–595 verified unchanged. View is orphaned (no URL registration, no template). Fix is defense-in-depth. 3 regression tests pass; pre-existing failures unchanged. AC #3 and #4 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 2.9 — replaced full `patient` object with `patient_id` and `patient_name` in the non-superuser branch of `patient_delete_confirm` in `patients/views.py`. Defense-in-depth fix for orphaned view; prevents accidental full record exposure if URL/template are added back.
