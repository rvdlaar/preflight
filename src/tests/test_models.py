"""Tests for preflight.db.models — Condition lifecycle, model creation."""

from preflight.db.models import Condition, Condition


class TestConditionLifecycle:
    def test_valid_statuses(self):
        assert "OPEN" in Condition.VALID_STATUSES
        assert "IN_PROGRESS" in Condition.VALID_STATUSES
        assert "MET" in Condition.VALID_STATUSES
        assert "WAIVED" in Condition.VALID_STATUSES
        assert "OVERDUE" in Condition.VALID_STATUSES

    def test_open_can_progress(self):
        assert "IN_PROGRESS" in Condition.VALID_TRANSITIONS["OPEN"]
        assert "WAIVED" in Condition.VALID_TRANSITIONS["OPEN"]
        assert "OVERDUE" in Condition.VALID_TRANSITIONS["OPEN"]
        assert "MET" not in Condition.VALID_TRANSITIONS["OPEN"]

    def test_in_progress_can_complete(self):
        assert "MET" in Condition.VALID_TRANSITIONS["IN_PROGRESS"]
        assert "WAIVED" in Condition.VALID_TRANSITIONS["IN_PROGRESS"]

    def test_met_is_terminal(self):
        assert len(Condition.VALID_TRANSITIONS["MET"]) == 0

    def test_waived_is_terminal(self):
        assert len(Condition.VALID_TRANSITIONS["WAIVED"]) == 0

    def test_overdue_can_progress(self):
        assert "IN_PROGRESS" in Condition.VALID_TRANSITIONS["OVERDUE"]
        assert "WAIVED" in Condition.VALID_TRANSITIONS["OVERDUE"]
