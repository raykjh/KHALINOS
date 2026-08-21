# Trinity Survivors evidence index

This directory keeps the current immutable KHALINOS Cloud proof, earlier historical proof, and local-only refinements explicitly separated.

## Canonical Cloud run

`cloud-run-8be19784/` is a curated, byte-for-byte copy of selected evidence stored under:

`gs://khalinos-agent-20260818-runs/runs/8be1978415eb40b99d4dddbe8d143c33/`

The run used `godot.gameplay` 1.6.2 and completed with an unbroken four-receipt chain:

- `visual-selection-receipt.json` — independent multimodal selection receipt
- `quests/Q1-receipt.json` through `Q3-receipt.json` — receipt-gated Quest completion
- `deterministic-evidence.json` — 44 passed runtime checks, zero issues
- `godot-gameplay-probe.json` — raw mechanics receipt from Godot
- `sprite-gate.json` — independent sprite-atlas gate
- `artifact-manifest.json` — final artifact, bundle, asset, ToolPack, and receipt digests
- `godot-gameplay-render.png` — one real 1280×720 display-backed Godot render; it is not used to overclaim temporal coverage
- `brief.json`, `gameplay-project-plan.json`, and `quest-plan.json` — immutable authority and execution plans
- `run-summary.json` — deployment, execution, receipt, and SHA summary
- `failure-recovery.json` — safe failures and generalized corrections made before the final PASS

The final manifest binds artifact SHA-256 `c4e8cce7780bed950e12f25b3df9419ceb8546b392cfc60a998cd31dc28ee05b` and bundle SHA-256 `4549ce7f7f08d689c3353ee6dac272caf75c711d4fed31dc7d66dddb79c27586`. The downloaded source ZIP SHA-256 is `f91288e2f0eb84afc69f2d6bb6dcecc87eeb6737c2ecc063a79b50bd8b52ed32`.

## Historical Cloud proof

`cloud-run-5f0964c8/` remains the earlier `godot.gameplay` 1.4.0 PASS. It is retained rather than rewritten, but it is no longer the current submission proof.

## Post-run Godot v5 validation

`post-run-godot-v5/` records deterministic validation after two general ToolPack improvements. It proves the first level-one enemy is beatable, all three heroes expose role-distinct basic attacks, skills obey cooldowns and have separate feedback, healing is visible, and nearby enemy attacks use a bounded cadence and hostile impact effect.

This is intentionally not presented as part of the earlier immutable Cloud run. The current `cloud-run-8be19784/` proof now covers those shared gameplay revisions in Cloud; this directory remains useful as the local development checkpoint that preceded it.
