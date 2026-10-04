"""Services métier des heures supplémentaires."""

from apps.overtime.services.calculation import (
    CalculationError,
    calculer_declaration,
    compute_duration_minutes,
)

__all__ = [
    "CalculationError",
    "calculer_declaration",
    "compute_duration_minutes",
]
