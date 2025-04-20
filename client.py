import requests
import json
import sys
import os
import time

class RaftClient:
    def __init__(self):
        self.peers_file = 'config/peers.json'

    def _get_leader(self):
        """Get current leader info from peers.json"""
        try:
            with open(self.peers_file, 'r') as f:
                peers_data = json.load(f)
                leader = peers_data.get('leader', {})
                if leader.get('host') and leader.get('port'):
                    return leader
                print("❌ No leader available")
                return None
        except Exception as e:
            print(f"❌ Error reading peers file: {str(e)}")
            return None

    def _send_request(self, endpoint, method='GET', data=None):
        """Send request to leader node"""
        leader = self._get_leader()  # Get fresh leader info for each request
        if not leader:
            print("❌ No leader available to process request")
            return None

        url = f"http://{leader['host']}:{leader['port']}/api/v1/{endpoint}"
        try:
            if method == 'GET':
                response = requests.get(url)
            else:
                response = requests.post(url, json=data)
            
            return response.json()
        except Exception as e:
            print(f"❌ Error sending request: {str(e)}")
            return None

    def add_printer(self, printer_id, company, model):
        """Add a new printer to the cluster"""
        data = {
            "id": printer_id,
            "company": company,
            "model": model
        }
        result = self._send_request('printers', 'POST', data)
        if result and result.get('success'):
            print(f"✅ Added printer {printer_id}")
        return result

    def add_filament(self, filament_id, filament_type, color, total_weight):
        """Add new filament to the cluster"""
        # Validate filament type
        valid_types = ['PLA', 'PETG', 'ABS', 'TPU']
        filament_type = filament_type.upper()
        if filament_type not in valid_types:
            print(f"❌ Invalid filament type. Must be one of: {', '.join(valid_types)}")
            return None

        data = {
            "id": filament_id,
            "type": filament_type,
            "color": color,
            "total_weight_in_grams": total_weight,
            "remaining_weight_in_grams": total_weight
        }
        result = self._send_request('filaments', 'POST', data)
        if result and result.get('success'):
            print(f"✅ Added filament {filament_id}")
        return result

    def add_print_job(self, job_id, printer_id, filament_id, filepath, weight):
        """Submit a new print job"""
        data = {
            "id": job_id,
            "printer_id": printer_id,
            "filament_id": filament_id,
            "filepath": filepath,
            "print_weight_in_grams": weight
        }
        result = self._send_request('jobs', 'POST', data)
        if result and result.get('success'):
            print(f"✅ Added print job {job_id}")
        return result

    def update_job_status(self, job_id, new_status):
        """Update the status of a print job"""
        valid_status = ['running', 'done', 'cancelled']
        if new_status.lower() not in valid_status:
            print(f"❌ Invalid status. Must be one of: {', '.join(valid_status)}")
            return None
        
        endpoint = f'jobs/{job_id}/status?status={new_status.lower()}'
        result = self._send_request(endpoint, 'POST')
        if result and result.get('success'):
            print(f"✅ Updated job {job_id} status to {new_status}")
        return result

    def get_printers(self):
        """Get list of all printers"""
        return self._send_request('printers')

    def get_filaments(self):
        """Get list of all filaments"""
        return self._send_request('filaments')

    def get_jobs(self):
        """Get list of all jobs"""
        return self._send_request('jobs')

if __name__ == "__main__":
    client = RaftClient()
    
    def clear_console():
        os.system('cls' if os.name == 'nt' else 'clear')

    while True:
        clear_console()
        print("\n=== 3D Printer Management System ===")
        print("1. Add Printer")
        print("2. Add Filament")
        print("3. Submit Print Job")
        print("4. Update Job Status")
        print("5. View Printers")
        print("6. View Filaments")
        print("7. View Jobs")
        print("0. Exit")
        
        choice = input("\nEnter your choice (0-7): ")
        
        # Get fresh leader info before executing command
        if choice != "0" and client._get_leader() is None:
            print("❌ No leader available. Please try again later.")
            time.sleep(2)  # Show error for 2 seconds
            continue

        if choice == "0":
            clear_console()
            break
            
        elif choice == "1":
            clear_console()
            printer_id = input("Enter printer ID: ")
            company = input("Enter printer company: ")
            model = input("Enter printer model: ")
            result = client.add_printer(printer_id, company, model)
            if result and result.get('success'):
                time.sleep(1)  # Show success message briefly
            else:
                time.sleep(2)  # Show error for longer
            
        elif choice == "2":
            clear_console()
            filament_id = input("Enter filament ID: ")
            filament_type = input("Enter filament type (PLA/ABS/PETG/TPU): ")
            color = input("Enter filament color: ")
            try:
                weight = float(input("Enter total weight in grams: "))
                result = client.add_filament(filament_id, filament_type, color, weight)
                if result and result.get('success'):
                    time.sleep(1)  # Show success message briefly
                else:
                    time.sleep(2)  # Show error for longer
            except ValueError:
                print("❌ Invalid weight value")
                time.sleep(2)
            
        elif choice == "3":
            clear_console()
            job_id = input("Enter job ID: ")
            printer_id = input("Enter printer ID to use: ")
            filament_id = input("Enter filament ID to use: ")
            filepath = input("Enter path to GCODE file: ")
            try:
                weight = float(input("Enter estimated print weight in grams: "))
                result = client.add_print_job(job_id, printer_id, filament_id, filepath, weight)
                if result and result.get('success'):
                    time.sleep(1)  # Show success message briefly
                else:
                    time.sleep(2)  # Show error for longer
            except ValueError:
                print("❌ Invalid weight value")
                time.sleep(2)

        elif choice == "4":
            clear_console()
            job_id = input("Enter job ID: ")
            status = input("Enter new status (running/done/cancelled): ")
            result = client.update_job_status(job_id, status)
            if result and result.get('success'):
                time.sleep(1)  # Show success message briefly
            else:
                time.sleep(2)  # Show error for longer
            
        elif choice == "5":
            clear_console()
            printers = client.get_printers()
            print("\nPrinters:", json.dumps(printers, indent=2))
            time.sleep(3)  # Show results for 3 seconds
            
        elif choice == "6":
            clear_console()
            filaments = client.get_filaments()
            print("\nFilaments:", json.dumps(filaments, indent=2))
            time.sleep(3)
            
        elif choice == "7":
            clear_console()
            jobs = client.get_jobs()
            print("\nJobs:", json.dumps(jobs, indent=2))
            time.sleep(3)
            
        else:
            print("❌ Invalid choice")
            time.sleep(1)
