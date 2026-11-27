# Security and privacy

CareerPilot handles CVs, private recruiter correspondence and application history on the candidate’s Linux machine. Report security issues privately to the repository maintainer. Use a fictional reproduction and omit secrets, private files and recruiter details.

| Threat | Implemented control and boundary |
| --- | --- |
| Unauthorized API access | All application endpoints require a bearer token, checked in constant time. Native services bind to loopback. Compose publishes only loopback ports. The health probes expose status. |
| Data in a public repository or image | Git exclusions cover private workspaces, source CVs, generated documents, secrets and backups. Docker uses an allowlisted context. Public-file checks and Trivy scans are configured in CI. |
| Instructions in postings, mail and source files | Inputs are parsed as data. The optional model receives controlled skill labels. Responses must validate against a schema and the supplied labels. Models have no tool bindings. |
| Unapproved professional claims | Source extraction starts unverified and private. Verification, disclosure and conflict checks gate selection. Versions are revalidated at approval, preparation, download and confirmation. |
| Source URL abuse | User-submitted URLs are stored for manual navigation. Automated HTTP reads use fixed ATS hosts, constrained board slugs and timeouts. External links allow only HTTP(S) without embedded credentials. |
| Document and mail content | Size limits, expanded DOCX limits, a page limit, MIME parsing and safe link selection constrain imports. LibreOffice converts newly generated documents. Attachments and email instructions have no execution path. |
| Mailbox state or mass application changes | Read-only IMAP selection and BODY.PEEK. Local suggestions require review. There is no mail sender or automatic application-submission adapter. |
| Duplicate or misattributed submissions | A unique vacancy foreign key, pinned document versions, current validation and explicit user confirmation guard recording. |
| Secret exposure in diagnostics | SQLAlchemy hides SQL parameters, API validation errors omit submitted values, source failures store error classes or HTTP status. Launchers disable access logging. Sensitive audit records are private. |
| Unexpected provider spend | Deterministic default, explicit local configuration, capped output, bounded vocabulary, daily reservations and cached results. |

Protect the local OS account and backups. Data at rest uses the host filesystem and database permissions. The application has no independent encryption layer. A compromised desktop, browser extension or local process with filesystem access is outside the single-user trust boundary. Avoid publishing the dashboard or proxying it to a public network. MCP clients can transmit returned disclosable evidence to their chosen model. Approve tool use in the client accordingly.

A source document can contain an incorrect claim. The software validates consistency with reviewed evidence. Human review remains necessary for provenance, employer disclosure rules and legal eligibility. File parsing is not a general sandbox for hostile binary files. Keep parser dependencies current.
