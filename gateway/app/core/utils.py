"""Utility functions for the gateway application."""

from datetime import date, timedelta
from typing import Optional

from gateway.app.core.config import settings


def get_current_week_number(
    reference_date: Optional[date] = None, semester_start: Optional[date] = None
) -> int:
    """Calculate the current week number based on semester start date.

    Args:
        reference_date: The date to calculate week number for. Defaults to today.
        semester_start: The start date of the semester. Defaults to settings.semester_start_date.

    Returns:
        Week number (1-based). Returns 1 if:
        - semester_start is not configured
        - reference_date is before semester_start
        - reference_date is after semester_end

    Examples:
        >>> get_current_week_number(date(2026, 2, 17), date(2026, 2, 17))
        1
        >>> get_current_week_number(date(2026, 2, 24), date(2026, 2, 17))
        2
    """
    start = semester_start or settings.semester_start_date

    # If no semester start date is configured, default to week 1
    if start is None:
        return 1

    ref = reference_date or date.today()

    # Calculate semester end date
    semester_end = start + timedelta(weeks=settings.semester_weeks)

    # If outside semester bounds, return 1 (or could raise/return special value)
    if ref < start or ref > semester_end:
        return 1

    # Calculate week number (1-based)
    days_diff = (ref - start).days
    week_number = (days_diff // 7) + 1

    return week_number


def is_within_semester(
    check_date: Optional[date] = None, semester_start: Optional[date] = None
) -> bool:
    """Check if a date is within the current semester.

    Args:
        check_date: The date to check. Defaults to today.
        semester_start: The start date of the semester. Defaults to settings.semester_start_date.

    Returns:
        True if the date is within semester bounds, False otherwise.
    """
    start = semester_start or settings.semester_start_date

    if start is None:
        return True  # If no start date, assume always in semester

    check = check_date or date.today()
    semester_end = start + timedelta(weeks=settings.semester_weeks)

    return start <= check <= semester_end
