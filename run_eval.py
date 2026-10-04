import os
import yaml
import time
import json
import argparse
from pathlib import Path
from rich.console import Console

from src.clinic.database import ClinicDatabase
from src.agent.scheduler import SchedulingAgent
from src.llm_client import LLMClient
from src.eval.simulated_patient import SimulatedPatient
from src.eval.judge import LLMJudge
from src.eval.verifier import FunctionalVerifier
from src.improve.patcher import ImprovementEngine
from src.agent.prompt_builder import update_metadata

console = Console()

def run_scenario(scenario: dict, prompt_version: str, llm_client: LLMClient):
    db = ClinicDatabase()
    agent = SchedulingAgent(db, patient_id=scenario['patient_persona']['patient_id'], prompt_version=prompt_version, llm_client=llm_client)
    patient = SimulatedPatient(scenario, llm_client)
    
    # Conversation Loop
    turns = 0
    msg = patient.get_opener()
    
    while turns < 10:
        agent_reply = agent.chat(msg)
        if "escalated" in agent_reply.lower() or "human" in agent_reply.lower() or "bye" in agent_reply.lower():
            break
        turns += 1
        time.sleep(4.5)  # Pace to ~13 Requests Per Minute to stay under 15 RPM limit
        msg = patient.respond(agent_reply, turns)
        time.sleep(4.5)  # Pace agent reply as well
        
    transcript = agent.get_transcript()
    return transcript, db

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--improve", action="store_true", help="Run improvement loop if failures occur")
    args = parser.parse_args()
    
    console.print("[bold blue]Starting Evaluation Harness[/bold blue]")
    
    llm = LLMClient()
    judge = LLMJudge(llm)
    verifier = FunctionalVerifier()
    
    # Load scenarios
    scenarios_dir = Path("scenarios")
    scenario_files = sorted(scenarios_dir.glob("*.yaml"))
    
    scenarios = []
    for sf in scenario_files:
        with open(sf) as f:
            scenarios.append(yaml.safe_load(f))
            
    current_version = "v0"
    
    # Run Eval
    def run_eval_suite(version):
        results = []
        failures = []
        console.print(f"\n[bold]Running suite against {version}[/bold]")
        
        for sc in scenarios:
            console.print(f"Running {sc['id']}: {sc['name']}...", end=" ")
            
            transcript, db = run_scenario(sc, version, llm)
            judge_res = judge.score(transcript, sc)
            func_res = verifier.verify(transcript, db, sc)
            
            # Combine scores
            final_score = (judge_res['weighted_average'] * 0.6) + (func_res['score'] * 0.4)
            passed = final_score >= 3.5 and func_res['passed']
            
            if passed:
                console.print(f"[green]PASS ({final_score:.1f}/5.0)[/green]")
            else:
                console.print(f"[red]FAIL ({final_score:.1f}/5.0)[/red]")
                failures.append({
                    "scenario_id": sc['id'],
                    "transcript": transcript,
                    "judge_reasoning": judge_res.get('reasoning', ''),
                    "func_details": func_res.get('details', {})
                })
                
            results.append({
                "scenario": sc['id'],
                "score": final_score,
                "passed": passed
            })
            
        avg = sum(r['score'] for r in results) / len(results)
        console.print(f"Average Score: [bold]{avg:.2f}/5.0[/bold]")
        return results, failures, avg

    # First Pass
    res1, fails1, avg1 = run_eval_suite(current_version)
    
    if args.improve and fails1:
        console.print("\n[bold yellow]Failures detected. Triggering Improvement Loop...[/bold yellow]")
        engine = ImprovementEngine(llm)
        new_ver = "v1"
        
        patched = engine.generate_and_apply_patch(fails1, current_version, new_ver)
        if patched:
            # Second Pass
            res2, fails2, avg2 = run_eval_suite(new_ver)
            
            delta = avg2 - avg1
            if delta > 0:
                console.print(f"\n[bold green]Improvement successful! Score moved by +{delta:.2f}[/bold green]")
                update_metadata(new_ver, {"parent": current_version, "score_delta": delta})
            else:
                console.print(f"\n[bold red]Regression detected or no improvement. Score moved by {delta:.2f}[/bold red]")
    else:
        if not fails1:
            console.print("\n[bold green]All scenarios passed. No improvement needed.[/bold green]")

if __name__ == "__main__":
    main()
