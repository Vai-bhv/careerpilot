# Thunderbird bridge

The extension targets Thunderbird 161.0, the version in the local Ubuntu Snap package. The implementation uses the documented account, folder, message, menus and compose APIs. Thunderbird owns mail authentication. CareerPilot uses a dedicated token that can authorize only status and message ingestion.

1. Start CareerPilot with `scripts/start.sh`. If ports are occupied, run `CAREERPILOT_PORT=8002 CAREERPILOT_DASHBOARD_PORT=8502 scripts/start.sh`.
2. Generate a dedicated token locally with `.venv/bin/careerpilot thunderbird pair`. Rerun this command to rotate it. Use `.venv/bin/careerpilot thunderbird revoke` to revoke it.
3. In Thunderbird, open **Add-ons and Themes**, choose **Debug Add-ons** from the gear menu and **Load Temporary Add-on**. Select `integrations/thunderbird/manifest.json`. Developer loads expire when Thunderbird restarts. Persistent installation has not been verified.
4. Open the extension’s settings. Paste the dedicated token, set the API port, and select the account, dedicated recruitment folder and initial date. Save settings and check the pairing status. Use a recent date and a dedicated folder to limit the historical import.
5. Select **Synchronize folder**. For selected messages, use the CareerPilot command from the message list context menu. Enable 15-minute synchronization only if desired. Open **Settings → Recruitment mail** in CareerPilot to review excerpts, link correspondence and import reviewed alert URLs.
6. The extension can open a native compose window from an explicitly chosen identity, recipient, subject and editable plaintext body. Finish reviewing and sending in Thunderbird.

Only plain or HTML body text and basic headers cross the loopback connection. The existing mail pipeline strips scripts and deduplicates by Internet Message-ID. The initial import ends at the run’s start time. Incremental sync overlaps the preceding 24 hours and advances its cursor after a successful run. Failed imports can be retried without creating duplicate records. Messages moved into the folder with dates older than the overlap require changing the initial date and saving again. Token storage is local to the extension and the server token file is owner-only.

Live installation, account selection and synchronization against a private mailbox require the user’s explicit permission. The server-side bridge has fictional integration tests. [Thunderbird MailExtension API](https://webextension-api.thunderbird.net/en/latest/messages.html)
