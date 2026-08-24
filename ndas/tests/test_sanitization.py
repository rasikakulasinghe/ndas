"""
ndas/tests/test_sanitization.py

Regression tests for sanitize_html() — part of
spec-fix-security-sanitization-gaps.

ALLOWED_ATTRIBUTES['a'] permits 'target' and 'rel', but bleach.clean() only
keeps or drops attributes an author supplies -- it can't synthesize new ones.
So a `<a target="_blank">` link with no rel (or an incomplete one) used to
pass through unchanged, letting the opened page use window.opener to
redirect the original tab to a phishing page (reverse tabnabbing). The fix
adds a post-process step, _enforce_noopener_noreferrer(), applied after
bleach.clean()/bleach.linkify(), that forces rel="noopener noreferrer" onto
every target="_blank" anchor, merging with (not replacing) any existing rel
value.
"""
from django.test import TestCase

from ndas.custom_codes.sanitization import sanitize_html


class SanitizeHtmlNoopenerNoreferrerTest(TestCase):
    """target="_blank" anchors must always carry rel="noopener noreferrer"."""

    def test_target_blank_with_no_rel_gets_rel_added(self):
        result = sanitize_html('<a href="https://example.com" target="_blank">x</a>')
        self.assertIn('target="_blank"', result)
        self.assertIn("noopener", result)
        self.assertIn("noreferrer", result)

    def test_target_blank_with_existing_rel_is_merged_not_replaced(self):
        result = sanitize_html(
            '<a href="https://example.com" target="_blank" rel="nofollow">x</a>'
        )
        self.assertIn("nofollow", result)
        self.assertIn("noopener", result)
        self.assertIn("noreferrer", result)

    def test_target_blank_with_both_tokens_already_present_is_idempotent(self):
        original = (
            '<a href="https://example.com" target="_blank" '
            'rel="noopener noreferrer">x</a>'
        )
        result = sanitize_html(original)
        # Tokens must appear exactly once each -- no duplication.
        self.assertEqual(result.count("noopener"), 1)
        self.assertEqual(result.count("noreferrer"), 1)

    def test_link_without_target_blank_is_untouched(self):
        original = '<a href="https://example.com">x</a>'
        result = sanitize_html(original)
        self.assertNotIn("noopener", result)
        self.assertNotIn("noreferrer", result)
        self.assertNotIn('target="_blank"', result)

    def test_running_sanitize_html_twice_is_idempotent(self):
        original = '<a href="https://example.com" target="_blank" rel="nofollow">x</a>'
        once = sanitize_html(original)
        twice = sanitize_html(once)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count("noopener"), 1)
        self.assertEqual(twice.count("noreferrer"), 1)
        self.assertIn("nofollow", twice)

    def test_running_sanitize_html_twice_is_idempotent_no_rel(self):
        original = '<a href="https://example.com" target="_blank">x</a>'
        once = sanitize_html(original)
        twice = sanitize_html(once)
        self.assertEqual(once, twice)

    def test_target_blank_with_surrounding_whitespace_still_gets_rel(self):
        """
        Regression: per the HTML5 spec, browsers strip ASCII whitespace when
        comparing the target attribute's browsing-context name, so
        target=" _blank" opens a new tab exactly like target="_blank" — an
        exact-match regex would silently miss this legitimate variant.
        """
        result = sanitize_html('<a href="https://example.com" target=" _blank">x</a>')
        self.assertIn("noopener", result)
        self.assertIn("noreferrer", result)

    def test_mixed_case_target_and_rel_attribute_names_are_handled(self):
        """Confirms re.IGNORECASE actually works end-to-end, not just on the value."""
        result = sanitize_html(
            '<a href="https://example.com" TARGET="_BLANK" REL="nofollow">x</a>'
        )
        self.assertIn("noopener", result)
        self.assertIn("noreferrer", result)
        self.assertIn("nofollow", result)

    def test_strip_mode_still_enforces_rel(self):
        """The rel-enforcement post-process must apply regardless of strip=True/False."""
        result = sanitize_html(
            '<a href="https://example.com" target="_blank">x</a>', strip=True
        )
        self.assertIn("noopener", result)
        self.assertIn("noreferrer", result)

    def test_title_containing_literal_escaped_gt_does_not_break_target_detection(self):
        """
        A title value containing '>' (serialized by bleach as the multi-char
        entity &gt;, never a raw '>') must not truncate the tag-boundary
        regex and cause the real target="_blank" to be missed.
        """
        result = sanitize_html(
            '<a href="https://example.com" title="a &gt; b" target="_blank">x</a>'
        )
        self.assertIn("noopener", result)
        self.assertIn("noreferrer", result)
        self.assertIn("a &gt; b", result)

    def test_disallowed_attribute_named_like_rel_or_target_is_stripped_by_bleach(self):
        """
        data-rel/data-target aren't in ALLOWED_ATTRIBUTES, so bleach.clean()
        strips them before _enforce_noopener_noreferrer ever runs — they
        can't be mistaken for the real target/rel attributes.
        """
        result = sanitize_html(
            '<a href="https://example.com" data-rel="evil" target="_blank">x</a>'
        )
        self.assertNotIn("data-rel", result)
        self.assertIn("noopener", result)
        self.assertIn("noreferrer", result)

    def test_linkified_bare_url_without_target_blank_is_unaffected(self):
        """
        bleach.linkify() auto-links bare URLs but doesn't add target="_blank"
        by default, so a co-occurring real target="_blank" anchor must still
        be fixed while the auto-linked one is left alone.
        """
        result = sanitize_html(
            'Visit http://example.com or '
            '<a href="https://other.com" target="_blank">this</a>'
        )
        self.assertIn('<a href="http://example.com"', result)
        self.assertIn("noopener", result)
        self.assertIn("noreferrer", result)


class SanitizeHtmlBasicBehaviorTest(TestCase):
    """Existing sanitize_html() behavior for non-adversarial input is unchanged."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(sanitize_html(""), "")

    def test_script_tag_is_stripped_by_default_escape_mode(self):
        result = sanitize_html('<p>Hello</p><script>alert("XSS")</script>')
        self.assertIn("<p>Hello</p>", result)
        self.assertNotIn("<script>", result)

    def test_safe_formatting_tags_preserved(self):
        result = sanitize_html("<p>Hello <strong>world</strong></p>")
        self.assertEqual(result, "<p>Hello <strong>world</strong></p>")


class SanitizePlainTextDoubleEncodingTest(TestCase):
    """
    sanitize_plain_text() is bleach-based (a real HTML parser), not the
    regex strip-then-unescape approach sanitize_text_input() used to have —
    it never decodes entities that weren't real tags to begin with, so it
    doesn't share that function's double-encoding vulnerability class.
    Documents/locks in that this function was never affected.
    """

    def test_entity_encoded_script_tag_stays_inert(self):
        from ndas.custom_codes.sanitization import sanitize_plain_text
        result = sanitize_plain_text("&lt;script&gt;alert(1)&lt;/script&gt;")
        # Must remain literal, non-executable entity text -- never decoded
        # into a raw, live <script> tag.
        self.assertNotIn("<script>", result)
