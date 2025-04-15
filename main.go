package main

import (
    "database/sql"
    "fmt"
    "log"
    "math/rand"
    "net/http"
    "os"
    "os/signal"
    "sync"
    "sync/atomic"
    "syscall"
    "time"
    _ "github.com/go-sql-driver/mysql"
)

var (
    dataStore = make(map[string]string)
    mu        sync.Mutex
    votedFor       string
    isLeader       bool
    lastHeartbeatTime time.Time
    leaderHeartbeat sync.Mutex
    currentTerm    int
    nodeTimer  *time.Timer
    HEARTBEAT_INTERVAL = 5 * time.Second    // Leader heartbeat interval
    INITIAL_TIMEOUT_MIN = 5 * time.Second  // Min timeout for first vote
    INITIAL_TIMEOUT_MAX = 30 * time.Second // Max timeout for first vote
    FOLLOWER_TIMEOUT_MIN = 20 * time.Second // Min timeout for followers
    FOLLOWER_TIMEOUT_MAX = 30 * time.Second // Max timeout for followers
    db        *sql.DB
    httpCode  string
)

func resetNodeTimer() {
    if nodeTimer != nil {
        nodeTimer.Stop()
    }

    var timeout time.Duration
    if votedFor == "" {
        // First vote - use initial timeout (5-30s)
        timeout = INITIAL_TIMEOUT_MIN +
            time.Duration(rand.Int63n(int64(INITIAL_TIMEOUT_MAX-INITIAL_TIMEOUT_MIN)))
    } else {
        // Subsequent timeouts (20-30s)
        timeout = FOLLOWER_TIMEOUT_MIN +
            time.Duration(rand.Int63n(int64(FOLLOWER_TIMEOUT_MAX-FOLLOWER_TIMEOUT_MIN)))
    }
    
    nodeTimer = time.AfterFunc(timeout, startHeartbeatProcess)
    log.Printf("Node timeout set to: %v", timeout)
}

func startHeartbeatProcess() {
    mu.Lock()
    // If we haven't received heartbeat from leader, become candidate
    if !isLeader {
        currentTerm++  // Increment term when becoming candidate
        votedFor = httpCode  // Vote for self
        log.Printf("Leader timeout detected. Becoming candidate for term %d", currentTerm)
        go sendInitialHeartbeat(db, httpCode)  // Start election
    }
    mu.Unlock()
}

func cleanup(db *sql.DB, httpCode string) {
    _, err := db.Exec("DELETE FROM Raftservers.servers_use WHERE http_localhost_code = ?", httpCode)
    if err != nil {
        log.Printf("Error cleaning up servers_use table: %v", err)
    }
    log.Println("Cleaned up database entries")
}

func main() {
    dsn := "root:Sanj@1904@tcp(127.0.0.1:3306)/"
    fmt.Print("Enter server code (e.g., http://localhost:8080): ")
    fmt.Scanln(&httpCode)

    if httpCode == "" {
        log.Fatal("Server code cannot be empty")
    }

    var err error
    db, err = sql.Open("mysql", dsn)
    if (err != nil) {
        log.Fatalf("Error connecting to MySQL: %v", err)
    }
    defer db.Close()

    _, err = db.Exec("CREATE DATABASE IF NOT EXISTS Raftservers")
    if err != nil {
        log.Fatalf("Error creating database: %v", err)
    }

    createServersUseTableQuery := `
    CREATE TABLE IF NOT EXISTS Raftservers.servers_use (
        id INT AUTO_INCREMENT,
        http_localhost_code VARCHAR(255) NOT NULL UNIQUE,
        PRIMARY KEY (id)
    ) ENGINE=InnoDB AUTO_INCREMENT=1;`
    
    _, err = db.Exec(createServersUseTableQuery)
    if err != nil {
        log.Fatalf("Error creating servers_use table: %v", err)
    }

    var exists bool
    err = db.QueryRow("SELECT EXISTS(SELECT 1 FROM Raftservers.servers_use WHERE http_localhost_code = ?)", httpCode).Scan(&exists)
    if err != nil {
        log.Fatalf("Error checking server existence: %v", err)
    }

    if exists {
        log.Fatalf("Server %s is already running", httpCode)
    }

    _, err = db.Exec("INSERT INTO Raftservers.servers_use (http_localhost_code) VALUES (?)", httpCode)
    if err != nil {
        log.Fatalf("Error inserting into servers_use table: %v", err)
    }
    fmt.Printf("Added server %s to servers_use table\n", httpCode)

    resetNodeTimer()

    fmt.Printf("Starting HTTP server at %s...\n", httpCode)
    http.HandleFunc("/heartbeat", func(w http.ResponseWriter, r *http.Request) {
        heartbeatHandler(w, r, httpCode)
    })

    go sendHeartbeats(db, httpCode)

    signalChan := make(chan os.Signal, 1)
    signal.Notify(signalChan, os.Interrupt, syscall.SIGTERM)

    go func() {
        <-signalChan
        fmt.Println("\nReceived an interrupt, cleaning up...")
        cleanup(db, httpCode)
        os.Exit(0)
    }()

    log.Fatal(http.ListenAndServe(httpCode[7:], nil))
}

