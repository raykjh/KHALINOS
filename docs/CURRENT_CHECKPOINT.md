# KHALINOS current checkpoint

This is the Git-side handoff for the active KHALINOS project. Google Drive remains the long-term human-readable memory canon; Git is the authority for code and file history.

## Active baseline

- Repository: `C:\memory R\KHALINOS`
- Branch: `main`
- Commit before this documentation update: `eb51a745b5efeab0a96cd1dd93dcfb029e5239eb`
- Remote state before this documentation update: `origin/main` matched the local commit.
- User-owned `smoke-input/` is intentionally untracked and must not be staged.
- Regression baseline: 52 passed; five third-party ADK/FastAPI deprecation warnings.

## Product boundary

KHALINOS is a specialized autonomous builder and repairer for bounded browser micro-products. The user supplies material and a goal, answers only material SixSense questions, reviews one Outcome Preview, and authorizes an immutable brief. Project Owner, visual selection when required, Maker, deterministic Runtime Check, Independent Verifier, and bounded Technical Repair then run in Google Cloud without step-by-step coding-assistant intervention.

It does not promise universal project completion. The previous general-purpose prototype is historical context, not the active project identity or scope.

## Verification baseline

- One active acceptance criterion maps to one browser journey.
- Every journey must include runtime assertion evidence for its criterion.
- Supported evidence includes bounded waits, input actions, text/count/attribute/class/state assertions, and deterministic random seeds.
- Source inspection alone cannot pass a criterion that requires execution evidence.
- Project Owner criteria must exactly match the approved brief and cannot expand scope with verification artifacts or implementation conveniences.
- Ordered Verifier findings are host-bound to the immutable criteria.

## Deployed worker

- Google Cloud project: `khalinos-agent-20260818`
- Region: `asia-northeast3`
- Cloud Run Job: `khalinos-worker`
- Image: `asia-northeast3-docker.pkg.dev/khalinos-agent-20260818/khalinos/runtime:verifier-binding-eb51a74`
- Digest: `sha256:73d933d307f4313fe44ef88c0902357e0fc52cf651dedae65f67a9627050a0c9`
- Cloud Build: `bbcd74eb-51b3-42d1-9060-be2790ac90c3`
- Safety: zero retries, 1800-second task timeout.

The final host-binding revision is deployed. No paid end-to-end holdout has run after that deployment, so final Cloud completion remains unverified.

## Visual asset experiment

The isolated paired experiment is stored at `E:\memory R data\KHALINOS-visual-ab\experiment-02`. CSS-only scored 8.8 and image-assisted scored 9.2. The benefit was real but visually small in the current layout, so no Production Visual Asset Agent is connected. Re-evaluate only after a future approved outcome has a dedicated visual asset slot.

## Next decision

Choose a new evaluation project before running KHALINOS again. Minesweeper is excluded because a coding assistant can normally produce it in one pass. Prefer a serverless task that is materially harder than a one-shot build and exposes both objective runtime evidence and visible quality differences.

After selection, follow this order: materials, goal, only necessary SixSense questions, Outcome Preview, explicit authorization, then autonomous Cloud execution. Do not implement the new product or spend on a new run before the outcome is approved.
