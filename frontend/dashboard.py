import csv
import io
import json
import os
from datetime import date
from typing import get_args

import httpx
import streamlit as st

from app.client import WorkspaceAPI
from app.schemas import VARIANTS, Kind, Stage, Status

st.set_page_config(
    page_title="CareerPilot", page_icon="◈", layout="wide", initial_sidebar_state="expanded"
)
api = WorkspaceAPI()


def call(method, path, **kwargs):
    try:
        return api.call(method, path, **kwargs)
    except httpx.HTTPStatusError as exc:
        try:
            reason = exc.response.json().get("detail", "Request failed")
        except ValueError:
            reason = "Request failed"
        st.error(f"{reason} ({exc.response.status_code})")
    except httpx.HTTPError:
        st.error("Cannot reach the local CareerPilot API. Start the workspace and reload.")
    st.stop()


def refresh(message):
    st.session_state["notice"] = message
    st.rerun()


def job_picker():
    query = st.text_input("Find a vacancy by title or company", key="pick_query")
    records = call("GET", "/jobs", params={"q": query, "limit": 500})
    if not records:
        st.info("Import a vacancy in Job discovery to start.")
        st.stop()
    by_id = {j["id"]: j for j in records}
    selected = st.session_state.get("current_job")
    key = st.selectbox(
        "Vacancy",
        list(by_id),
        index=list(by_id).index(selected) if selected in by_id else 0,
        format_func=lambda n: f"{by_id[n]['title']} · {by_id[n]['company']} (#{n})",
    )
    st.session_state["current_job"] = key
    return by_id[key]


def overview():
    stats = call("GET", "/statistics")
    st.title("Search overview")
    metrics = st.columns(5)
    for col, (label, key) in zip(
        metrics,
        [
            ("New vacancies", "new"),
            ("Strong matches", "strong_matches"),
            ("Submitted", "submitted"),
            ("Interviews", "interviews"),
            ("Follow-ups due", "follow_ups"),
        ],
        strict=True,
    ):
        col.metric(label, stats[key], border=True)
    st.divider()
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Ranked opportunities")
        ranked = call("GET", "/rankings", params={"limit": 6})
        if not ranked:
            st.caption("Evaluate an imported vacancy to see its rank here.")
        for r in ranked:
            j = call("GET", f"/jobs/{r['job_id']}")
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.text(j["title"])
                c1.caption(j["company"] + " · " + (j["location"] or "Location unknown"))
                c2.metric("Fit score", r["score"])
                if st.button("View vacancy", key=f"view{j['id']}"):
                    st.session_state["current_job"] = j["id"]
                    st.session_state["next_page"] = "Job details"
                    st.rerun()
    with right:
        st.subheader("Application funnel")
        if stats["funnel"]:
            st.bar_chart(
                {k.replace("_", " "): v for k, v in stats["funnel"].items()}, horizontal=True
            )
        else:
            st.caption("Vacancy stages appear here after import.")


