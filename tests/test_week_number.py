"""Tests for week number calculation utilities."""

from datetime import date

import pytest

from gateway.app.core.utils import get_current_week_number, is_within_semester


class TestGetCurrentWeekNumber:
    """Test suite for get_current_week_number function."""
    
    def test_week_1_on_start_date(self):
        """First day of semester should be week 1."""
        result = get_current_week_number(
            reference_date=date(2026, 2, 17),
            semester_start=date(2026, 2, 17)
        )
        assert result == 1
    
    def test_week_1_during_first_week(self):
        """Any day in first week should be week 1."""
        result = get_current_week_number(
            reference_date=date(2026, 2, 23),  # 6 days later
            semester_start=date(2026, 2, 17)
        )
        assert result == 1
    
    def test_week_2_on_second_week(self):
        """Exactly one week later should be week 2."""
        result = get_current_week_number(
            reference_date=date(2026, 2, 24),
            semester_start=date(2026, 2, 17)
        )
        assert result == 2
    
    def test_week_8_mid_semester(self):
        """Middle of semester should calculate correctly."""
        result = get_current_week_number(
            reference_date=date(2026, 4, 7),  # ~7 weeks later
            semester_start=date(2026, 2, 17)
        )
        assert result == 8
    
    def test_default_to_week_1_before_semester(self):
        """Dates before semester start should default to week 1."""
        result = get_current_week_number(
            reference_date=date(2026, 2, 10),
            semester_start=date(2026, 2, 17)
        )
        assert result == 1
    
    def test_default_to_week_1_after_semester(self):
        """Dates after semester end should default to week 1."""
        result = get_current_week_number(
            reference_date=date(2026, 7, 1),  # Well after 16-week semester
            semester_start=date(2026, 2, 17)
        )
        assert result == 1
    
    def test_default_to_week_1_when_no_start_date(self):
        """When semester_start is None, should default to week 1."""
        result = get_current_week_number(
            reference_date=date(2026, 2, 17),
            semester_start=None
        )
        assert result == 1


class TestIsWithinSemester:
    """Test suite for is_within_semester function."""
    
    def test_date_within_semester(self):
        """Date within semester bounds should return True."""
        result = is_within_semester(
            check_date=date(2026, 3, 1),
            semester_start=date(2026, 2, 17)
        )
        assert result is True
    
    def test_start_date_within_semester(self):
        """Semester start date should be within semester."""
        result = is_within_semester(
            check_date=date(2026, 2, 17),
            semester_start=date(2026, 2, 17)
        )
        assert result is True
    
    def test_end_date_within_semester(self):
        """Last day of 16-week semester should be within semester."""
        from gateway.app.core.config import settings
        semester_start = date(2026, 2, 17)
        semester_end = semester_start + __import__('datetime').timedelta(weeks=settings.semester_weeks)
        
        result = is_within_semester(
            check_date=semester_end,
            semester_start=semester_start
        )
        assert result is True
    
    def test_date_before_semester(self):
        """Date before semester start should return False."""
        result = is_within_semester(
            check_date=date(2026, 2, 10),
            semester_start=date(2026, 2, 17)
        )
        assert result is False
    
    def test_date_after_semester(self):
        """Date after semester end should return False."""
        result = is_within_semester(
            check_date=date(2026, 7, 1),
            semester_start=date(2026, 2, 17)
        )
        assert result is False
    
    def test_true_when_no_start_date(self):
        """When semester_start is None, should return True (permissive)."""
        result = is_within_semester(
            check_date=date(2026, 2, 17),
            semester_start=None
        )
        assert result is True
