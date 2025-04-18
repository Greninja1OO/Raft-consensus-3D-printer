# Raft Consensus 3D Printer

A distributed system implementation using Raft consensus protocol for 3D printer management.

## Prerequisites

- Python 3.12 or higher
- Flask
- Requests library

## Installation

1. Install the required Python packages:
```bash
pip install flask requests
```

## Running the System

1. Start the welcome server:
```bash
python welcome_server.py
```
The welcome server will start on `http://127.0.0.1:5100`

2. Start individual Raft nodes:
```bash
python run_node.py node_<id>
```
eg. python run_node.py node_1

Note : Make sure the config file is created.


## Configuration

The system uses configuration files located in the `config/` directory:
- `peers.json`: Contains information about all nodes in the cluster
- `node1.json` to `node5.json`: Individual node configurations

## API Endpoints

The welcome server provides the following endpoints:
- `/NodeStatus` - Get status of all nodes
- `/peers` - Get peer information
- `/leader` - Get current leader information
- `/proxy/<path>` - Proxy requests to the current leader