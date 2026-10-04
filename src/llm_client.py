import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(Path(__file__).parent.parent / '.env')
console = Console()


# Global throttle to strictly enforce 14 Requests Per Minute limit across the whole app
_LAST_CALL_TIME = 0

class LLMClient:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
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
            
        if not self.providers:
            raise ValueError("No API keys found")

    def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.7) -> dict:
        global _LAST_CALL_TIME
        elapsed = time.time() - _LAST_CALL_TIME
        if elapsed < 4.3:  # 60 seconds / 14 requests = ~4.28s per request
            time.sleep(4.3 - elapsed)
        _LAST_CALL_TIME = time.time()
        
        max_retries = 3
        sanitized = self._sanitize_messages(messages)
        
        for idx, provider in enumerate(self.providers):
            for attempt in range(max_retries):
                try:
                    payload = {
                        "model": provider["model"],
                        "messages": sanitized,
                        "temperature": temperature
                    }
                    if tools:
                        payload["tools"] = tools
                        
                    resp = requests.post(provider["url"], headers=provider["headers"], json=payload, timeout=60)
                    
                    if resp.status_code == 429:
                        if attempt < max_retries - 1:
                            console.print(f"[dim]Rate limit (429) hit on {provider['name']}. Sleeping 10s...[/dim]")
                            time.sleep(1)
                            continue
                        else:
                            console.print(f"[yellow]Rate limit exhausted on {provider['name']}.[/yellow]")
                            break
                    
                    if resp.status_code == 503:
                        console.print(f"[dim]Server overloaded (503) on {provider['name']}. Sleeping 5s...[/dim]")
                        time.sleep(5)
                        if attempt < max_retries - 1:
                            continue
                        else:
                            break
                            
                    if resp.status_code != 200:
                        error_text = resp.text
                        console.print(f"[dim]API Error {resp.status_code} with {provider['name']}: {error_text[:200]}[/dim]")
                        break
                        
                    data = resp.json()
                    message = data["choices"][0]["message"]
                    
                    result = {
                        "content": message.get("content"),
                        "tool_calls": [],
                        "raw_message": message
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
                    
                except requests.exceptions.Timeout:
                    console.print(f"[dim]Timeout on {provider['name']}. Retrying...[/dim]")
                    time.sleep(2)
                except Exception as e:
                    if idx == len(self.providers) - 1 and attempt == max_retries - 1:
                        raise e
                    time.sleep(1)
                    
        raise RuntimeError("All LLM providers and retries failed.")

llm = LLMClient()
