# KHALINOS 3:50 recording runbook

Use this runbook with [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). The script is the
second-by-second source of truth; this file prepares the recording environment.

## Recording contract

- Record one continuous take at 1× speed. Do not cut, trim, stitch, or hide a failure.
- Start from the authenticated **Materials** step. Move through Goal, Route/SixSense, and Preview before the recorded authorization click.
- Start the real side-scroll Cloud execution only after the recorded authorization click. Do not retry the authorization if the first dispatch is accepted.
- The live execution does not need to reach PASS during the video. Always show its truthful current state.
- Label earlier artifacts **PREVIOUSLY VERIFIED CLOUD OUTPUT** during the take.
- Use the approved English narration track; do not add subtitles or narration after recording.
- Do not reveal account email, billing details, OAuth client IDs, access tokens, environment variables, or private Firestore owner identifiers.
- Stop at 3:50 and remain below the four-minute limit.

## Approved narration

- Voice: Microsoft `en-US-BrianMultilingualNeural` (`Brian Multilingual`).
- Pitch: default (`+0Hz`).
- Speed: 1.0× (`+0%`).
- Exact recording track: `docs/submission/demo-audio/KHALINOS-demo-narration-3m50s.wav`.
- MP3 convenience copy: `docs/submission/demo-audio/KHALINOS-demo-narration-3m50s.mp3`.
- Segment timing and measured headroom: `docs/submission/demo-audio/manifest.json`.

Prefer the WAV in OBS because it is exactly 230.000 seconds. Start recording,
then start the track inside the opening three-second silent window. The narration
track intentionally remains silent during UI transitions and the two gameplay-audio
windows so genuine application sound remains audible.

## Chrome tab order

1. Authenticated KHALINOS Materials step — active at recording start, with **New project** selected and the prepared Goal values retained for the next step.
2. Full-window architecture image — `C:\memory R\KHALINOS\docs\architecture\khalinos-architecture.png`.
3. Cloud Run Jobs list filtered to `khalinos-worker`, project `khalinos-agent-20260818`, region `asia-northeast3`; hide the `Creator` column and do not open execution details.
4. Prepared Browser result — `C:\memory R\KHALINOS-DEMO-READY-20260824\browser\index.html`.

Use Chrome for every web surface. Hide the bookmarks bar, download shelf,
unrelated tabs, notifications, password-manager prompts, and account menus.

## Prepared local applications

- Side-scroll project: `C:\memory R\KHALINOS-DEMO-READY-20260824\side-scroll`.
- Trinity project: `C:\memory R\KHALINOS-DEMO-READY-20260824\trinity`.
- Browser project: `C:\memory R\KHALINOS-DEMO-READY-20260824\browser`.
- Approved Godot executable: `E:\memory R data\archive_20260818_first_priority\C-tmp\khalinos-engine-bakeoff\godot\Godot_v4.7.1-stable_win64.exe`.

Do not use `KHALINOS-DEMO-READY-20260822`: that earlier rehearsal copy does not
contain the licensed-art atlas. Before recording, confirm the side-scroll atlas
SHA-256 is `3d7f794dd1e3385e36e93ee8d725ec73a9d2e549cf20e17c550dfaf3b1ebc94e`
and the Trinity atlas SHA-256 is
`310350dfa301a8349092e6723f123b7b7f8807e4a26d74ed7ac3539769564b56`.

Open both Godot projects before recording. Switch to side-scroll at 2:29 but
start the scene at 2:33; restart it once at 2:46 for the gameplay-audio window.
Keep Trinity on its built-in **START** screen for 2:53. Do not leave either
gameplay scene running before the take. Confirm window switching does not expose
unrelated folders.

## Live labels and screen order

- 0:00–0:12: authenticated Materials step and new-project choice.
- 0:12–0:25: prepared Goal and acceptance boundary.
- 0:25–0:38: truthful exact-route selection.
- 0:38–0:55: one visible SixSense visual-direction choice and its resolution.
- 0:55–0:58: Outcome Preview.
- 0:58–1:31: authorization and live agent state.
- 1:31–1:50: architecture image.
- 1:50–2:14: Google Cloud execution proof.
- 2:14–2:31: truthful KHALINOS live state and verifier evidence.
- 2:31–2:35: side-scroll transition and ready state with **PREVIOUSLY VERIFIED CLOUD OUTPUT** visible.
- 2:35–2:48: one complete side-scroll run and its genuine completion state.
- 2:48–2:53: restart the same side-scroll scene for genuine gameplay audio.
- 2:53–3:12: Trinity result with the same label visible.
- 3:12–3:25: Browser result with the same label visible.
- 3:25–3:50: return to truthful KHALINOS state and close.

The label must be present during recording, either in a prepared capture overlay
or in the visible prepared window. Do not add it in post-production.

## Audio and display

- Capture at 1920×1080 or higher and at least 30 fps.
- Keep Chrome at 100% zoom and use consistent Windows scaling.
- Capture the narration track and system audio without clipping.
- Leave game sound audible only where the narration track is silent.
- Disable system notifications and close unrelated applications.
- Keep a timer visible to the presenter but outside the captured frame.

## Final rehearsal checks

- Public KHALINOS URL and `/health` return HTTP 200.
- Google sign-in remains active and the Project Library loads.
- Materials starts authenticated with **New project** selected; the next Goal screen retains the prepared side-scroll project name and bounded requirements.
- The Route/SixSense request reaches a compatible side-scroll Outcome Preview before authorization.
- Cloud Console is filtered to the correct Worker Job and region, the `Creator` column is hidden, and no execution detail page is open.
- The architecture image is readable at full-window scale.
- The Browser board loads locally in Chrome and its controls respond.
- Side-scroll starts from 0 m and completes in roughly four seconds; Trinity waits at its START gate.
- Side-scroll visibly uses the licensed warrior, archer, priest, enemy, prop, and destination sprites; Trinity visibly uses its licensed hero sprites after START.
- The approved 3:50 WAV plays once and does not loop.
- The three **PREVIOUSLY VERIFIED CLOUD OUTPUT** labels are visible at the intended times.
- For a no-cost timing rehearsal, stop before authorization. For an explicitly approved final rehearsal or submission take, authorize exactly once and keep monitoring the truthful live state after recording.

## Evidence anchors

- Final release tag: `v0.6.0-hackathon-final`.
- Latest image digest: `sha256:56a8f4429365c5170cf4c0c6149a497236b43a51144308154c633d1ed3fec24b`.
- Trinity PASS: `15100d664c8840c2b85a24d2068e270f`, 59/59 checks.
- Side-scroll PASS: `c9fa277674c940a685c48de576713239`, 30/30 checks.
- Browser PASS: `32b5306b2c984683b406012b4ffb79f6`, 12/12 checks.
- Machine-readable release record: `docs/evidence/capability-pack-composition/submission-release-cloud-qualification-20260823.json`.
- Browser qualification: `docs/evidence/browser-product/launch-triage-cloud-qualification-20260823.json`.
