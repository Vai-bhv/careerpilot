# CareerPilot implementation status

Verified locally on 27 November 2026. The offline application workflow works with fictional evidence on both supported databases. The personal workspace is at the human evidence-review step. The container release scan has outstanding findings.

## Milestones

| Milestone | Implemented and exercised | Remaining acceptance |
| --- | --- | --- |
| 0 · Environment | Inspected Ubuntu 24.04.4, Python 3.12.3, LibreOffice, Poppler, PostgreSQL client and Docker. Created the private boundary, locked dependencies, architecture record and test environments. | Recheck dependencies and scans at release time. |
| 1 · Core | SQLAlchemy persistence, two incremental Alembic revisions, typed evidence, profile history, local DOCX/PDF import, structured manual import, authenticated API and fictional fixtures. Reimported all six private baselines without duplicating claims. | Candidate reviews claim wording, conflicts and disclosure. |
| 2 · Job intelligence | English/Czech extraction, canonical URLs, source provenance, fuzzy duplicate suggestions, weighted fit and eligibility, search, role recommendations and Streamlit views. Imported one complete Prague vacancy through the manual workflow. | Expand the four-case labelled dataset and review more real Czech advertisements. |
| 3 · Tailoring | Baseline selection, evidence validation, private version history, section regeneration, comparisons, approval, DOCX/PDF/text/JSON export and on-demand communications. Four fictional CVs passed page-count and hyperlink checks. | Compare a personally approved CV with the candidate’s source material. Live model accounts remain unverified. |
| 4 · Discovery | Read-only Yahoo and mock adapter, Greenhouse, Ashby and Lever adapters, local caching, scheduling, error history and incremental cursors. Lever’s documented live demo returned 9 valid records and 1 malformed record. Immediate repeat used cache. | Verify opted-in Yahoo mailbox, Ashby and EU Lever reads and the Greenhouse board-list adapter with an intended employer. A single live Greenhouse detail read succeeded. |
| 5 · Applications | Manual shortlist, readiness, version-specific confirmation, duplicate prevention, timeline, human-reviewed mail suggestions, interview and follow-up dates. Exercised the acceptance path against fictional data. | The candidate decides whether and where to apply. |
| 6 · MCP | 19 stdio tools, read/write annotations, local HTTP client, VS Code configuration and a real SDK client/server round trip. | VS Code’s interactive trust dialogue was not exercised. |
| 7 · Portfolio release | README, architecture, threat model, screenshots, sample CV, evaluation harness, CI, source and image scanning, Compose smoke test. | Container release gate is failing. Hosted CI awaits an authorized push. |

## Acceptance evidence

- Six real DOCX baselines imported locally. The supplied PDF counterparts remain in the private source directory. A second import returned the same six templates and 59 evidence records. Two records have conflict flags. The private workspace had zero externally approved claims, generated documents and submissions at verification.
- Imported the full 4,478-character text of a published Prague analytics-engineering vacancy through the manual JSON importer. The original public job ID and application URL were checked before import. Extraction identified dbt, SQL, Snowflake, Python and AWS as required skills. Eligibility suggested clarification. The private database contains the posting and its source URL.
- A fictional acceptance run imported all six variants, used approved claims from two concurrent part-time positions and two projects, generated a CV and a cover letter, approved both and recorded their exact version IDs. The sample PDF and DOCX preserve three clickable links. The real user approval and submission steps require the candidate.
- Browser verification rendered all eight dashboard views. The Streamlit test exercises those views against the authenticated API and a fictional mailbox record. The personal source document content was excluded from screenshots.
- The official MCP client negotiated stdio, discovered tool annotations, imported a vacancy, retrieved it via search and obtained its match explanation. The server has no submit or send tool.

## Validation and evaluation

| Check | Observed result |
| --- | --- |
| Full local suite with disposable PostgreSQL | 25 passed, 1 upstream deprecation warning, in 12.84 seconds. Includes API, migrations, importer, grounding, documents, submission, scheduler, providers, UI and MCP. |
| Dependency resolution | `python -m pip check` found no broken requirements. |
| Static checks | `ruff check .`, `ruff format --check .` and the public-file privacy check passed. |
| Docker Compose | Fresh PostgreSQL volume migrated, API readiness and Streamlit health passed, a fictional one-page PDF generated and validated against PostgreSQL, and the disposable stack was removed. |
| Matching rubric | Predicted bands matched four manually assigned fictional labels. Scores were 100 and 100 for the two strong roles, 49 for the stretch role and 6 for the poor role. |
| Mandatory skill extraction | 11 true positives, 0 false positives and 0 false negatives on those four labelled descriptions. |
| Grounding and rendering | Four of four fictional exports validated. They contained 56 approved evidence references and 12 hyperlink occurrences. Tests rejected changed metrics, wrong employer attribution, revoked disclosure and injected instructions. This is a small controlled evaluation. |
| Trivy 0.76.2 | Public-source scan reported zero high/critical vulnerability or secret findings at the configured severity. The refreshed image reported 89 high and 1 critical Debian package findings, zero with a fixed package version listed for that image. |

