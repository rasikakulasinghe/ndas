"""
ndas/tests/test_validators_sanitization.py

Regression tests for sanitize_text_input() — part of
spec-fix-security-sanitization-gaps.

sanitize_text_input() used to strip <tag> patterns, event handlers, and
dangerous protocols *before* calling html.unescape() at the very end. An
entity-encoded payload like "&lt;script&gt;alert(1)&lt;/script&gt;" contains
no raw "<" characters when the strip regexes run, so it passed every filter
untouched and was only decoded back into live <script>...</script> markup by
the trailing unescape call (a double-encoded XSS bypass). The fix moves
html.unescape() to run immediately after the input is coerced to a string,
before any of the strip regexes, so entity-encoded payloads are decoded
first and then actually get caught by the tag/event-handler/protocol strips.
"""
from django.test import TestCase

from ndas.custom_codes.validators import sanitize_text_input


class SanitizeTextInputDoubleEncodingTest(TestCase):
    """Double-encoded payloads must be neutralized, not decoded into live markup."""

    def test_double_encoded_script_tag_is_neutralized(self):
        result = sanitize_text_input("&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotIn("<script", result.lower())
        self.assertNotIn("</script", result.lower())
        # The strip-script-tag regex removes the tag *and* its content, so the
        # payload should not survive at all.
        self.assertNotIn("alert(1)", result)

    def test_double_encoded_script_tag_with_trailing_text(self):
        result = sanitize_text_input(
            "&lt;script&gt;alert('xss')&lt;/script&gt;Hello"
        )
        self.assertNotIn("<script", result.lower())
        self.assertIn("Hello", result)

    def test_double_encoded_img_onerror_is_neutralized(self):
        result = sanitize_text_input(
            '&lt;img src="x" onerror="alert(1)"&gt;Note'
        )
        self.assertNotIn("<img", result.lower())
        self.assertNotIn("onerror", result.lower())
        self.assertIn("Note", result)

    def test_double_encoded_javascript_protocol_is_stripped(self):
        result = sanitize_text_input("&lt;a href=&quot;javascript:alert(1)&quot;&gt;x&lt;/a&gt;")
        self.assertNotIn("javascript:", result.lower())
        self.assertNotIn("<a", result.lower())

    def test_triple_encoded_script_tag_is_neutralized(self):
        """
        Regression: html.unescape() only decodes one layer per call, so a
        single unescape() pass leaves one layer of encoding undecoded (and
        therefore unstripped) for multiply-encoded payloads. The fix loops
        to a fixed point (bounded) instead of a single pass.
        """
        result = sanitize_text_input(
            "&amp;amp;lt;script&amp;amp;gt;alert(1)&amp;amp;lt;/script&amp;amp;gt;"
        )
        self.assertNotIn("<script", result.lower())
        self.assertNotIn("alert(1)", result)


class SanitizeTextInputMedicalNotationTest(TestCase):
    """Medical notation using < and > must survive sanitization unchanged."""

    def test_less_than_medical_notation_preserved(self):
        result = sanitize_text_input("BP < 120/80 mmHg")
        self.assertEqual(result, "BP < 120/80 mmHg")

    def test_greater_than_medical_notation_preserved(self):
        result = sanitize_text_input("Temperature > 38°C")
        self.assertEqual(result, "Temperature > 38°C")

    def test_entity_encoded_medical_notation_is_decoded_and_preserved(self):
        result = sanitize_text_input("Temp &lt;5")
        self.assertEqual(result, "Temp <5")

    def test_entity_encoded_greater_than_medical_notation_is_decoded_and_preserved(self):
        result = sanitize_text_input("Temp &gt;38")
        self.assertEqual(result, "Temp >38")


class SanitizeTextInputBasicXssTest(TestCase):
    """Existing (non-double-encoded) behavior must remain unchanged."""

    def test_raw_script_tag_is_stripped(self):
        result = sanitize_text_input("<script>alert('xss')</script>Test")
        self.assertNotIn("<script", result.lower())
        self.assertIn("Test", result)

    def test_event_handler_is_stripped(self):
        result = sanitize_text_input('<img src="x" onerror="alert(1)">Note')
        self.assertNotIn("onerror", result.lower())
        self.assertIn("Note", result)

    def test_empty_and_none_values_pass_through(self):
        self.assertEqual(sanitize_text_input(""), "")
        self.assertIsNone(sanitize_text_input(None))


class SanitizeTextInputObfuscatedProtocolTest(TestCase):
    """
    Regression: the dangerous-protocol strip used a literal-string regex
    (javascript|data|vbscript): that only matched the exact unbroken string.
    Browsers strip whitespace/control characters (tab, newline, CR) from a
    URL before parsing its scheme, so "java\\tscript:alert(1)" is still a
    live javascript: URI to a browser even though it never contains the
    literal substring "javascript:" — the old regex let it through untouched.
    """

    def test_tab_obfuscated_javascript_protocol_is_stripped(self):
        result = sanitize_text_input("java\tscript:alert(1)")
        self.assertNotIn("javascript:", result.replace("\t", "").lower())
        self.assertNotIn("script:", result.lower())

    def test_newline_obfuscated_javascript_protocol_is_stripped(self):
        result = sanitize_text_input("java\nscript:alert(1)")
        self.assertNotIn("script:", result.lower())

    def test_space_obfuscated_data_protocol_is_stripped(self):
        result = sanitize_text_input("da ta:text/html,<script>alert(1)</script>")
        self.assertNotIn("data:", result.lower())
        self.assertNotIn("ta:", result.lower())

    def test_obfuscated_vbscript_protocol_is_stripped(self):
        result = sanitize_text_input("vb\tscript:msgbox(1)")
        self.assertNotIn("script:", result.lower())

    def test_unobfuscated_protocols_still_stripped(self):
        """Non-regression: the plain (non-obfuscated) case must keep working."""
        result = sanitize_text_input("javascript:alert(1)")
        self.assertNotIn("javascript:", result.lower())

    def test_data_label_with_trailing_space_preserved(self):
        """
        "Data: BP 120/80" is ordinary English labeling, not a data: URI — a
        real dangerous URI never has whitespace right after its colon. Must
        survive intact (CLAUDE.md requires preserving medical notation).
        """
        result = sanitize_text_input("Investigation data: pending review")
        self.assertEqual(result, "Investigation data: pending review")

    def test_metadata_word_not_treated_as_data_protocol(self):
        """"metadata:" must not be treated as the "data" protocol mid-word."""
        result = sanitize_text_input("See metadata:version=2 for details")
        self.assertIn("metadata:version=2", result)
