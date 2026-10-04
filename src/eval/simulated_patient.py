import json
from src.llm_client import LLMClient

class SimulatedPatient:
    def __init__(self, scenario_data: dict, llm_client: LLMClient):
        self.persona = scenario_data['patient_persona']
        self.goal = self.persona.get('goal', '')
        self.triggers = self.persona.get('follow_up_triggers', [])
        self.llm = llm_client
        self.messages = []
        
        system_prompt = f"""You are a patient talking to a medical clinic scheduling agent.
Your name is {self.persona['name']}. 
Your personality: {self.persona.get('personality', 'Normal')}
Your goal: {self.goal}

RULES:
1. Act naturally like a patient. Keep responses relatively short.
2. Do not reveal that you are an AI.
3. If the agent helps you achieve your goal, say thank you and end the conversation naturally.
4. Do NOT be overly cooperative if it goes against your personality.
"""
        self.messages.append({"role": "system", "content": system_prompt})
        
    def get_opener(self) -> str:
        opener = self.persona.get('opener', "Hello, I'd like to book an appointment.")
        self.messages.append({"role": "assistant", "content": opener}) # For LLM, patient's own words are assistant
        return opener
        
    def respond(self, agent_message: str, turn_number: int) -> str:
        self.messages.append({"role": "user", "content": agent_message}) # Agent's words are user to the patient LLM
        
        # Check triggers
        for t in self.triggers:
            if t.get('after_turn') == turn_number:
                trigger_msg = t.get('message')
                self.messages.append({"role": "assistant", "content": trigger_msg})
                return trigger_msg
                
        # Ask LLM for next response
        response = self.llm.chat(messages=self.messages, temperature=0.7)
        patient_text = response.get("content", "Okay.")
        self.messages.append({"role": "assistant", "content": patient_text})
        return patient_text
