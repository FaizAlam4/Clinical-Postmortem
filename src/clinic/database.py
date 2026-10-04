import yaml
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.clinic.models import Doctor, TimeSlot, Patient, Appointment, EscalationTicket

DATA_DIR = Path(__file__).parent.parent.parent / "data"

class ClinicDatabase:
    def __init__(self):
        self.doctors: Dict[str, Doctor] = {}
        self.slots: Dict[str, TimeSlot] = {}
        self.patients: Dict[str, Patient] = {}
        self.appointments: Dict[str, Appointment] = {}
        self.escalations: Dict[str, EscalationTicket] = {}
        self.reset()

    def reset(self):
        """Reload seed data for clean state."""
        self.doctors.clear()
        self.slots.clear()
        self.patients.clear()
        self.appointments.clear()
        self.escalations.clear()
        
        seed_path = DATA_DIR / "seed.yaml"
        if not seed_path.exists():
            return
            
        with open(seed_path, 'r') as f:
            data = yaml.safe_load(f)

        for d in data.get('doctors', []):
            self.doctors[d['id']] = Doctor(**d)

        for p in data.get('patients', []):
            self.patients[p['id']] = Patient(**p)
            
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for s in data.get('slots', []):
            slot_date = today + timedelta(days=s['day_offset'])
            slot_datetime = slot_date.replace(hour=s['hour'], minute=s['minute']).isoformat()
            
            slot = TimeSlot(
                id=s['id'],
                doctor_id=s['doctor_id'],
                datetime=slot_datetime,
                is_booked=s.get('is_booked', False)
            )
            self.slots[slot.id] = slot

    def get_available_slots(self, doctor_name: Optional[str] = None, department: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[dict]:
        available = []
        today = datetime.now().isoformat()
        
        for slot in self.slots.values():
            if slot.is_booked:
                continue
            
            # Reject past dates
            if slot.datetime < today:
                continue
                
            doc = self.doctors.get(slot.doctor_id)
            if not doc:
                continue
                
            if doctor_name and doctor_name.lower() not in doc.name.lower():
                continue
            if department and department.lower() not in doc.department.lower():
                continue
            if date_from and slot.datetime < date_from:
                continue
            if date_to and slot.datetime > date_to + "T23:59:59":
                continue
                
            slot_dict = slot.model_dump()
            slot_dict['doctor_name'] = doc.name
            slot_dict['department'] = doc.department
            available.append(slot_dict)
            
        return sorted(available, key=lambda x: x['datetime'])

    def book_appointment(self, patient_id: str, slot_id: str, reason: str) -> dict:
        if slot_id not in self.slots:
            return {"error": f"Slot {slot_id} does not exist."}
        if self.slots[slot_id].is_booked:
            return {"error": f"Slot {slot_id} is already booked."}
        if patient_id not in self.patients:
            return {"error": f"Patient {patient_id} does not exist."}
            
        apt_id = f"APT-{uuid.uuid4().hex[:6].upper()}"
        slot = self.slots[slot_id]
        
        apt = Appointment(
            id=apt_id,
            patient_id=patient_id,
            slot_id=slot_id,
            doctor_id=slot.doctor_id,
            reason=reason,
            status='confirmed',
            booked_at=datetime.now().isoformat()
        )
        
        self.appointments[apt_id] = apt
        slot.is_booked = True
        self.patients[patient_id].existing_appointments.append(apt_id)
        
        doc = self.doctors[slot.doctor_id]
        return {
            "status": "success",
            "appointment_id": apt_id,
            "datetime": slot.datetime,
            "doctor": doc.name,
            "message": "Appointment successfully booked."
        }

    def cancel_appointment(self, appointment_id: str, patient_id: str) -> dict:
        if appointment_id not in self.appointments:
            return {"error": "Appointment not found."}
            
        apt = self.appointments[appointment_id]
        if apt.patient_id != patient_id:
            return {"error": "Unauthorized. Patient ID does not match."}
        if apt.status == 'cancelled':
            return {"error": "Appointment is already cancelled."}
            
        apt.status = 'cancelled'
        apt.cancelled_at = datetime.now().isoformat()
        
        if apt.slot_id in self.slots:
            self.slots[apt.slot_id].is_booked = False
            
        return {"status": "success", "message": f"Appointment {appointment_id} cancelled."}

    def get_patient(self, patient_id: str) -> dict:
        if patient_id not in self.patients:
            return {"error": "Patient not found."}
            
        p = self.patients[patient_id]
        apts = []
        for apt_id in p.existing_appointments:
            if apt_id in self.appointments:
                apt = self.appointments[apt_id]
                doc = self.doctors[apt.doctor_id]
                slot = self.slots[apt.slot_id]
                apts.append({
                    "appointment_id": apt.id,
                    "datetime": slot.datetime,
                    "doctor": doc.name,
                    "status": apt.status,
                    "reason": apt.reason
                })
                
        return {
            "id": p.id,
            "name": p.name,
            "phone": p.phone,
            "appointments": apts
        }

    def get_appointment(self, appointment_id: str) -> Optional[dict]:
        if appointment_id in self.appointments:
            return self.appointments[appointment_id].model_dump()
        return None

    def create_escalation(self, reason: str, urgency: str, summary: str) -> dict:
        ticket_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
        ticket = EscalationTicket(
            id=ticket_id,
            reason=reason,
            urgency=urgency,
            conversation_summary=summary,
            created_at=datetime.now().isoformat()
        )
        self.escalations[ticket_id] = ticket
        return ticket.model_dump()
