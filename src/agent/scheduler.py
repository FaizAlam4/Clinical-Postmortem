"""
Core scheduling agent — the main conversation loop.

The agent:
1. Takes patient messages
2. Calls the LLM with system prompt + conversation history + tools
3. Executes any tool calls the LLM requests
4. Returns the agent's text response
5. Logs everything for evaluation
"""

import json
from datetime import datetime
from typing import Any

from src.agent.tools import TOOL_SCHEMAS, ToolExecutor
from src.agent.prompt_builder import build_system_prompt
from src.llm_client import LLMClient


MAX_TOOL_CALLS_PER_TURN = 5  # Prevent infinite tool-calling loops


class SchedulingAgent:
    """Patient appointment scheduling agent."""

    def __init__(
        self,
        clinic_db,
        patient_id: str,
        prompt_version: str = "v0",
        llm_client: LLMClient | None = None,
    ):
        self.db = clinic_db
        self.patient_id = patient_id
        self.prompt_version = prompt_version
        self.llm = llm_client or LLMClient()
        self.tool_executor = ToolExecutor(clinic_db)

        # Build system prompt
        self.system_prompt = build_system_prompt(prompt_version)
        # Inject patient context
        self.system_prompt += f"\n\n---\n\nThe current patient you are speaking with has ID: {patient_id}. Use this when calling tools that require a patient_id."
        self.system_prompt += f"\nCurrent date and time: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}"

        # Conversation history
        self.messages: list[dict] = [
            {"role": "system", "content": self.system_prompt}
        ]

        # Full transcript for evaluation
        self.transcript: list[dict] = []

        # Track if conversation ended
        self.conversation_ended = False
        self.escalated = False

    def chat(self, patient_message: str) -> str:
        """
        Process a patient message and return the agent's response.

        This is the core loop:
        1. Add patient message to history
        2. Call LLM
        3. If LLM wants to call tools → execute → feed results back → call LLM again
        4. Return text response
        """
        # Log patient message
        self.messages.append({"role": "user", "content": patient_message})
        self.transcript.append({
            "role": "patient",
            "content": patient_message,
            "timestamp": datetime.now().isoformat()
        })

        # LLM loop (may iterate for tool calls)
        tool_call_count = 0
        while tool_call_count < MAX_TOOL_CALLS_PER_TURN:
            # Call LLM
            response = self.llm.chat(
                messages=self.messages,
                tools=TOOL_SCHEMAS,
                temperature=0.3  # Lower temp for more consistent scheduling
            )

            # Check for tool calls
            if response.get("tool_calls"):
                self.messages.append(response["raw_message"])
                for tool_call in response["tool_calls"]:
                    tool_call_count += 1
                    func_name = tool_call["function_name"]
                    func_args = tool_call["arguments"]

                    # Log the tool call decision
                    self.transcript.append({
                        "role": "tool_call",
                        "function": func_name,
                        "arguments": func_args,
                        "timestamp": datetime.now().isoformat()
                    })

                    # Execute the tool
                    result = self.tool_executor.execute(func_name, func_args)

                    # Log tool result
                    self.transcript.append({
                        "role": "tool_result",
                        "function": func_name,
                        "result": json.loads(result),
                        "timestamp": datetime.now().isoformat()
                    })

                    # Then add the tool result
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", f"call_{tool_call_count}"),
                        "name": func_name,
                        "content": result
                    })

                    # Check if this was an escalation
                    if func_name == "escalate_to_human":
                        self.escalated = True

                # Continue loop to get LLM's response after tool execution
                continue
            else:
                # Text response — we're done
                agent_text = response.get("content", "I apologize, I'm having trouble processing that. Could you rephrase?")

                self.messages.append({"role": "assistant", "content": agent_text})
                self.transcript.append({
                    "role": "agent",
                    "content": agent_text,
                    "timestamp": datetime.now().isoformat()
                })

                return agent_text

        # Exceeded max tool calls — safety valve
        fallback = "I apologize, but I'm having some technical difficulty right now. Let me connect you with a staff member who can help."
        self.messages.append({"role": "assistant", "content": fallback})
        self.transcript.append({
            "role": "agent",
            "content": fallback,
            "note": "Max tool calls exceeded",
            "timestamp": datetime.now().isoformat()
        })
        return fallback

    def get_transcript(self) -> list[dict]:
        """Return the full conversation transcript for evaluation."""
        return self.transcript.copy()

    def get_tool_calls(self) -> list[dict]:
        """Return all tool calls made during the conversation."""
        return self.tool_executor.get_call_log()

    def get_messages(self) -> list[dict]:
        """Return the raw message history."""
        return self.messages.copy()
