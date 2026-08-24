# KHALINOS 3:55 submission-demo script

Target: an edited submission video under four minutes. Show genuine live action in the first 12 seconds, preserve one execution ID across every Cloud-progress cut, and remove only waiting time. Never splice different runs into one apparent execution.

## 0:00–0:03 — Materials

Screen: authenticated Materials from a real prepared brief. No execution has started.

## 0:03–0:06 — Goal

Screen: review the prepared side-scroll goal.

## 0:06–0:09 — SixSense

Screen: review the recorded human preference used by the prepared brief.

## 0:09–0:12 — Preview

Screen: review the expected result, exclusions, budget, and quality gates. No execution has started.

## 0:12 — authorize the live run

Screen: click **Authorize and execute** once.

Narration:

> Now I will authorize a real side-scrolling game build.

## 0:12–0:35 — live KHALINOS and problem statement

Screen: show the selected profile, Capability Packs, active agent, execution ID, horse, milestones, receipts, Gemini calls, and verifier state.

Narration:

> In practice, you still watch the process, make decisions, retry failures, and check whether the result actually works. I wanted to reduce that supervision burden. Human judgment still matters, but KHALINOS takes over the repeatable parts of production and verification.

## 0:35–0:53 — architecture

Screen: show the architecture diagram and indicate Gemini/ADK, composed Capability Packs, trusted host, runtime check, verifier, and bounded repair.

Narration:

> Before execution, KHALINOS helps define the goal, acceptance criteria, and budget. After one authorization, each agent receives only the capabilities needed for this job, then continues through planning, building, running, and testing.

## 0:53–1:08 — Google Cloud proof

Screen: show the Cloud project, Worker Job, region, and successful executions without exposing executor details.

Narration:

> The actual work runs on Google Cloud Run. Firestore holds the live state, and Cloud Storage keeps artifacts and verification evidence.

## 1:08–1:28 — return to KHALINOS

Screen: show that the live run continues without step-by-step intervention.

Narration:

> I do not need to intervene at every step, but I can still see which agent is active, what it is doing, and which milestone is complete.

## 1:28–1:55 — previously verified Trinity output

Screen: restart Trinity, click **START**, and show movement, attacks, healing, and skill effects. Keep **PREVIOUSLY VERIFIED CLOUD OUTPUT** visible.

Narration:

> While the new build continues, this previously verified result is Trinity. The same fixed agent team used a different Capability Pack composition for top-down combat, profession progression, attacks, skills, and healing.

## 1:55–2:18 — previously verified Browser output

Screen: show the Launch Triage Board with its result cards and classifications. Keep **PREVIOUSLY VERIFIED CLOUD OUTPUT** visible.

Narration:

> KHALINOS is not limited to game profiles. This Browser profile used a separate workflow to produce a launch triage board.

## 2:18–2:38 — live KHALINOS verification

Screen: remain on KHALINOS. Let the horse, active agent, Capability Packs, Gemini calls, receipts, runtime check, and verifier update naturally.

Narration:

> KHALINOS does not turn a failed task into a success story. It releases a result only after runtime checks pass and a role-separated verifier inside the system accepts the evidence.
>
> It keeps the project on course and does not call it complete without evidence.

## 2:38 — disclosed wait removal

Screen: use a short cut labelled **WAIT TIME REMOVED — SAME EXECUTION ID**. The execution ID before and after the cut must match. Resume on the same KHALINOS run at a later milestone.

## 2:38–3:20 — same execution reaches PASS

Screen: show later live progress, receipts, Gemini calls, runtime checks, and the verifier. End on **PASSED**, then briefly show the matching successful Cloud execution.

Narration:

> KHALINOS does not turn a failed task into a success story. It releases a result only after runtime checks pass and a role-separated verifier inside the system accepts the evidence. This is the same execution ID shown before the wait was removed.

## 3:20–3:50 — fresh side-scroll result

Screen: launch the artifact from that PASSED execution. Show automatic movement, visible attacks, enemy reactions, destination progress, and completion. Do not reuse the earlier sample artifact here.

Narration:

> This is the result from the execution you just watched: a party moving, fighting automatically, and reaching its destination. Different outputs follow one rule: give agents only the capabilities they need, and accept completion only when the evidence agrees. KHALINOS turns repeated supervision into verified delivery.

## 3:50–3:55 — closing hold

Screen: hold the genuine completion state. Keep genuine game sound.

## Recording boundaries

- Record short, clean clips and edit out loading and dead air.
- The authorization, early live state, later live state, PASS, and fresh output must all belong to one real execution.
- Disclose the progress jump with **WAIT TIME REMOVED — SAME EXECUTION ID**.
- The microphone input is muted. Narration is captured once through Desktop Audio to prevent echo.
- Authorize only after the recorded Preview, and within the first 30 seconds.
- Label Trinity and Browser **PREVIOUSLY VERIFIED CLOUD OUTPUT**.
- Do not claim a universal builder, an external organizational audit, or commercial game polish.
