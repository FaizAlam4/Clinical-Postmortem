from typing import List, Literal, Optional
from pydantic import BaseModel
from datetime import datetime

class Doctor(BaseModel):
    id: str
    name: str
    department: str
    specialties: List[str]

class TimeSlot(BaseModel):
    id: str
    doctor_id: str
    datetime: str
    duration_minutes: int = 30
    is_booked: bool = False

class Patient(BaseModel):
    id: str
    name: str
    phone: str
    date_of_birth: str
    existing_appointments: List[str] = []

class Appointment(BaseModel):
    id: str
    patient_id: str
    slot_id: str
    doctor_id: str
    reason: str
    status: Literal['confirmed', 'cancelled']
    booked_at: str
    cancelled_at: Optional[str] = None

class EscalationTicket(BaseModel):
    id: str
    reason: str
    urgency: Literal['routine', 'urgent', 'emergency']
    conversation_summary: str
    created_at: str
