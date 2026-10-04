import os
from rich.console import Console
from src.agent.scheduler import SchedulingAgent
from src.clinic.database import ClinicDatabase

console = Console()

def main():
    console.print("[bold blue]Sunrise Medical Clinic - Agent Test CLI[/bold blue]")
    console.print("Type 'quit' to exit.\n")
    
    db = ClinicDatabase()
    
    # We'll use P001 (John Doe) by default
    agent = SchedulingAgent(db, patient_id="P001")
    
    while True:
        try:
            user_input = input("\nPatient (You): ")
            if user_input.lower() in ['quit', 'exit']:
                break
                
            response = agent.chat(user_input)
            console.print(f"\n[green]Agent: {response}[/green]")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    main()
