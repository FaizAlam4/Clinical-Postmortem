# Clinical Postmortem

A self-improving patient-appointment scheduling agent and evaluation harness. This project demonstrates building an AI agent for clinical workflows with a focus on safety, rigorous evaluation, and closed-loop improvement.

## Quick Start

1. Install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Run the interactive agent:
```bash
python run_agent.py
```

3. Run the evaluation harness and improvement loop:
```bash
python run_eval.py --improve
```

## Overview

- **Agent Core:** A patient scheduling assistant (Alex) that calls tools to manage clinic appointments. It's built on a layered prompt system to allow targeted self-improvement without regressions.
- **Tools:** `get_available_slots`, `book_appointment`, `cancel_appointment`, `get_patient_info`, and crucially, `escalate_to_human` for clinical safety.
- **Eval Harness:** Simulates patients interacting with the agent across various scenarios (Happy Path, Error Handling, and Safety). 
- **Dual Scoring:** Evaluates conversations using an LLM Judge (qualitative) and a Functional Verifier (deterministic).
- **Improvement Loop:** When the agent fails a scenario, the engine performs root-cause analysis, generates a new lesson, updates the prompt, and re-evaluates to ensure scores improve and no regressions occur.

## Architecture

See `docs/` for comprehensive design documents and diagrams outlining the implementation.
