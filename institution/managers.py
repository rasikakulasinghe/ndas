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

        # When institution=None must mean "nothing", not "everything"
        # (e.g. a cross-tenant lookup that must never fall back to
        # unfiltered data): use for_institution_or_none() instead of
        # repeating `for_institution(x) if x else Model.objects.none()`.
        patients = Patient.objects.for_institution_or_none(request.institution)

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

    def for_institution_or_none(self, institution):
        """
        Return a queryset filtered to the given institution, or an EMPTY
        queryset (never Python None) when institution is None.

        Use this instead of the ad hoc
        `for_institution(institution) if institution else X.objects.none()`
        pattern at call sites that must NOT fall back to for_institution()'s
        Phase 1 unfiltered-when-None behavior.
        """
        if institution is None:
            return self.get_queryset().none()
        return self.for_institution(institution)
