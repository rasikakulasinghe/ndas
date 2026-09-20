"""
backup/forms.py — Story 1.2, extended by Story 1.4.

`mode`/`institutions` are only ever *trusted* for a `UserType.SUPERADMIN`
submission — `backup/views.py` coerces every non-superadmin POST straight to
`scope_type=single` + the requester's own institution regardless of what
these two fields contain, so a crafted `scope_type`/`institutions` field in
a non-superadmin's POST body is never trusted (see spec I/O matrix:
"Non-superadmin sends elevated scope"). `start_date`/`end_date` (Story 1.4)
are the opposite: validated and applied for *every* submitter, superadmin or
not — the date-range filter is never privilege-gated. Because of this, the
form as a whole is now built and validated for every submission (not just
superadmin ones); only the mode/institutions *values* are ignored for a
non-superadmin afterward.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from institution.models import Institution
from ndas.custom_codes.choice import BackupJobScopeType


class BackupScopeForm(forms.Form):
    """
    Backup scope + date-range selector (Story 1.2 + Story 1.4).

    `mode`/`institutions` are SUPERADMIN-only in effect: `mode` chooses one
    of the three scoping shapes, and `institutions` is only consulted (and
    required) when `mode == multi` — enforced in `clean()` so an empty
    multi-selection is refused before any `BackupJob` row is created (spec
    I/O matrix: "Superadmin: multi-select, empty"). `backup/views.py`
    ignores/coerces both fields' values for a non-superadmin submitter
    regardless of what's posted, and must never let a `mode`/`institutions`
    validation error refuse a non-superadmin's request either (only a
    genuinely invalid `start_date`/`end_date` may do that for them).

    `start_date`/`end_date` (Story 1.4) are the opposite: validated and
    applied for every submitter, superadmin or not — never privilege-gated.
    """
    mode = forms.ChoiceField(
        choices=BackupJobScopeType.choices,
        initial=BackupJobScopeType.SINGLE,
        required=False,
        widget=forms.RadioSelect,
    )
    institutions = forms.ModelMultipleChoiceField(
        # Matches the existing single-select institution-queryset convention
        # (users/forms.py:426-428): only active institutions are selectable.
        queryset=Institution.objects.filter(is_active=True).order_by('name'),
        required=False,
        # "form-check-input" (not an empty class) -- backup/templates/backup/
        # create.html renders each option inside a Bootstrap 4 `form-check`
        # wrapper, matching the AdminLTE conventions used by the scope-mode
        # radios on the same form.
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text=_(
            "Story 1.4: optional inclusive lower bound on Patient.created_at's "
            "date -- only whether the PATIENT was created on/after this date, "
            "not each related record's own date (a video's recording date, an "
            "assessment date, etc. can fall outside this range and still be "
            "included, since a qualifying patient's related records always "
            "export in full). Available to any user who can trigger a "
            "backup, not just superadmins. Leave blank for an open-ended/no "
            "lower bound."
        ),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text=_(
            "Story 1.4: optional inclusive upper bound on Patient.created_at's "
            "date -- same Patient-created_at-only scope as start_date above. "
            "Leave blank for an open-ended/no upper bound."
        ),
    )

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('mode') or BackupJobScopeType.SINGLE
        cleaned['mode'] = mode
        if mode == BackupJobScopeType.MULTI and not cleaned.get('institutions'):
            raise forms.ValidationError(
                _("Select at least one institution for a multi-institution backup.")
            )
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        if start_date and end_date and end_date < start_date:
            # Attached to the `end_date` field specifically (not a bare
            # non-field error) so it can be styled/positioned near the
            # actual offending input, and so callers can distinguish "a
            # genuinely invalid date range" (which must refuse every
            # submitter, superadmin or not) from a `mode`/`institutions`
            # non-field error (which must never refuse a non-superadmin --
            # see backup/views.py's `_resolve_scope_from_request`).
            self.add_error('end_date', _("End date cannot be before start date."))
        return cleaned
