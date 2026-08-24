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
