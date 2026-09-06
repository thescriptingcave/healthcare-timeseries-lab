from dataclasses import dataclass
from datetime import datetime
from random import Random

from healthcare_timeseries_lab.patients.models import PatientProfile
from healthcare_timeseries_lab.physiology.models import PhysiologicalState


@dataclass(frozen=True)
class SignalParameters:
    mean_reversion_strength: float
    noise_stddev: float


class PhysiologyEngine:
    def __init__(self, rng: Random) -> None:
        self._rng = rng

        self._heart_rate = SignalParameters(
            mean_reversion_strength=0.05,
            noise_stddev=0.35,
        )
        self._spo2 = SignalParameters(
            mean_reversion_strength=0.08,
            noise_stddev=0.05,
        )
        self._respiration = SignalParameters(
            mean_reversion_strength=0.06,
            noise_stddev=0.12,
        )
        self._temperature = SignalParameters(
            mean_reversion_strength=0.03,
            noise_stddev=0.01,
        )
        self._systolic_bp = SignalParameters(
            mean_reversion_strength=0.05,
            noise_stddev=0.45,
        )
        self._diastolic_bp = SignalParameters(
            mean_reversion_strength=0.05,
            noise_stddev=0.30,
        )

    def next_state(
        self,
        patient: PatientProfile,
        previous_state: PhysiologicalState,
        timestamp: datetime,
    ) -> PhysiologicalState:
        variability = patient.variability_factor

        heart_rate = self._next_value(
            current=previous_state.heart_rate_bpm,
            baseline=patient.baseline_heart_rate_bpm,
            parameters=self._heart_rate,
            variability=variability,
        )

        spo2 = self._next_value(
            current=previous_state.spo2_pct,
            baseline=patient.baseline_spo2_pct,
            parameters=self._spo2,
            variability=variability,
        )

        respiration = self._next_value(
            current=previous_state.respiration_rate_bpm,
            baseline=patient.baseline_respiration_rate_bpm,
            parameters=self._respiration,
            variability=variability,
        )

        temperature = self._next_value(
            current=previous_state.temperature_c,
            baseline=patient.baseline_temperature_c,
            parameters=self._temperature,
            variability=variability,
        )

        systolic = self._next_value(
            current=previous_state.systolic_bp_mmhg,
            baseline=patient.baseline_systolic_bp_mmhg,
            parameters=self._systolic_bp,
            variability=variability,
        )

        diastolic = self._next_value(
            current=previous_state.diastolic_bp_mmhg,
            baseline=patient.baseline_diastolic_bp_mmhg,
            parameters=self._diastolic_bp,
            variability=variability,
        )

        if systolic <= diastolic:
            systolic = diastolic + 1.0

        return PhysiologicalState(
            timestamp=timestamp,
            heart_rate_bpm=heart_rate,
            spo2_pct=spo2,
            respiration_rate_bpm=respiration,
            temperature_c=temperature,
            systolic_bp_mmhg=systolic,
            diastolic_bp_mmhg=diastolic,
        )

    def _next_value(
        self,
        *,
        current: float,
        baseline: float,
        parameters: SignalParameters,
        variability: float,
    ) -> float:
        mean_reversion = (
            baseline - current
        ) * parameters.mean_reversion_strength

        noise = self._rng.gauss(
            mu=0.0,
            sigma=parameters.noise_stddev * variability,
        )

        return current + mean_reversion + noise