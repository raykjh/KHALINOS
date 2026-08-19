# KHALINOS current checkpoint

This is the Git-side handoff for the active KHALINOS project. Google Drive remains the long-term human-readable memory canon; Git is the authority for code and file history.

## Active baseline

- Repository: `C:\memory R\KHALINOS`
- Branch: `agent/toolpack-restoration`
- Active deployed code: `c22f755`.
- User-owned `smoke-input/` is intentionally untracked and must not be staged.
- User-authored `docs/test-projects/` inputs are intentionally untracked and must not be staged with ToolPack code.
- Regression baseline: 115 passed; five third-party ADK/FastAPI deprecation warnings.

## Product boundary

KHALINOS is a specialized autonomous builder for bounded browser micro-products and bounded Godot prototypes. The Godot routes are separate: screen topology, visual prototype, and a data-driven 2D top-down gameplay vertical slice. The user supplies material and a goal, answers only material SixSense questions, reviews one Outcome Preview, and authorizes an immutable brief. Project Owner, visual selection when required, trusted compiler, deterministic Runtime Check, Independent Verifier, and bounded Technical Repair then run in Google Cloud without step-by-step coding-assistant intervention.

It does not promise universal project completion. The previous general-purpose prototype is historical context, not the active project identity or scope.

## Verification baseline

- One active acceptance criterion maps to one browser journey.
- Every journey must include runtime assertion evidence for its criterion.
- Supported evidence includes bounded waits, input actions, text/count/attribute/class/state assertions, and deterministic random seeds.
- Criterion-bound text assertions require a CSS selector; unscoped page-wide text matches are rejected.
- Source inspection alone cannot pass a criterion that requires execution evidence.
- Project Owner criteria must exactly match the approved brief and cannot expand scope with verification artifacts or implementation conveniences.
- Ordered Verifier findings are host-bound to the immutable criteria.

## Browser visual production path

- Browser new-product builds create three distinct visual concepts.
- Nano Banana `gemini-3.1-flash-lite-image` produces one bounded 16:9 PNG for each concept.
- A raw multimodal Visual Asset Gate rejects readable text, interface elements, logos, and watermarks before the Maker receives even the asset metadata.
- The trusted host owns the bytes and attaches exactly one validated `assets/visual-foundation.png`; model structured output remains text-only.
- Network-isolated Chromium requires the asset to load visibly and produces screenshots. Only deterministically eligible candidates reach the independent Visual Verifier.
- At least two eligible candidates are required. The selected receipt binds candidate, artifact, screenshot, and asset digests.
- Transient image API 429/5xx errors receive at most two backoff retries; other failures stop.

Qualification run `708ec62505e544ca85bbfa898343704b` passed with 16 model calls. V1 and V2 were eligible, V2 was selected, and the final Q2 receipt preserved both Q1 and Q2 selector-bound runtime evidence. Browser ToolPack manifest: `162bd5734bdc4dab9810ce1e127b9110ec0400d30b36c7d83ea5d381009f2f8a`.

## Godot gameplay production path

- `godot.gameplay` accepts only bounded offline 2D top-down action or survival vertical slices.
- Gemini authors a strict data plan for heroes, enemy archetypes, automatic abilities, shared party stats, session length, and deterministic level-choice cadence; it never writes GDScript.
- The trusted compiler owns `project.godot`, the scene, gameplay script, probe, manifest, README, and one gated Nano Banana environmental PNG.
- PASS requires actual movement, enemy spawning, automatic ability execution, shared health initialization, deterministic level choice, approved runtime digest, asset import, and real rendered frames.
- 3D, multiplayer, networking, arbitrary plugins/scripts, existing-project repair, platform distribution, and unrestricted full-game claims remain excluded.

Cloud qualification execution `khalinos-godot-toolpack-staging-b6gww` passed the gameplay smoke after automatic route and intake-role changes. The approved ToolPack manifest SHA-256 is `c3117d61e6045580218fe7af9a8025448409c70e5da5093ae98c3466100c9c44`.

## Deployment target

- Google Cloud project: `khalinos-agent-20260818`
- Region: `asia-northeast3`
- Cloud Run Job: `khalinos-worker`
- Service: `khalinos`
- Cloud Run Job: `khalinos-worker`
- Code commit deployed: `c22f755`.
- Image: `asia-northeast3-docker.pkg.dev/khalinos-agent-20260818/khalinos/runtime:auto-route-c22f755`.
- Digest: `sha256:493aa3fbc96f473950838b7c829a1037724e25128de2f49937fba9b5523455a2`.
- Cloud Build: `5775c2c8-9a88-4c86-8a90-ff51d8c6b154`.
- Service revision: `khalinos-00025-ksn`, serving 100 percent of traffic.
- Worker generation: `23`.
- Safety: zero retries, 1800-second task timeout.

The qualified code is deployed to the service and Worker with the same image digest. The public `/health` endpoint returned `ok: true` after deployment.

## Next decision

Run the prepared Trinity Survivors input through the user UI. Confirm the Route Advisor recommends `godot.gameplay`, review the bounded SixSense preview, and only then authorize the first paid end-to-end gameplay run. Do not reinterpret the gameplay vertical slice as a full production game.

For a new project, follow this order: materials, goal, approved ToolPack Route recommendation and user confirmation, only necessary SixSense questions, Outcome Preview, explicit authorization, then autonomous Cloud execution. Route semantics may be model-assisted, but candidate IDs, compatibility, manifest digests, and authorization remain host-controlled. Existing-project repair continues from its verified source type. Do not implement the new product or spend on a new run before the outcome is approved.
