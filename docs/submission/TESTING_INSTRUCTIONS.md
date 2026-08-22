# Judge testing instructions

## Public path

1. Open `https://khalinos-lnvkyx4gca-du.a.run.app`.
2. Confirm that the landing page and **Load Judge Demo inputs** work without signing in.
3. The public demo is an inspection path and does not start paid Cloud execution.

## Authenticated live path

1. Select **Sign in with Google** and use any ordinary Google account accepted by the published OAuth consent configuration.
2. Choose **New project**, continue without files, and enter a bounded Browser or Godot goal.
3. Review the selected route and SixSense preview. No execution occurs before **Authorize and execute**.
4. After authorization, observe the Cloud project, region, Job execution ID, selected profile, composed Capability Packs, active agent, Gemini call count, verifier state, horse handoffs, and M01–M06 milestone cargo.
5. On PASS, use **Download verified source**. Browser results also expose **Play verified result**.

The service is free to access during judging. Private projects are owner-bound; one signed-in user cannot list or download another user's result.

## Local and Cloud reproduction

Use the exact commands in the repository `README.md`. The Godot-capable image must be built with `cloudbuild.godot.yaml` and `Dockerfile.godot`; a plain `docker build` from `Dockerfile` does not contain the approved Godot runtime. The verified Worker shape is 8 GiB memory, 2 CPU, a 1,800-second timeout, and zero automatic retries.

## Evidence index

- `docs/architecture/khalinos-architecture.png`
- `docs/evidence/capability-pack-composition/combat-feedback-cloud-qualification-20260821.json`
- `docs/evidence/capability-pack-composition/live-execution-telemetry-cloud-qualification-20260822.json`
- `docs/evidence/trinity-survivors/`

The repository intentionally preserves failed qualification records where they explain a corrected structural cause. Those failures are not represented as successful runs.
