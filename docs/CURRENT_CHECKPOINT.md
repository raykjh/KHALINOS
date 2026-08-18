# KHALINOS current checkpoint

This is the Git-side handoff for the active KHALINOS project. Google Drive remains the long-term human-readable memory canon; Git is the authority for code and file history.

## Active baseline

- Repository: `C:\memory R\KHALINOS`
- Branch: `agent/toolpack-restoration`
- Baseline before the Browser visual integration: `9fd4211`.
- User-owned `smoke-input/` is intentionally untracked and must not be staged.
- Regression baseline: 102 passed; five third-party ADK/FastAPI deprecation warnings.

## Product boundary

KHALINOS is a specialized autonomous builder and repairer for bounded browser micro-products. The user supplies material and a goal, answers only material SixSense questions, reviews one Outcome Preview, and authorizes an immutable brief. Project Owner, visual selection when required, Maker, deterministic Runtime Check, Independent Verifier, and bounded Technical Repair then run in Google Cloud without step-by-step coding-assistant intervention.

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

## Deployment target

- Google Cloud project: `khalinos-agent-20260818`
- Region: `asia-northeast3`
- Cloud Run Job: `khalinos-worker`
- Service: `khalinos`
- Cloud Run Job: `khalinos-worker`
- Code commit deployed: `aff16fbdeeb6104b0b064ca38e04f609a099ecfd`.
- Image: `asia-northeast3-docker.pkg.dev/khalinos-agent-20260818/khalinos/runtime:visual-assets-aff16fb`.
- Digest: `sha256:30cd4669fa6430fa7414f1145abf48dbea5889a126f1d4ca7a4035440ed7768e`.
- Cloud Build: `c04f577b-2a34-4586-8f58-2e3c9a29544b`.
- Service revision: `khalinos-00022-2wj`, serving 100 percent of traffic.
- Worker generation: `19`.
- Safety: zero retries, 1800-second task timeout.

The qualified code is deployed to the service and Worker with the same image digest. The public `/health` endpoint returned `ok: true` after deployment.

## Next decision

After deployment, run a bounded Browser new-product smoke from the user UI and confirm that the selected PNG appears in **Play verified result**. Then choose a new evaluation project that is materially harder than a one-shot Minesweeper build and exposes both objective runtime evidence and visible quality differences.

For a new project, follow this order: materials, goal, approved ToolPack Route recommendation and user confirmation, only necessary SixSense questions, Outcome Preview, explicit authorization, then autonomous Cloud execution. Route semantics may be model-assisted, but candidate IDs, compatibility, manifest digests, and authorization remain host-controlled. Existing-project repair continues from its verified source type. Do not implement the new product or spend on a new run before the outcome is approved.
