# Raft Consensus 3D Printer Manager

A distributed system implementation using the Raft consensus protocol for managing multiple 3D printers. This system ensures reliable and consistent operation of 3D printers across a network, with features for printer management, filament tracking, and print job scheduling.

## Features

- **Distributed Consensus**: Uses Raft protocol for leader election and state replication
- **Printer Management**: Add and track multiple 3D printers
- **Filament Tracking**: Monitor filament usage and availability
- **Job Management**: Schedule and monitor print jobs
- **Automatic Recovery**: Handles node failures and network partitions
- **State Synchronization**: Maintains consistent state across all nodes

## Prerequisites

- Python 3.12 or higher
- Required Python packages:
  - Flask
  - Requests

## Installation

1. Clone the repository
2. Install the required Python packages:
```bash
pip install flask requests
```

## Configuration

The system uses JSON configuration files in the `config/` directory:
- `peers.json`: Contains information about all nodes in the cluster
- Individual node configurations are created automatically when nodes start

## Running the System

1. Start the welcome server (handles client requests and routes to leader):
```bash
python welcome_server.py
```
The welcome server will start on `http://127.0.0.1:5100`

2. Start multiple Raft nodes (each representing a cluster member):
```bash
python run_node.py 5001
python run_node.py 5002
python run_node.py 5003
```
Replace port numbers as needed. At least 3 nodes are recommended for fault tolerance.

3. Run the client interface:
```bash
python client.py
```

## API Endpoints

### Welcome Server Endpoints
- `GET /NodeStatus` - Get status of all nodes
- `GET /peers` - Get peer information
- `GET /leader` - Get current leader information
- `/proxy/<path>` - Proxy requests to current leader

### Node Endpoints
- `POST /api/v1/printers` - Add a new printer
- `GET /api/v1/printers` - List all printers
- `POST /api/v1/filaments` - Add new filament
- `GET /api/v1/filaments` - List all filaments
- `POST /api/v1/jobs` - Submit a print job
- `GET /api/v1/jobs` - List all jobs
- `PATCH /api/v1/jobs/<job_id>/status` - Update job status

## Client Usage

The client provides an interactive interface for:
1. Adding and listing printers
2. Managing filament inventory
3. Submitting and monitoring print jobs
4. Updating job statuses

## System Architecture

- **Welcome Server**: Entry point for client requests
- **Raft Nodes**: Cluster members that maintain consensus
- **Client**: Interface for interacting with the system

Each node maintains:
- Log of all operations
- Current state (printers, filaments, jobs)
- Raft consensus state (term, role, etc.)

## Fault Tolerance

The system can continue operating as long as a majority of nodes are functional. Features:
- Automatic leader election
- State replication across nodes
- Automatic recovery of failed nodes
- Consistent state maintenance

## Data Persistence

All operations are:
1. Logged to disk
2. Replicated across nodes
3. Automatically recovered after node restarts

## Error Handling

The system handles various failure scenarios:
- Node failures
- Network partitions
- Request timeouts
- State inconsistencies

## Development Status

This is a functional distributed system implementation suitable for managing multiple 3D printers in a networked environment.