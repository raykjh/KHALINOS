# KHALINOS 3:55 submission-video runbook

Use this runbook with [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). The script is the
second-by-second source of truth; this file prepares the recording environment.

## Recording contract

- Record short, clean clips and edit out loading screens and dead air, as recommended by the submission guidance.
- Keep the live proof truthful: authorization, early progress, later progress, PASS, and the fresh artifact must use one execution ID.
- Put **WAIT TIME REMOVED — SAME EXECUTION ID** over the only long progress jump.
- Start from the authenticated **Materials** step. Move through Goal, Route/SixSense, and Preview before the recorded authorization click.
- Start the real side-scroll Cloud execution only after the recorded authorization click. Do not retry the authorization if the first dispatch is accepted.
- The live execution does not need to reach PASS during the video. Always show its truthful current state.
- Label earlier artifacts **PREVIOUSLY VERIFIED CLOUD OUTPUT** during the take.
- Use the approved English narration track; do not add subtitles or narration after recording.
- Do not reveal account email, billing details, OAuth client IDs, access tokens, environment variables, or private Firestore owner identifiers.
- Finish the scored content by 3:50 and stop by 3:55.

## Approved narration

- Voice: Microsoft `en-US-BrianMultilingualNeural` (`Brian Multilingual`).
- Pitch: default (`+0Hz`).
- Speed: 1.0× (`+0%`).
- Exact recording track: `docs/submission/demo-audio/KHALINOS-demo-narration-4m.wav`.
- MP3 convenience copy: `docs/submission/demo-audio/KHALINOS-demo-narration-4m.mp3`.
- Segment timing and measured headroom: `docs/submission/demo-audio/manifest.json`.

Prefer the WAV in the editor. The generated track is 240 seconds long, but all
spoken content ends at 3:50. Trim the final silence at 3:55. Keep genuine game
sound under the gameplay clips without obscuring narration.

## Chrome tab order

1. Authenticated KHALINOS Materials step — active at recording start, with **New project** selected and the prepared Goal values retained for the next step.
2. Full-window architecture image — `C:\memory R\KHALINOS\docs\architecture\khalinos-architecture.png`.
3. Cloud Run Jobs list filtered to `khalinos-worker`, project `khalinos-agent-20260818`, region `asia-northeast3`; hide the `Creator` column and do not open execution details.
4. Prepared Browser result image — `C:\memory R\KHALINOS\docs\evidence\browser-product\launch-triage-final-qa-completed.png`.

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

Record Trinity from a fresh autoplay restart and record the final side-scroll
artifact from a fresh launch. Rebind each OBS Window Capture to the newly opened
Godot window and fit it to the canvas before capturing. Confirm window switching
does not expose unrelated folders.

## Live labels and screen order

- 0:00–0:12: Materials, Goal, SixSense, and Preview, three seconds each.
- 0:12–0:35: authorization and genuine early live state.
- 0:35–0:53: architecture image.
- 0:53–1:08: matching Google Cloud project, worker, and region.
- 1:08–1:28: return to the same live execution.
- 1:28–1:55: moving Trinity gameplay labelled **PREVIOUSLY VERIFIED CLOUD OUTPUT**.
- 1:55–2:18: full-width bright Browser result with the same label.
- 2:18–2:38: same KHALINOS execution before the progress cut.
- 2:38: disclosed **WAIT TIME REMOVED — SAME EXECUTION ID** cut.
- 2:38–3:20: later state and PASS from the same execution, plus matching Cloud success.
- 3:20–3:50: fresh side-scroll artifact from that PASSED execution.
- 3:50–3:55: genuine completion hold.

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
- The Browser evidence image fills the 1920×1080 OBS canvas and has no black right-side area.
- Trinity autoplay is moving before its clip begins; the party remains centered over scrolling top-down terrain.
- Side-scroll starts from 0 m, visibly moves, and completes; its heroes and enemies touch the road line.
- Side-scroll has no castle destination graphic or repeated foreground prop icons; Trinity has no side-scroll ground band or decorative unit rings.
- The approved 3:50 WAV plays once and does not loop.
- The two **PREVIOUSLY VERIFIED CLOUD OUTPUT** labels are visible at the intended times.
- For a no-cost timing rehearsal, stop before authorization. For an explicitly approved final rehearsal or submission take, authorize exactly once and keep monitoring the truthful live state after recording.

## Evidence anchors

- Final release tag: `v0.6.0-hackathon-final`.
- Latest image digest: `sha256:56a8f4429365c5170cf4c0c6149a497236b43a51144308154c633d1ed3fec24b`.
- Trinity PASS: `15100d664c8840c2b85a24d2068e270f`, 59/59 checks.
- Side-scroll PASS: `c9fa277674c940a685c48de576713239`, 30/30 checks.
- Browser PASS: `32b5306b2c984683b406012b4ffb79f6`, 12/12 checks.
- Machine-readable release record: `docs/evidence/capability-pack-composition/submission-release-cloud-qualification-20260823.json`.
- Browser qualification: `docs/evidence/browser-product/launch-triage-cloud-qualification-20260823.json`.
