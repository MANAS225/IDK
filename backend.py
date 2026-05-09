# Requirements: fastapi, uvicorn
import sqlite3
import hashlib
import time
import threading
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from contextlib import closing

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    init_db()
    t = threading.Thread(target=_alarm_generator_loop, daemon=True)
    t.start()
    yield

app = FastAPI(title="NEXUS IQ HMI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "nexus_iq.db"
SECRET_KEY = "nexus_super_secret"

# 1. Standard DB function for background tasks and startup events
def get_direct_db():
    conn = sqlite3.connect(DB_FILE, timeout=10.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

# 2. Generator DB function specifically for FastAPI endpoints
def get_db():
    conn = get_direct_db()
    try:
        yield conn  
    finally:
        conn.close()

def init_db():
    with closing(get_direct_db()) as conn:
        c = conn.cursor()
        
        # Create tables
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            created_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT UNIQUE,
            expires_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            machineId TEXT,
            status TEXT,
            temperature REAL,
            pressure REAL,
            vibration REAL,
            updated_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            source TEXT,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_by TEXT,
            ack_time TEXT,
            created_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL,
            pressure REAL,
            rpm REAL,
            source TEXT,
            created_at TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            source TEXT,
            event_type TEXT,
            description TEXT
        )''')
        
        # Seed Data
        c.execute('SELECT COUNT(*) FROM users')
        if c.fetchone()[0] == 0:
            pw_hash = hashlib.sha256("password123".encode()).hexdigest()
            c.execute('INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
                      ('Admin', 'admin@hmi.com', pw_hash, 'operator', datetime.now().isoformat()))
                      
        c.execute('SELECT COUNT(*) FROM machines')
        if c.fetchone()[0] == 0:
            machines = [
                ("Extruder A1", "EXT-A1", "Running", 142.5, 45.2, 2.1, datetime.now().isoformat()),
                ("Mixer B2", "MIX-B2", "Idle", 85.0, 14.7, 0.5, datetime.now().isoformat()),
                ("Pump Station C", "PMP-C", "Warning", 95.5, 88.3, 4.2, datetime.now().isoformat()),
                ("Cooling Tower 1", "CLW-1", "Running", 45.2, 35.1, 1.2, datetime.now().isoformat()),
                ("Compressor K1", "CMP-K1", "Running", 88.9, 120.5, 3.8, datetime.now().isoformat()),
                ("Packaging Line 1", "PKG-1", "Fault", 25.4, 14.7, 0.0, datetime.now().isoformat())
            ]
            c.executemany('INSERT INTO machines (name, machineId, status, temperature, pressure, vibration, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)', machines)
            
        c.execute('SELECT COUNT(*) FROM alerts')
        if c.fetchone()[0] == 0:
            alerts = [
                ("CRITICAL", "High temperature detected on Extruder A1", "EXT-A1", 0, None, None, datetime.now().isoformat()),
                ("WARNING", "Vibration levels elevated on Pump Station C", "PMP-C", 0, None, None, datetime.now().isoformat()),
                ("INFO", "Routine maintenance completed on Mixer B2", "MIX-B2", 1, "Admin", datetime.now().isoformat(), datetime.now().isoformat()),
                ("CRITICAL", "Pressure drop in Cooling Tower 1", "CLW-1", 0, None, None, datetime.now().isoformat()),
                ("WARNING", "Packaging Line 1 sensor communication error", "PKG-1", 0, None, None, datetime.now().isoformat())
            ]
            c.executemany('INSERT INTO alerts (level, message, source, acknowledged, acknowledged_by, ack_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', alerts)
            
        conn.commit()

# ── Background alarm generator ───────────────────────────────────────────────
def _alarm_generator_loop():
    """Runs every 5s. Reads latest sensor reading and inserts alerts
    for threshold breaches, deduplicating against last 60s."""
    while True:
        time.sleep(5)
        try:
            with closing(get_direct_db()) as conn:
                c = conn.cursor()

                # Latest sensor reading
                c.execute("SELECT temperature, pressure, rpm FROM sensor_readings ORDER BY created_at DESC LIMIT 1")
                row = c.fetchone()
                if not row:
                    continue

                temp, pres, rpm = row["temperature"], row["pressure"], row["rpm"]
                cutoff = (datetime.now() - timedelta(seconds=60)).isoformat()

                checks = []
                if temp > 130:
                    checks.append(("CRITICAL", f"High temperature: {temp:.1f}°C exceeds 130°C threshold", "sensor-auto"))
                if pres < 60:
                    checks.append(("CRITICAL", f"Low pressure: {pres:.1f} PSI below 60 PSI threshold", "sensor-auto"))
                if rpm > 2000:
                    checks.append(("CRITICAL", f"High RPM: {rpm:.0f} exceeds 2000 RPM threshold", "sensor-auto"))

                now = datetime.now().isoformat()
                for level, message, source in checks:
                    # Deduplicate: skip if identical unacknowledged alert exists in last 60s
                    c.execute(
                        "SELECT id FROM alerts WHERE level=? AND source=? AND acknowledged=0 AND created_at>?",
                        (level, source, cutoff)
                    )
                    if c.fetchone() is None:
                        c.execute(
                            "INSERT INTO alerts (level, message, source, acknowledged, created_at) VALUES (?, ?, ?, 0, ?)",
                            (level, message, source, now)
                        )

                conn.commit()
        except Exception as e:
            print(f"Background Alarm Error: {e}")

# Models
class LoginReq(BaseModel):
    email: str
    password: str

class RegisterReq(BaseModel):
    name: str
    email: str
    password: str
    role: str

class AckReq(BaseModel):
    alert_id: int
    acknowledged_by: str

class MachineUpdateReq(BaseModel):
    status: str
    temperature: float
    pressure: float
    vibration: float

class IngestReq(BaseModel):
    temperature: float
    pressure: float
    rpm: float
    source: str

class AlertIngestReq(BaseModel):
    level: str
    message: str
    source: str

class EventIngestReq(BaseModel):
    source: str
    event_type: str
    description: str

def get_current_user(
    authorization: Optional[str] = Header(None),
    conn: sqlite3.Connection = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ")[1]
    
    c = conn.cursor()
    c.execute("SELECT u.id, u.name, u.email, u.role, s.expires_at FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = ?", (token,))
    row = c.fetchone()
    
    if not row:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    if datetime.fromisoformat(row["expires_at"]) < datetime.now():
        raise HTTPException(status_code=401, detail="Token expired")
        
    return dict(row)

# Endpoints
@app.post("/api/auth/login")
def login(req: LoginReq, conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    c.execute("SELECT id, name, role FROM users WHERE email = ? AND password_hash = ?", (req.email, pw_hash))
    user = c.fetchone()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
        
    token_str = req.email + SECRET_KEY + str(time.time())
    token = hashlib.sha256(token_str.encode()).hexdigest()[:32]
    expires = (datetime.now() + timedelta(hours=8)).isoformat()
    
    c.execute("INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)", (user["id"], token, expires))
    conn.commit()
    
    return {"token": token, "user": {"name": user["name"], "role": user["role"]}}

@app.post("/api/auth/register", status_code=201)
def register(req: RegisterReq, conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    
    c.execute("SELECT id FROM users WHERE email = ?", (req.email,))
    if c.fetchone():
        raise HTTPException(status_code=400, detail="Email already exists")
        
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    c.execute("INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
              (req.name, req.email, pw_hash, req.role, datetime.now().isoformat()))
    conn.commit()
    return {"message": "User registered successfully"}

@app.get("/api/data/machines")
def get_machines(user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    c.execute("SELECT * FROM machines")
    rows = c.fetchall()
    return [dict(r) for r in rows]

@app.put("/api/data/machines/{machineId}")
def update_machine(machineId: str, req: MachineUpdateReq, user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "UPDATE machines SET status = ?, temperature = ?, pressure = ?, vibration = ?, updated_at = ? WHERE machineId = ?",
        (req.status, req.temperature, req.pressure, req.vibration, now, machineId)
    )
    conn.commit()
    return {"message": "Machine updated", "updated_at": now}

@app.get("/api/data/alerts")
def get_alerts(user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    c.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 50")
    rows = c.fetchall()
    return [dict(r) for r in rows]

@app.post("/api/data/alerts/acknowledge")
def ack_alert(req: AckReq, user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE alerts SET acknowledged = 1, acknowledged_by = ?, ack_time = ? WHERE id = ?", (req.acknowledged_by, now, req.alert_id))
    conn.commit()
    return {"message": "Alert acknowledged"}

@app.get("/api/sensor/live")
def get_live_sensor(user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    c.execute("SELECT * FROM sensor_readings ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    return dict(row) if row else {}

@app.post("/api/sensor/ingest")
def ingest_sensor(req: IngestReq, conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    c.execute("INSERT INTO sensor_readings (temperature, pressure, rpm, source, created_at) VALUES (?, ?, ?, ?, ?)",
              (req.temperature, req.pressure, req.rpm, req.source, datetime.now().isoformat()))
    conn.commit()
    return {"message": "Reading ingested"}

@app.post("/api/data/alerts/ingest")
def ingest_alert(req: AlertIngestReq, conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO alerts (level, message, source, acknowledged, created_at) VALUES (?, ?, ?, 0, ?)",
        (req.level, req.message, req.source, now)
    )
    alert_id = c.lastrowid
    conn.commit()
    return {"id": alert_id, "created_at": now}

@app.get("/api/data/alerts/stats")
def get_alert_stats(user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0")
    unacknowledged = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 1")
    acknowledged = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM alerts WHERE level = 'SUPPRESSED'")
    suppressed = c.fetchone()[0]

    cutoff_24h = (datetime.now() - timedelta(hours=24)).isoformat()
    c.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 1 AND ack_time > ?", (cutoff_24h,))
    cleared_today = c.fetchone()[0]


    return {
        "unacknowledged": unacknowledged,
        "acknowledged": acknowledged,
        "suppressed": suppressed,
        "cleared_today": cleared_today
    }
@app.get("/api/events")
def get_events(limit: int = 50, user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    c.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    return [dict(r) for r in rows]

@app.post("/api/events/ingest", status_code=201)
def ingest_event(req: EventIngestReq, conn: sqlite3.Connection = Depends(get_db)):
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO events (timestamp, source, event_type, description) VALUES (?, ?, ?, ?)",
        (now, req.source, req.event_type, req.description)
    )
    conn.commit()
    return {"id": c.lastrowid}

@app.get("/")
def health_check():
    return {"status": "ok", "service": "NEXUS IQ Backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)