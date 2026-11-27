# Source capability matrix

All external reads are opt-in. Enable a board only when its owner and applicable terms permit the intended personal use. Employer-facing publishing endpoints are scoped to an individual company. There is no cross-portal search credential or default board list.

| Source | Discovery | Details | Submission in CareerPilot | Verification |
| --- | --- | --- | --- | --- |
| Manual URL and text, CSV, JSON | User import | Supplied description and structured fields | Official link and manual confirmation | Local tests |
| Yahoo Mail | Configured folder and sender, MIME links, summaries | Candidate reviews alert and imports a selected link with supplied details | Manual | Mock mailbox and MIME fixtures |
| Greenhouse | Published jobs for one enabled board | List endpoint with content | Official link | Mock listing and live single-detail read |
| Lever and Lever EU | Paginated published postings for one employer | Description, lists, location, apply URL | Official link | Mock HTTP and live global demo (9 valid, 1 malformed) |
| Ashby | Published and listed jobs for an enabled board | Description, arrangement and URLs | Official link | Mock HTTP |
| LinkedIn, Jobs.cz, StartupJobs.cz, Prace.cz, Indeed, Expats.cz, EURES | User-provided alert or manual import | Supplied text | Official link | Manual workflow only |
| Workday and other direct company career pages | Manual import or user-obtained alert | Supplied text | Official link | Manual workflow only |

Greenhouse documents public board GET operations and separately authenticated application POST operations. CareerPilot uses board listing reads only. Consult the employer’s terms for use of its content. [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html)

Lever documents publicly available postings, company namespaces, global and EU instances and separate application operations. CareerPilot reads postings, with a one-second interval between full pages and a local per-run limit. [Lever Postings API](https://github.com/lever/postings-api) · [Lever terms](https://www.lever.co/legal/terms-of-service)

Ashby documents published postings for an organization and exposes `isListed`, job URLs and application URLs. The adapter skips explicitly unlisted entries. [Ashby API](https://developers.ashbyhq.com/docs/public-job-posting-api) · [Ashby customer terms](https://www.ashbyhq.com/resources/terms)

Board adapters use fixed HTTPS origins, validated slugs, timeouts and a 15-minute database-backed cache. Errors and malformed record counts appear in integration history. Rate limits respect Retry-After. The worker retries due jobs and honours board cooldowns. No adapter visits a user-pasted webpage. Credentials for employer application APIs are unnecessary.

## Yahoo setup

Create a Yahoo app password locally. Set `YAHOO_EMAIL` and `YAHOO_APP_PASSWORD` in the ignored `.env`, use an owner-only file mode, and create or choose a dedicated recruitment folder. Set `YAHOO_FOLDER`, optional exact sender `YAHOO_FROM`, and `YAHOO_SEARCH` to ALL, UNSEEN, SEEN or FLAGGED. Choose ALL for incremental reads regardless of read state. Restart after environment changes. Trigger **Settings → Recruitment mail** or enable the mail schedule.

Yahoo specifies IMAP over TLS on port 993 at `imap.mail.yahoo.com`, full email address and app password. CareerPilot selects the folder read-only and requests `BODY.PEEK`. A UIDVALIDITY change resets that cursor. Hashed Message-IDs prevent repeat processing. Each run handles up to 100 messages and reads at most the first MB per message. Poster links and HTML remain inert until a human acts. The mock adapter reads a fictional fixture with `CAREERPILOT_MAIL=mock`. [Yahoo connection settings](https://help.yahoo.com/kb/imap-settings-sln4075.html) · [Python IMAP documentation](https://docs.python.org/3.12/library/imaplib.html)

The UI exposes suggestions for recruiter responses, interviews and rejections. Linking a communication and accepting a stage are explicit actions. A confirmation email can never mark an application submitted. No SMTP or mailbox mutation operations are implemented.
