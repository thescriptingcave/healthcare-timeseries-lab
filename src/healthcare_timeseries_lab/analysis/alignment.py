"""Aligned observed-vs-truth samples for device analysis (Milestone 9).

``align_observed_to_truth`` joins a runner's true ``PhysiologicalState``
sequence (one per tick, ``sequence_number`` starting at 1) with the observed
``VitalsTelemetryEvent`` stream, preserving the gaps where dropout suppressed
an event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from healthcare_timeseries_lab.physiology.models import PhysiologicalState
from healthcare_timeseries_lab.telemetry.events import VitalsTelemetryEvent

SequenceNumber = int


@dataclass(frozen=True)
class AlignmentSample:
    sequence_number: SequenceNumber
    timestamp: datetime
    true: PhysiologicalState
    event: VitalsTelemetryEvent | None = None


def align_observed_to_truth(
    states: list[PhysiologicalState],
    events: list[VitalsTelemetryEvent],
) -> list[AlignmentSample]:
    """Pair each true state with its observed event (or ``None`` on dropout).

    ``states`` is produced by the runners as one ``PhysicalState`` per tick
    with ``sequence_number`` starting at 1 (index ``sequence_number - 1``);
    ``events`` carry the same ``sequence_number``, so an event missing from
    the sequence indicates device dropout.
    """
    by_sequence: dict[SequenceNumber, VitalsTelemetryEvent] = {
        event.sequence_number: event for event in events
    }

    return [
        AlignmentSample(
            sequence_number=i + 1,
            timestamp=state.timestamp,
            true=state,
            event=by_sequence.get(i + 1),
        )
        for i, state in enumerate(states)
    ]


__all__ = [
    "AlignmentSample",
    "align_observed_to_truth",
]