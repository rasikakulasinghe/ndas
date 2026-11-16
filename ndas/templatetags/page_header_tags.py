"""
Page Header Template Tags
File: ndas/templatetags/page_header_tags.py
Part of "Page Header: Icon Removal, Compact Title & Right-Aligned Secondary Slot" change.

Provides a single reusable block tag pair, `{% page_header %}` / `{% endpage_header %}`,
that renders the shared page-header-card shell (card wrapper, title, right-hand slot)
used at the top of `{% block content_header %}` across the app's templates.

The tag only abstracts the *outer* shell -- the badge/breadcrumb markup inside the
`.page-header-right` slot stays exactly as each template authors it today (including
any `{% if %}`, `{% url %}`, `|pluralize`, etc.) and is passed through verbatim as the
tag's nodelist rather than modeled as string kwargs.

Usage:
    {% load page_header_tags %}
    {% page_header accent="primary" title="Dashboard" %}
      <span class="badge badge-pill badge-light border">...</span>
      <ol class="breadcrumb">...</ol>
    {% endpage_header %}
"""

from django import template
from django.template.base import token_kwargs
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


class PageHeaderNode(template.Node):
    def __init__(self, nodelist, kwargs):
        self.nodelist = nodelist
        self.kwargs = kwargs

    def render(self, context):
        accent_expr = self.kwargs.get('accent')
        title_expr = self.kwargs.get('title')

        accent = accent_expr.resolve(context) if accent_expr is not None else 'primary'
        title = title_expr.resolve(context) if title_expr is not None else ''

        # Node.render() bypasses Django's autoescape for manually-built HTML strings,
        # so title (and accent, for defense in depth) must be explicitly escaped here
        # before being concatenated into the final markup.
        accent_escaped = conditional_escape(accent)
        title_escaped = conditional_escape(title)

        # The nodelist (badge/breadcrumb markup authored in each template) renders
        # through the normal template engine, so its own variables are already
        # escaped per the surrounding context's autoescape setting.
        right_content = self.nodelist.render(context)

        html = (
            '<div class="card page-header-card border-top border-' + accent_escaped + ' shadow-sm mb-0">'
            '<div class="card-body d-flex justify-content-between align-items-center flex-wrap py-2">'
            '<h1 class="page-header-title m-0">' + title_escaped + '</h1>'
            '<div class="page-header-right">' + right_content + '</div>'
            '</div>'
            '</div>'
        )
        return mark_safe(html)


@register.tag('page_header')
def do_page_header(parser, token):
    bits = token.split_contents()
    remaining_bits = bits[1:]
    kwargs = token_kwargs(remaining_bits, parser, support_legacy=False)
    nodelist = parser.parse(('endpage_header',))
    parser.delete_first_token()
    return PageHeaderNode(nodelist, kwargs)
