"""
Tool definitions and handlers for the scheduling agent.

Each tool has:
1. An OpenAI function-calling schema (for the LLM)
2. A handler function (for execution)
3. Built-in guardrails (validation, error handling)
"""

import json
from datetime import datetime, timedelta
from typing import Any


# --- Tool Schemas (what the LLM sees) ---

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Check available appointment slots at the clinic. Always call this BEFORE attempting to book. Returns a list of available time slots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Filter by doctor name (e.g., 'Smith', 'Dr. Chen'). Optional — omit to see all doctors."
                    },
                    "department": {
                        "type": "string",
                        "description": "Filter by department (e.g., 'Cardiology', 'General Medicine'). Optional."
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Start date for search range in YYYY-MM-DD format. Must be today or later."
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End date for search range in YYYY-MM-DD format. Maximum 14 days from today."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment for a patient in a specific slot. MUST confirm details with patient before calling this. Requires a slot_id from get_available_slots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient's ID (e.g., 'P001')."
                    },
                    "slot_id": {
                        "type": "string",
                        "description": "The time slot ID from get_available_slots results."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the appointment (e.g., 'general checkup', 'knee pain')."
                    }
                },
                "required": ["patient_id", "slot_id", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. Requires the appointment ID and patient ID for verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "The appointment ID to cancel (e.g., 'APT-001')."
                    },
                    "patient_id": {
                        "type": "string",
                        "description": "The patient's ID for ownership verification."
                    }
                },
                "required": ["appointment_id", "patient_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_info",
            "description": "Look up a patient's scheduling information — their name, existing appointments, and contact info. Does NOT return medical records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient's ID (e.g., 'P001')."
                    }
                },
                "required": ["patient_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Transfer the conversation to a human staff member. Use this when: (1) patient mentions emergency symptoms, (2) situation is beyond scheduling scope, (3) patient is upset and needs human help, (4) you are unsure how to proceed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why the escalation is needed."
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["routine", "urgent", "emergency"],
                        "description": "Urgency level. Use 'emergency' for acute symptoms (chest pain, breathing difficulty, etc.)."
                    },
                    "conversation_summary": {
                        "type": "string",
                        "description": "Brief summary of the conversation so far for the human staff member."
                    }
                },
                "required": ["reason", "urgency", "conversation_summary"]
            }
        }
    }
]


class ToolExecutor:
    """Executes tool calls against the clinic database."""

    def __init__(self, clinic_db):
        self.db = clinic_db
        self.call_log: list[dict] = []  # Track all tool calls for eval

    def execute(self, function_name: str, arguments: dict) -> str:
        """Execute a tool call and return the result as a JSON string."""
        handler = getattr(self, f"_handle_{function_name}", None)
        if handler is None:
            result = {"error": f"Unknown tool: {function_name}"}
        else:
            try:
                result = handler(**arguments)
            except Exception as e:
                result = {"error": f"Tool execution error: {str(e)}"}

        # Log the call
        self.call_log.append({
            "function": function_name,
            "arguments": arguments,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

        return json.dumps(result, indent=2, default=str)

    def _handle_get_available_slots(
        self,
        doctor_name: str | None = None,
        department: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None
    ) -> dict:
        """Check available slots with guardrails."""
        slots = self.db.get_available_slots(
            doctor_name=doctor_name,
            department=department,
            date_from=date_from,
            date_to=date_to
        )

        if not slots:
            return {
                "available_slots": [],
                "message": "No available slots found for the given criteria. Try different dates or a different doctor."
            }

        return {
            "available_slots": slots,
            "count": len(slots)
        }

    def _handle_book_appointment(
        self,
        patient_id: str,
        slot_id: str,
        reason: str
    ) -> dict:
        """Book an appointment with guardrails."""
        if not reason or len(reason.strip()) < 3:
            return {"error": "A reason for the appointment is required."}

        return self.db.book_appointment(patient_id, slot_id, reason)

    def _handle_cancel_appointment(
        self,
        appointment_id: str,
        patient_id: str
    ) -> dict:
        """Cancel an appointment with ownership verification."""
        return self.db.cancel_appointment(appointment_id, patient_id)

    def _handle_get_patient_info(self, patient_id: str) -> dict:
        """Get patient scheduling info (no medical data)."""
        return self.db.get_patient(patient_id)

    def _handle_escalate_to_human(
        self,
        reason: str,
        urgency: str = "routine",
        conversation_summary: str = ""
    ) -> dict:
        """Escalate to human staff. Always succeeds."""
        ticket = self.db.create_escalation(reason, urgency, conversation_summary)
        return {
            "status": "escalated",
            "ticket_id": ticket["id"],
            "message": f"Conversation has been escalated to a human staff member (urgency: {urgency}). A staff member will reach out to the patient shortly.",
            "urgency": urgency
        }

    def get_call_log(self) -> list[dict]:
        """Return the full tool call log for evaluation."""
        return self.call_log.copy()

    def reset_log(self):
        """Clear the tool call log."""
        self.call_log = []
