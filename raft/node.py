import time
import threading
import requests
import random
import os
import json

class RaftNode:
    def __init__(self, node_id, peers, host, port):
        self.node_id = node_id
        self.peers = [[p[0], p[1]] if isinstance(p, tuple) else p for p in peers]  # Convert any tuples to lists
        self.host = host
        self.port = port
        self.role = 'follower'
        self.term = 0
        self.voted_for = None
        self.votes_received = 0

        self.heartbeat_enabled = True
        self.state_file = f"state_{self.node_id}.json"
        self._load_state()

        self.last_heartbeat = time.time()
        self.election_timeout_range = (5, 10)
        self.reset_election_timeout()

        self.lock = threading.Lock()
        self.discovery_interval = 30  # seconds between peer discovery attempts

        # Start election thread
        self.election_thread = threading.Thread(target=self._run_election)
        self.election_thread.daemon = True
        self.election_thread.start()

        # Start peer discovery thread
        self.discovery_thread = threading.Thread(target=self._run_peer_discovery)
        self.discovery_thread.daemon = True
        self.discovery_thread.start()

    def reset_election_timeout(self):
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(*self.election_timeout_range)

    def _load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                self.term = data.get('term', 0)
                self.voted_for = data.get('voted_for', None)
                # Initialize data structures
                self.printers = data.get('printers', {})
                self.filaments = data.get('filaments', {})
                self.jobs = data.get('jobs', {})
        else:
            self.printers = {}
            self.filaments = {}
            self.jobs = {}

    def _save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump({
                'term': self.term,
                'voted_for': self.voted_for,
                'printers': self.printers,
                'filaments': self.filaments,
                'jobs': self.jobs
            }, f, indent=4)
        print(f"[{self.node_id}] 💾 State saved to {self.state_file}")

    def _get_alive_peers(self):
        """Get list of peers that are marked as alive in peers.json"""
        try:
            with open('config/peers.json', 'r') as f:
                peers_data = json.load(f)
                alive_peers = []
                for peer in peers_data.get('peers', []):
                    if (peer.get('status') == 'alive' and 
                        not (peer['port'] == self.port and peer['host'] == self.host)):
                        alive_peers.append([peer['host'], peer['port']])
                return alive_peers
        except Exception as e:
            print(f"[{self.node_id}] ❌ Error reading peers.json: {str(e)}")
            return self.peers

    def _run_election(self):
        while True:
            time.sleep(0.5)
            with self.lock:
                if self.role != 'leader' and time.time() - self.last_heartbeat > self.election_timeout:
                    print(f"[{self.node_id}] ⚠️ Starting election (no heartbeat in {round(self.election_timeout, 2)}s)")
                    self.term += 1
                    self.role = 'candidate'
                    self.voted_for = self.node_id
                    self.votes_received = 1
                    self._save_state()

                    current_peers = self._get_alive_peers()
                    for peer_host, peer_port in current_peers:
                        try:
                            res = requests.post(f'http://{peer_host}:{peer_port}/vote', json={
                                'term': self.term,
                                'candidate_id': self.node_id
                            }, timeout=1)
                            if res.status_code == 200 and res.json().get('vote_granted'):
                                self.votes_received += 1
                                print(f"[{self.node_id}] ✓ Received vote from {peer_host}:{peer_port}")
                        except Exception:
                            print(f"[{self.node_id}] ❌ Failed to get vote from {peer_host}:{peer_port}")
                            self._mark_peer_dead(peer_host, peer_port)

                    total_alive_nodes = len(current_peers) + 1  # Include self
                    if self.votes_received > total_alive_nodes // 2:
                        print(f"[{self.node_id}] 👑 Elected as leader for term {self.term}")
                        self.role = 'leader'
                        self._start_heartbeat()
                    else:
                        print(f"[{self.node_id}] 🔄 Election failed, returning to follower state")
                        self.role = 'follower'

                    self.reset_election_timeout()

    def _start_heartbeat(self):
        def heartbeat_loop():
            while self.role == 'leader':
                if self.heartbeat_enabled:
                    current_peers = self._get_alive_peers()
                    for peer_host, peer_port in current_peers:
                        try:
                            requests.post(f'http://{peer_host}:{peer_port}/heartbeat', json={
                                'term': self.term,
                                'leader_id': self.node_id
                            }, timeout=1)
                            print(f"[{self.node_id}] 💗 Heartbeat sent to {peer_host}:{peer_port}")
                        except Exception:
                            print(f"[{self.node_id}] ⚠️ Failed to reach {peer_host}:{peer_port}")
                            self._mark_peer_dead(peer_host, peer_port)
                time.sleep(2)
        threading.Thread(target=heartbeat_loop, daemon=True).start()

    def _mark_peer_dead(self, host, port):
        """Mark a peer as dead in peers.json when it's unreachable"""
        try:
            with open('config/peers.json', 'r') as f:
                peers_data = json.load(f)
            
            # Update status for the unreachable peer
            for peer in peers_data.get('peers', []):
                if peer['host'] == host and peer['port'] == port and peer['status'] != 'dead':
                    peer['status'] = 'dead'
                    print(f"[{self.node_id}] 💀 Marked peer {host}:{port} as dead")
                    with open('config/peers.json', 'w') as f:
                        json.dump(peers_data, f, indent=4)
                    break
        except Exception as e:
            print(f"[{self.node_id}] ❌ Error marking peer as dead: {str(e)}")

    def receive_heartbeat(self, term):
        with self.lock:
            if term >= self.term:
                if self.role != 'follower':
                    print(f"[{self.node_id}] ⬇️ Stepping down to follower (term {term})")
                self.term = term
                self.role = 'follower'
                self.voted_for = None
                self.reset_election_timeout()
                print(f"[{self.node_id}] 💗 Heartbeat received (term {term})")

    def receive_vote_request(self, term, candidate_id):
        with self.lock:
            if term > self.term:
                self.term = term
                self.voted_for = None
                self.role = 'follower'

            if self.voted_for is None and term == self.term:
                self.voted_for = candidate_id
                self._save_state()
                self.reset_election_timeout()
                print(f"[{self.node_id}] 🗳️ Voted for {candidate_id} (term {term})")
                return True
            return False

    def replicate_command(self, command):
        """Replicate a command to all followers"""
        if self.role != 'leader':
            return False
            
        success_count = 1  # Count self
        current_peers = self._get_alive_peers()
        
        for peer_host, peer_port in current_peers:
            try:
                response = requests.post(
                    f'http://{peer_host}:{peer_port}/replicate',
                    json={
                        'term': self.term,
                        'leader_id': self.node_id,
                        'command': command
                    },
                    timeout=2
                )
                if response.status_code == 200:
                    success_count += 1
                    print(f"[{self.node_id}] ✅ Command replicated to {peer_host}:{peer_port}")
                else:
                    print(f"[{self.node_id}] ❌ Failed to replicate to {peer_host}:{peer_port}")
            except Exception as e:
                print(f"[{self.node_id}] ❌ Error replicating to {peer_host}:{peer_port}: {str(e)}")
                self._mark_peer_dead(peer_host, peer_port)
        
        # Command is successful if majority of nodes acknowledge it
        return success_count > (len(current_peers) + 1) // 2

    def apply_command(self, command):
        """Apply a command and replicate it to followers if leader"""
        print(f"[{self.node_id}] ⚙️ Applying command: {command}")
        
        # Apply the change locally
        self._apply_state_change(command)
        
        if self.role == 'leader':
            if self.replicate_command(command):
                print(f"[{self.node_id}] ✅ Command successfully replicated to majority")
                return True
            else:
                print(f"[{self.node_id}] ❌ Failed to replicate command to majority")
                return False
        return True

    def _apply_state_change(self, command):
        """Apply a state change from a command"""
        op = command.get('op')
        data = command.get('data', {})

        if op == 'add_printer':
            printer_id = data.get('id')
            self.printers[printer_id] = {
                'company': data.get('company'),
                'model': data.get('model')
            }
        elif op == 'add_filament':
            filament_id = data.get('id')
            self.filaments[filament_id] = {
                'type': data.get('type'),
                'color': data.get('color'),
                'total_weight': data.get('total_weight_in_grams'),
                'remaining_weight': data.get('remaining_weight_in_grams')
            }
        elif op == 'add_job':
            job_id = data.get('id')
            self.jobs[job_id] = data
        elif op == 'update_job_status':
            job_id = data.get('job_id')
            new_status = data.get('status')
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = new_status
                if new_status == 'Done':
                    f_id = self.jobs[job_id]['filament_id']
                    used = self.jobs[job_id]['print_weight_in_grams']
                    self.filaments[f_id]['remaining_weight'] = max(0, self.filaments[f_id]['remaining_weight'] - used)
        
        self._save_state()

    def _run_peer_discovery(self):
        while True:
            try:
                self.peers = self._get_alive_peers()
                print(f"[{self.node_id}] 📡 Updated peers list: {self.peers}")
            except Exception as e:
                print(f"[{self.node_id}] ❌ Error updating peers: {str(e)}")
            time.sleep(self.discovery_interval)
