from flask import Flask, request, jsonify
import os, json

def create_raft_server(raft_node):
    app = Flask(__name__)

    printers = {}
    filaments = {}
    jobs = {}

    STATE_FILE = f"state_{raft_node.node_id}_data.json"

    def save_all_state():
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'printers': printers,
                'filaments': filaments,
                'jobs': jobs
            }, f)
        print(f"[{raft_node.node_id}] 💾 State saved to {STATE_FILE}")

    def load_all_state():
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                printers.update(data.get('printers', {}))
                filaments.update(data.get('filaments', {}))
                jobs.update(data.get('jobs', {}))
            print(f"[{raft_node.node_id}] 📂 State loaded from {STATE_FILE}")

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
        
        save_all_state()

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

        # Apply the replicated command
        try:
            apply_state_change(command)
            print(f"[{raft_node.node_id}] ✅ Applied replicated command from leader {leader_id}")
            return jsonify({'success': True}), 200
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
                    printers.update(peer_state.get('printers', {}))
                    filaments.update(peer_state.get('filaments', {}))
                    jobs.update(peer_state.get('jobs', {}))
                    print(f"[{raft_node.node_id}] 🔄 Synced state with peer {host}:{port}")
            except Exception as e:
                print(f"[{raft_node.node_id}] ❌ Failed to sync with peer {host}:{port}: {str(e)}")
        save_all_state()

    def is_leader():
        return raft_node.role == 'leader'

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
        if not is_leader():
            return jsonify({'error': 'This node is not the leader'}), 403
        data = request.json
        printer_id = data.get('id')
        if not printer_id or printer_id in printers:
            return jsonify({'error': 'Invalid or duplicate printer ID'}), 400

        command = {'op': 'add_printer', 'data': data}
        if raft_node.apply_command(command):
            apply_state_change(command)
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
        filament_id = data.get('id')
        if not filament_id or filament_id in filaments:
            return jsonify({'error': 'Invalid or duplicate filament ID'}), 400
        filaments[filament_id] = {
            'type': data.get('type'),
            'color': data.get('color'),
            'total_weight': data.get('total_weight_in_grams'),
            'remaining_weight': data.get('remaining_weight_in_grams')
        }
        raft_node.apply_command({'op': 'add_filament', 'data': data})
        save_all_state()
        return jsonify({'success': True}), 201

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
        status = 'Queued'

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

        jobs[job_id] = {
            'printer_id': printer_id,
            'filament_id': filament_id,
            'filepath': filepath,
            'print_weight_in_grams': weight,
            'status': status
        }

        raft_node.apply_command({'op': 'add_job', 'data': jobs[job_id]})
        save_all_state()
        return jsonify({'success': True}), 201

    @app.route('/api/v1/jobs', methods=['GET'])
    def get_jobs():
        return jsonify([
            {'id': jid, **jdata} for jid, jdata in jobs.items()
        ]), 200

    @app.route('/api/v1/jobs/<job_id>/status', methods=['PATCH'])
    def update_job_status(job_id):
        if not is_leader():
            return jsonify({'error': 'This node is not the leader'}), 403
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        data = request.json
        new_status = data.get('status', '').capitalize()
        current_status = jobs[job_id]['status']

        valid = {
            'Queued': ['Running', 'Cancelled'],
            'Running': ['Done', 'Cancelled'],
            'Done': [],
            'Cancelled': []
        }
        if new_status not in valid[current_status]:
            return jsonify({'error': f'Invalid transition: {current_status} → {new_status}'}), 400

        jobs[job_id]['status'] = new_status
        if new_status == 'Done':
            f_id = jobs[job_id]['filament_id']
            used = jobs[job_id]['print_weight_in_grams']
            filaments[f_id]['remaining_weight'] = max(0, filaments[f_id]['remaining_weight'] - used)

        raft_node.apply_command({'op': 'update_job_status', 'data': {'job_id': job_id, 'status': new_status}})
        save_all_state()
        return jsonify({'success': True}), 200

    load_all_state()
    return app
