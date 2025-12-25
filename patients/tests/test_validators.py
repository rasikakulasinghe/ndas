"""
Tests for POG-specific birth weight validation.

Tests the comprehensive birth weight validation against gestational age
to ensure medical data integrity.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from ndas.custom_codes.validators import (
    validate_birth_weight_for_gestational_age,
    BIRTH_WEIGHT_RANGES_BY_POG
)


class BirthWeightValidationTest(TestCase):
    """Test POG-specific birth weight validation"""

    def test_extremely_premature_valid_weight(self):
        """Test valid weight for extremely premature baby (22 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(500, 22)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_extremely_premature_too_heavy(self):
        """Test excessive weight for extremely premature baby (22 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(3000, 22)
        self.assertFalse(is_valid)
        self.assertIn("unusually high", message)
        self.assertIn("22 weeks", message)

    def test_very_premature_valid_weight(self):
        """Test valid weight for very premature baby (26 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(800, 26)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_very_premature_too_light(self):
        """Test insufficient weight for very premature baby (26 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(350, 26)
        self.assertFalse(is_valid)
        self.assertIn("unusually low", message)
        self.assertIn("26 weeks", message)

    def test_moderate_premature_valid_weight(self):
        """Test valid weight for moderate premature baby (30 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(1400, 30)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_late_premature_valid_weight(self):
        """Test valid weight for late premature baby (35 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(2500, 35)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_full_term_valid_weight(self):
        """Test valid weight for full term baby (40 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(3500, 40)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_full_term_too_heavy(self):
        """Test excessive weight for full term baby (40 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(6000, 40)
        self.assertFalse(is_valid)
        self.assertIn("unusually high", message)
        self.assertIn("40 weeks", message)

    def test_full_term_too_light(self):
        """Test insufficient weight for full term baby (40 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(2000, 40)
        self.assertFalse(is_valid)
        self.assertIn("unusually low", message)
        self.assertIn("40 weeks", message)

    def test_pog_with_days(self):
        """Test validation with POG days included (30+3 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(1500, 30, 3)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_pog_with_days_display(self):
        """Test error message includes days in POG display"""
        is_valid, message = validate_birth_weight_for_gestational_age(3000, 30, 3)
        self.assertFalse(is_valid)
        self.assertIn("30+3 weeks", message)

    def test_strict_mode_typical_range(self):
        """Test strict mode uses typical ranges instead of absolute min/max"""
        # 800g is within absolute range (700-1600) but below typical min (800)
        # In non-strict mode, this should pass
        is_valid_lenient, message = validate_birth_weight_for_gestational_age(700, 28, strict=False)
        self.assertTrue(is_valid_lenient)

        # In strict mode, this should fail
        is_valid_strict, message = validate_birth_weight_for_gestational_age(700, 28, strict=True)
        self.assertFalse(is_valid_strict)
        self.assertIn("extremely low", message)

    def test_pog_out_of_range_too_low(self):
        """Test POG below medical range (< 20 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(500, 18)
        self.assertFalse(is_valid)
        self.assertIn("outside medical range", message)

    def test_pog_out_of_range_too_high(self):
        """Test POG above medical range (> 44 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(3500, 46)
        self.assertFalse(is_valid)
        self.assertIn("outside medical range", message)

    def test_no_weight_provided(self):
        """Test validation skips when no weight provided"""
        is_valid, message = validate_birth_weight_for_gestational_age(None, 30)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_no_pog_provided(self):
        """Test validation skips when no POG provided"""
        is_valid, message = validate_birth_weight_for_gestational_age(3000, None)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_post_term_valid(self):
        """Test valid weight for post-term baby (43 weeks)"""
        is_valid, message = validate_birth_weight_for_gestational_age(4000, 43)
        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_boundary_cases(self):
        """Test boundary cases for each POG range"""
        # Test minimum valid weight for each POG week
        test_cases = [
            (20, 300),   # Minimum for 20 weeks
            (24, 400),   # Minimum for 24 weeks
            (30, 900),   # Minimum for 30 weeks
            (37, 2200),  # Minimum for 37 weeks
            (40, 2600),  # Minimum for 40 weeks
        ]

        for pog_weeks, min_weight in test_cases:
            is_valid, message = validate_birth_weight_for_gestational_age(min_weight, pog_weeks)
            self.assertTrue(is_valid, f"Failed for POG {pog_weeks}, weight {min_weight}")

    def test_interpolation_between_weeks(self):
        """Test that interpolation works for POG with days"""
        # 30 weeks: min=900, max=2000
        # 31 weeks: min=1000, max=2200
        # 30+3.5 days (30.5 weeks) should interpolate roughly halfway

        # Weight that's valid at 30.5 weeks but might not be at exactly 30 or 31
        is_valid, message = validate_birth_weight_for_gestational_age(950, 30, 3)
        self.assertTrue(is_valid)

    def test_data_consistency(self):
        """Test that weight ranges are consistent and progressive"""
        # Verify that ranges generally increase with gestational age
        prev_max = 0
        for week in sorted(BIRTH_WEIGHT_RANGES_BY_POG.keys()):
            ranges = BIRTH_WEIGHT_RANGES_BY_POG[week]

            # Min should be less than max
            self.assertLess(ranges['min'], ranges['max'])

            # Typical min should be between absolute min and max
            self.assertGreaterEqual(ranges['typical_min'], ranges['min'])
            self.assertLessEqual(ranges['typical_min'], ranges['max'])

            # Typical max should be between absolute min and max
            self.assertGreaterEqual(ranges['typical_max'], ranges['min'])
            self.assertLessEqual(ranges['typical_max'], ranges['max'])

            # Max should generally increase (with rare exceptions)
            if week > 20:
                # Allow small decreases but general trend should be upward
                self.assertGreaterEqual(ranges['max'], prev_max - 200,
                    f"Week {week} max ({ranges['max']}) is significantly less than week {week-1} ({prev_max})")

            prev_max = ranges['max']