def discovery():
    st.title("Job discovery")
    browse, manual, bulk = st.tabs(["Vacancies", "Paste a vacancy", "Import CSV or JSON"])
    with browse:
        cols = st.columns(4)
        q = cols[0].text_input("Search")
        company = cols[1].text_input("Company")
        location = cols[2].text_input("Location")
        source = cols[3].text_input("Source")
        filters = st.columns(3)
        category = filters[0].selectbox(
            "Evaluated role category", [""] + VARIANTS, format_func=lambda x: x or "All categories"
        )
        score = filters[1].number_input("Minimum fit score", min_value=0, max_value=100)
        days = filters[2].selectbox(
            "Freshness", [0, 7, 30, 90], format_func=lambda x: f"Last {x} days" if x else "Any time"
        )
        page = st.number_input("Result page", min_value=1, step=1)
        rows = call(
            "GET",
            "/jobs",
            params={
                "q": q,
                "company": company,
                "location": location,
                "source": source,
                "offset": (page - 1) * 50,
                "min_score": score,
                **({"category": category} if category else {}),
                **({"within_days": days} if days else {}),
            },
        )
        ranks = {r["job_id"]: r for r in call("GET", "/rankings", params={"limit": 500})}
        if rows:
            st.dataframe(
                [
                    {
                        "ID": j["id"],
                        "Role": j["title"],
                        "Company": j["company"],
                        "Location": j["location"],
                        "Category": ranks.get(j["id"], {}).get("variant"),
                        "Score": ranks.get(j["id"], {}).get("score"),
                        "Stage": j["status"],
                        "Last imported": j["checked"][:10],
                    }
                    for j in rows
                ],
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("No vacancies match these filters.")
    with manual, st.form("new"):
        title = st.text_input("Job title")
        employer = st.text_input("Employer")
        loc = st.text_input("Location as advertised")
        url = st.text_input("Posting URL")
        apply_url = st.text_input("Application URL, if different")
        desc = st.text_area("Original job description", height=200)
        if st.form_submit_button("Import vacancy", type="primary"):
            j = call(
                "POST",
                "/jobs",
                json={
                    "title": title,
                    "company": employer,
                    "location": loc or None,
                    "url": url or None,
                    "apply_url": apply_url or None,
                    "description": desc,
                },
            )
            st.session_state["current_job"] = j["id"]
            refresh(f"Imported {j['title']}. Open Job details to evaluate it.")
    with bulk:
        f = st.file_uploader("Vacancy records", type=["json", "csv"])
        if f and st.button("Import records"):
            try:
                text = f.getvalue().decode("utf-8-sig")
                records = (
                    list(csv.DictReader(io.StringIO(text)))
                    if f.name.endswith(".csv")
                    else json.loads(text)
                )
                st.dataframe(
                    call(
                        "POST", "/imports", json=records if isinstance(records, list) else [records]
                    ),
                    hide_index=True,
                )
            except (ValueError, UnicodeError):
                st.error("Use a UTF-8 CSV or JSON file.")


def details():
    st.title("Job details")
    j = job_picker()
    key = j["id"]
    r = call("GET", f"/jobs/{key}/match")
    st.subheader(j["title"])
    st.caption(j["company"] + " · " + (j["location"] or "Location unknown"))
    cols = st.columns(3)
    cols[0].metric("Suitability", f"{r['score']} / 100")
    cols[1].metric("Eligibility", r["eligibility"].replace("_", " ").title())
    cols[2].metric("CV variant", r["variant"])
    st.write(r["explanation"])
    for label, field in [
        ("Matched skills", "matched"),
        ("Missing mandatory skills", "missing_required"),
        ("Missing preferred skills", "missing_preferred"),
    ]:
        st.write(f"**{label}**", ", ".join(r[field]) or "None identified")
    for concern in r["concerns"]:
        st.caption(concern)
    a, b = st.columns(2)
    if a.button("Save evaluation", type="primary"):
        call("POST", f"/jobs/{key}/match")
        refresh("Evaluation saved.")
    if b.button("Shortlist vacancy"):
        call("PUT", f"/jobs/{key}/tracking", json={"status": "shortlisted"})
        refresh("Added to shortlist.")
    with st.expander("Original posting and extracted fields"):
        st.text(j["description"])
        st.json(j["fields"])
        if j["url"]:
            st.link_button("View original posting", j["url"])
    with st.expander("Evidence and scoring breakdown"):
        st.json(r)
    if st.button("Explore transferable skills"):
        advisory = call("GET", f"/jobs/{key}/transferable")
        st.caption(
            "Related approved skills for interview discussion. Mandatory-skill coverage is scored separately."
        )
        st.json(advisory)
    if st.button("Prepare interview questions"):
        for q in call("GET", f"/jobs/{key}/interview")["questions"]:
            st.write(q)


def evidence_workspace():
    st.title("Profile and evidence")
    review_tab, add, templates = st.tabs(["Review evidence", "Add a claim", "Import baselines"])
    rows = call("GET", "/evidence", params={"limit": 500})
    with review_tab:
        st.caption(
            "Review each source, correct the wording and explicitly allow external use before generating a CV."
        )
        only = st.checkbox("Show unresolved conflicts only")
        choices = {e["id"]: e for e in rows if not only or e["conflict"]}
        if choices:
            key = st.selectbox(
                "Claim",
                list(choices),
                format_func=lambda n: f"#{n} · {choices[n]['status']} · {choices[n]['claim'][:95]}",
            )
            row = choices[key]
            if row["conflict"]:
                st.warning(
                    "Conflicting source wording detected. Mark superseded alternatives as not_approved before approving the retained claim."
                )
            evidence_form(row)
        else:
            st.info("No claims in this view.")
    with add:
        evidence_form(None)
    with templates:
        saved = call("GET", "/templates")
        st.dataframe(
            [{"ID": t["id"], "Variant": t["variant"], "Source file": t["filename"]} for t in saved],
            hide_index=True,
        )
        v = st.selectbox("CV variant", VARIANTS)
        f = st.file_uploader("Local baseline", type=["docx", "pdf"])
        if f and st.button("Import for review"):
            call("POST", "/templates", files={"file": (f.name, f.getvalue())}, data={"variant": v})
            refresh("Baseline imported. Review its claims before external use.")
        if saved:
            n = st.selectbox("Inspect source paragraphs", [t["id"] for t in saved])
            source = call("GET", f"/templates/{n}")
            st.dataframe(
                [
                    {"Paragraph": i + 1, "Text": p[0], "Link": p[1]}
                    for i, p in enumerate(source["paragraphs"])
                ],
                hide_index=True,
            )


def evidence_form(row):
    e = row or {
        "id": "new",
        "kind": "achievement",
        "owner": "",
        "claim": "",
        "source": "",
        "status": "unverified",
        "external": False,
        "link": "",
        "technologies": [],
        "notes": "",
        "roles": [],
        "metric": "",
    }
    with st.form(f"evidence_{e['id']}"):

        def val(label, name):
            return st.text_input(label, value=e[name], key=f"e_{e['id']}_{name}")

        kinds = get_args(Kind)
        statuses = get_args(Status)
        kind = st.selectbox("Type", kinds, index=kinds.index(e["kind"]))
        owner = val("Employer, project or candidate", "owner")
        claim = st.text_area("Claim as it may appear in a document", value=e["claim"])
        src = val("Supporting source", "source")
        link = val("Hyperlink", "link")
        tech = st.text_input("Technologies, comma separated", value=", ".join(e["technologies"]))
        metric = val("Verified metric, if applicable", "metric")
        roles = st.text_input("Applicable roles, comma separated", value=", ".join(e["roles"]))
        notes = st.text_area("Private review notes", value=e["notes"])
        status = st.selectbox("Verification", statuses, index=statuses.index(e["status"]))
        external = st.checkbox(
            "I permit this information in application materials", value=e["external"]
        )
        if st.form_submit_button("Save reviewed claim" if row else "Add evidence"):
            data = {
                "kind": kind,
                "owner": owner,
                "claim": claim,
                "source": src,
                "link": link,
                "technologies": [v.strip() for v in tech.split(",") if v.strip()],
                "metric": metric,
                "roles": [v.strip() for v in roles.split(",") if v.strip()],
                "notes": notes,
                "status": status,
                "external": external,
            }
            call(
                "PUT" if row else "POST",
                f"/evidence/{row['id']}" if row else "/evidence",
                json=data,
            )
            refresh("Evidence saved.")


def cv_workspace():
    st.title("CV workspace")
    j = job_picker()
    key = j["id"]
    with st.form("generate"):
        cols = st.columns(3)
        kind = cols[0].selectbox(
            "Document",
            [
                "cv",
                "cover_letter",
                "motivation",
                "recruiter_message",
                "email_application",
                "follow_up",
                "availability",
            ],
        )
        lang = cols[1].selectbox("Message language", ["en", "cs"])
        tone = cols[2].selectbox("Tone", ["formal", "direct"])
        length = st.selectbox("Message length", ["standard", "brief"])
        exclude = st.text_input("Evidence IDs to omit, comma separated")
        if st.form_submit_button("Generate draft", type="primary"):
            try:
                ids = [int(i.strip()) for i in exclude.split(",") if i.strip()]
            except ValueError:
                st.error("Evidence IDs must be integers.")
                st.stop()
            doc = call(
                "POST",
                f"/jobs/{key}/documents",
                json={
                    "kind": kind,
                    "language": lang,
                    "tone": tone,
                    "length": length,
                    "exclude": ids,
                },
            )
            refresh(f"Draft #{doc['id']} created.")
    versions = call("GET", f"/jobs/{key}/documents")
    if not versions:
        st.info("Generated versions will appear here.")
        return
    docs = {d["id"]: d for d in versions}
    n = st.selectbox(
        "Document version",
        list(docs),
        format_func=lambda i: (
            f"#{i} · {docs[i]['kind']} · " + ("approved" if docs[i]["approved"] else "draft")
        ),
    )
    d = docs[n]
    preview, sources, comparison = st.tabs(["Preview and download", "Evidence", "Compare"])
    with preview:
        st.text(d["plain"])
        validation = call("GET", f"/documents/{n}/validate")
        if validation["valid"]:
            st.success("Evidence validated" + (" · 1 A4 page" if d["kind"] == "cv" else ""))
            for col, fmt in zip(
                st.columns(4),
                ["docx", "pdf", "txt", "json"] if d["kind"] == "cv" else ["txt", "json"],
            ):
                resp = api.request("GET", f"/documents/{n}/download/{fmt}")
                col.download_button(
                    fmt.upper(),
                    resp.content,
                    file_name=f"careerpilot-{n}.{fmt}",
                    mime=resp.headers["content-type"],
                )
            if not d["approved"] and st.button(f"Approve version #{n}", type="primary"):
                call("POST", f"/documents/{n}/approve")
                refresh("Version approved for this vacancy.")
        else:
            st.error(" · ".join(validation["errors"]))
    if d["kind"] == "cv":
        with st.expander("Regenerate one section"):
            section = st.selectbox(
                "Section",
                [
                    "Profile",
                    "Experience",
                    "Projects",
                    "Skills",
                    "Education",
                    "Certifications",
                    "Languages",
                ],
            )
            choices = [
                e
                for e in d["snapshot"]["claims"]
                if e["kind"]
                in {
                    "achievement",
                    "project_bullet",
                    "summary",
                    "skill",
                    "education",
                    "certification",
                    "language",
                }
            ]
            omitted = st.multiselect(
                "Omit these claims from the revised section",
                [e["id"] for e in choices],
                format_func=lambda i: next(e["text"] for e in choices if e["id"] == i),
            )
            if st.button("Create revised CV version"):
                updated = call(
                    "POST",
                    f"/jobs/{key}/documents",
                    json={"base_version": n, "section": section, "exclude": omitted},
                )
                refresh(f"Section regenerated in draft #{updated['id']}.")
    with sources:
        st.dataframe(d["snapshot"]["claims"], hide_index=True, width="stretch")
    with comparison:
        opts = [0] + [k for k in docs if k != n]
        other = st.selectbox(
            "Compare with",
            opts,
            format_func=lambda x: "Original baseline" if not x else f"Version #{x}",
        )
        data = call("GET", f"/documents/{n}/compare", params={"previous": other} if other else {})
        left, right = st.columns(2)
        left.text(data["original"])
        right.text(data["tailored"])


def tracker():
    st.title("Application tracker")
    stage = st.selectbox(
        "Filter by stage",
        [""] + list(get_args(Stage)),
        format_func=lambda v: v.replace("_", " ") or "All stages",
    )
    rows = call("GET", "/applications", params={"status": stage, "limit": 500})
    if rows:
        st.dataframe(
            [
                {k: r[k] for k in ("title", "company", "status", "submitted", "cv_id", "letter_id")}
                for r in rows
            ],
            hide_index=True,
            width="stretch",
        )
    j = job_picker()
    key = j["id"]
    prep = call("GET", f"/jobs/{key}/prepare")
    with st.expander("Prepare and confirm application", expanded=True):
        if prep["application_url"]:
            st.link_button("Open official application page", prep["application_url"])
        if prep["ready"] and j["status"] in {
            "discovered",
            "evaluated",
            "shortlisted",
            "cv_generated",
            "awaiting_approval",
            "ready_to_apply",
        }:
            cvs = [d["id"] for d in prep["documents"] if d["kind"] == "cv"]
            cv = st.selectbox("Submitted CV version", cvs)
            letter = st.selectbox(
                "Submitted cover letter",
                [None] + [d["id"] for d in prep["documents"] if d["kind"] == "cover_letter"],
            )
            for d in prep["documents"]:
                if d["id"] in {cv, letter}:
                    st.code(d["plain"], language=None)
            yes = st.checkbox(
                f"I submitted application #{key} with CV #{cv}"
                + (f" and letter #{letter}." if letter else ".")
            )
            if st.button("Record confirmed submission", disabled=not yes):
                call(
                    "POST",
                    f"/jobs/{key}/confirm",
                    json={"cv_id": cv, "letter_id": letter, "confirmed": yes},
                )
                refresh("Submission recorded with the selected document versions.")
        else:
            st.caption(
                "Submission confirmation requires an open vacancy and an approved CV. Recorded submissions appear in the timeline."
            )
    current = next(
        (a for a in call("GET", "/applications", params={"limit": 500}) if a["job_id"] == key), {}
    )
    prev = current.get("details", {})
    with st.form("tracking"):
        stages = [s for s in get_args(Stage) if s != "applied"]
        new = st.selectbox(
            "Update stage",
            stages,
            index=stages.index(j["status"])
            if j["status"] in stages
            else stages.index("recruiter_responded"),
        )
        notes = st.text_area("Notes", prev.get("notes", ""))
        recruiter = st.text_input("Recruiter", prev.get("recruiter", ""))
        due = st.date_input(
            "Follow-up date",
            value=date.fromisoformat(prev["follow_up"]) if prev.get("follow_up") else None,
        )
        meet = st.date_input(
            "Interview date",
            value=date.fromisoformat(prev["interview"]) if prev.get("interview") else None,
        )
        if st.form_submit_button("Save tracker update"):
            call(
                "PUT",
                f"/jobs/{key}/tracking",
                json={
                    "status": new,
                    "notes": notes,
                    "recruiter": recruiter,
                    "follow_up": str(due) if due else None,
                    "interview": str(meet) if meet else None,
                },
            )
            refresh("Tracker updated.")
    st.subheader("Timeline")
    st.dataframe(call("GET", f"/jobs/{key}/timeline"), hide_index=True)
    for m in call("GET", "/communications"):
        if m["job_id"] == key:
            st.write(m["category"], m["subject"], m["summary"])


def skills():
    st.title("Skills intelligence")
    scope = st.checkbox("Shortlisted vacancies only")
    role = st.text_input("Role contains")
    data = call("GET", "/skills", params={"shortlisted": scope, "role": role})
    for label, key in [
        ("Required skills", "demand"),
        ("Missing mandatory skills", "missing"),
        ("Skills in strong matches", "strong"),
    ]:
        st.subheader(label)
        if data[key]:
            st.bar_chart(data[key], horizontal=True)
        else:
            st.caption("No observations in this selection.")


def settings():
    st.title("Settings")
    profile, discovery, mail, schedules = st.tabs(
        ["Candidate preferences", "Discovery sources", "Recruitment mail", "Scheduling and AI"]
    )
    with profile:
        data = call("GET", "/profile")
        with st.form("prefs"):
            data["name"] = st.text_input("Name", value=data["name"])
            data["contact"] = st.text_input("Contact information", value=data["contact"])
            data["github"] = st.text_input("GitHub profile URL", value=data["github"])
            prefs = st.text_area(
                "Career preferences and score weights (JSON)",
                value=json.dumps(data["preferences"], indent=2, ensure_ascii=False),
                height=350,
            )
            if st.form_submit_button("Save preferences"):
                try:
                    data["preferences"] = json.loads(prefs)
                except ValueError:
                    st.error("Enter valid JSON.")
                    st.stop()
                call("PUT", "/profile", json=data)
                refresh("Preferences updated.")
    with discovery:
        st.caption("Configure a published board you are authorised to read.")
        with st.form("boards"):
            platform = st.selectbox("Platform", ["greenhouse", "lever", "lever-eu", "ashby"])
            slug = st.text_input("Board slug")
            company = st.text_input("Employer name")
            if st.form_submit_button("Synchronise board"):
                st.json(
                    call(
                        "POST",
                        "/integrations/board",
                        json={"platform": platform, "slug": slug, "company": company},
                    )
                )
        st.dataframe(call("GET", "/integrations"), hide_index=True)
    with mail:
        if st.button("Read Yahoo folder"):
            st.json(call("POST", "/integrations/yahoo"))
        messages = call("GET", "/communications")
        for m in messages:
            with st.expander(f"{m['category']} · {m['subject']}"):
                st.text(m["summary"])
                st.write("Classification confidence", m["confidence"])
                for u in m["links"]:
                    st.link_button(u, u, key=f"url_{m['id']}_{u}")
                if m["category"] == "job_alert" and m["links"]:
                    with st.form(f"alert_{m['id']}"):
                        link = st.selectbox("Advertised link", m["links"])
                        title = st.text_input("Advertised job title")
                        company = st.text_input("Advertised employer")
                        description = st.text_area("Vacancy description", m["summary"])
                        if st.form_submit_button("Import reviewed vacancy"):
                            job = call(
                                "POST",
                                f"/communications/{m['id']}/vacancies",
                                json={
                                    "title": title,
                                    "company": company,
                                    "description": description,
                                    "url": link,
                                },
                            )
                            refresh(f"Vacancy #{job['id']} imported.")
                if (
                    m["job_id"]
                    and m.get("suggested_status")
                    and st.button(
                        f"Accept suggested stage · {m['suggested_status']}",
                        key=f"suggest_{m['id']}",
                    )
                ):
                    call(
                        "PUT",
                        f"/jobs/{m['job_id']}/tracking",
                        json={"status": m["suggested_status"]},
                    )
                    refresh("Recruitment stage updated.")
                n = st.number_input(
                    "Associate with vacancy ID", min_value=1, step=1, key=f"assoc{m['id']}"
                )
                if st.button("Link to vacancy", key=f"link{m['id']}"):
                    call("PUT", f"/communications/{m['id']}/job/{n}")
                    refresh("Communication linked.")
        if not messages:
            st.caption("No messages imported.")
    with schedules:
        st.caption(
            "Start the local worker to run enabled schedules. Mail classification happens during ingestion."
        )
        task = st.selectbox(
            "Scheduled task", ["boards", "mail", "matching", "freshness", "follow_ups"]
        )
        cfg = next(
            (r["state"] for r in call("GET", "/integrations") if r["name"] == "schedule/" + task),
            {},
        )
        enabled = st.checkbox("Enabled", cfg.get("enabled", False), key="enabled_" + task)
        mins = st.number_input(
            "Interval in minutes",
            min_value=5,
            max_value=10080,
            value=cfg.get("interval_minutes", 60),
            key="time_" + task,
        )
        if st.button("Save schedule"):
            call("PUT", "/schedules/" + task, json={"enabled": enabled, "interval_minutes": mins})
            refresh("Schedule saved.")
        st.subheader("Execution history")
        st.dataframe(call("GET", "/history"), hide_index=True)
        st.subheader("AI provider")
        ai = call("GET", "/ai-settings")
        with st.form("ai"):
            providers = ["mock", "ollama", "openai"]
            provider = st.selectbox("Provider", providers, index=providers.index(ai["provider"]))
            model = st.text_input("Model identifier", ai["model"])
            budget = st.number_input(
                "Daily spending limit (USD)", min_value=0.0, value=float(ai["daily_usd"])
            )
            if st.form_submit_button("Save AI settings"):
                call(
                    "PUT",
                    "/ai-settings",
                    json={"provider": provider, "model": model, "daily_usd": budget},
                )
                refresh("AI settings saved.")
        st.subheader("AI usage")
        st.caption(
            "Configure provider, model, local prices and daily budget in .env. The default uses deterministic questions."
        )
        st.dataframe(call("GET", "/usage"), hide_index=True)


pages = {
    "Overview": overview,
    "Job discovery": discovery,
    "Job details": details,
    "Profile and evidence": evidence_workspace,
    "CV workspace": cv_workspace,
    "Application tracker": tracker,
    "Skills intelligence": skills,
    "Settings": settings,
}
st.sidebar.title("CareerPilot")
st.sidebar.caption("Fictional demo" if os.getenv("CAREERPILOT_DEMO") else "Personal workspace")
if "next_page" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("next_page")
page = st.sidebar.radio("Workspace", list(pages), key="nav")
if "notice" in st.session_state:
    st.success(st.session_state.pop("notice"))
pages[page]()
