from flask import Flask, request, jsonify
import os, json
import requests

def create_raft_server(raft_node):
    app = Flask(__name__)

    STATE_FILE = f"state_{raft_node.node_id}.json"  # Changed to match node state file

    def save_all_state():
        state = {
            'term': raft_node.term,
            'voted_for': raft_node.voted_for,
            'printers': raft_node.printers,
            'filaments': raft_node.filaments,
            'jobs': raft_node.jobs
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
        print(f"[{raft_node.node_id}] 💾 State saved to {STATE_FILE}")

    def load_all_state():
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                raft_node.printers.update(data.get('printers', {}))
                raft_node.filaments.update(data.get('filaments', {}))
                raft_node.jobs.update(data.get('jobs', {}))
            print(f"[{raft_node.node_id}] 📂 State loaded from {STATE_FILE}")

    def apply_state_change(command):
        """Apply a state change from a command"""
        op = command.get('op')
        data = command.get('data', {})

        if op == 'add_printer':
            printer_id = data.get('id')
            raft_node.printers[printer_id] = {
                'company': data.get('company'),
                'model': data.get('model')
            }
        elif op == 'add_filament':
            filament_id = data.get('id')
            raft_node.filaments[filament_id] = {
                'type': data.get('type'),
                'color': data.get('color'),
                'total_weight': data.get('total_weight_in_grams'),
                'remaining_weight': data.get('remaining_weight_in_grams')
            }
        elif op == 'add_job':
            job_id = data.get('id')
            raft_node.jobs[job_id] = {
                'printer_id': data.get('printer_id'),
                'filament_id': data.get('filament_id'),
                'filepath': data.get('filepath'),
                'print_weight_in_grams': data.get('print_weight_in_grams'),
                'status': 'Queued'
            }
        elif op == 'update_job_status':
            job_id = data.get('job_id')
            new_status = data.get('status')
            if job_id in raft_node.jobs:
                raft_node.jobs[job_id]['status'] = new_status
                if new_status == 'Done':
                    f_id = raft_node.jobs[job_id]['filament_id']
                    used = raft_node.jobs[job_id]['print_weight_in_grams']
                    raft_node.filaments[f_id]['remaining_weight'] = max(0, raft_node.filaments[f_id]['remaining_weight'] - used)
        
        raft_node._save_state()

    @app.route('/replicate', methods=['POST'])
    def replicate():
        """Handle command replication from leader"""
        data = request.json
        term = data.get('term')
        leader_id = data.get('leader_id')
        command = data.get('command')
        leader_log_index = data.get('log_index')

        if term < raft_node.term:
            return jsonify({'success': False, 'error': 'Term is outdated'}), 400

        if raft_node.role == 'leader':
            return jsonify({'success': False, 'error': 'Already leader'}), 400

        # Update term if needed
        if term > raft_node.term:
            raft_node.term = term
            raft_node.voted_for = None
            raft_node.role = 'follower'

        # Apply the replicated command and save to log
        try:
            # Save to log first
            raft_node._save_log_entry(command, term)
            
            # Then apply the change
            apply_state_change(command)
            save_all_state()
            
            print(f"[{raft_node.node_id}] ✅ Applied and logged replicated command from leader {leader_id}")
            return jsonify({'success': True, 'log_index': raft_node.log_index}), 200
        except Exception as e:
            print(f"[{raft_node.node_id}] ❌ Failed to apply replicated command: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    def sync_state_with_peers():
        """Sync state with other nodes when becoming leader"""
        if not is_leader():
            return
        
        for peer in raft_node.peers:
            try:
                host, port = peer
                # Get state from each peer
                response = requests.get(f'http://{host}:{port}/state', timeout=2)
                if response.status_code == 200:
                    peer_state = response.json()
                    # Merge state - take most recent updates
                    raft_node.printers.update(peer_state.get('printers', {}))
                    raft_node.filaments.update(peer_state.get('filaments', {}))
                    raft_node.jobs.update(peer_state.get('jobs', {}))
                    print(f"[{raft_node.node_id}] 🔄 Synced state with peer {host}:{port}")
            except Exception as e:
                print(f"[{raft_node.node_id}] ❌ Failed to sync with peer {host}:{port}: {str(e)}")
        save_all_state()

    def is_leader():
        return raft_node.role == 'leader'

    @app.route('/state', methods=['GET'])
    def get_state():
        """Get current state for synchronization"""
        return jsonify({
            'printers': raft_node.printers,
            'filaments': raft_node.filaments,
            'jobs': raft_node.jobs,
            'log_index': raft_node.log_index
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
        raft_node.receive_heartbeat(term)
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
        if not raft_node.role == 'leader':
            return jsonify({'error': 'This node is not the leader'}), 403

        data = request.json
        printer_id = data.get('id')
        if not printer_id or printer_id in raft_node.printers:
            return jsonify({'error': 'Invalid or duplicate printer ID'}), 400

        command = {'op': 'add_printer', 'data': data}
        if raft_node.apply_command(command):
            return jsonify({'success': True}), 201
        return jsonify({'error': 'Failed to replicate command'}), 500

    @app.route('/api/v1/printers', methods=['GET'])
    def get_printers():
        return jsonify([
            {'id': pid, **pdata} for pid, pdata in raft_node.printers.items()
        ]), 200

    # ------------------ FILAMENTS ------------------
    @app.route('/api/v1/filaments', methods=['POST'])
    def create_filament():
        if not raft_node.role == 'leader':
            return jsonify({'error': 'This node is not the leader'}), 403

        data = request.json
        filament_id = data.get('id')
        if not filament_id or filament_id in raft_node.filaments:
            return jsonify({'error': 'Invalid or duplicate filament ID'}), 400

        command = {'op': 'add_filament', 'data': data}
        if raft_node.apply_command(command):
            return jsonify({'success': True}), 201
        return jsonify({'error': 'Failed to replicate command'}), 500

    @app.route('/api/v1/filaments', methods=['GET'])
    def get_filaments():
        return jsonify([
            {'id': fid, **fdata} for fid, fdata in raft_node.filaments.items()
        ]), 200

    # ------------------ JOBS ------------------
    @app.route('/api/v1/jobs', methods=['POST'])
    def create_job():
        if not raft_node.role == 'leader':
            return jsonify({'error': 'This node is not the leader'}), 403

        data = request.json
        job_id = data.get('id')
        printer_id = data.get('printer_id')
        filament_id = data.get('filament_id')
        filepath = data.get('filepath')
        weight = data.get('print_weight_in_grams')

        # Validation checks
        if not all([job_id, printer_id, filament_id, filepath, weight]):
            return jsonify({'error': 'Missing required fields'}), 400
        if job_id in raft_node.jobs:
            return jsonify({'error': 'Job ID already exists'}), 409
        if printer_id not in raft_node.printers:
            return jsonify({'error': 'Printer not found'}), 404
        if filament_id not in raft_node.filaments:
            return jsonify({'error': 'Filament not found'}), 404

        # Check printer availability
        printer_busy = any(
            job['printer_id'] == printer_id and job['status'] in ['Queued', 'Running']
            for job in raft_node.jobs.values()
        )
        if printer_busy:
            return jsonify({'error': 'Printer is currently busy'}), 400

        # Calculate available filament weight
        filament = raft_node.filaments[filament_id]
        queued_weight = sum(
            job['print_weight_in_grams']
            for job in raft_node.jobs.values()
            if job['filament_id'] == filament_id and job['status'] in ['Queued', 'Running']
        )
        available_weight = filament['remaining_weight'] - queued_weight

        if weight > available_weight:
            return jsonify({
                'error': f'Insufficient filament. Available: {available_weight}g, Required: {weight}g'
            }), 400

        # Add job with initial status
        data['status'] = 'Queued'
        command = {'op': 'add_job', 'data': data}
        if raft_node.apply_command(command):
            return jsonify({'success': True}), 201
        return jsonify({'error': 'Failed to replicate command'}), 500

    @app.route('/api/v1/jobs', methods=['GET'])
    def get_jobs():
        return jsonify([
            {'id': jid, **jdata} for jid, jdata in raft_node.jobs.items()
        ]), 200

    @app.route('/api/v1/jobs/<job_id>/status', methods=['PATCH'])
    def update_job_status(job_id):
        if not raft_node.role == 'leader':
            return jsonify({'error': 'This node is not the leader'}), 403
        
        if job_id not in raft_node.jobs:
            return jsonify({'error': 'Job not found'}), 404

        data = request.json
        new_status = data.get('status', '').capitalize()
        current_status = raft_node.jobs[job_id]['status']

        # Define valid state transitions
        valid_transitions = {
            'Queued': ['Running', 'Cancelled'],
            'Running': ['Done', 'Cancelled'],
            'Done': [],
            'Cancelled': []
        }

        if new_status not in valid_transitions.get(current_status, []):
            return jsonify({
                'error': f'Invalid status transition: {current_status} → {new_status}'
            }), 400

        # Check printer availability for 'Running' status
        if new_status == 'Running':
            printer_id = raft_node.jobs[job_id]['printer_id']
            printer_busy = any(
                j['printer_id'] == printer_id and j['status'] == 'Running'
                for jid, j in raft_node.jobs.items()
                if jid != job_id
            )
            if printer_busy:
                return jsonify({'error': 'Printer is currently busy with another job'}), 400

        command = {'op': 'update_job_status', 'data': {'job_id': job_id, 'status': new_status}}
        if raft_node.apply_command(command):
            return jsonify({'success': True}), 200
        return jsonify({'error': 'Failed to replicate command'}), 500

    @app.route('/logs/<int:from_index>', methods=['GET'])
    def get_logs(from_index):
        """Get log entries from a specific index"""
        missing_logs = [
            log for log in raft_node.log_entries 
            if log['index'] >= from_index
        ]
        return jsonify(missing_logs), 200

    def find_current_leader():
        """Find the current leader node by checking each peer"""
        for peer_host, peer_port in raft_node.peers:
            try:
                response = requests.get(f'http://{peer_host}:{peer_port}/status', timeout=1)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('role') == 'leader':
                        return peer_host, peer_port
            except:
                continue
        return None, None

    load_all_state()
    return app
