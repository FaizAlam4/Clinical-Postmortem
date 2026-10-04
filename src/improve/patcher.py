import json
import yaml
from pathlib import Path
from src.llm_client import LLMClient
from src.agent.prompt_builder import copy_version, update_lessons

class ImprovementEngine:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        
    def generate_and_apply_patch(self, failures: list, current_version: str, new_version: str):
        if not failures:
            return None
            
        # 1. Analyze failures
        prompt = "Analyze the following eval failures and generate a new lesson to add to the agent's system prompt.\n"
        for f in failures:
            prompt += f"\nScenario: {f['scenario_id']}\n"
            prompt += f"Reasoning: {f['judge_reasoning']}\n"
            prompt += "Transcript:\n"
            for t in f['transcript'][-6:]: # Last 6 turns
                if t['role'] in ['patient', 'agent']:
                    prompt += f"[{t['role']}] {t['content']}\n"
                    
        prompt += """
Generate exactly one clear, targeted rule/lesson to fix this.
Return ONLY valid JSON in this format:
{
    "trigger": "when the patient mentions X...",
    "action": "use tool Y and do Z...",
    "priority": "critical"
}
"""
        response = self.llm.chat([{"role": "user", "content": prompt}], temperature=0.2)
        content = response.get("content", "").strip()
        
        # Clean JSON
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        try:
            lesson = json.loads(content.strip())
        except Exception as e:
            print(f"Failed to parse patch: {e}")
            return None
            
        # 2. Apply patch
        print(f"\n[Patch Generator] Creating version {new_version}...")
        print(f"[Patch Generator] Adding lesson: If {lesson.get('trigger')} -> {lesson.get('action')}")
        
        copy_version(current_version, new_version)
        update_lessons(new_version, [lesson])
        
        return new_version
