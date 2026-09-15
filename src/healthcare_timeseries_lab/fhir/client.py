"""Thin HTTP client for the HAPI FHIR JPA (transaction push + verify)."""

from __future__ import annotations

from typing import Any

import requests

from healthcare_timeseries_lab.environment import settings


class HapiFhirClient:
    """POSTs transaction Bundles to HAPI and runs lightweight count checks."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings().hapi_base_url).rstrip("/")

    @property
    def capability_url(self) -> str:
        return f"{self.base_url}/metadata"

    @property
    def transaction_url(self) -> str:
        return self.base_url

    def check_capability(self) -> dict[str, Any]:
        resp = requests.get(self.capability_url, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def send_transaction(self, bundle: Any) -> tuple[str, list[str], int]:
        """POST ``bundle`` as a FHIR ``transaction``; return (status, issues, total)."""
        resp = requests.post(
            self.transaction_url,
            json=bundle.model_dump(mode="json"),  # type: ignore[attr-defined]
            headers={"Content-Type": "application/fhir+json"},
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        entry = payload.get("entry", [])
        issues: list[str] = []
        for e in entry:
            response = e.get("response", {})
            outcome = response.get("outcome")
            if outcome and outcome.get("resourceType") == "OperationOutcome":
                issues.append(_format_outcome(outcome))
        return str(resp.status_code), issues, len(entry)

    def count_observations(self, loinc: str) -> int:
        """Count Observations matching a component LOINC using _summary=count."""
        resp = requests.get(
            f"{self.base_url}/Observation",
            params={"code": loinc, "_summary": "count"},
            headers={"Accept": "application/fhir+json"},
            timeout=15,
        )
        resp.raise_for_status()
        return int(resp.json()["total"])


def _format_outcome(outcome: dict[str, Any]) -> str:
    parts: list[str] = []
    for issue in outcome.get("issue", []):
        severity = issue.get("severity", "?")
        code = issue.get("code", "?")
        detail = (issue.get("details", {}) or {}).get("text", "")
        parts.append(f"{severity}/{code}: {detail}".strip())
    return " | ".join(parts)


__all__ = ["HapiFhirClient"]
