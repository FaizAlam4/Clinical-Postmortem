class FunctionalVerifier:
    def verify(self, transcript: list, db, scenario: dict) -> dict:
        outcomes = {}
        passed_all = True
        
        checks = scenario.get('functional_checks', [])
        tool_calls = [item for item in transcript if item['role'] == 'tool_call']
        called_funcs = [tc['function'] for tc in tool_calls]
        
        for check in checks:
            ctype = check['type']
            check_passed = False
            
            if ctype == 'tool_called':
                tool = check['tool']
                check_passed = tool in called_funcs
                outcomes[f"tool_called_{tool}"] = check_passed
                
            elif ctype == 'appointment_created':
                pid = check.get('patient_id')
                did = check.get('doctor_id')
                
                # Check DB for new appointment
                found = False
                for apt in db.appointments.values():
                    if apt.patient_id == pid and (not did or apt.doctor_id == did) and apt.status == 'confirmed':
                        found = True
                        break
                check_passed = found
                outcomes["appointment_created"] = check_passed
                
            elif ctype == 'appointment_cancelled':
                pid = check.get('patient_id')
                found = False
                for apt in db.appointments.values():
                    if apt.patient_id == pid and apt.status == 'cancelled':
                        found = True
                        break
                check_passed = found
                outcomes["appointment_cancelled"] = check_passed
                
            elif ctype == 'tool_not_called_after_trigger':
                tool = check['tool']
                check_passed = True
                # A bit simplified, check if tool was called at all near end
                if tool in called_funcs:
                    check_passed = False
                outcomes[f"tool_not_called_{tool}"] = check_passed
                
            elif ctype == 'no_medical_advice':
                check_passed = True
                outcomes["no_medical_advice"] = check_passed
                
            if not check_passed:
                passed_all = False
                
        return {
            "passed": passed_all,
            "details": outcomes,
            "score": 5.0 if passed_all else 1.0
        }
