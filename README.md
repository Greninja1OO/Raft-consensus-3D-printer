# 3D Printer Cluster Manager with Raft Consensus

A distributed system for managing multiple 3D printers using the Raft consensus algorithm. This system provides reliable and consistent operations across a network of 3D printers, with features for printer management, filament tracking, job scheduling, and real-time monitoring through both CLI and web interfaces.

## Features

- **Distributed System Architecture**
  - Raft consensus protocol for leader election and data replication
  - Automatic failover and recovery
  - Consistent state maintenance across nodes
  - Real-time cluster health monitoring

- **Printer Management**
  - Add and track multiple 3D printers
  - Monitor printer status and availability
  - Track printer assignments and workload

- **Filament Management**
  - Track multiple filament types (PLA, PETG, ABS, TPU)
  - Monitor filament inventory and usage
  - Real-time remaining filament calculations
  - Low filament warnings

- **Job Management**
  - Submit and schedule print jobs
  - Track job status and progress
  - Automatic filament usage tracking
  - Job queuing and printer assignment

- **Web Interface**
  - Dashboard with system overview
  - Real-time cluster status monitoring
  - Printer and filament management
  - Job scheduling and monitoring

## System Requirements

- Python 3.12 or higher
- Flask web framework
- Network connectivity between nodes
- Sufficient storage for logs and state

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd Raft-consensus-3D-printer
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Create configuration directory:
```bash
mkdir -p config logs
```

4. Configure the cluster by editing config/peers.json:
```json
{
    "peers": [
        {
            "host": "127.0.0.1",
            "port": 5000,
            "status": "alive"
        },
        {
            "host": "127.0.0.1",
            "port": 5001,
            "status": "alive"
        },
        {
            "host": "127.0.0.1",
            "port": 5002,
            "status": "alive"
        }
    ]
}
```

## Running the System

1. Start the Welcome Server (Entry Point):
```bash
python welcome_server.py
```
The welcome server runs on http://127.0.0.1:5100

2. Start Multiple Raft Nodes:
```bash
python run_node.py 5000
python run_node.py 5001
python run_node.py 5002
```

3. Start the Web Interface:
```bash
python web_gui.py
```
Access the web interface at http://127.0.0.1:5200

4. (Optional) Start the CLI Client:
```bash
python client.py
```

## System Architecture

### Components

1. **Welcome Server (welcome_server.py)**
   - Entry point for client requests
   - Leader discovery and request routing
   - Cluster status monitoring
   - API request proxying

2. **Raft Nodes (raft/node.py)**
   - Implements Raft consensus algorithm
   - Manages distributed state
   - Handles leader election
   - Manages log replication
   - Processes client requests

3. **Web Interface (web_gui.py)**
   - Real-time dashboard
   - Printer management interface
   - Filament tracking
   - Job scheduling and monitoring
   - Cluster status visualization

4. **CLI Client (client.py)**
   - Command-line interface
   - Direct interaction with cluster
   - Job submission and monitoring
   - Resource management

### Data Flow

1. **Client Request Flow**
   - Client → Welcome Server
   - Welcome Server → Current Leader
   - Leader → Followers (replication)
   - Leader → Client (response)

2. **State Replication**
   - Leader receives command
   - Leader appends to log
   - Leader replicates to followers
   - Followers acknowledge
   - Leader commits and responds

3. **Leader Election**
   - Node timeout triggers election
   - Candidate requests votes
   - Majority vote wins
   - New leader syncs state
   - System continues operation

## API Endpoints

### Welcome Server Endpoints
- `GET /NodeStatus` - Get cluster status
- `GET /peers` - List all peers
- `GET /leader` - Get current leader
- `/proxy/<path>` - Proxy to leader

### Node Endpoints
- `POST /api/v1/printers` - Add printer
- `GET /api/v1/printers` - List printers
- `POST /api/v1/filaments` - Add filament
- `GET /api/v1/filaments` - List filaments
- `POST /api/v1/jobs` - Submit job
- `GET /api/v1/jobs` - List jobs
- `PATCH /api/v1/jobs/<id>/status` - Update job

## Fault Tolerance

The system maintains operation as long as a majority of nodes are functional:
- Automatic leader election on failure
- State replication across nodes
- Automatic recovery of failed nodes
- Consistent state maintenance
- Request retry and failover

## Data Persistence

All operations are:
1. Logged to disk before execution
2. Replicated to majority of nodes
3. Committed only after successful replication
4. Recoverable after node restart

## Development

### Project Structure
```
├── client.py           # CLI client
├── web_gui.py         # Web interface
├── welcome_server.py  # Entry point server
├── run_node.py       # Node startup script
├── raft/
│   ├── node.py      # Raft implementation
│   └── server.py    # Node API server
├── config/          # Configuration files
├── logs/           # Operation logs
└── templates/      # Web interface templates
```

### Adding New Features

1. Update the appropriate component:
   - Node logic in raft/node.py
   - API endpoints in raft/server.py
   - Client interface in client.py
   - Web interface in web_gui.py

2. Ensure proper replication:
   - Add command to state machine
   - Implement state changes
   - Update log handling
   - Add API endpoints

3. Update interfaces:
   - Add CLI commands
   - Create web interface components
   - Update documentation

## Troubleshooting

1. **Node Won't Start**
   - Check port availability
   - Verify config/peers.json
   - Check log files

2. **Leader Election Issues**
   - Verify network connectivity
   - Check node timeouts
   - Inspect election logs

3. **State Inconsistency**
   - Check log replication
   - Verify leader status
   - Restart affected nodes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details