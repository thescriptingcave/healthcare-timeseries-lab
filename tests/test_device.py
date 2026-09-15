from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from healthcare_timeseries_lab.device import (
    DeviceChannelConfig,
    DeviceSimulationConfig,
    DeviceSimulator,
    DeviceStatus,
    DisconnectWindow,
    FlatlineWindow,
    QualityCode,
)
from healthcare_timeseries_lab.physiology.models import PhysiologicalState

EVENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SIMULATION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PATIENT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DEVICE_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

START = datetime(2026, 1, 1, tzinfo=UTC)


def make_state(
    *,
    timestamp: datetime = START,
    **overrides: float,
) -> PhysiologicalState:
    base = {
        "heart_rate_bpm": 72.0,
        "spo2_pct": 98.0,
        "respiration_rate_bpm": 14.0,
        "temperature_c": 36.8,
        "systolic_bp_mmhg": 120.0,
        "diastolic_bp_mmhg": 76.0,
    }
    base.update(overrides)
    return PhysiologicalState(timestamp=timestamp, **base)


def observe(
    sim: DeviceSimulator,
    state: PhysiologicalState,
    sequence_number: int = 1,
):
    return sim.observe(
        state=state,
        simulation_id=SIMULATION_ID,
        patient_id=PATIENT_ID,
        device_id=DEVICE_ID,
        sequence_number=sequence_number,
        event_id=EVENT_ID,
    )


def test_identity_passthrough_with_no_channel_config() -> None:
    config = DeviceSimulationConfig(seed=0)
    sim = DeviceSimulator(config=config)

    event = observe(sim, make_state())

    assert event is not None
    assert event.heart_rate_bpm == 72.0
    assert event.spo2_pct == 98.0
    assert event.temperature_c == 36.8
    assert event.device_status == DeviceStatus.CONNECTED.value
    assert event.quality_code == QualityCode.GOOD.value
    assert event.event_time == START


def test_noise_does_not_change_mean() -> None:
    config = DeviceSimulationConfig(
        seed=123,
        channels={
            "heart_rate_bpm": DeviceChannelConfig(noise_stddev=10.0),
        },
    )
    sim = DeviceSimulator(config=config)

    values = [
        observe(sim, make_state(), sequence_number=i + 1).heart_rate_bpm
        for i in range(1000)
    ]

    mean = sum(values) / len(values)
    assert abs(mean - 72.0) < 2.0


def test_precision_rounds_values() -> None:
    config = DeviceSimulationConfig(
        seed=0,
        channels={
            "temperature_c": DeviceChannelConfig(precision=0),
        },
    )
    sim = DeviceSimulator(config=config)

    event = observe(sim, make_state())

    assert event is not None
    assert event.temperature_c == round(36.8, 0)


def test_clock_skew_shifts_event_time() -> None:
    config = DeviceSimulationConfig(
        seed=0,
        clock_skew=timedelta(seconds=30),
    )
    sim = DeviceSimulator(config=config)

    event = observe(sim, make_state())

    assert event is not None
    assert event.event_time == START + timedelta(seconds=30)


def test_latency_shifts_event_time() -> None:
    config = DeviceSimulationConfig(
        seed=0,
        latency_seconds=2.0,
        dropout_probability=0.0,
    )
    sim = DeviceSimulator(config=config)

    event = observe(sim, make_state())

    assert event is not None
    assert event.event_time >= START


def test_dropout_returns_none() -> None:
    config = DeviceSimulationConfig(
        seed=0,
        dropout_probability=1.0,
    )
    sim = DeviceSimulator(config=config)

    event = observe(sim, make_state())

    assert event is None


def test_drift_increases_over_time() -> None:
    config = DeviceSimulationConfig(
        seed=0,
        channels={
            "spo2_pct": DeviceChannelConfig(
                noise_stddev=0.0,
                drift_per_hour=1.0,
            ),
        },
    )
    sim = DeviceSimulator(config=config)

    t0 = observe(sim, make_state(timestamp=START), sequence_number=1)
    t1 = observe(
        sim,
        make_state(timestamp=START + timedelta(hours=1)),
        sequence_number=2,
    )

    assert t0 is not None
    assert t1 is not None
    assert t1.spo2_pct > t0.spo2_pct


def test_spike_adds_amplitude() -> None:
    config = DeviceSimulationConfig(
        seed=42,
        channels={
            "spo2_pct": DeviceChannelConfig(
                spike_probability=1.0,
                spike_amplitude=5.0,
                noise_stddev=0.0,
            ),
        },
    )
    sim = DeviceSimulator(config=config)

    event = observe(sim, make_state())

    assert event is not None
    assert abs(event.spo2_pct - 98.0) == pytest.approx(5.0, abs=0.1)


