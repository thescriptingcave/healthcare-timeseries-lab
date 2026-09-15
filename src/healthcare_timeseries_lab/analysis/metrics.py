"""Error metrics comparing observed device telemetry to true physiology (M9).

Pure-Python helpers (no pandas) so the analysis core is unit-testable; the
notebook applies them per channel and per quality bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev

from healthcare_timeseries_lab.analysis.alignment import AlignmentSample

_VITAL_FIELDS = (
    "heart_rate_bpm",
    "spo2_pct",
    "respiration_rate_bpm",
    "temperature_c",
    "systolic_bp_mmhg",
    "diastolic_bp_mmhg",
)


@dataclass(frozen=True)
class ErrorMetrics:
    n: int
    missing: int
    bias: float
    mae: float
    rmse: float
    max_abs_error: float
    p95_abs_error: float


def error_metrics(
    samples: list[AlignmentSample],
    channel: str,
) -> ErrorMetrics:
    """Pointwise observed-minus-true metrics for ``channel``.

    ``missing`` is the number of true states with no observed event (dropout);
    only present samples contribute to the error terms.
    """
    if channel not in _VITAL_FIELDS:
        raise ValueError(
            f"unknown channel: {channel!r} (expected one of {_VITAL_FIELDS})"
        )

    observed = [sample for sample in samples if sample.event is not None]
    missing = len(samples) - len(observed)

    errors = [
        getattr(sample.event, channel) - getattr(sample.true, channel)
        for sample in observed
    ]

    if not errors:
        return ErrorMetrics(
            n=0,
            missing=missing,
            bias=0.0,
            mae=0.0,
            rmse=0.0,
            max_abs_error=0.0,
            p95_abs_error=0.0,
        )

    absolute = [abs(error) for error in errors]
    absolute.sort()

    return ErrorMetrics(
        n=len(errors),
        missing=missing,
        bias=mean(errors),
        mae=mean(absolute),
        rmse=(pstdev(errors) ** 2 + mean(errors) ** 2) ** 0.5,
        max_abs_error=absolute[-1],
        p95_abs_error=_p95(absolute),
    )


def dropout_count(samples: list[AlignmentSample]) -> int:
    """Number of true states that produced no observed event."""
    return sum(sample.event is None for sample in samples)


def quality_counts(
    samples: list[AlignmentSample],
) -> dict[str, int]:
    """Counts by observed :class:`QualityCode` (only present samples)."""
    counts: dict[str, int] = {}
    for sample in samples:
        if sample.event is None:
            continue
        counts[sample.event.quality_code] = (
            counts.get(sample.event.quality_code, 0) + 1
        )
    return counts


def _p95(sorted_abs: list[float]) -> float:
    if not sorted_abs:
        return 0.0
    index = min(len(sorted_abs) - 1, int(len(sorted_abs) * 0.95))
    return sorted_abs[index]


__all__ = [
    "ErrorMetrics",
    "dropout_count",
    "error_metrics",
    "quality_counts",
]