The critical image finding is CVE-2026-6653 in libxml2. Debian lists the installed trixie version as vulnerable. The image gate deliberately exits nonzero. The detailed JSON reports are in the ignored local security-report directories. [Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-6653)

## Decisions and limits

- PostgreSQL 16 is the Compose deployment target. SQLite is the native fallback and contains the imported personal workspace. A modular monolith, one worker and stdio avoid the resource cost of a broker or vector database. On the inspected host, the virtual environment used about 613 MiB. The optional Trivy database/cache used about 1.8 GiB. Host memory was approximately 15 GiB with 223 GiB of disk available at initial inspection. Peak application RSS and sustained ingestion throughput have not been benchmarked.
- Tailoring is extractive and prioritizes verified wording. Optional model-assisted advice works with controlled skill labels. The software cannot determine whether the underlying human-approved evidence is true. PDF line breaks may require correction. Rendered CV download requires working LibreOffice Writer.
- The public project uses the MIT license. Real claims, mail, application records, generated personal documents, tokens and backups belong in private storage. No release, external deployment or job submission has been performed.
- Unknown application requirements, disjunctions, language levels and qualifications beyond the vocabulary still require review. Fuzzy matching suggests candidates for review and leaves uncertain records separate. Salary comparisons require compatible currency and period. Archived or stale links can require manual rechecking.
- The test client emits one upstream Starlette deprecation warning about its HTTPX backend. Current API tests pass with the pinned versions. Live paid-provider billing, personal mailbox authentication, hosted CI, a backup restore drill and public multi-user operation are unverified.

## Next actionable steps

For personal use, open **Profile and evidence**, resolve the two flagged records, and approve the identity, contact, official employment headers, project headers and supporting bullets intended for disclosure. Review the imported vacancy, generate the first personal draft, inspect it, and approve a version before recording any real submission.

For a portfolio release, rebuild and rescan when Debian publishes package updates, verify hosted CI upon authorization, and retain the measured limitations in the public documentation.

## Public development-stage preparation

The audit found and corrected an evidence review inconsistency involving normalized employer names. The expanded 30-case synthetic matching evaluation agreed with 26 fit labels and identified all 81 required and 26 labelled preferred skill occurrences. See [the audit](docs/IMPLEMENTATION_AUDIT.md) and [the evaluation](docs/architecture/evaluation.md).

The publication regression run passed 25 tests in 16.77 seconds on the local suite with disposable PostgreSQL. Trivy found no secrets or high/critical dependency findings in the public working tree at the configured severity. The local image rescan found 89 high and one critical Debian finding, with zero listed fixed versions. Publish development source only.

## Operational readiness

The evidence screen now groups claims by owner and type, shows source references and flags, and indicates the minimum missing evidence for CV generation. Explicit batch approval checks each submitted snapshot and rejects stale, conflicting and restricted records. Applications made with existing CVs can be recorded by filename or version. Saved board configurations support enabling scheduled reads and retaining the last successful sync.

The local PostgreSQL regression suite passed 26 tests. Ruff and the public-file privacy check passed. The matching-only evaluation reproduced 26 of 30 fit bands, 81 required skills and 26 labelled preferred skills. The native API readiness check passed. Live Yahoo and model verification still require local configuration. The container image has no runtime changes in this increment. The last measured image scan reported one critical and 89 high Debian findings.

## Thunderbird bridge increment

Added a Thunderbird 161.0 MailExtension with account/folder selection, a user-set starting date, selected-message import, opt-in incremental folder sync, redacted history and native plaintext compose. The dedicated loopback API authenticates with an independently rotatable token and limits request size. It reuses mail classification and deduplication. The fictional regression suite passed 27 tests with disposable PostgreSQL, including token scope, rotation, origin checks, size limits and duplicate handling. JavaScript syntax, Ruff and the public-file privacy check passed.

Live Thunderbird access is pending explicit user permission. Native replies and attachment transfer, richer alert extraction and application matching, the dedicated AI workspace and MCP expansion remain pending. The hosted LibreOffice install now retries package downloads. The image vulnerability gate remains enabled.

The rebuilt Compose stack passed the PostgreSQL, dashboard and PDF smoke test. Trivy reported zero high/critical source findings and zero secrets. The image scan remains failing with one critical and 89 high Debian findings and no fixed package versions listed by the scan.
