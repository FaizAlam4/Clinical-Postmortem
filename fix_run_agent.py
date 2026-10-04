with open("run_agent.py", "r") as f:
    content = f.read()

content = content.replace('agent = SchedulingAgent(db, patient_id="P001", version=version)',
                          'agent = SchedulingAgent(db, patient_id="P001", prompt_version=version)')

with open("run_agent.py", "w") as f:
    f.write(content)