def test_flatline_freezes_value_and_sets_poor() -> None:
    config = DeviceSimulationConfig(
        seed=0,
        flatline_windows=(
            FlatlineWindow(
                channel="spo2_pct",
                start_offset=timedelta(seconds=0),
                end_offset=timedelta(seconds=60),
            ),
        ),
    )
    sim = DeviceSimulator(config=config)

    first = observe(sim, make_state(), sequence_number=1)
    second = observe(
        sim,
        make_state(timestamp=START + timedelta(seconds=30)),
        sequence_number=2,
    )

    assert first is not None
    assert second is not None
    assert second.spo2_pct == first.spo2_pct
    assert second.quality_code == QualityCode.POOR.value


def test_disconnect_freezes_and_sets_lost() -> None:
    config = DeviceSimulationConfig(
        seed=0,
        disconnect_windows=(
            DisconnectWindow(
                start_offset=timedelta(seconds=30),
                end_offset=timedelta(seconds=90),
            ),
        ),
    )
    sim = DeviceSimulator(config=config)

    before = observe(sim, make_state(), sequence_number=1)
    during = observe(
        sim,
        make_state(timestamp=START + timedelta(seconds=30)),
        sequence_number=2,
    )

    assert before is not None
    assert during is not None
    assert during.device_status == DeviceStatus.DISCONNECTED.value
    assert during.quality_code == QualityCode.LOST.value
    assert during.heart_rate_bpm == before.heart_rate_bpm


def test_disconnect_recovery_restores_connected() -> None:
    config = DeviceSimulationConfig(
        seed=0,
        disconnect_windows=(
            DisconnectWindow(
                start_offset=timedelta(seconds=30),
                end_offset=timedelta(seconds=60),
            ),
        ),
    )
    sim = DeviceSimulator(config=config)

    observe(sim, make_state(), sequence_number=1)
    observe(
        sim,
        make_state(timestamp=START + timedelta(seconds=30)),
        sequence_number=2,
    )
    after = observe(
        sim,
        make_state(timestamp=START + timedelta(seconds=60)),
        sequence_number=3,
    )

    assert after is not None
    assert after.device_status == DeviceStatus.CONNECTED.value
    assert after.quality_code == QualityCode.GOOD.value


def test_runner_without_device_produces_full_events() -> None:
    from healthcare_timeseries_lab.patients.models import PatientProfile
    from healthcare_timeseries_lab.simulation.runner import (
        BaselineSimulationConfig,
        run_baseline_simulation,
    )

    patient = PatientProfile(
        patient_id=PATIENT_ID,
        age=45,
        sex="female",
        baseline_heart_rate_bpm=72.0,
        baseline_spo2_pct=98.0,
        baseline_respiration_rate_bpm=14.0,
        baseline_temperature_c=36.8,
        baseline_systolic_bp_mmhg=120.0,
        baseline_diastolic_bp_mmhg=76.0,
        variability_factor=1.0,
    )

    config = BaselineSimulationConfig(
        simulation_id=SIMULATION_ID,
        device_id=DEVICE_ID,
        start_time=START,
        duration=timedelta(seconds=15),
        step=timedelta(seconds=5),
        seed=42,
    )

    result = run_baseline_simulation(patient=patient, config=config)

    assert len(result.events) == 3
    assert len(result.states) == 3


def test_runner_with_device_filters_dropped_events() -> None:
    from healthcare_timeseries_lab.patients.models import PatientProfile
    from healthcare_timeseries_lab.simulation.runner import (
        BaselineSimulationConfig,
        run_baseline_simulation,
    )

    patient = PatientProfile(
        patient_id=PATIENT_ID,
        age=45,
        sex="female",
        baseline_heart_rate_bpm=72.0,
        baseline_spo2_pct=98.0,
        baseline_respiration_rate_bpm=14.0,
        baseline_temperature_c=36.8,
        baseline_systolic_bp_mmhg=120.0,
        baseline_diastolic_bp_mmhg=76.0,
        variability_factor=1.0,
    )

    device_config = DeviceSimulationConfig(
        seed=42,
        dropout_probability=1.0,
    )

    config = BaselineSimulationConfig(
        simulation_id=SIMULATION_ID,
        device_id=DEVICE_ID,
        start_time=START,
        duration=timedelta(seconds=15),
        step=timedelta(seconds=5),
        seed=42,
    )

    result = run_baseline_simulation(
        patient=patient,
        config=config,
        device=device_config,
    )

    assert len(result.events) == 0
    assert len(result.states) == 3


def test_config_validation_rejects_bad_channel() -> None:
    with pytest.raises(ValueError, match="unknown channel"):
        DeviceSimulationConfig(
            channels={
                "invalid_channel": DeviceChannelConfig(noise_stddev=1.0),
            }
        )


def test_flatline_window_requires_valid_channel() -> None:
    with pytest.raises(ValueError, match="unknown channel"):
        FlatlineWindow(
            channel="invalid",
            start_offset=timedelta(seconds=0),
            end_offset=timedelta(seconds=60),
        )


def test_flatline_window_requires_start_before_end() -> None:
    with pytest.raises(ValueError, match="end_offset"):
        FlatlineWindow(
            channel="spo2_pct",
            start_offset=timedelta(seconds=60),
            end_offset=timedelta(seconds=0),
        )
