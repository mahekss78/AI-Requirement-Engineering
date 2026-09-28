"""
app/services/scoring.py
========================
Confidence & Health Scoring Engines for the AREA platform.

Formulas strictly implement PDS Volume 2 Chapter 13:

1. Confidence Engine (PDS Vol 2 §13.5):
   Confidence = (0.30 * Completeness) + (0.20 * Clarity) + (0.20 * Consistency)
              + (0.15 * Testability)  + (0.15 * Traceability)
   Bounded strictly to [0.0, 100.0]. Stores sub-metric breakdown dict.

2. Health Engine (PDS Vol 2 §13.5):
   Health = max(0.0, 100.0 - (5.0 * Q_open) - (10.0 * R_rejections) - P_delay)
   Where P_delay = 15.0 if peer_review_duration > 48 hours else 0.0.

   Status Label Mapping:
   - [90.0, 100.0] -> "Healthy"
   - [70.0, 89.9]  -> "Needs Review"
   - [50.0, 69.9]  -> "At Risk"
   - [0.0, 49.9]   -> "Blocked"
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """
    Evaluates composite requirement confidence metrics.
    """

    @staticmethod
    def calculate(
        completeness: float = 0.0,
        clarity: float = 0.0,
        consistency: float = 0.0,
        testability: float = 0.0,
        traceability: float = 0.0,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate normalized composite confidence score (0.0 to 100.0).

        Returns:
            Tuple of (composite_confidence_score: float, breakdown_dict: dict[str, float])
        """
        c_comp = min(max(float(completeness), 0.0), 100.0)
        c_clar = min(max(float(clarity), 0.0), 100.0)
        c_cons = min(max(float(consistency), 0.0), 100.0)
        c_test = min(max(float(testability), 0.0), 100.0)
        c_trac = min(max(float(traceability), 0.0), 100.0)

        # PDS Vol 2 §13.5 Weights
        weights = {
            "completeness": 0.30,
            "clarity": 0.20,
            "consistency": 0.20,
            "testability": 0.15,
            "traceability": 0.15,
        }

        total_score = (
            (weights["completeness"] * c_comp)
            + (weights["clarity"] * c_clar)
            + (weights["consistency"] * c_cons)
            + (weights["testability"] * c_test)
            + (weights["traceability"] * c_trac)
        )

        normalized_score = round(min(max(total_score, 0.0), 100.0), 2)
        breakdown = {
            "completeness": round(c_comp, 2),
            "clarity": round(c_clar, 2),
            "consistency": round(c_cons, 2),
            "testability": round(c_test, 2),
            "traceability": round(c_trac, 2),
        }

        return normalized_score, breakdown


class HealthEngine:
    """
    Evaluates workflow health score and maps discrete status labels.
    """

    @staticmethod
    def calculate(
        open_questions_count: int = 0,
        rejections_count: int = 0,
        peer_review_duration_hours: float = 0.0,
    ) -> Tuple[float, str]:
        """
        Calculate workflow health score and status label per PDS Vol 2 §13.5.

        Returns:
            Tuple of (health_score: float, health_status_label: str)
        """
        q_penalty = 5.0 * max(int(open_questions_count), 0)
        r_penalty = 10.0 * max(int(rejections_count), 0)
        p_delay = 15.0 if peer_review_duration_hours > 48.0 else 0.0

        raw_health = 100.0 - q_penalty - r_penalty - p_delay
        health_score = round(max(0.0, min(raw_health, 100.0)), 2)

        # Status Label Mapping (PDS Vol 2 §13.5)
        if health_score >= 90.0:
            health_status = "Healthy"
        elif health_score >= 70.0:
            health_status = "Needs Review"
        elif health_score >= 50.0:
            health_status = "At Risk"
        else:
            health_status = "Blocked"

        return health_score, health_status


confidence_engine = ConfidenceEngine()
health_engine = HealthEngine()
