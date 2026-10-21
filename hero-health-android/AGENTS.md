# 健康星 Android

User authorized Android development on 2026-10-19 and selected local features first, AI later. Preserve the sibling prototype; its template/runtime rules do not apply to this new production project.

- Brand: 健康星 (renamed from Hero健康 on 2026-10-19). Preserve package cn.herohealth.app, signing identity, vault aliases and backup format for in-place upgrades. On 2026-10-19 user changed UI palette to reference screenshots: purple #7548F5 / lavender #EEE8FF / background #F6F7FB / near-black #111321, with pink, emerald and orange accents. User subsequently supplied C:/Users/herol/Desktop/健康星.png as the new logo for launcher/home/settings, and explicitly removed all mascot images. Use supplied in-app artwork unchanged. Launcher uses an opaque purple adaptive background and enlarged foreground, with no white padding.
- Real app starts empty; never seed private health records, mock reports, artificial AI output or diagnoses. User now authorized real report and comprehensive AI analysis using phone-saved credentials. Use a native OpenAI-compatible Chat Completions adapter with MiniMax M3 reasoning separation, business-code validation and text-only connectivity testing; never provision or access a desktop key for phone use. Default report workflow is one-click processing of ALL files grouped by each associated card with its history, automatically chunked (up to 8 pages/3 documents). Concentrated review commits complete reports only; interrupted chunks remain resumable and partial results cannot enter trends. Report images/PDF raster pages may be sent only after explicit in-app action showing destination and scope. AI values are pending until user review. Preserve raw and reviewed versions, prevent duplicates, show failures honestly. Never return saved credentials to WebView or health backups. Address changes without a new key must clear the old key.
- Home metrics derive from active cards, deduplicated, with saved visibility choices. Basic information card is pinned, with fixed height/weight/blood pressure definitions.
- Cards show under 100 characters of recent status/trend/attention. Red up, green down reflect numerical direction only; pressure components compared independently.
- Reports require a card association before import. Actual files remain encrypted in app-private storage. Do not request broad external-storage permissions.
- Full password-encrypted backup works across devices, excludes keys; validate before restore, require current archive safety export, commit atomically. A canceled export must cancel restore.
- Native Android host uses trusted bundled content only. No remote WebView navigation. INTERNET permission is for native HTTPS AI calls only; no redirects, raw provider errors or automatic retries. No secrets or medical contents in logs.
- Build tools and signing secrets stay local and ignored. Do not overwrite signing keys; keep upgrade identity stable.
- Windows builds stage compiler inputs/tools in an owned ASCII directory under the user's temp folder to avoid Unicode path bugs. Verify absolute paths and the ownership marker before replacing staging copies; do not alter original source or signing identity.
- Run meaningful domain, backup and native storage tests plus Android build/lint. The user explicitly ended prototype verification; do not resume browser prototype QA.

## Engineering delivery

Use the repository-root `.agents/skills/` and `engineering/PROTOCOL.md` for feature PRs. `engineering/check-local.ps1` runs debug verification without release keys; do not substitute the existing signed release build script. Daily PRs keep versionName `0.3.0`, versionCode `4` and signing identity unchanged until an explicit release request.

## Code Review Rules

- Trace native bridge calls and asynchronous AI/restore callbacks through cancellation, lifecycle destruction and partial failure. A partial AI batch or canceled safety export must not commit reviewed data or restore state.
- Credentials and raw health records must stay out of WebView-returned configuration, logs and plaintext fallback storage. Check endpoint changes clear the old credential and preserve explicit transmission consent.
- Check backup schema and vault aliases for upgrade compatibility. Examine both Java and TypeScript changes; successful JVM tests alone do not cover bridge/domain behavior.
