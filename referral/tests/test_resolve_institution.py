"""
referral/tests/test_resolve_institution.py

Direct unit tests for referral.views.resolve_institution() -- the helper
extracted (deferred-work batch 6) to replace 6 duplicated
`getattr(request, 'institution', None) or getattr(request.user, 'institution', None)`
call sites. These tests assert the helper returns byte-for-byte the same
value as that original inline expression across its branches: request
institution present, absent, explicitly None, and the user-institution
fallback itself absent or None.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from referral.views import resolve_institution


class ResolveInstitutionTest(SimpleTestCase):
    def test_returns_request_institution_when_set(self):
        request_institution = SimpleNamespace(name='Request Institution')
        user_institution = SimpleNamespace(name='User Institution')
        request = SimpleNamespace(
            institution=request_institution,
            user=SimpleNamespace(institution=user_institution),
        )
        self.assertIs(resolve_institution(request), request_institution)

    def test_falls_back_to_user_institution_when_request_institution_missing(self):
        # request has no `institution` attribute at all
        request = SimpleNamespace(user=SimpleNamespace(institution=SimpleNamespace(name='User Institution')))
        self.assertIs(resolve_institution(request), request.user.institution)

    def test_falls_back_to_user_institution_when_request_institution_none(self):
        # request.institution exists but is explicitly None
        user_institution = SimpleNamespace(name='User Institution')
        request = SimpleNamespace(institution=None, user=SimpleNamespace(institution=user_institution))
        self.assertIs(resolve_institution(request), user_institution)

    def test_returns_none_when_neither_set(self):
        request = SimpleNamespace(institution=None, user=SimpleNamespace(institution=None))
        self.assertIsNone(resolve_institution(request))

    def test_returns_none_when_neither_attribute_exists(self):
        request = SimpleNamespace(user=SimpleNamespace())
        self.assertIsNone(resolve_institution(request))
