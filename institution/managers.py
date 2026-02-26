"""
InstitutionScopedManager: provides institution-filtered querysets for all
models with an institution FK. The single point of truth for data isolation.
"""
from django.db import models


class InstitutionScopedManager(models.Manager):
    """
    Custom manager that scopes querysets to a single institution.

    Usage:
        # In any institution-scoped view:
        patients = Patient.objects.for_institution(request.institution)

        # In SUPERADMIN aggregate views only:
        all_patients = Patient.objects.all_institutions()

    NEVER use .all() or inline .filter(institution=...) in institution-scoped views.
    """

    def for_institution(self, institution):
        """
        Return queryset filtered to the given institution.
        If institution is None (Phase 1 / transitional state), returns all records.
        """
        if institution is None:
            # Phase 1 safe: no institution context active → unfiltered (backward compatible)
            return self.get_queryset()
        return self.get_queryset().filter(institution=institution)

    def all_institutions(self):
        """
        Return unfiltered queryset — for SUPERADMIN aggregate use ONLY.
        Never call this from a regular institution-scoped view.
        """
        return self.get_queryset()
