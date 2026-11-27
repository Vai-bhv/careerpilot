# Local MCP connection

Run the native API or the Compose stack. Open the repository in VS Code and use its workspace MCP configuration. The bridge starts with the repository virtual environment and the private directory for the target API. A custom `CAREERPILOT_TOKEN` must match the API’s configuration. The bridge speaks stdio exclusively and sends authenticated requests to the configured local CareerPilot API.

| Tool group | Available operations |
| --- | --- |
| Read-only | search_jobs, get_job_details, get_matching_explanation, recommend_cv_variant, get_approved_professional_evidence, validate_generated_cv, compare_cv_versions, list_applications, prepare_application, analyse_skill_gaps, get_job_search_statistics |
| Local writes | import_job_description, match_job_to_profile, generate_tailored_cv, generate_cover_letter, shortlist_job, update_application_status |
| May perform a configured external read | sync_job_sources, generate_interview_questions |

Example arguments for three successive calls are shown below. Use the actual job and document IDs returned by the server.

```json
{"name":"import_job_description","arguments":{"title":"Data Analyst","company":"Sample Transit","description":"Required: SQL and Excel. Preferred: Python.","location":"Prague"}}
{"name":"match_job_to_profile","arguments":{"job_id":1}}
{"name":"generate_tailored_cv","arguments":{"job_id":1}}
```

Tool annotations describe read, write and external behaviour. No tool accepts a shell command, filesystem path, mailbox password or submission confirmation. CV generation returns version and evidence identifiers. CV comparison returns changed evidence identifiers. Use the local dashboard for personal contact information and full source documents. A connected model can see what its client sends it, including any disclosable evidence requested through a tool.

The integration test starts a local HTTP API and an official MCP stdio client, negotiates the protocol, lists annotated tools, imports a vacancy, searches and matches it. [Official Python SDK](https://github.com/modelcontextprotocol/python-sdk) · [MCP protocol versioning](https://modelcontextprotocol.io/specification/versioning)
