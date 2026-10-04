import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(Path(__file__).parent.parent / '.env')
console = Console()

class LLMClient:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.providers = []
        if self.gemini_key:
            self.providers.append({
                "name": "Gemini 3.5 Flash Lite",
                "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "headers": {"Authorization": f"Bearer {self.gemini_key}", "Content-Type": "application/json"},
                "model": "gemini-3.5-flash-lite"
            })
            self.providers.append({
                "name": "Gemini 3.1 Flash Lite",
                "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "headers": {"Authorization": f"Bearer {self.gemini_key}", "Content-Type": "application/json"},
                "model": "gemini-3.1-flash-lite"
            })
            self.providers.append({
                "name": "Gemini 3.8 Flash",
                "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "headers": {"Authorization": f"Bearer {self.gemini_key}", "Content-Type": "application/json"},
                "model": "gemini-3.8-flash"
            })
            

        if self.groq_key:
            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            groq_headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
            
            self.providers.append({
                "name": "Groq GPT OSS 120B",
                "url": groq_url,
                "headers": groq_headers,
                "model": "openai/gpt-oss-120b"
            })
            self.providers.append({
                "name": "Groq Qwen 3.8 27B",
                "url": groq_url,
                "headers": groq_headers,
                "model": "qwen/qwen3.8-27b"
            })
            self.providers.append({
                "name": "Groq GPT OSS 20B",
                "url": groq_url,
                "headers": groq_headers,
                "model": "openai/gpt-oss-20b"
            })
            
        if not self.providers:
            raise ValueError("No API keys found")

    def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.7) -> dict:
        max_retries = 3
        
        for idx, provider in enumerate(self.providers):
            for attempt in range(max_retries):
                try:
                    payload = {
                        "model": provider["model"],
                        "messages": messages,
                        "temperature": temperature
                    }
                    if tools:
                        payload["tools"] = tools
                        
                    resp = requests.post(provider["url"], headers=provider["headers"], json=payload, timeout=30)
                    
                    if resp.status_code == 429:
                        if attempt < max_retries - 1:
                            console.print(f"[dim]Rate limit (429) hit on {provider['name']}. Sleeping 10s...[/dim]")
                            time.sleep(10)
                            continue
                        else:
                            console.print(f"[yellow]Rate limit exhausted on {provider['name']}.[/yellow]")
                            break
                            
                    if resp.status_code != 200:
                        error_text = resp.text
                        if "INVALID_ARGUMENT" in error_text and "function_response.name" in error_text:
                            # Print a useful debug message
                            console.print(f"[dim]Gemini Function Response format error. Payload sent:[/dim]")
                            # Find the tool messages
                            for m in messages:
                                if m.get("role") == "tool":
                                    console.print(f"[dim]Tool Msg: {m}[/dim]")
                        
                        console.print(f"[dim]API Error {resp.status_code} with {provider['name']}: {error_text}[/dim]")
                        break
                        
                    data = resp.json()
                    message = data["choices"][0]["message"]
                    
                    result = {
                        "content": message.get("content"),
                        "tool_calls": [],
                        "raw_message": message # Full dictionary from JSON, includes extra_content
                    }
                    
                    if "tool_calls" in message:
                        for tc in message["tool_calls"]:
                            func = tc["function"]
                            try:
                                args = json.loads(func["arguments"])
                            except:
                                args = func["arguments"]
                            
                            result["tool_calls"].append({
                                "id": tc["id"],
                                "function_name": func["name"],
                                "arguments": args
                            })
                    return result
                    
                except Exception as e:
                    if idx == len(self.providers) - 1 and attempt == max_retries - 1:
                        raise e
                    time.sleep(1)
                    
        raise RuntimeError("All LLM providers and retries failed.")

llm = LLMClient()
