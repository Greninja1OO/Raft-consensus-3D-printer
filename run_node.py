import sys
import json
import signal
from raft.node import RaftNode
from raft.server import create_raft_server
import threading
import time
import atexit
import os

def update_peer_status(host, port, status):
    peers_file = 'config/peers.json'
    try:
        with open(peers_file, 'r') as f:
            peers_data = json.load(f)
        
        # Update status for the specified peer
        for peer in peers_data['peers']:
            if peer['host'] == host and peer['port'] == port:
                peer['status'] = status
                break
        
        with open(peers_file, 'w') as f:
            json.dump(peers_data, f, indent=4)
            print(f"[{node_id}] 📝 Updated peer {host}:{port} status to {status}")
    except Exception as e:
        print(f"[{node_id}] ❌ Error updating peer status: {str(e)}")

def update_leader_info(host, port, node_id):
    """Update the current leader information in peers.json"""
    peers_file = 'config/peers.json'
    try:
        with open(peers_file, 'r') as f:
            peers_data = json.load(f)
        
        peers_data['leader'] = {
            "host": host,
            "port": port,
            "node_id": node_id
        }
        
        with open(peers_file, 'w') as f:
            json.dump(peers_data, f, indent=4)
            print(f"[{node_id}] 👑 Updated leader info: {host}:{port}")
    except Exception as e:
        print(f"[{node_id}] ❌ Error updating leader info: {str(e)}")

def register_peer(node_info):
    peers_file = 'config/peers.json'
    try:
        with open(peers_file, 'r') as f:
            peers_data = json.load(f)
    except FileNotFoundError:
        peers_data = {
            "peers": [],
            "leader": {
                "host": None,
                "port": None,
                "node_id": None
            }
        }
    except json.JSONDecodeError:
        print(f"[{node_id}] ❌ Error: {peers_file} is corrupt. Creating new peers list.")
        peers_data = {
            "peers": [],
            "leader": {
                "host": None,
                "port": None,
                "node_id": None
            }
        }
    
    # Ensure leader field exists
    if 'leader' not in peers_data:
        peers_data['leader'] = {
            "host": None,
            "port": None,
            "node_id": None
        }

    # Create new peer entry
    new_peer = {
        "host": node_info['host'],
        "port": node_info['port'],
        "status": "alive"
    }
    
    # Check if peer already exists
    peer_exists = False
    for peer in peers_data['peers']:
        if peer['host'] == new_peer['host'] and peer['port'] == new_peer['port']:
            peer['status'] = "alive"  # Update existing peer status
            peer_exists = True
            break
    
    if not peer_exists:
        peers_data['peers'].append(new_peer)
    
    try:
        with open(peers_file, 'w') as f:
            json.dump(peers_data, f, indent=4)
        print(f"[{node_id}] ✅ Successfully registered peer: {new_peer}")
    except Exception as e:
        print(f"[{node_id}] ❌ Error writing to {peers_file}: {str(e)}")
    
    # Convert peers to the format expected by RaftNode
    raft_peers = []
    for peer in peers_data['peers']:
        if peer['status'] == 'alive':
            raft_peers.append([peer['host'], peer['port']])
    return raft_peers

def cleanup():
    """Mark node as dead and check if all nodes are dead"""
    try:
        # First mark this node as dead
        update_peer_status(host, port, "dead")
        print(f"\n[{node_id}] 💀 Node marked as dead in peers.json")
        
        # Check if all nodes are dead
        with open('config/peers.json', 'r') as f:
            peers_data = json.load(f)
            
        all_dead = all(peer['status'] == 'dead' for peer in peers_data.get('peers', []))
        if all_dead:
            peers_data['leader'] = {
                "host": None,
                "port": None,
                "node_id": None
            }
            with open('config/peers.json', 'w') as f:
                json.dump(peers_data, f, indent=4)
            print(f"[{node_id}] ⚠️ All nodes are dead, reset leader info")
    except Exception as e:
        print(f"[{node_id}] ❌ Error in cleanup: {str(e)}")

# Register cleanup handler
atexit.register(cleanup)

# Handle SIGINT (Ctrl+C) and SIGTERM
def signal_handler(signum, frame):
    print(f"\n[{node_id}] ⚡ Received termination signal")
    sys.exit(0)  # This will trigger the cleanup handler

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def create_config_file(port):
    """Create a new config file for the given port if it doesn't exist"""
    node_id = f"node_{port}"
    config = {
        "node_id": node_id,
        "host": "127.0.0.1",
        "port": port
    }
    
    config_path = f'config/{node_id}.json'
    os.makedirs('config', exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    return config

def initialize_log_file(port):
    """Initialize or load the log file for the node"""
    log_file = f'log_node_{port}.json'
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f:
            json.dump({"log_entries": []}, f, indent=4)
        print(f"[node_{port}] 📝 Created new log file")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_node.py <port_number>")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)

    # Initialize log file
    initialize_log_file(port)

    node_id = f"node_{port}"
    config_path = f'config/{node_id}.json'

    # Create config if it doesn't exist
    if not os.path.exists(config_path):
        config = create_config_file(port)
        print(f"Created new config file for port {port}")
    else:
        with open(config_path) as f:
            config = json.load(f)

    node_id = config['node_id']
    host = config['host']
    port = config['port']

    # Register this node and get updated peers list
    peers = register_peer({"host": host, "port": port})
    print(f"[{node_id}] 📋 Initial peers list: {peers}")

    # Start Raft node
    raft_node = RaftNode(node_id=node_id, peers=peers, host=host, port=port)

    # Start Flask server
    app = create_raft_server(raft_node)
    threading.Thread(target=lambda: app.run(host=host, port=port), daemon=True).start()

    print(f"[{node_id}] 🚀 Node started with peers: {peers}")
    while True:
        time.sleep(1)