func heartbeatHandler(w http.ResponseWriter, r *http.Request, currentServer string) {
    if r.Method != http.MethodPost {
        http.Error(w, "Invalid request method", http.StatusMethodNotAllowed)
        return
    }

    sender := r.URL.Query().Get("sender")
    if sender == "" {
        http.Error(w, "Sender is required", http.StatusBadRequest)
        return
    }

    senderTerm := r.URL.Query().Get("term")
    if senderTerm == "" {
        http.Error(w, "Term is required", http.StatusBadRequest)
        return
    }
    termNum := 0
    fmt.Sscanf(senderTerm, "%d", &termNum)

    mu.Lock()
    defer mu.Unlock()

    if termNum < currentTerm {
        log.Printf("Rejecting heartbeat from %s with lower term %d (our term: %d)", 
            sender, termNum, currentTerm)
        fmt.Fprintln(w, "Negative")
        return
    }

    // Step down if we see higher term
    if termNum > currentTerm {
        if isLeader {
            log.Printf("Stepping down: discovered higher term %d", termNum)
            isLeader = false
        }
        currentTerm = termNum
        votedFor = "" // Reset vote for higher term
    }

    // If we're getting heartbeat from valid leader
    if sender == votedFor && !isLeader {
        resetNodeTimer() // Reset timeout when receiving heartbeat from leader
        log.Printf("Term: %d | Server: %s | Leader: %s", 
            currentTerm, currentServer, sender)
        fmt.Fprintln(w, "Positive")
        return
    }

    // If we're a candidate or haven't voted
    if votedFor == "" || votedFor == currentServer {
        votedFor = sender
        log.Printf("Voting for %s in term %d", votedFor, currentTerm)
        fmt.Fprintln(w, "Positive")
        resetNodeTimer()
    } else {
        fmt.Fprintln(w, "Negative")
    }
}

func sendHeartbeats(db *sql.DB, currentServer string) {
    for {
        mu.Lock()
        hasLeader := (votedFor != "")  // Check if we've voted for a leader
        isCurrentLeader := isLeader    // Store current leader status
        mu.Unlock()

        if isCurrentLeader {
            sendHeartbeatToAll(db, currentServer)
            time.Sleep(HEARTBEAT_INTERVAL)
        } else if hasLeader {
            // If we've voted for a leader but aren't the leader, just wait
            time.Sleep(time.Second)
        } else {
            // Not voted for anyone yet, continue normal operation
            time.Sleep(time.Second)
        }
    }
}

func sendHeartbeatToAll(db *sql.DB, currentServer string) {
    rows, err := db.Query("SELECT http_localhost_code FROM Raftservers.servers_use WHERE http_localhost_code != ?", currentServer)
    if err != nil {
        log.Printf("Error retrieving servers for heartbeat: %v", err)
        time.Sleep(time.Duration(rand.Intn(int(FOLLOWER_TIMEOUT_MAX.Seconds()-FOLLOWER_TIMEOUT_MIN.Seconds()))+int(FOLLOWER_TIMEOUT_MIN.Seconds())) * time.Second)
        return
    }

    servers := make([]string, 0)
    deadservers := make([]string, 0)
    for rows.Next() {
        var server string
        if err := rows.Scan(&server); err != nil {
            log.Printf("Error scanning server: %v", err)
            continue
        }
        servers = append(servers, server)
    }
    rows.Close()

    majority := (len(servers) + 1) / 2

    var voteCount int32 = 1
    var wg sync.WaitGroup

    for _, server := range servers {
        wg.Add(1)
        go func(server string) {
            defer wg.Done()
            resp, err := http.Post(
                fmt.Sprintf("%s/heartbeat?sender=%s&term=%d", 
                    server, currentServer, currentTerm),
                "application/json", 
                nil)
            if err != nil {
                log.Printf("Error sending heartbeat to %s: %v", server, err)
                return
            }
            defer resp.Body.Close()

            var response string
            fmt.Fscan(resp.Body, &response)

            if isLeader {
                log.Printf("Term: %d | Server: %s | Heartbeat to: %s", 
                    currentTerm, currentServer, server)
            } else {
                // Only track votes if not leader
                if len(server)
                if response == "Positive" {
                    atomic.AddInt32(&voteCount, 1)
                    log.Printf("Vote count updated: %d", atomic.LoadInt32(&voteCount))
                    
                    if atomic.LoadInt32(&voteCount) > int32(majority) {
                        mu.Lock()
                        if (!isLeader) {
                            isLeader = true
                            log.Println("This server has become the leader! Starting frequent heartbeats.")
                        }
                        mu.Unlock()
                    }
                }
            }
        }(server)
    }

    wg.Wait()

    if isLeader {
        time.Sleep(HEARTBEAT_INTERVAL)
    }
}

func sendInitialHeartbeat(db *sql.DB, currentServer string) {
    sendHeartbeatToAll(db, currentServer)
}