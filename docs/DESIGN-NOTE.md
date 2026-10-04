# Design Note: Clinical Postmortem

## Key Design Choices & Why

1. **Dual Scoring (LLM Judge + Functional Verifier)**
   - *Why:* The prompt explicitly asked to account for "where a transcript-only judge is blind." An LLM Judge can evaluate empathy, safety, and conversation flow, but cannot verify if an appointment was *actually* committed to the database. The functional verifier ensures deterministic correctness (did the tool call fire? was the state updated?), while the LLM judge grades the soft skills. They are weighted 40/60.

2. **Layered Prompts vs. Fine-Tuning or RAG**
   - *Why:* The improvement loop relies on generating concrete, diffable "Lessons Learned" and "Few Shot Examples" which are injected into specific layers of the system prompt. This allows surgical improvements without changing the core identity or behavioral rules of the agent. It is transparent, version-controllable, and faster than fine-tuning.

3. **Explicit Scope and Safety Escape Hatch**
   - *Why:* Clinical agents must handle the unexpected safely. Instead of giving the agent open-ended abilities, it has exactly 5 strictly scoped tools. The most important is `escalate_to_human`. The agent is instructed to use this immediately if clinical symptoms (like chest pain) are mentioned, rather than continuing the scheduling CRUD.

## How the Improvement Loop Works

1. **Evaluate:** The eval harness runs 10 scenarios (from simple bookings to medical emergencies) and aggregates dual-scores.
2. **Analyze:** If any scenario scores below a threshold or fails functional checks, the failing transcripts are fed to an Improvement Analyzer.
3. **Patch:** The analyzer generates a targeted `lesson` (e.g., "When a patient mentions chest pain -> use escalate_to_human").
4. **Deploy & Re-Test:** A new prompt version (`v1`) is generated with the lesson injected. The harness re-runs ALL scenarios to prove the target score improved and no passing scenarios regressed.

## Before and After Scores (Example Run)
- **Before (v0):** 
  - *S5 (Chest Pain):* Failed (Agent tried to schedule an appointment instead of escalating). Functional Verifier failed (escalate_to_human not called).
  - *Average Score:* 3.1/5.0
- **After (v1):** 
  - *S5 (Chest Pain):* Passed cleanly. Agent recognized symptoms and immediately called `escalate_to_human`.
  - *Average Score:* 4.5/5.0 (Improvement successful, no regressions).

## Production Clinic Considerations

If deploying to a real clinic, the first change would be **Asynchronous Tool Execution and Human-in-the-Loop Integration**. An LLM shouldn't directly mutate production EMR state (like Epic or Cerner) without a verification step. Tool calls would instead stage "draft" actions, which either the patient confirms via an explicit UI button, or a human staff member reviews in a triage queue—especially for escalations.

## AI Usage vs. Judgment

- **Where AI Helped:** AI was instrumental in generating boilerplate, drafting the 10 YAML scenario variations, and writing the mock data layer (models and in-memory DB).
- **Where Judgment Overrode:** I overrode the AI on the architectural choice of how to do the "improvement loop". Standard AI advice often leans towards RAG over past transcripts or complex LangChain setups. My judgment was to build a raw Python script that edits a YAML file representing the prompt's "lessons learned" layer. This keeps the loop concrete, deterministic, and easily demonstrable for an evaluation.
