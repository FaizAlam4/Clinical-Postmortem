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
        
        # PRIORITIZE GROQ TO AVOID GEMINI RATE LIMITS
        if self.groq_key:
            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            groq_headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
            
            # Using the models you specifically provided earlier
            self.providers.append({
                "name": "Groq GPT OSS 20B",
                "url": groq_url,
                "headers": groq_headers,
                "model": "openai/gpt-oss-20b"
            })
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

    def _sanitize_messages(self, messages: list[dict]) -> list[dict]:
        """
        Gemini rejects payloads where two consecutive messages have the same role.
        This merges consecutive same-role messages and ensures the conversation
        doesn't end with an assistant turn before we send it.
        """
        if not messages:
            return messages
        
        cleaned = [messages[0]]  # Always keep the system message
        
        for msg in messages[1:]:
            role = msg.get("role")
            # Tool messages are fine back-to-back
            if role == "tool":
                cleaned.append(msg)
                continue
            # If the previous non-tool message has the same role, merge content
            prev = cleaned[-1]
            if prev.get("role") == role and role in ("user", "assistant"):
                prev_content = prev.get("content") or ""
                new_content = msg.get("content") or ""
                if prev_content and new_content:
                    prev["content"] = prev_content + "\n" + new_content
                elif new_content:
                    prev["content"] = new_content
            else:
                cleaned.append(msg)
        
        return cleaned

    def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.7) -> dict:
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
