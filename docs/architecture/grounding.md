# Matching and document grounding

## Vacancy interpretation

Manual import stores the supplied advertisement verbatim. Rule-based extraction recognizes required and preferred sections, skill aliases, selected Czech and English headings, explicit salary ranges, work arrangements, and some authorisation language. Unknown values are JSON null. Structured CSV/JSON or API fields can supply precise information. The vocabulary and grammar are deliberately bounded. Disjunctions, negated requirements, language levels and unfamiliar Czech phrases need human review. Classification confidence is a description of the extraction method. Mail confidence is a heuristic score.

Canonical URLs retain identity-bearing query parameters and remove known tracking parameters. A source ID or canonical URL is a strong identity. Exact description, normalized company, title and location can link sources. Separate requisition IDs at the same source stay separate. Similar descriptions with the same company and title suggest duplicate IDs for review. The default similarity threshold is 0.78 and can be set with `CAREERPILOT_DUPLICATE_SIMILARITY`.

## Suitability

The required-skill component is the fraction of identified mandatory skills backed by disclosable evidence. Preferred skills, role similarity, responsibility overlap, domain, portfolio relevance, location, work arrangement, employment type, seniority and comparable salary ranges contribute configured weights when data is available. Weights are normalized over applicable components. Evidence IDs and missing skills accompany the result. The score measures fit on this rubric. Scores of 80, 60 and 35 mark the strong, reasonable and stretch bands.

Eligibility and recommendation are separate outputs. Missing candidate authorisation warrants clarification. A hard conflict requires both the structured vacancy requirement `authorisation_required` and candidate confirmation `not_authorised`. Language gaps route to review. Experience text prompts a review of official dates. Concurrent part-time roles retain their actual dates. Type and location preferences affect ranking. The available role variants use title and description cues. Saved evaluations populate the ranking and funnel.

Optional transferable-skill advice orders existing controlled skill labels for discussion of missing requirements. Interview preparation uses the same limited provider interface. Neither path can create a new professional fact. With no model configured, both return deterministic results. Remote requests contain vocabulary labels and system instructions. Drafts, mail, contact details, employer names, evidence descriptions and source files stay local.

## Grounding and rendering

1. Candidate or document-supported verification, explicit external permission and a resolved conflict state gate evidence selection.
2. The generator selects a role variant, relevant evidence and matching source citations. It composes sections from approved wording. Employment and project bullets require an approved owner header. The extractive approach preserves delivered versus in-development wording. Reviewed summaries and project bullets can be edited in the evidence workspace before regeneration.
3. The validator compares every claim ID, owner, type, rendered text and link with current approved evidence. It checks the active section owner, exact text and file digests. Numbers, qualifiers, dates and education therefore share the same deterministic check. Weekly hours are removed by a narrow display rule. AI project performance lines require both data and evaluation-method wording and are suppressed for other variants.
4. DOCX uses single-column A4 and 10.5-point body text. LibreOffice converts newly authored DOCX files in an isolated temporary profile. The exporter inspects page count and PDF URI annotations. Extra bullets and lower-priority text can be removed to fit. It fails for manual adjustment if the remaining content exceeds one page.
5. Documents are immutable. Full and section regeneration create new IDs. Approval, preparation, download and submission revalidate current evidence. Changed claims can invalidate an old version while its historical submitted bytes remain stored. Manually altered exported files need separate review outside the application.
6. Cover letters and recruiter messages use English or Czech framing around verbatim approved facts. Provide approved Czech evidence when a fully Czech draft is needed. No automatic translation of professional claims is enabled.

Generated text is validated against the candidate’s reviewed registry. Verifying the truth, confidentiality and provenance of the registry itself is the candidate’s responsibility. The demo uses labelled fictional evidence.
