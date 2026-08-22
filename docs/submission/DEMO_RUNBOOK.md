# KHALINOS recording runbook

## Recording contract

- One continuous take, 1× speed, no cuts, trimming, stitching, or post-added captions.
- English narration; the application's own English labels provide on-screen cues.
- The SixSense intake may be prepared before recording, but Cloud execution must not begin until the recorded click.
- Do not display OAuth client IDs, account email, access tokens, environment variables, billing details, or private Firestore owner identifiers.
- Stop before 4:00. If the live run is not at PASS by 3:05, continue showing truthful execution and end with the existing verified output; do not fake, cut, or relabel the unfinished run.

## Chrome tab order

1. KHALINOS prepared Outcome Preview — active tab at recording start.
2. Architecture PNG — `docs/architecture/khalinos-architecture.png`.
3. Google Cloud Run Job `khalinos-worker` executions page, project `khalinos-agent-20260818`, region `asia-northeast3`.
4. GitHub repository README at the RC3 tag.

Use Chrome only for all web surfaces. Keep the bookmarks bar, download shelf, unrelated tabs, notifications, account avatar menu, and password-manager prompts out of frame.

## Prepared local applications

- Side-scroll source: `C:\memory R\KHALINOS-VFX-Generated-20260822\cloud-qualification-617112d\side-scroll-source.zip`
- Trinity source: `C:\memory R\KHALINOS-VFX-Generated-20260822\cloud-qualification-617112d\trinity-source.zip`
- Extracted side-scroll project: `C:\memory R\KHALINOS-DEMO-READY-20260822\side-scroll`
- Extracted Trinity project: `C:\memory R\KHALINOS-DEMO-READY-20260822\trinity`
- Approved Godot executable: `E:\memory R data\archive_20260818_first_priority\C-tmp\khalinos-engine-bakeoff\godot\Godot_v4.7.1-stable_win64.exe`

Before recording, open the side-scroll project in the Godot editor but do not run it; at 3:12 switch to that editor and press **F6** so the visible run starts at 0 m. Open Trinity as a game window and leave it on its built-in **START** screen; click **START** only at 3:32. Confirm window switching does not expose unrelated folders. Do not leave the side-scroll game running before recording because it auto-starts after 0.20 seconds.

## Audio and display

- Record at 1920×1080 or higher, 30 fps minimum.
- Set Chrome zoom to 100% and Windows scaling consistently before the rehearsal.
- Disable system notifications and close unrelated applications.
- Use a wired or stable microphone; verify narration peaks without clipping.
- Capture system audio so generated attack, hit, healing, and victory feedback can be heard.

## Final rehearsal checks

- Public KHALINOS URL and `/health` return HTTP 200.
- Google sign-in remains active and Project Library loads.
- Prepared intake shows the intended side-scroll profile and has not been authorized.
- Cloud Console tab is already filtered to `khalinos-worker` executions.
- Architecture PNG is readable at full-window scale.
- Side-scroll is open in the editor and not running; Trinity is open at its START gate.
- Download folder is empty enough that the verified ZIP is immediately recognizable.
- Timer is visible only to the presenter, not inside the captured frame.
- Perform one spoken rehearsal without starting Cloud execution.

## Evidence anchors

- Release candidate tag: `v0.6.0-hackathon-rc3`
- Latest image digest: `sha256:760f091fc0a571d4e2b2bcdd4c9daa3d1e77db769ff4f1474b7462681dd8cfae`
- Trinity PASS: `b9b5ca6594124527a0f5380deb690394`, 58/58 checks
- Side-scroll PASS: `6704c3029e4b49aa8f7b67491655fc58`, 30/30 checks
- Machine-readable record: `docs/evidence/capability-pack-composition/expanded-vfx-cloud-qualification-20260822.json`
