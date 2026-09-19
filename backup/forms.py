"""
backup/forms.py — Story 1.2.

`BackupScopeForm` is only ever bound/validated for a `UserType.SUPERADMIN`
submission — `backup/views.py` coerces every non-superadmin POST straight to
`scope_type=single` + the requester's own institution before this form is
ever consulted, so a crafted `scope_type`/`institutions` field in a
non-superadmin's POST body is never trusted (see spec I/O matrix:
"Non-superadmin sends elevated scope").
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from institution.models import Institution
from ndas.custom_codes.choice import BackupJobScopeType


class BackupScopeForm(forms.Form):
    """
    SUPERADMIN-only backup scope selector.

    `mode` chooses one of the three scoping shapes; `institutions` is only
    consulted (and required) when `mode == multi` — enforced in `clean()` so
    an empty multi-selection is refused before any `BackupJob` row is
    created (spec I/O matrix: "Superadmin: multi-select, empty").
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

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('mode') or BackupJobScopeType.SINGLE
        cleaned['mode'] = mode
        if mode == BackupJobScopeType.MULTI and not cleaned.get('institutions'):
            raise forms.ValidationError(
                _("Select at least one institution for a multi-institution backup.")
            )
        return cleaned
