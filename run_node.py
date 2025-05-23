import sys
import json
import signal
from raft.node import RaftNode
from raft.server import create_raft_server
import threading
import time
import atexit
import os

def create_node_config(port):
    """Create a new node configuration file for the given port"""
    config = {
        "node_id": f"node_{port}",
        "host": "127.0.0.1",
        "port": port
    }
    
    # Create config directory if it doesn't exist
    os.makedirs('config', exist_ok=True)
    
    # Save the configuration
    config_path = f'config/node_{port}.json'
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"[node_{port}] ✨ Created new node configuration at {config_path}")
    return config

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

def register_peer(node_info):
    peers_file = 'config/peers.json'
    try:
        with open(peers_file, 'r') as f:
            peers_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create new peers.json if it doesn't exist or is corrupt
        peers_data = {"peers": []}
        os.makedirs('config', exist_ok=True)
    
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
    # Mark node as dead in peers.json when terminating
    update_peer_status(host, port, "dead")
    print(f"\n[{node_id}] 💀 Node marked as dead in peers.json")

# Register cleanup handler
atexit.register(cleanup)

# Handle SIGINT (Ctrl+C) and SIGTERM
def signal_handler(signum, frame):
    print(f"\n[{node_id}] ⚡ Received termination signal")
    sys.exit(0)  # This will trigger the cleanup handler

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_node.py <port>")
        sys.exit(1)

    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)

    # Try to load existing config or create new one
    config_file = f'config/node_{port}.json'
    try:
        with open(config_file) as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = create_node_config(port)

    node_id = config['node_id']
    host = config['host']
    port = config['port']

    # Register this node and get updated peers list
    peers = register_peer({"host": host, "port": port})
    print(f"[{node_id}] 📋 Initial peers list: {peers}")

    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Start Raft node
    raft_node = RaftNode(node_id=node_id, peers=peers, host=host, port=port)

    # Start Flask server
    app = create_raft_server(raft_node)
    threading.Thread(target=lambda: app.run(host=host, port=port), daemon=True).start()

    print(f"[{node_id}] 🚀 Node started with peers: {peers}")
    while True:
        time.sleep(1)

