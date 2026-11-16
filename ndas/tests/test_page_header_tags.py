"""
ndas/tests/test_page_header_tags.py

Regression tests for ndas/templatetags/page_header_tags.py — part of
spec-page-header-card-refinement.

PageHeaderNode.render() builds its HTML via manual string concatenation
rather than going through Django's autoescape machinery, so these tests
pin the one behavior that would silently regress into an XSS hole if
someone "simplified" the Node back to plain concatenation without
re-adding conditional_escape: an unsafe title must come out
HTML-escaped. They also pin the tag's actual (lenient) kwarg handling —
`accent`/`title` fall back to defaults when omitted and an unrecognized
kwarg is silently ignored rather than raising, via Django's
`token_kwargs` — and that nodelist content (badge/breadcrumb markup)
still renders normally through the surrounding template context.
"""
from django.template import Context, Template
from django.test import SimpleTestCase


class PageHeaderTagTest(SimpleTestCase):
    def render(self, template_string, context=None):
        return Template(template_string).render(Context(context or {}))

    def test_title_is_html_escaped(self):
        html = self.render(
            '{% load page_header_tags %}'
            '{% page_header accent="primary" title=title %}{% endpage_header %}',
            {"title": "<script>alert(1)</script>"},
        )
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_renders_expected_shell_with_no_icon(self):
        html = self.render(
            '{% load page_header_tags %}'
            '{% page_header accent="warning" title="Backup" %}'
            '<span class="badge">Inst</span>'
            '{% endpage_header %}'
        )
        self.assertIn('class="card page-header-card border-top border-warning shadow-sm mb-0"', html)
        self.assertIn('class="page-header-title m-0">Backup</h1>', html)
        self.assertIn('class="page-header-right"><span class="badge">Inst</span></div>', html)
        self.assertNotIn('fa-', html)
        self.assertNotIn('<i class="fas', html)

    def test_nodelist_content_renders_with_context(self):
        html = self.render(
            '{% load page_header_tags %}'
            '{% page_header accent="info" title="Referral Inbox" %}'
            '<span>{{ thread_count }} thread{{ thread_count|pluralize }}</span>'
            '{% endpage_header %}',
            {"thread_count": 3},
        )
        self.assertIn("<span>3 threads</span>", html)

    def test_empty_nodelist_renders_empty_right_slot(self):
        html = self.render(
            '{% load page_header_tags %}'
            '{% page_header accent="secondary" title="Staff Dashboard" %}{% endpage_header %}'
        )
        self.assertIn('<div class="page-header-right"></div>', html)

    def test_missing_title_kwarg_defaults_to_empty_title(self):
        html = self.render(
            '{% load page_header_tags %}'
            '{% page_header accent="primary" %}{% endpage_header %}'
        )
        self.assertIn('class="page-header-title m-0"></h1>', html)

    def test_missing_accent_kwarg_defaults_to_primary(self):
        html = self.render(
            '{% load page_header_tags %}'
            '{% page_header title="Dashboard" %}{% endpage_header %}'
        )
        self.assertIn('border-top border-primary', html)

    def test_unknown_kwarg_is_silently_ignored(self):
        html = self.render(
            '{% load page_header_tags %}'
            '{% page_header accent="primary" title="Dashboard" icon="fa-home" %}'
            '{% endpage_header %}'
        )
        self.assertIn('class="page-header-title m-0">Dashboard</h1>', html)
        self.assertNotIn('fa-home', html)
