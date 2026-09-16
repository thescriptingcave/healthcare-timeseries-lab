# Documentation

Project documentation for the Healthcare Time-Series Lab. Each document
describes a slice of the repository as it stands today (Milestones 1-10).

| Document | What it covers |
|----------|----------------|
| [architecture](architecture.md) | Components, layers, and key architectural decisions |
| [data_flow](data_flow.md) | End-to-end batch pipelines and read paths |
| [data_model](data_model.md) | Tables, the Avro contract, entities, and LOINC mapping |
| [infrastructure](infrastructure.md) | Docker topology, ports, catalogs, and bootstrap |
| [reliability](reliability.md) | Determinism, idempotency, healthchecks, and guardrails |
| [scope](scope.md) | What is included, out of scope, and planned |
| [testing](testing.md) | Test strategy, module map, and gates |
| [training](training.md) | Lesson library, notebooks, dashboards, learning path |

Diagrams use Mermaid and render on GitHub. The repository is a **synthetic
data platform for software-engineering and analytics education**; it is not a
clinically validated physiological simulator and must not be used for
diagnosis, treatment, or clinical decision-making.