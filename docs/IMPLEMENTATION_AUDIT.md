# Implementation audit

The public source is a development-stage release. The personal SQLite workspace is independent of the repository.

| Priority | Finding | Disposition |
| --- | --- | --- |
| P0 | The last scanned Compose image had a critical Debian libxml2 finding. | Keep the image release gate failing. Publish source separately after the privacy checks. The previous report also recorded 89 high findings. |
| P1 | Evidence reviews queried exact owner spelling before applying normalized contradiction checks. | Review all records of the same evidence type so spelling and case cannot bypass the contradiction predicate. |
| P1 | Live Yahoo, OpenAI and Ollama verification depends on account or local runtime configuration. | Keep deterministic and fixture coverage. Activation instructions are in the operations guide. |
| P2 | Czech and English rule-based extraction has bounded vocabulary and heading coverage. | Report labelled results and retain human review for eligibility and ambiguous requirements. |
| P2 | PostgreSQL full-text search differs from SQLite substring search. | Both backends share relational constraints and ingestion logic. Search semantics are documented in the data model. |
| P2 | Official automated discovery is limited to implemented ATS adapters and mail. | Refer to the integration capability matrix for current scope and live verification. |
| P3 | Sustained workload, backup restore and interactive VS Code setup need additional verification. | Keep them outside the verified acceptance claims. |
