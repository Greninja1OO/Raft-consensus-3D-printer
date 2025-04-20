from flask import Flask, request, jsonify
import os, json
import time
def create_raft_server(raft_node):
    app = Flask(__name__)

    printers = {}
    filaments = {}
    jobs = {}

    def save_state():
        """Save state to the node's state file"""
        state_file = f"state_{raft_node.node_id}.json"
        try:
            # Read existing state
            with open(state_file, 'r') as f:
                existing_state = json.load(f)
                
            # Update only Raft consensus info, preserve application data
            existing_state.update({
                'term': raft_node.term,
                'voted_for': raft_node.voted_for
            })
            
            # Only update application data if it exists (not empty)
            if printers:
                existing_state['printers'] = printers
            if filaments:
                existing_state['filaments'] = filaments
            if jobs:
                existing_state['jobs'] = jobs
            
            # Write back the merged state
            with open(state_file, 'w') as f:
                json.dump(existing_state, f, indent=4)
                
        except FileNotFoundError:
            # If file doesn't exist, create it with current state
            with open(state_file, 'w') as f:
                json.dump({
                    'term': raft_node.term,
                    'voted_for': raft_node.voted_for,
                    'printers': printers,
                    'filaments': filaments,
                    'jobs': jobs
                }, f, indent=4)

    def load_state():
        """Load state from the node's state file"""
        state_file = f"state_{raft_node.node_id}.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    # Only update if there's data
                    if state.get('printers'):
                        printers.update(state['printers'])
                    if state.get('filaments'):
                        filaments.update(state['filaments'])
                    if state.get('jobs'):
                        jobs.update(state['jobs'])
                print(f"[{raft_node.node_id}] 📂 Loaded existing state")
            except Exception as e:
                print(f"[{raft_node.node_id}] ❌ Error loading state: {str(e)}")

    def apply_state_change(command):
        """Apply a state change from a command"""
        op = command.get('op')
        data = command.get('data', {})

        if op == 'add_printer':
            printer_id = data.get('id')
            printers[printer_id] = {
                'company': data.get('company'),
                'model': data.get('model')
            }
        elif op == 'add_filament':
            filament_id = data.get('id')
            filaments[filament_id] = {
                'type': data.get('type'),
                'color': data.get('color'),
                'total_weight': data.get('total_weight_in_grams'),
                'remaining_weight': data.get('remaining_weight_in_grams')
            }
        elif op == 'add_job':
            job_id = data.get('id')
            jobs[job_id] = data
        elif op == 'update_job_status':
            job_id = data.get('job_id')
            new_status = data.get('status')
            if job_id in jobs:
                jobs[job_id]['status'] = new_status
                if new_status == 'Done':
                    f_id = jobs[job_id]['filament_id']
                    used = jobs[job_id]['print_weight_in_grams']
                    filaments[f_id]['remaining_weight'] = max(0, filaments[f_id]['remaining_weight'] - used)
        
        save_state()

    def validate_printer(data):
        """Validate printer data"""
        required = {'id', 'company', 'model'}
        if not all(k in data for k in required):
            return False, "Missing required fields"
        if data['id'] in printers:
            return False, "Printer ID already exists"
        return True, None

    def validate_filament(data):
        """Validate filament data"""
        required = {'id', 'type', 'color', 'total_weight_in_grams'}
        if not all(k in data for k in required):
            return False, "Missing required fields"
        if data['id'] in filaments:
            return False, "Filament ID already exists"
        if data['type'] not in ['PLA', 'PETG', 'ABS', 'TPU']:
            return False, "Invalid filament type"
        try:
            weight = float(data['total_weight_in_grams'])
            if weight <= 0:
                return False, "Weight must be positive"
            data['total_weight_in_grams'] = weight
            data['remaining_weight_in_grams'] = weight
        except ValueError:
            return False, "Invalid weight value"
        return True, None

    def check_filament_availability(filament_id, required_weight):
        """Check if filament has enough material for print"""
        if filament_id not in filaments:
            return False, "Filament not found"
        
        queued_weight = sum(
            job['print_weight_in_grams']
            for job in jobs.values()
            if job['filament_id'] == filament_id 
            and job['status'] in ['Queued', 'Running']
        )
        
        available = filaments[filament_id]['remaining_weight'] - queued_weight
        if required_weight > available:
            return False, f"Not enough filament. Available: {available}g"
        return True, None

    def validate_job_status_transition(current_status, new_status):
        """Validate job status transitions"""
        valid_transitions = {
            'Queued': ['Running', 'Cancelled'],
            'Running': ['Done', 'Cancelled'],
            'Done': [],
            'Cancelled': []
        }
        return new_status in valid_transitions.get(current_status, [])

    @app.route('/replicate', methods=['POST'])
    def replicate():
        """Handle command replication from leader"""
        data = request.json
        term = data.get('term')
        leader_id = data.get('leader_id')
        command = data.get('command')

        if term < raft_node.term:
            return jsonify({'success': False, 'error': 'Term is outdated'}), 400

        if raft_node.role == 'leader':
            return jsonify({'success': False, 'error': 'Already leader'}), 400

        # First log the command
        log_file = f'log_node_{raft_node.port}.json'
        try:
            with open(log_file, 'r') as f:
                log_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log_data = {"log_entries": []}
        
        log_data["log_entries"].append({
            "term": term,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "command": command
        })
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=4)

        # Then apply the command
        try:
            apply_state_change(command)
            save_state()  # Save to state file
            print(f"[{raft_node.node_id}] ✅ Applied and logged command from leader {leader_id}")
            return jsonify({'success': True}), 200
        except Exception as e:
            print(f"[{raft_node.node_id}] ❌ Failed to apply command: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    def sync_state_with_peers():
        """Sync state with other nodes when becoming leader"""
        if not is_leader():
            return
        
        merged_state = {
            'printers': {},
            'filaments': {},
            'jobs': {}
        }
        
        # First add our own state
        merged_state['printers'].update(printers)
        merged_state['filaments'].update(filaments)
        merged_state['jobs'].update(jobs)
        
        # Then merge with other peers
        for peer in raft_node.peers:
            try:
                host, port = peer
                response = requests.get(f'http://{host}:{port}/state', timeout=2)
                if response.status_code == 200:
                    peer_state = response.json()
                    merged_state['printers'].update(peer_state.get('printers', {}))
                    merged_state['filaments'].update(peer_state.get('filaments', {}))
                    merged_state['jobs'].update(peer_state.get('jobs', {}))
                    print(f"[{raft_node.node_id}] 🔄 Merged state with peer {host}:{port}")
            except Exception as e:
                print(f"[{raft_node.node_id}] ❌ Failed to sync with peer {host}:{port}: {str(e)}")
        
        # Update our state with merged data
        printers.clear()
        filaments.clear()
        jobs.clear()
        printers.update(merged_state['printers'])
        filaments.update(merged_state['filaments'])
        jobs.update(merged_state['jobs'])
        save_state()
        print(f"[{raft_node.node_id}] ✅ State sync complete")

    # Set sync callback in node
    raft_node.set_sync_callback(sync_state_with_peers)

    def is_leader():
        return raft_node.role == 'leader'

    def log_command(command):
        """Log command to node's log file"""
        log_file = f'log_node_{raft_node.port}.json'
        try:
            with open(log_file, 'r') as f:
                log_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log_data = {"log_entries": []}
        
        log_data["log_entries"].append({
            "term": raft_node.term,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "command": command
        })
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=4)

    def apply_command(command):
        """Apply command only after replication"""
        if not is_leader():
            # Followers apply command directly after leader validation
            apply_state_change(command)
            log_command(command)
            return True
        
        # Leader must replicate first
        if raft_node.replicate_command(command):
            apply_state_change(command)
            log_command(command)
            return True
        return False

    @app.route('/state', methods=['GET'])
    def get_state():
        """Endpoint for peers to get state"""
        return jsonify({
            'printers': printers,
            'filaments': filaments,
            'jobs': jobs
        }), 200

    @app.route('/vote', methods=['POST'])
    def vote():
        data = request.json
        term = data.get('term')
        candidate_id = data.get('candidate_id')
        granted = raft_node.receive_vote_request(term, candidate_id)
        return jsonify({'vote_granted': granted}), 200

    @app.route('/heartbeat', methods=['POST'])
    def heartbeat():
        data = request.json
        term = data.get('term')
        leader_id = data.get('leader_id')
        leader_host = data.get('leader_host')
        leader_port = data.get('leader_port')
        raft_node.receive_heartbeat(term, leader_id, leader_host, leader_port)
        return jsonify({'success': True}), 200

    @app.route('/status', methods=['GET'])
    def status():
        return jsonify({
            'node_id': raft_node.node_id,
            'role': raft_node.role,
            'term': raft_node.term,
            'peers': raft_node.peers
        }), 200

    # ------------------ PRINTERS ------------------
    @app.route('/api/v1/printers', methods=['POST'])
    def create_printer():
        if not is_leader():
            return jsonify({'error': 'This node is not the leader'}), 403
        
        data = request.json
        command = {'op': 'add_printer', 'data': data}
        
        if apply_command(command):
            return jsonify({'success': True}), 201
        return jsonify({'error': 'Failed to replicate command'}), 500

    @app.route('/api/v1/printers', methods=['GET'])
    def get_printers():
        return jsonify([
            {'id': pid, **pdata} for pid, pdata in printers.items()
        ]), 200

    # ------------------ FILAMENTS ------------------
    @app.route('/api/v1/filaments', methods=['POST'])
    def create_filament():
        if not is_leader():
            return jsonify({'error': 'This node is not the leader'}), 403
        
        data = request.json
        # Validate input
        if not data.get('id') or data.get('id') in filaments:
            return jsonify({'error': 'Invalid or duplicate filament ID'}), 400
            
        command = {'op': 'add_filament', 'data': data}
        if apply_command(command):
            return jsonify({'success': True}), 201
        return jsonify({'error': 'Failed to replicate command'}), 500

    @app.route('/api/v1/filaments', methods=['GET'])
    def get_filaments():
        return jsonify([
            {'id': fid, **fdata} for fid, fdata in filaments.items()
        ]), 200

    # ------------------ JOBS ------------------
    @app.route('/api/v1/jobs', methods=['POST'])
    def create_job():
        if not is_leader():
            return jsonify({'error': 'This node is not the leader'}), 403

        data = request.json
        job_id = data.get('id')
        printer_id = data.get('printer_id')
        filament_id = data.get('filament_id')
        filepath = data.get('filepath')
        weight = data.get('print_weight_in_grams')

        if not all([job_id, printer_id, filament_id, filepath, weight]):
            return jsonify({'error': 'Missing job parameters'}), 400
        if job_id in jobs:
            return jsonify({'error': 'Job already exists'}), 409
        if printer_id not in printers:
            return jsonify({'error': 'Printer not found'}), 404
        if filament_id not in filaments:
            return jsonify({'error': 'Filament not found'}), 404

        queued_weight = sum(
            job['print_weight_in_grams']
            for job in jobs.values()
            if job['filament_id'] == filament_id and job['status'] in ['Queued', 'Running']
        )
        available = filaments[filament_id]['remaining_weight'] - queued_weight
        if weight > available:
            return jsonify({'error': f'Not enough available filament. Available: {available}g'}), 400

        data['status'] = 'Queued'  # Add initial status
        command = {'op': 'add_job', 'data': data}
        
        if apply_command(command):
            return jsonify({'success': True}), 201
        return jsonify({'error': 'Failed to replicate command'}), 500

    @app.route('/api/v1/jobs', methods=['GET'])
    def get_jobs():
        return jsonify([
            {'id': jid, **jdata} for jid, jdata in jobs.items()
        ]), 200

    @app.route('/api/v1/jobs/<job_id>/status', methods=['POST'])
    def update_job_status(job_id):
        if not is_leader():
            return jsonify({'error': 'This node is not the leader'}), 403
        
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        
        new_status = request.args.get('status', '').capitalize()
        current_status = jobs[job_id]['status']

        if not validate_job_status_transition(current_status, new_status):
            return jsonify({
                'error': f'Invalid transition: {current_status} → {new_status}'
            }), 400

        # Handle filament weight update when job is done
        if new_status == 'Done':
            filament_id = jobs[job_id]['filament_id']
            used_weight = float(jobs[job_id]['print_weight_in_grams'])
            if filament_id in filaments:
                current_weight = float(filaments[filament_id].get('remaining_weight', 
                    filaments[filament_id]['total_weight']))
                # Update remaining weight
                new_remaining = current_weight - used_weight
                filaments[filament_id]['remaining_weight'] = max(0, new_remaining)
                print(f"[{raft_node.node_id}] ⚖️ Updated filament {filament_id} remaining weight: {new_remaining}g (used {used_weight}g)")

        # Update job status and create command
        jobs[job_id]['status'] = new_status
        command = {
            'op': 'update_job_status',
            'data': {
                'job_id': job_id,
                'status': new_status,
                'filament_id': jobs[job_id]['filament_id'],
                'print_weight_in_grams': float(jobs[job_id]['print_weight_in_grams'])
            }
        }
        
        if apply_command(command):
            return jsonify({'success': True}), 200
        return jsonify({'error': 'Failed to update job status'}), 500

    load_state()
    return app
