from flask import Flask, jsonify, request
import requests
import json

app = Flask(__name__)

def load_peers():
    """Load peer information from peers.json"""
    with open('config/peers.json', 'r') as f:
        return json.load(f)

def find_current_leader():
    """Find the current leader node by checking each peer"""
    peers_data = load_peers()
    for peer in peers_data['peers']:
        if peer['status'] != 'alive':
            continue
        try:
            response = requests.get(
                f"http://{peer['host']}:{peer['port']}/status",
                timeout=1
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('role') == 'leader':
                    return {
                        'host': peer['host'],
                        'port': peer['port'],
                        'node_id': data['node_id']
                    }
        except:
            continue
    return None



@app.route('/NodeStatus', methods=['GET'])
def get_status():
    """Endpoint to get the status of the nodes"""
    peers_data = load_peers()
    leader = find_current_leader()

    status = {
        'success': True,
        'leader': leader,
        'peers': peers_data['peers']
    }

    return jsonify(status), 200

@app.route('/peers', methods=['GET'])
def get_peers():
    """Endpoint to get peer information"""
    peers_data = load_peers()
    return jsonify({
        'success': True,
        'peers': peers_data['peers']
    }), 200

@app.route('/leader', methods=['GET'])
def get_leader():
    """Endpoint to get current leader information"""
    leader = find_current_leader()
    if leader:
        return jsonify({
            'success': True,
            'leader': leader
        }), 200
    return jsonify({
        'success': False,
        'error': 'No leader found'
    }), 404

@app.route('/proxy/<path:subpath>', methods=['GET', 'POST', 'PATCH'])
def proxy_to_leader(subpath):
    """Proxy all API requests to the current leader"""
    leader = find_current_leader()
    if not leader:
        return jsonify({
            'success': False,
            'error': 'No leader found'
        }), 404
    
    try:
        leader_url = f"http://{leader['host']}:{leader['port']}/{subpath}"
        timeout = 5  # 5 seconds timeout for all requests
        
        if request.method == 'GET':
            response = requests.get(leader_url, timeout=timeout)
        elif request.method == 'POST':
            response = requests.post(leader_url, json=request.json, timeout=timeout)
        elif request.method == 'PATCH':
            response = requests.patch(leader_url, json=request.json, timeout=timeout)
        
        try:
            return jsonify(response.json()), response.status_code
        except ValueError:
            # Handle case where response is not JSON
            return response.text, response.status_code
            
    except requests.Timeout:
        return jsonify({
            'success': False,
            'error': 'Request to leader timed out'
        }), 504  # Gateway Timeout
    except requests.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Could not connect to leader'
        }), 502  # Bad Gateway
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to forward request to leader: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5100)