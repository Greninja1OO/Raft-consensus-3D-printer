import requests
import json
from typing import Dict, List, Optional

class PrinterClient:
    def __init__(self, welcome_server_url: str = "http://127.0.0.1:5100"):
        self.welcome_server_url = welcome_server_url

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make a request through the welcome server"""
        try:
            url = f"{self.welcome_server_url}/proxy/{endpoint}"
            if method == "GET":
                response = requests.get(url)
            else:
                response = requests.request(method, url, json=data)
            return response.json()
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def get_cluster_status(self) -> Dict:
        """Get the status of the printer cluster"""
        try:
            response = requests.get(f"{self.welcome_server_url}/NodeStatus")
            return response.json()
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def add_printer(self, printer_id: str, company: str, model: str) -> Dict:
        """Add a new printer to the cluster"""
        if not all([printer_id, company, model]):
            return {"success": False, "error": "All printer fields are required"}
        
        data = {
            "id": printer_id,
            "company": company,
            "model": model
        }
        return self._make_request("POST", "api/v1/printers", data)

    def list_printers(self) -> List[Dict]:
        """Get list of all printers"""
        response = self._make_request("GET", "api/v1/printers")
        return response if isinstance(response, list) else []

    def add_filament(self, filament_id: str, filament_type: str, color: str, 
                    weight: float) -> Dict:
        """Add a new filament to the cluster"""
        valid_types = ["PLA", "PETG", "ABS", "TPU"]
        if filament_type.upper() not in valid_types:
            return {"success": False, "error": f"Filament type must be one of: {', '.join(valid_types)}"}
        
        if not all([filament_id, color]) or not weight > 0:
            return {"success": False, "error": "All filament fields are required and weight must be positive"}
        
        data = {
            "id": filament_id,
            "type": filament_type.upper(),
            "color": color,
            "total_weight_in_grams": weight,
            "remaining_weight_in_grams": weight  # Set same as total weight initially
        }
        return self._make_request("POST", "api/v1/filaments", data)

    def list_filaments(self) -> List[Dict]:
        """Get list of all filaments"""
        response = self._make_request("GET", "api/v1/filaments")
        return response if isinstance(response, list) else []

    def submit_print_job(self, job_id: str, printer_id: str, filament_id: str, 
                        filepath: str, print_weight: float) -> Dict:
        """Submit a new print job"""
        if not all([job_id, printer_id, filament_id, filepath]) or print_weight <= 0:
            return {"success": False, "error": "All job fields are required and print weight must be positive"}
        
        data = {
            "id": job_id,
            "printer_id": printer_id,
            "filament_id": filament_id,
            "filepath": filepath,
            "print_weight_in_grams": print_weight
        }
        return self._make_request("POST", "api/v1/jobs", data)

    def list_jobs(self) -> List[Dict]:
        """Get list of all print jobs"""
        response = self._make_request("GET", "api/v1/jobs")
        return response if isinstance(response, list) else []

    def update_job_status(self, job_id: str, new_status: str) -> Dict:
        """Update the status of a print job"""
        valid_statuses = ["Running", "Done", "Cancelled"]
        if new_status not in valid_statuses:
            return {"success": False, "error": f"Status must be one of: {', '.join(valid_statuses)}"}
        
        data = {"status": new_status}
        return self._make_request("PATCH", f"api/v1/jobs/{job_id}/status", data)

    def list_jobs_by_status(self, status: str = None) -> List[Dict]:
        """Get list of jobs, optionally filtered by status"""
        endpoint = "api/v1/jobs"
        if status:
            endpoint += f"?status={status}"
        response = self._make_request("GET", endpoint)
        return response if isinstance(response, list) else []



def format_response(response):
    """Format response into readable statement"""
    if isinstance(response, list):
        return response  # Keep lists as is for display
    
    if not isinstance(response, dict):
        return str(response)
        
    if response.get('success') == False:
        error = response.get('error', 'Unknown error')
        if 'No leader found' in error:
            return "No active leader found in the cluster. Please try again in a few moments."
        elif 'leader timed out' in error:
            return "Connection to leader timed out. Please try again."
        elif 'Could not connect to leader' in error:
            return "Unable to connect to leader node. The leader might be down."
        else:
            return f"Error: {error}"
    elif response.get('success') == True:
        return "Operation completed successfully"
    else:
        return "Unknown response format"

def main():
    client = PrinterClient()
    
    while True:
        print("=== 3D Printer Cluster Management ===")
        print("1. POST Printer (Create new printer)")
        print("2. GET Printers (List all printers)")
        print("3. POST Filament (Create new filament)")
        print("4. GET Filaments (List all filaments)")
        print("5. POST Print Job (Create new print job)")
        print("6. GET Print Jobs (List all jobs)")
        print("7. Update Print Job Status")
        print("8. Exit")
        
        choice = input("\nEnter your choice (1-8): ")
        print()  # Add blank line for better readability
        
        if choice == "1":
            printer_id = input("Enter Printer ID: ")
            company = input("Enter Printer Company: ")
            model = input("Enter Printer Model: ")
            response = client.add_printer(printer_id, company, model)
            print("\nResponse:", format_response(response))
            
        elif choice == "2":
            printers = client.list_printers()
            print("\n=== All Printers ===")
            if not printers:
                print("No printers found")
            for printer in printers:
                print(f"Printer ID: {printer['id']}")
                print(f"Company: {printer['company']}")
                print(f"Model: {printer['model']}")
                print()
            
        elif choice == "3":
            filament_id = input("Enter Filament ID: ")
            print("\nValid filament types: PLA, PETG, ABS, TPU")
            filament_type = input("Enter Filament Type: ").upper()
            color = input("Enter Color: ")
            weight = float(input("Enter Weight (g): "))
            response = client.add_filament(filament_id, filament_type, color, weight)
            print("\nResponse:", format_response(response))
            
        elif choice == "4":
            filaments = client.list_filaments()
            print("\n=== All Filaments ===")
            if not filaments:
                print("No filaments found")
            for filament in filaments:
                print(f"Filament ID: {filament['id']}")
                print(f"Type: {filament['type']}")
                print(f"Color: {filament['color']}")
                print(f"Remaining Weight: {filament['remaining_weight']}g")
                print()
            
        elif choice == "5":
            # Show available printers first
            printers = client.list_printers()
            print("\nAvailable Printers:")
            for printer in printers:
                print(f"ID: {printer['id']}, Model: {printer['model']}")
            
            # Show available filaments
            filaments = client.list_filaments()
            print("\nAvailable Filaments:")
            for filament in filaments:
                print(f"ID: {filament['id']}, Type: {filament['type']}, "
                      f"Color: {filament['color']}, "
                      f"Remaining: {filament['remaining_weight']}g")
            
            # Get job details
            job_id = input("\nEnter Job ID: ")
            printer_id = input("Enter Printer ID: ")
            filament_id = input("Enter Filament ID: ")
            filepath = input("Enter G-code File Path: ")
            print_weight = float(input("Enter Print Weight (g): "))
            
            response = client.submit_print_job(
                job_id, printer_id, filament_id, filepath, print_weight
            )
            print("\nResponse:", format_response(response))
            
        elif choice == "6":
            jobs = client.list_jobs()
            print("\n=== All Print Jobs ===")
            if not jobs:
                print("No jobs found")
            for job in jobs:
                print(f"Job ID: {job['id']}")
                print(f"Printer: {job['printer_id']}")
                print(f"Filament: {job['filament_id']}")
                print(f"Status: {job['status']}")
                print(f"Print Weight: {job['print_weight_in_grams']}g")
                print()
            
        elif choice == "7":
            # Show current jobs first
            jobs = client.list_jobs()
            print("\nCurrent Jobs:")
            for job in jobs:
                print(f"ID: {job['id']}, Status: {job['status']}, "
                      f"Printer: {job['printer_id']}")
            
            job_id = input("\nEnter Job ID: ")
            print("\nValid transitions:")
            print("- Queued → Running")
            print("- Running → Done")
            print("- Queued/Running → Cancelled")
            new_status = input("Enter New Status: ")
            
            response = client.update_job_status(job_id, new_status)
            print("\nResponse:", format_response(response))
            
        elif choice == "8":
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
