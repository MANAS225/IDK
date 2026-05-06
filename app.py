import dash
from dash import dcc, html, Input, Output, callback, State, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import random
from datetime import datetime, timedelta
from collections import deque
import plotly.graph_objs as go
import requests
import base64

# --- HMI Design Principles ---
NORMAL_COLOR   = "#00E676"
WARNING_COLOR  = "#FFB300"
CRITICAL_COLOR = "#EF5350"
INFO_COLOR     = "#26C6DA"
BACKGROUND_COLOR = "var(--bg-primary)"
TEXT_COLOR     = "var(--text-primary)"
CARD_BACKGROUND  = "var(--bg-card)"
ACCENT_COLOR   = "#00E676"
BORDER_COLOR   = "var(--border-color)"
SUCCESS_COLOR  = "#00E676"
SURFACE_COLOR  = "var(--bg-surface)"

# --- Backend Configuration ---
BACKEND_URL = "http://localhost:8000"
_backend_status = {"available": None, "last_check": None}

def is_backend_available():
    now = datetime.now()
    if (_backend_status["last_check"] is None or
        (now - _backend_status["last_check"]).total_seconds() > 30):
        try:
            r = requests.get(f"{BACKEND_URL}/", timeout=0.5)
            _backend_status["available"] = (r.status_code < 500)
        except:
            _backend_status["available"] = False
        _backend_status["last_check"] = now
    return _backend_status["available"]

# --- Data Simulation Setup ---
MAX_HISTORY = 300
sensor_history = deque(maxlen=MAX_HISTORY)

alarm_state = {"unacknowledged": 0, "acknowledged": 0, "suppressed": 0}

DEMO_MACHINES = [
    {"name": "Reactor R-401",    "machineId": "R-401", "status": "running", "pressure": 90,  "vibration": 1.2, "temperature": 112, "health": 94},
    {"name": "Feed Pump P-101",  "machineId": "P-101", "status": "running", "pressure": 85,  "vibration": 0.8, "temperature": 42,  "health": 98},
    {"name": "Compressor K1",    "machineId": "K1",    "status": "standby", "pressure": 0,   "vibration": 0,   "temperature": 0,   "health": 85},
    {"name": "Separator S-101",  "machineId": "S-101", "status": "running", "pressure": 55,  "vibration": 0.5, "temperature": 38,  "health": 99},
    {"name": "Heat Exchanger E1","machineId": "E1",    "status": "running", "pressure": 75,  "vibration": 0.3, "temperature": 76,  "health": 97},
    {"name": "Pump P-202",       "machineId": "P-202", "status": "fault",   "pressure": 22,  "vibration": 4.1, "temperature": 88,  "health": 41},
]

def fetch_real_machines(auth_data):
    if not auth_data or not auth_data.get("token") or auth_data.get("token") == "demo":
        return DEMO_MACHINES
    if not is_backend_available():
        return DEMO_MACHINES
    token = auth_data.get("token")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{BACKEND_URL}/api/data/machines", headers=headers, timeout=1)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return DEMO_MACHINES

def fetch_real_alerts(auth_data):
    if not auth_data or not auth_data.get("token"):
        return []
    if auth_data.get("token") == "demo" or not is_backend_available():
        return []
    token = auth_data.get("token")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{BACKEND_URL}/api/data/alerts", headers=headers, timeout=1)
        if response.status_code == 200:
            return [(a["level"], a["message"], a.get("id", f"idx-{i}")) for i, a in enumerate(response.json())]
    except:
        pass
    return []

def generate_sensor_data(force_critical=False):
    if force_critical:
        return {
            "timestamp": datetime.now(),
            "temperature": random.uniform(135, 145),
            "pressure": random.uniform(25, 50),
            "rpm": random.uniform(2100, 2400)
        }
    temp = random.uniform(80, 120)
    pressure = random.uniform(50, 150)
    rpm = random.uniform(1000, 2000)
    if random.random() < 0.05:
        temp = random.uniform(125, 150)
    if random.random() < 0.03:
        pressure = random.uniform(20, 45)
    if random.random() < 0.02:
        rpm = random.uniform(2100, 2500)
    return {"timestamp": datetime.now(), "temperature": temp, "pressure": pressure, "rpm": rpm}

def analyze_data(data, thresholds=None):
    if thresholds is None:
        thresholds = {"temp_warn": 110, "temp_crit": 130, "pres_warn": 80, "pres_crit": 60, "rpm_warn": 1700, "rpm_crit": 2000}
    alerts = []
    insights = []
    temp, pressure, rpm = data["temperature"], data["pressure"], data["rpm"]
    if temp > thresholds.get("temp_crit", 130):
        alerts.append(("CRITICAL", f"High Temperature: {temp:.2f}°C - Immediate action required!"))
        insights.append("High temperature detected. Check cooling system.")
    elif temp > thresholds.get("temp_warn", 110):
        alerts.append(("WARNING", f"Elevated Temperature: {temp:.2f}°C - Monitor closely."))
    if pressure < thresholds.get("pres_crit", 60):
        alerts.append(("CRITICAL", f"Low Pressure: {pressure:.2f} PSI - System integrity compromised!"))
    elif pressure < thresholds.get("pres_warn", 80):
        alerts.append(("WARNING", f"Reduced Pressure: {pressure:.2f} PSI - Investigate cause."))
    if rpm > thresholds.get("rpm_crit", 2000):
        alerts.append(("CRITICAL", f"Excessive RPM: {rpm:.2f} - Risk of mechanical failure!"))
    elif rpm > thresholds.get("rpm_warn", 1700):
        alerts.append(("WARNING", f"High RPM: {rpm:.2f} - Monitor for vibrations."))
    if not alerts:
        alerts.append(("INFO", "All systems operating within normal parameters."))
        insights.append("All parameters are stable. No immediate concerns.")
    return alerts, insights

def detect_anomalies(history):
    if len(history) < 10:
        return []
    history_list = list(history)
    results = []
    for param in ["temperature", "pressure", "rpm"]:
        vals = [d[param] for d in history_list]
        mean = sum(vals) / len(vals)
        std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
        if std == 0:
            continue
        last = vals[-1]
        z_score = (last - mean) / std
        n = len(vals)
        slope = 0
        if n >= 2:
            x_mean = (n - 1) / 2
            num = sum((i - x_mean) * (vals[i] - mean) for i in range(n))
            den = sum((i - x_mean) ** 2 for i in range(n))
            slope = num / den if den != 0 else 0
        if abs(z_score) > 2.5:
            color = CRITICAL_COLOR
            badge = "ANOMALY"
            msg = f"Statistically significant deviation detected. Z-score {z_score:+.2f} indicates unusual {param} behavior."
        elif abs(z_score) > 1.5:
            color = WARNING_COLOR
            badge = "ELEVATED"
            msg = f"Mild deviation detected in {param}. Monitoring recommended."
        else:
            color = SUCCESS_COLOR
            badge = "NORMAL"
            msg = f"{param.capitalize()} is within expected statistical range."
        results.append({
            "param": param,
            "z_score": z_score,
            "slope": slope,
            "color": color,
            "badge": badge,
            "message": msg
        })
    return results

for _ in range(50):
    sensor_history.append(generate_sensor_data())

# --- Dash App Setup ---
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="NEXUS IQ — Industrial Intelligence Platform"
)

app.index_string = '''
<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>{%title%}</title>
  {%favicon%}
  {%css%}
  <style>
    :root {
      --bg-primary:  #09090b;
      --bg-card:     #161B22;
      --bg-surface:  #1a1a1f;
      --text-primary:#E6EDF3;
      --text-muted:  #8B949E;
      --text-dimmed: #484F58;
      --border-color:#27272a;
      --scrollbar-track: #0d0d10;
      --input-bg:    #09090b;
      --login-card-bg: #161B22;
      --login-page-bg: #0D1117;
      --login-right-bg: #000000;
      --role-btn-bg: #09090b;
    }
    body.light-theme {
      --bg-primary:  #ffffff;
      --bg-card:     #f5f7fa;
      --bg-surface:  #eaecf0;
      --text-primary:#1a1a1f;
      --text-muted:  #555;
      --text-dimmed: #888;
      --border-color:#dce0e5;
      --scrollbar-track: #e8e8e8;
      --input-bg:    #f0f2f5;
      --login-card-bg: #ffffff;
      --login-page-bg: #f0f2f5;
      --login-right-bg: #e8eaed;
      --role-btn-bg: #f0f2f5;
    }
    *, *::before, *::after { box-sizing: border-box; }
    body {
      font-family: 'Inter', system-ui, sans-serif !important;
      background-color: var(--bg-primary) !important;
      color: var(--text-primary) !important;
      transition: background-color 0.3s ease, color 0.3s ease;
    }
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: var(--scrollbar-track); }
    ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 2px; }
    ::-webkit-scrollbar-thumb:hover { background: #00E676; }

    /* Page content fade transition for smooth navigation */
    #page-content {
      animation: pageIn 0.18s ease;
    }
    @keyframes pageIn {
      from { opacity: 0; transform: translateY(6px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .nav-pills .nav-link {
      color: var(--text-muted) !important;
      font-size: 12px;
      font-weight: 600;
      padding: 9px 14px;
      border-radius: 4px;
      margin-bottom: 2px;
      border: 1px solid transparent;
      transition: all 0.18s ease;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .nav-pills .nav-link:hover {
      color: var(--text-primary) !important;
      background-color: var(--bg-surface) !important;
      border-color: var(--border-color) !important;
    }
    .nav-pills .nav-link.active {
      color: #09090b !important;
      background-color: #00E676 !important;
      border-color: #00E676 !important;
      font-weight: 700;
      box-shadow: 0 0 16px rgba(0, 230, 118, 0.25);
    }
    .metric-card {
      border: 1px solid var(--border-color) !important;
      border-radius: 8px !important;
      transition: all 0.2s ease;
      cursor: default;
      background-color: var(--bg-card) !important;
    }
    .metric-card:hover {
      border-color: #00E676 !important;
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 230, 118, 0.12) !important;
    }
    .card { background-color: var(--bg-card) !important; border-color: var(--border-color) !important; }
    .card-body { background-color: var(--bg-card) !important; }
    .ai-card {
      border-radius: 8px !important;
      border: 1px solid #26C6DA !important;
      transition: all 0.2s ease;
    }
    .ai-card:hover { box-shadow: 0 8px 24px rgba(38, 198, 218, 0.15) !important; transform: translateY(-2px); }
    .alert { border-radius: 4px !important; border-left-width: 3px !important; font-size: 12px; }
    .alert-danger  { background-color: #1a0808 !important; border-color: #EF5350 !important; color: #FFCDD2 !important; }
    .alert-warning { background-color: #1a1100 !important; border-color: #FFB300 !important; color: #FFE082 !important; }
    .alert-info    { background-color: #001518 !important; border-color: #26C6DA !important; color: #B2EBF2 !important; }
    .alert-success { background-color: #001a0a !important; border-color: #00E676 !important; color: #A5D6A7 !important; }
    .btn { border-radius: 4px !important; font-weight: 700 !important; font-size: 11px !important; padding: 9px 20px !important; transition: all 0.18s ease !important; letter-spacing: 0.08em; text-transform: uppercase; }
    .btn-primary { background-color: #00E676 !important; border-color: #00E676 !important; color: #09090b !important; }
    .btn-primary:hover { background-color: #00ff84 !important; border-color: #00ff84 !important; box-shadow: 0 0 20px rgba(0,230,118,0.4) !important; transform: translateY(-1px); color: #09090b !important; }
    .btn-success { background-color: #00E676 !important; border-color: #00E676 !important; color: #09090b !important; }
    .btn-success:hover { background-color: #00ff84 !important; border-color: #00ff84 !important; box-shadow: 0 0 20px rgba(0,230,118,0.35) !important; transform: translateY(-1px); color: #09090b !important; }
    .btn-outline-secondary { border-color: var(--border-color) !important; color: var(--text-muted) !important; background: transparent !important; }
    .btn-outline-secondary:hover { background-color: var(--bg-surface) !important; border-color: #00E676 !important; color: var(--text-primary) !important; }
    .btn:active { transform: translateY(0) !important; }
    .form-control, .form-select {
      background-color: var(--input-bg) !important;
      border: 1px solid var(--border-color) !important;
      color: var(--text-primary) !important;
      border-radius: 4px !important;
      font-size: 13px !important;
      transition: border-color 0.18s ease, box-shadow 0.18s ease;
    }
    .form-control:focus, .form-select:focus {
      border-color: #00E676 !important;
      box-shadow: 0 0 0 3px rgba(0,230,118,0.15) !important;
      background-color: var(--input-bg) !important;
      color: var(--text-primary) !important;
    }
    label { color: var(--text-muted) !important; font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; margin-top: 12px; }
    .table-dark { background-color: var(--bg-card) !important; border-color: var(--border-color) !important; font-size: 12px; }
    .table-dark th { background-color: var(--bg-surface) !important; color: #00E676 !important; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
    .table-dark tr:hover td { background-color: var(--bg-surface) !important; }
    .equip-card { border: 1px solid var(--border-color) !important; border-radius: 8px !important; transition: all 0.2s ease; }
    .equip-card:hover { border-color: #00E676 !important; transform: translateY(-3px); box-shadow: 0 10px 28px rgba(0,0,0,0.5) !important; }
    h3, h4 { font-weight: 700 !important; letter-spacing: -0.02em; color: var(--text-primary) !important; }
    h3 { font-size: 20px !important; margin-bottom: 20px !important; }
    h4 { font-size: 13px !important; color: var(--text-muted) !important; font-weight: 700 !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; }
    .js-plotly-plot .plotly { border-radius: 8px; overflow: hidden; }
    hr { border-color: var(--border-color) !important; opacity: 1 !important; }
    .logo-mark { font-size: 20px; font-weight: 800; letter-spacing: -0.03em; color: #00E676; line-height: 1.1; }
    .logo-sub  { font-size: 9px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--text-dimmed); margin-top: 2px; }
    .theme-toggle-btn {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 4px;
      color: var(--text-muted);
      font-size: 10px;
      font-weight: 700;
      padding: 7px 12px;
      cursor: pointer;
      transition: all 0.2s ease;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;
      margin-top: 8px;
      font-family: 'Inter', sans-serif;
    }
    .theme-toggle-btn:hover { border-color: #00E676; color: var(--text-primary); box-shadow: 0 0 12px rgba(0,230,118,0.15); }
    .theme-icon { width: 14px; height: 14px; border-radius: 50%; background: linear-gradient(135deg, #fff 50%, #000 50%); border: 1px solid #444; flex-shrink: 0; }
    .login-page { min-height: 100vh; background: var(--login-page-bg); display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; }
    .login-bg-grid { position: absolute; inset: 0; background-image: linear-gradient(rgba(0,230,118,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,230,118,0.03) 1px, transparent 1px); background-size: 40px 40px; pointer-events: none; }
    .login-bg-glow { position: absolute; width: 500px; height: 500px; border-radius: 50%; background: radial-gradient(circle, rgba(0,230,118,0.06) 0%, transparent 70%); top: -100px; right: -100px; pointer-events: none; }
    .login-bg-glow-2 { position: absolute; width: 400px; height: 400px; border-radius: 50%; background: radial-gradient(circle, rgba(38,198,218,0.04) 0%, transparent 70%); bottom: -80px; left: -80px; pointer-events: none; }
    .login-card { background: var(--login-card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 40px 44px; width: 100%; max-width: 420px; position: relative; z-index: 1; box-shadow: 0 24px 60px rgba(0,0,0,0.6); animation: slideUp 0.4s ease; }
    @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    .login-logo { text-align: center; margin-bottom: 28px; }
    .login-logo-mark { font-size: 26px; font-weight: 800; letter-spacing: -0.03em; color: #00E676; line-height: 1.1; }
    .login-logo-sub  { font-size: 9px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: var(--text-dimmed); margin-top: 4px; }
    .login-title    { font-size: 20px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; letter-spacing: -0.02em; }
    .login-subtitle { font-size: 12px; color: var(--text-muted); margin-bottom: 28px; }
    .login-input-group { margin-bottom: 16px; }
    .login-label    { font-size: 10px; font-weight: 700; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.1em; text-transform: uppercase; }
    .login-input { width: 100%; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-primary); font-size: 14px; padding: 11px 14px; outline: none; transition: border-color 0.18s ease, box-shadow 0.18s ease; font-family: 'Inter', sans-serif; }
    .login-input:focus { border-color: #00E676; box-shadow: 0 0 0 3px rgba(0,230,118,0.12); }
    .login-input::placeholder { color: var(--text-dimmed); }
    .login-btn { width: 100%; background: #00E676; border: none; border-radius: 4px; color: #09090b; font-size: 12px; font-weight: 700; padding: 13px; cursor: pointer; letter-spacing: 0.1em; text-transform: uppercase; transition: all 0.2s ease; margin-top: 8px; font-family: 'Inter', sans-serif; }
    .login-btn:hover { background: #00ff84; box-shadow: 0 0 24px rgba(0,230,118,0.4); transform: translateY(-1px); }
    .login-btn:active { transform: translateY(0); }
    .login-divider { display: flex; align-items: center; gap: 12px; margin: 20px 0; }
    .login-divider-line { flex: 1; height: 1px; background: var(--border-color); }
    .login-divider-text { font-size: 10px; color: var(--text-dimmed); font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; }
    .login-switch-text { text-align: center; font-size: 12px; color: var(--text-muted); margin-top: 20px; }
    .login-switch-link { color: #00E676; cursor: pointer; font-weight: 700; text-decoration: none; transition: color 0.15s ease; }
    .login-switch-link:hover { color: #26C6DA; }
    .login-error { background: rgba(239,83,80,0.08); border: 1px solid rgba(239,83,80,0.25); border-radius: 4px; color: #FFCDD2; font-size: 12px; padding: 10px 14px; margin-bottom: 14px; display: none; }
    .login-error.visible { display: block; animation: shake 0.3s ease; }
    @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-6px); } 75% { transform: translateX(6px); } }
    .login-success { background: rgba(0,230,118,0.08); border: 1px solid rgba(0,230,118,0.25); border-radius: 4px; color: #A5D6A7; font-size: 12px; padding: 10px 14px; margin-bottom: 14px; display: none; }
    .login-success.visible { display: block; }
    .terms-text { font-size: 10px; color: var(--text-dimmed); text-align: center; margin-top: 16px; line-height: 1.6; }
    .terms-link { color: #00E676; cursor: pointer; }
    .role-btn { display: flex; align-items: center; background: var(--role-btn-bg); border: 1px solid var(--border-color); border-radius: 4px; padding: 12px 16px; margin-bottom: 8px; cursor: pointer; transition: all 0.2s ease; }
    .role-btn:hover { border-color: #00E676 !important; transform: translateX(4px); box-shadow: 0 4px 12px rgba(0,230,118,0.1); }
    .role-btn.role-active { border-color: #00E676 !important; background: rgba(0,230,118,0.05) !important; }
    .role-indicator { width: 6px; height: 6px; border-radius: 1px; flex-shrink: 0; }
    .ack-btn { background: transparent; border: 1px solid #FFB300; border-radius: 3px; color: #FFB300; font-size: 9px; font-weight: 700; padding: 3px 8px; cursor: pointer; letter-spacing: 0.08em; text-transform: uppercase; transition: all 0.15s ease; font-family: 'Inter', sans-serif; margin-left: 8px; }
    .ack-btn:hover { background: #FFB300; color: #09090b; }
    .supp-btn { background: transparent; border: 1px solid #26C6DA; border-radius: 3px; color: #26C6DA; font-size: 9px; font-weight: 700; padding: 3px 8px; cursor: pointer; letter-spacing: 0.08em; text-transform: uppercase; transition: all 0.15s ease; font-family: 'Inter', sans-serif; margin-left: 4px; }
    .supp-btn:hover { background: #26C6DA; color: #09090b; }
    .hmi-toast { background: #161B22; border: 1px solid #EF5350; border-left: 4px solid #EF5350; border-radius: 4px; padding: 12px 16px; color: #FFCDD2; font-size: 12px; font-family: Inter, sans-serif; animation: toastIn 0.3s ease, toastOut 0.3s ease 4.7s forwards; }
    @keyframes toastIn  { from {opacity:0;transform:translateX(20px)} to {opacity:1;transform:translateX(0)} }
    @keyframes toastOut { from {opacity:1} to {opacity:0;height:0;padding:0;margin:0} }
    .hmi-toast-warn { border-color: #FFB300; border-left-color: #FFB300; color: #FFE082; }
  </style>
</head>
<body>
  {%app_entry%}
  <footer>
    {%config%}
    {%scripts%}
    {%renderer%}
  </footer>
  <script>
    document.addEventListener('click', function(e) {
      var btn = e.target.closest('[data-theme-toggle]');
      if (btn) {
        var isLight = document.body.classList.toggle('light-theme');
        var label = btn.querySelector('.theme-label');
        if (label) label.textContent = isLight ? 'Dark Theme' : 'Light Theme';
      }
    });
  </script>
</body>
</html>
'''

# --- Layout Constants ---
SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0, "width": "15rem",
    "padding": "24px 14px",
    "backgroundColor": "var(--bg-primary)",
    "borderRight": "1px solid var(--border-color)",
    "overflowY": "auto",
}
CONTENT_STYLE = {
    "marginLeft": "17rem", "marginRight": "2rem",
    "padding": "28px 20px",
    "backgroundColor": "var(--bg-primary)",
    "minHeight": "100vh",
    "color": "var(--text-primary)",
}

def make_logo():
    return html.Div([
        html.Div([
            html.Span("■", style={"color": ACCENT_COLOR, "marginRight": "10px", "fontSize": "12px"}),
            html.Span("NEXUS IQ", className="logo-mark", style={"fontSize": "16px"}),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div("Industrial Intelligence Platform", className="logo-sub"),
    ], style={"marginBottom": "20px"})

def make_theme_toggle():
    return html.Button(
        [html.Div(className="theme-icon"), html.Span("Light Theme", className="theme-label")],
        className="theme-toggle-btn",
        n_clicks=0,
        **{"data-theme-toggle": "1"}
    )

def make_demo_mode_btn(role_suffix):
    return html.Button("\u2b21  DEMO MODE", id=f"demo-mode-btn-{role_suffix}", n_clicks=0,
        style={"width": "100%", "background": "transparent",
               "border": "1px solid #26C6DA", "borderRadius": "4px",
               "color": "#26C6DA", "fontSize": "10px", "fontWeight": "700",
               "letterSpacing": "0.1em", "padding": "8px 12px",
               "cursor": "pointer", "marginBottom": "4px",
               "fontFamily": "Inter, sans-serif", "transition": "all 0.18s ease"})

def make_logout_btn(suffix):
    return html.Button("⬡  LOGOUT", id=f"logout-btn-{suffix}", n_clicks=0, style={
        "width": "100%", "background": "transparent",
        "border": "1px solid #EF5350",
        "borderRadius": "4px", "color": "#EF5350",
        "fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em",
        "padding": "8px 12px", "cursor": "pointer", "transition": "all 0.18s ease",
        "fontFamily": "Inter, sans-serif", "marginTop": "4px",
    })

def make_plant_status():
    return html.Div([
        html.Span("● ", style={"color": SUCCESS_COLOR, "fontSize": "10px"}),
        html.Strong("PLANT STATUS", style={"color": "var(--text-dimmed)", "fontSize": "9px", "letterSpacing": "0.1em"}),
        html.Br(),
        html.Span("Operational", style={"color": SUCCESS_COLOR, "fontWeight": "700", "fontSize": "11px", "letterSpacing": "0.06em"})
    ])

def make_nav_label(text):
    return html.P(text, style={
        "color": "var(--text-dimmed)", "fontSize": "9px", "fontWeight": "700",
        "letterSpacing": "0.14em", "textTransform": "uppercase", "marginBottom": "10px"
    })

# ── SIDEBARS (defined once, always in DOM) ───────────────────────────────────
operator_sidebar = html.Div([
    make_logo(), html.Hr(),
    make_nav_label("Operator Navigation"),
    dbc.Nav([
        dbc.NavLink("⬡  Overview",      href="/",            active="exact"),
        dbc.NavLink("⬡  Process Map",   href="/process-map", active="exact"),
        dbc.NavLink("⬡  Trends",        href="/trends",      active="exact"),
        dbc.NavLink("⬡  Alarms",        href="/alarms",      active="exact"),
        dbc.NavLink("⬡  Events",        href="/events",      active="exact"),
        dbc.NavLink("⬡  Equipment",     href="/equipment",   active="exact"),
        dbc.NavLink("⬡  AI Insights",   href="/ai-insights", active="exact"),
        dbc.NavLink("⬡  Reports",       href="/reports",     active="exact"),
        dbc.NavLink("⬡  Settings",      href="/settings",    active="exact"),
    ], vertical=True, pills=True),
    html.Hr(),
    make_plant_status(),
    html.Hr(),
    make_theme_toggle(),
    html.Hr(),
    make_demo_mode_btn("op"),
    make_logout_btn("op"),
], style=SIDEBAR_STYLE)

engineer_sidebar = html.Div([
    make_logo(), html.Hr(),
    make_nav_label("Engineer Navigation"),
    dbc.Nav([
        dbc.NavLink("⬡  Overview",        href="/engineer",              active="exact"),
        dbc.NavLink("⬡  Diagnostics",     href="/engineer/diagnostics",  active="exact"),
        dbc.NavLink("⬡  Calibration",     href="/engineer/calibration",  active="exact"),
        dbc.NavLink("⬡  Signal Library",  href="/engineer/signals",      active="exact"),
        dbc.NavLink("⬡  Maintenance",     href="/engineer/maintenance",  active="exact"),
        dbc.NavLink("⬡  Trends",          href="/engineer/trends",       active="exact"),
        dbc.NavLink("⬡  Reports",         href="/engineer/reports",      active="exact"),
        dbc.NavLink("⬡  Settings",        href="/engineer/settings",     active="exact"),
    ], vertical=True, pills=True),
    html.Hr(),
    html.Div([
        html.Span("● ", style={"color": INFO_COLOR, "fontSize": "10px"}),
        html.Strong("ENG. CONSOLE", style={"color": "var(--text-dimmed)", "fontSize": "9px", "letterSpacing": "0.1em"}),
        html.Br(),
        html.Span("All Systems Nominal", style={"color": INFO_COLOR, "fontWeight": "700", "fontSize": "11px", "letterSpacing": "0.06em"})
    ]),
    html.Hr(),
    make_theme_toggle(),
    html.Hr(),
    make_demo_mode_btn("eng"),
    make_logout_btn("eng"),
], style=SIDEBAR_STYLE)

manager_sidebar = html.Div([
    make_logo(), html.Hr(),
    make_nav_label("Manager Navigation"),
    dbc.Nav([
        dbc.NavLink("⬡  Executive Summary", href="/manager",             active="exact"),
        dbc.NavLink("⬡  Plant Performance", href="/manager/performance", active="exact"),
        dbc.NavLink("⬡  KPI Dashboard",     href="/manager/kpis",        active="exact"),
        dbc.NavLink("⬡  Shift Reports",     href="/manager/shifts",      active="exact"),
        dbc.NavLink("⬡  Compliance",        href="/manager/compliance",  active="exact"),
        dbc.NavLink("⬡  Budget & Cost",     href="/manager/budget",      active="exact"),
        dbc.NavLink("⬡  Reports",           href="/manager/reports",     active="exact"),
        dbc.NavLink("⬡  Settings",          href="/manager/settings",    active="exact"),
    ], vertical=True, pills=True),
    html.Hr(),
    html.Div([
        html.Span("● ", style={"color": WARNING_COLOR, "fontSize": "10px"}),
        html.Strong("PLANT OEE", style={"color": "var(--text-dimmed)", "fontSize": "9px", "letterSpacing": "0.1em"}),
        html.Br(),
        html.Span("87.4%  This Shift", style={"color": WARNING_COLOR, "fontWeight": "700", "fontSize": "11px", "letterSpacing": "0.06em"})
    ]),
    html.Hr(),
    make_theme_toggle(),
    html.Hr(),
    make_demo_mode_btn("mgr"),
    make_logout_btn("mgr"),
], style=SIDEBAR_STYLE)

# ── LOGIN PAGE ────────────────────────────────────────────────────────────────
login_page = html.Div([
    html.Div([
        html.Div([
            html.Div([
                html.Span("■", style={"color": "#00E676", "marginRight": "12px", "fontSize": "14px"}),
                html.Span("NEXTGEN · HMI", style={"color": "#8B949E", "fontSize": "11px", "letterSpacing": "0.15em", "fontWeight": "600"})
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "60px"}),
            html.H1([
                html.Span("Plant operations,", style={"color": "#FFFFFF", "display": "block", "fontSize": "56px", "fontWeight": "700", "lineHeight": "1.1", "letterSpacing": "-0.02em"}),
                html.Span("de-cluttered.", style={"color": "#00E676", "display": "block", "fontSize": "56px", "fontWeight": "700", "lineHeight": "1.1", "letterSpacing": "-0.02em"})
            ], style={"marginBottom": "24px"}),
            html.P(
                "Auto-generated HMI screens. AI-prioritized alarms. Role-aware UI. Built for small-scale industrial control rooms that need clarity, not noise.",
                style={"color": "#8B949E", "fontSize": "16px", "lineHeight": "1.6", "maxWidth": "480px"}
            )
        ], style={"flex": "1", "display": "flex", "flexDirection": "column", "justifyContent": "center", "padding": "0 80px"}),
        html.Div("V0.1 - CONTROL ROOM BUILD - 2026",
            style={"position": "absolute", "bottom": "40px", "left": "80px", "color": "#484F58", "fontSize": "10px", "letterSpacing": "0.1em", "fontWeight": "600"})
    ], style={"flex": "1", "position": "relative", "backgroundColor": "#09090b", "display": "flex", "flexDirection": "column"}),

    html.Div([
        html.Div([
            html.Div("AUTHENTICATE", style={"color": "#8B949E", "fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em", "marginBottom": "8px"}),
            html.H2("Sign in to your account", style={"color": "#FFFFFF", "fontSize": "24px", "fontWeight": "600", "marginBottom": "32px"}),

            html.Div(id="login-error-msg",   className="login-error"),
            html.Div(id="login-success-msg", className="login-success"),

            html.Div([
                html.Label("USERNAME / EMAIL", style={"color": "#8B949E", "fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em", "marginBottom": "8px", "display": "block"}),
                dcc.Input(
                    id="login-email", type="text",
                    placeholder="Enter username or email",
                    style={"width": "100%", "backgroundColor": "#09090b", "border": "1px solid #27272a", "borderRadius": "4px",
                           "color": "#FFFFFF", "padding": "12px 16px", "fontSize": "14px", "outline": "none", "fontFamily": "Inter, sans-serif"}
                )
            ], style={"marginBottom": "16px"}),

            html.Div([
                html.Label("PASSWORD", style={"color": "#8B949E", "fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em", "marginBottom": "8px", "display": "block"}),
                dcc.Input(
                    id="login-password", type="password",
                    placeholder="Enter password",
                    style={"width": "100%", "backgroundColor": "#09090b", "border": "1px solid #27272a", "borderRadius": "4px",
                           "color": "#FFFFFF", "padding": "12px 16px", "fontSize": "14px", "outline": "none", "fontFamily": "Inter, sans-serif"}
                )
            ], style={"marginBottom": "24px"}),

            html.Div([
                html.Label("ROLE", style={"color": "#8B949E", "fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em", "marginBottom": "8px", "display": "block"}),
                html.Div([
                    html.Div("⬡", style={"color": "#00E676", "fontSize": "18px", "marginRight": "16px"}),
                    html.Div([
                        html.Div("Operator", style={"color": "#FFFFFF", "fontSize": "14px", "fontWeight": "600"}),
                        html.Div("Live ops · alarms · acknowledgments", style={"color": "#8B949E", "fontSize": "11px"})
                    ], style={"flex": "1"}),
                    html.Div(id="role-indicator-operator", style={"width": "6px", "height": "6px", "backgroundColor": "#00E676"}),
                ], id="role-btn-operator", n_clicks=0, className="role-btn role-active",
                   style={"display": "flex", "alignItems": "center", "backgroundColor": "rgba(0,230,118,0.05)",
                          "border": "1px solid #00E676", "borderRadius": "4px",
                          "padding": "12px 16px", "marginBottom": "8px", "cursor": "pointer", "transition": "all 0.2s ease"}),

                html.Div([
                    html.Div("⬡", style={"color": "#26C6DA", "fontSize": "18px", "marginRight": "16px"}),
                    html.Div([
                        html.Div("Engineer", style={"color": "#E6EDF3", "fontSize": "14px", "fontWeight": "600"}),
                        html.Div("Signal library · diagnostics · calibration", style={"color": "#8B949E", "fontSize": "11px"})
                    ], style={"flex": "1"}),
                    html.Div(id="role-indicator-engineer", style={"width": "6px", "height": "6px", "backgroundColor": "#27272a"}),
                ], id="role-btn-engineer", n_clicks=0, className="role-btn",
                   style={"display": "flex", "alignItems": "center", "backgroundColor": "#09090b",
                          "border": "1px solid #27272a", "borderRadius": "4px",
                          "padding": "12px 16px", "marginBottom": "8px", "cursor": "pointer", "transition": "all 0.2s ease"}),

                html.Div([
                    html.Div("⬡", style={"color": "#FFB300", "fontSize": "18px", "marginRight": "16px"}),
                    html.Div([
                        html.Div("Manager", style={"color": "#E6EDF3", "fontSize": "14px", "fontWeight": "600"}),
                        html.Div("KPIs · executive summary · compliance", style={"color": "#8B949E", "fontSize": "11px"})
                    ], style={"flex": "1"}),
                    html.Div(id="role-indicator-manager", style={"width": "6px", "height": "6px", "backgroundColor": "#27272a"}),
                ], id="role-btn-manager", n_clicks=0, className="role-btn",
                   style={"display": "flex", "alignItems": "center", "backgroundColor": "#09090b",
                          "border": "1px solid #27272a", "borderRadius": "4px",
                          "padding": "12px 16px", "marginBottom": "24px", "cursor": "pointer", "transition": "all 0.2s ease"}),
            ]),

            html.Button([
                html.Span("🛡", style={"marginRight": "8px"}),
                html.Span("ENTER CONTROL ROOM")
            ], id="login-btn", n_clicks=0, style={
                "width": "100%", "backgroundColor": "#00E676", "color": "#09090b",
                "border": "none", "borderRadius": "4px", "padding": "14px",
                "fontSize": "12px", "fontWeight": "700", "letterSpacing": "0.1em",
                "cursor": "pointer", "display": "flex", "alignItems": "center",
                "justifyContent": "center", "fontFamily": "Inter, sans-serif"
            }),

            html.Div("DEMO CREDENTIALS: admin@hmi.com / password123", style={
                "color": "#484F58", "fontSize": "10px", "fontWeight": "600",
                "letterSpacing": "0.1em", "textAlign": "center", "marginTop": "16px"
            })
        ], style={
            "backgroundColor": "#161B22", "width": "420px", "padding": "48px",
            "borderRadius": "8px", "boxShadow": "0 24px 48px rgba(0,0,0,0.6)",
            "border": "1px solid #27272a"
        })
    ], style={"flex": "1", "backgroundColor": "#000000", "display": "flex", "alignItems": "center", "justifyContent": "center"})
], style={"display": "flex", "minHeight": "100vh", "fontFamily": "Inter, sans-serif"})


signup_page = html.Div([
    html.Div(className="login-bg-grid"),
    html.Div(className="login-bg-glow"),
    html.Div(className="login-bg-glow-2"),
    html.Div([
        html.Div("NEXUS IQ",                         className="login-logo-mark"),
        html.Div("Industrial Intelligence Platform", className="login-logo-sub"),
    ], className="login-logo"),
    html.Div("Create Account",          className="login-title"),
    html.Div("Register a new account",  className="login-subtitle"),
    html.Div(id="signup-error-msg",   className="login-error"),
    html.Div(id="signup-success-msg", className="login-success"),
    html.Div([
        html.Label("Full Name", className="login-label"),
        dcc.Input(id="signup-name", type="text", placeholder="John Smith", className="login-input"),
    ], className="login-input-group"),
    html.Div([
        html.Label("Work Email", className="login-label"),
        dcc.Input(id="signup-email", type="email", placeholder="operator@plant.com", className="login-input"),
    ], className="login-input-group"),
    html.Div([
        html.Label("Operator Role", className="login-label"),
        dcc.Dropdown(
            id="signup-role",
            options=[
                {"label": "Control Room Operator", "value": "operator"},
                {"label": "Shift Supervisor",      "value": "supervisor"},
                {"label": "Maintenance Engineer",  "value": "maintenance"},
                {"label": "Plant Manager",         "value": "manager"},
                {"label": "AI/Data Analyst",       "value": "analyst"},
            ],
            placeholder="Select your role...",
            style={"backgroundColor": "#09090b", "color": "#E6EDF3", "border": "1px solid #27272a", "borderRadius": "4px", "fontSize": "13px"},
        ),
    ], className="login-input-group"),
    html.Div([
        html.Label("Password", className="login-label"),
        dcc.Input(id="signup-password", type="password", placeholder="Min. 8 characters", className="login-input"),
    ], className="login-input-group"),
    html.Div([
        html.Label("Confirm Password", className="login-label"),
        dcc.Input(id="signup-confirm-password", type="password", placeholder="Re-enter password", className="login-input"),
    ], className="login-input-group"),
    html.Button("CREATE ACCOUNT", id="signup-btn", className="login-btn", n_clicks=0),
    html.Div(["Already have an account? ", html.A("Sign in", href="/login", className="login-switch-link")], className="login-switch-text"),
    html.Div(["By creating an account, you agree to our ", html.Span("Terms of Service", className="terms-link"), " and ", html.Span("Privacy Policy", className="terms-link"), "."], className="terms-text"),
], className="login-card", style={"maxWidth": "440px", "margin": "40px auto"})


# ── APP LAYOUT — All sidebars always in DOM for reliable callbacks ─────────────
app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Interval(id="interval-component", interval=5000, n_intervals=0),
    dcc.Store(id="latest-data-store"),
    dcc.Store(id="auth-store",
              data={"logged_in": False, "user": None, "role": "operator"},
              storage_type="session"),
    dcc.Store(id="selected-role-store", data="operator", storage_type="session"),
    dcc.Store(id="trend-range-store",  data="1H"),
    dcc.Store(id="equipment-live-store"),
    dcc.Store(id="alarm-ack-store",    data=None),
    dcc.Store(id="report-gen-store",   data={"last": None, "count": 47}),
    dcc.Store(id="settings-store",
              data={"refresh": 2, "ai": True, "notifications": True, "export_fmt": "CSV",
                    "temp_warn": 110, "temp_crit": 130, "pres_warn": 80, "pres_crit": 60,
                    "rpm_warn": 1700, "rpm_crit": 2000},
              storage_type="local"),
    dcc.Store(id="last-toast-store",  data=None),
    dcc.Store(id="demo-mode-store",   data=False),
    dcc.Store(id="uptime-store",      data={"start": datetime.now().isoformat()}),

    # ── LOGIN PAGE ─────────────────────────────────────────────────────────────
    html.Div(id="login-container", children=login_page,
             style={"display": "flex"}),

    # ── SIGNUP PAGE ────────────────────────────────────────────────────────────
    html.Div(id="signup-container",
             children=html.Div(signup_page, style={
                 "minHeight": "100vh", "backgroundColor": "var(--login-page-bg)",
                 "display": "flex", "alignItems": "center", "justifyContent": "center",
                 "position": "relative", "overflow": "hidden"
             }),
             style={"display": "none"}),

    # ── MAIN APP (all 3 sidebars always present, hidden via CSS when not active) ──
    html.Div(id="app-container", style={"display": "none"}, children=[
        # Operator sidebar wrapper
        html.Div(id="sidebar-op-wrapper",  children=operator_sidebar,  style={}),
        # Engineer sidebar wrapper
        html.Div(id="sidebar-eng-wrapper", children=engineer_sidebar,  style={"display": "none"}),
        # Manager sidebar wrapper
        html.Div(id="sidebar-mgr-wrapper", children=manager_sidebar,   style={"display": "none"}),
        # Page content area
        html.Div(id="page-content", style=CONTENT_STYLE),
    ]),

    # ── TOAST NOTIFICATIONS (always present) ──────────────────────────────────
    html.Div(id="toast-container", style={
        "position": "fixed", "bottom": "24px", "right": "280px",
        "zIndex": "9999", "display": "flex", "flexDirection": "column",
        "gap": "8px", "width": "320px"
    }),
], style={"backgroundColor": "var(--bg-primary)"})


# ── GLOBAL DATA UPDATE ────────────────────────────────────────────────────────
@app.callback(
    Output("latest-data-store", "data"),
    Input("interval-component", "n_intervals"),
    State("auth-store",       "data"),
    State("demo-mode-store",  "data"),
    prevent_initial_call=False,
)
def update_global_data(n, auth_data, demo_mode):
    use_backend = (not demo_mode
                   and auth_data
                   and auth_data.get("token")
                   and auth_data.get("token") != "demo"
                   and is_backend_available())
    if use_backend:
        try:
            r = requests.get(
                f"{BACKEND_URL}/api/sensor/live",
                headers={"Authorization": f"Bearer {auth_data['token']}"},
                timeout=1
            )
            if r.status_code == 200:
                data = r.json()
                if data:
                    ts = data.get("created_at", datetime.now().isoformat())
                    new_data = {
                        "timestamp": datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.now(),
                        "temperature": data.get("temperature", 0),
                        "pressure":    data.get("pressure",    0),
                        "rpm":         data.get("rpm",         0)
                    }
                    sensor_history.append(new_data)
                    data_dict = new_data.copy()
                    data_dict["timestamp"] = data_dict["timestamp"].isoformat()
                    return data_dict
        except Exception:
            pass
    new_data = generate_sensor_data(force_critical=bool(demo_mode))
    sensor_history.append(new_data)
    data_dict = new_data.copy()
    data_dict["timestamp"] = data_dict["timestamp"].isoformat()
    return data_dict


# ── ROLE SELECTION ────────────────────────────────────────────────────────────
@app.callback(
    Output("selected-role-store",      "data"),
    Output("role-btn-operator",        "style"),
    Output("role-btn-engineer",        "style"),
    Output("role-btn-manager",         "style"),
    Output("role-indicator-operator",  "style"),
    Output("role-indicator-engineer",  "style"),
    Output("role-indicator-manager",   "style"),
    Output("role-btn-operator",        "className"),
    Output("role-btn-engineer",        "className"),
    Output("role-btn-manager",         "className"),
    Input("role-btn-operator",  "n_clicks"),
    Input("role-btn-engineer",  "n_clicks"),
    Input("role-btn-manager",   "n_clicks"),
    State("selected-role-store","data"),
    prevent_initial_call=True,
)
def select_role(op_clicks, eng_clicks, mgr_clicks, current_role):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    role_map = {"role-btn-operator": "operator", "role-btn-engineer": "engineer", "role-btn-manager": "manager"}
    selected = role_map.get(trigger_id, current_role)
    base = {"display": "flex", "alignItems": "center", "borderRadius": "4px",
            "padding": "12px 16px", "cursor": "pointer", "transition": "all 0.2s ease"}
    op_active  = {**base, "backgroundColor": "rgba(0,230,118,0.05)", "border": "1px solid #00E676", "marginBottom": "8px"}
    eng_active = {**base, "backgroundColor": "rgba(38,198,218,0.05)", "border": "1px solid #26C6DA", "marginBottom": "8px"}
    mgr_active = {**base, "backgroundColor": "rgba(255,179,0,0.05)",  "border": "1px solid #FFB300", "marginBottom": "8px"}
    inactive   = {**base, "backgroundColor": "#09090b", "border": "1px solid #27272a", "marginBottom": "8px"}
    ind_op  = {"width": "6px", "height": "6px", "backgroundColor": "#00E676"}
    ind_eng = {"width": "6px", "height": "6px", "backgroundColor": "#26C6DA"}
    ind_mgr = {"width": "6px", "height": "6px", "backgroundColor": "#FFB300"}
    ind_off = {"width": "6px", "height": "6px", "backgroundColor": "#27272a"}
    if selected == "operator":
        return selected, op_active, inactive, inactive, ind_op, ind_off, ind_off, "role-btn role-active", "role-btn", "role-btn"
    elif selected == "engineer":
        return selected, inactive, eng_active, inactive, ind_off, ind_eng, ind_off, "role-btn", "role-btn role-active", "role-btn"
    else:
        return selected, inactive, inactive, mgr_active, ind_off, ind_off, ind_mgr, "role-btn", "role-btn", "role-btn role-active"


# ── ROUTING — show/hide containers and sidebars ───────────────────────────────
@app.callback(
    Output("login-container",    "style"),
    Output("signup-container",   "style"),
    Output("app-container",      "style"),
    Output("sidebar-op-wrapper", "style"),
    Output("sidebar-eng-wrapper","style"),
    Output("sidebar-mgr-wrapper","style"),
    Input("url",        "pathname"),
    Input("auth-store", "data"),
    prevent_initial_call=False,
)
def route_app(pathname, auth_data):
    is_logged_in = bool(auth_data and auth_data.get("logged_in", False))

    HIDE      = {"display": "none"}
    SHOW_FLEX = {"display": "flex"}
    SHOW_BLOCK= {}

    if pathname == "/signup":
        return HIDE, SHOW_BLOCK, HIDE, HIDE, HIDE, HIDE

    if not is_logged_in:
        return SHOW_FLEX, HIDE, HIDE, HIDE, HIDE, HIDE

    role = (auth_data or {}).get("role", "operator")
    if role == "engineer":
        return HIDE, HIDE, SHOW_BLOCK, HIDE, SHOW_BLOCK, HIDE
    elif role == "manager":
        return HIDE, HIDE, SHOW_BLOCK, HIDE, HIDE, SHOW_BLOCK
    else:
        return HIDE, HIDE, SHOW_BLOCK, SHOW_BLOCK, HIDE, HIDE


# ── LOGOUT — buttons are always in DOM so this always works ──────────────────
@app.callback(
    Output("auth-store", "data"),
    Output("url",        "pathname"),
    Input("logout-btn-op",  "n_clicks"),
    Input("logout-btn-eng", "n_clicks"),
    Input("logout-btn-mgr", "n_clicks"),
    prevent_initial_call=True,
)
def handle_logout(op, eng, mgr):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    triggered_val = ctx.triggered[0]["value"]
    if not triggered_val:
        raise dash.exceptions.PreventUpdate
    return {"logged_in": False, "user": None, "role": "operator"}, "/login"


# ── LOGIN ─────────────────────────────────────────────────────────────────────
@app.callback(
    Output("auth-store",        "data",      allow_duplicate=True),
    Output("login-error-msg",   "children"),
    Output("login-error-msg",   "className"),
    Output("login-success-msg", "children"),
    Output("login-success-msg", "className"),
    Output("url",               "pathname",  allow_duplicate=True),
    Input("login-btn",          "n_clicks"),
    State("login-email",        "value"),
    State("login-password",     "value"),
    State("auth-store",         "data"),
    State("selected-role-store","data"),
    prevent_initial_call=True,
)
def handle_login(n_clicks, email, password, auth_data, selected_role):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    selected_role = selected_role or "operator"
    role_paths = {"operator": "/", "engineer": "/engineer", "manager": "/manager"}
    redirect_path = role_paths.get(selected_role, "/")
    if not email or not str(email).strip():
        return auth_data, "⚠ Please enter your username/email.", "login-error visible", "", "login-success", "/login"
    if not password or not str(password).strip():
        return auth_data, "⚠ Please enter your password.", "login-error visible", "", "login-success", "/login"
    effective_password = str(password).strip()
    if is_backend_available():
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/auth/login",
                json={"email": email, "password": effective_password},
                timeout=2
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                new_auth = {"logged_in": True, "user": data.get("user"), "token": token, "role": selected_role}
                return new_auth, "", "login-error", "✓ Access Granted! Redirecting...", "login-success visible", redirect_path
            else:
                try:
                    error_message = response.json().get("detail", response.json().get("message", "Invalid credentials"))
                except:
                    error_message = "Invalid credentials"
                return auth_data, f"⚠ {error_message}", "login-error visible", "", "login-success", "/login"
        except Exception:
            pass
    new_auth = {"logged_in": True, "user": {"name": email, "role": selected_role}, "token": "demo", "role": selected_role}
    return new_auth, "", "login-error", "✓ Demo Mode — Redirecting...", "login-success visible", redirect_path


# ── SIGNUP ────────────────────────────────────────────────────────────────────
@app.callback(
    Output("signup-error-msg",   "children"),
    Output("signup-error-msg",   "className"),
    Output("signup-success-msg", "children"),
    Output("signup-success-msg", "className"),
    Input("signup-btn",          "n_clicks"),
    State("signup-name",         "value"),
    State("signup-email",        "value"),
    State("signup-password",     "value"),
    State("signup-role",         "value"),
    prevent_initial_call=True,
)
def handle_signup(n_clicks, name, email, password, role):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    if not is_backend_available():
        return "⚠ Backend not reachable — demo mode only.", "login-error visible", "", "login-success"
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/auth/register",
            json={"name": name or "Plant Admin", "email": email or "admin@hmi.com",
                  "password": password or "password123", "role": role or "operator"},
            timeout=2
        )
        if response.status_code == 201:
            return "", "login-error", "✓ Account created! Click 'Sign in' below.", "login-success visible"
        else:
            try:
                error_msg = response.json().get("message", "Failed")
            except:
                error_msg = "Failed"
            return f"⚠ {error_msg}", "login-error visible", "", "login-success"
    except Exception:
        return "⚠ Backend not reachable — demo mode only.", "login-error visible", "", "login-success"


# ── SHARED PAGE HELPERS ───────────────────────────────────────────────────────
def cs(border_color=None):
    return {
        "backgroundColor": "var(--bg-card)",
        "border": f"1px solid {border_color or 'var(--border-color)'}",
        "borderRadius": "8px",
        "boxShadow": "0 4px 20px rgba(0,0,0,0.4)",
    }

def section_label(text):
    return html.P(text, style={
        "fontSize": "9px", "fontWeight": "700", "letterSpacing": "0.14em",
        "textTransform": "uppercase", "color": "var(--text-dimmed)", "marginBottom": "10px"
    })

def stat_card(label, value, sub, color):
    return dbc.Card(dbc.CardBody([
        html.P(label, style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                             "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
        html.H3(value, style={"color": color, "fontWeight": "700", "fontSize": "24px",
                              "letterSpacing": "-0.02em", "marginBottom": "4px"}),
        html.P(sub, style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
    ]), style=cs(), className="metric-card")


# ── PAGE CONTENT RENDER ───────────────────────────────────────────────────────
@app.callback(
    Output("page-content", "children"),
    Input("url",        "pathname"),
    State("auth-store", "data"),
    prevent_initial_call=False,
)
def render_page_content(pathname, auth_data):
    is_logged_in = auth_data and auth_data.get("logged_in", False)
    if not is_logged_in:
        raise dash.exceptions.PreventUpdate

    if pathname in ("/", "/operator"):
        return render_operator_overview()
    elif pathname == "/process-map":
        return render_process_map()
    elif pathname == "/trends":
        return render_trends()
    elif pathname == "/alarms":
        return render_alarms(auth_data)
    elif pathname == "/events":
        return render_events()
    elif pathname == "/equipment":
        return render_equipment(auth_data)
    elif pathname == "/ai-insights":
        return render_ai_insights()
    elif pathname == "/reports":
        return render_reports("Operator")
    elif pathname == "/settings":
        return render_settings()
    elif pathname == "/engineer":
        return render_engineer_overview()
    elif pathname == "/engineer/diagnostics":
        return render_engineer_diagnostics()
    elif pathname == "/engineer/calibration":
        return render_engineer_calibration()
    elif pathname == "/engineer/signals":
        return render_engineer_signals()
    elif pathname == "/engineer/maintenance":
        return render_engineer_maintenance()
    elif pathname == "/engineer/trends":
        return render_trends()
    elif pathname == "/engineer/reports":
        return render_reports("Engineer")
    elif pathname == "/engineer/settings":
        return render_settings()
    elif pathname == "/manager":
        return render_manager_executive()
    elif pathname == "/manager/performance":
        return render_manager_performance()
    elif pathname == "/manager/kpis":
        return render_manager_kpis()
    elif pathname == "/manager/shifts":
        return render_manager_shifts()
    elif pathname == "/manager/compliance":
        return render_manager_compliance()
    elif pathname == "/manager/budget":
        return render_manager_budget()
    elif pathname == "/manager/reports":
        return render_reports("Manager")
    elif pathname == "/manager/settings":
        return render_settings()

    return html.Div([
        html.H3("Page Not Found"),
        html.P(f"No page configured for: {pathname}", style={"color": "var(--text-muted)"}),
    ])


# ── TREND RANGE STORE ─────────────────────────────────────────────────────────
@app.callback(
    Output("trend-range-store", "data"),
    Input("trend-btn-1h",  "n_clicks"),
    Input("trend-btn-6h",  "n_clicks"),
    Input("trend-btn-24h", "n_clicks"),
    Input("trend-btn-7d",  "n_clicks"),
    prevent_initial_call=True,
)
def update_trend_range(b1, b6, b24, b7):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    tid = ctx.triggered[0]["prop_id"].split(".")[0]
    return {"trend-btn-1h": "1H", "trend-btn-6h": "6H",
            "trend-btn-24h": "24H", "trend-btn-7d": "7D"}.get(tid, "1H")


# ── ALARM ACK/SUPPRESS ────────────────────────────────────────────────────────
@app.callback(
    Output("alarm-ack-store", "data"),
    Input("alarm-ack-all-btn",  "n_clicks"),
    Input("alarm-supp-btn",     "n_clicks"),
    Input({"type": "alarm-row-ack",  "index": ALL}, "n_clicks"),
    Input({"type": "alarm-row-supp", "index": ALL}, "n_clicks"),
    State("alarm-ack-store",    "data"),
    State("latest-data-store",  "data"),
    State("auth-store",         "data"),
    prevent_initial_call=True,
)
def handle_alarm_actions(ack_clicks, supp_clicks, row_ack, row_supp, store, live_data, auth_data):
    ctx = dash.callback_context
    if not ctx.triggered or not live_data:
        raise dash.exceptions.PreventUpdate

    prop_id = ctx.triggered[0]["prop_id"]
    triggered_val = ctx.triggered[0]["value"]
    if not triggered_val:
        raise dash.exceptions.PreventUpdate

    alerts_raw, _ = analyze_data(live_data)
    store = store or {"unack": 0, "ack": 0, "supp": 0, "acked_ids": [], "supp_ids": []}
    acked_ids = list(store.get("acked_ids", []))
    supp_ids  = list(store.get("supp_ids",  []))

    if "alarm-ack-all-btn" in prop_id:
        # Ack all current alarms
        all_ids = [str(i) for i in range(len(alerts_raw))]
        new_acked = list(set(acked_ids + all_ids))
        total_newly_acked = len([i for i in all_ids if i not in acked_ids])
        return {
            "unack": 0,
            "ack":   store.get("ack", 0) + total_newly_acked,
            "supp":  store.get("supp", 0),
            "acked_ids": new_acked,
            "supp_ids":  supp_ids,
        }

    elif "alarm-supp-btn" in prop_id and "index" not in prop_id:
        # Suppress all current alarms
        all_ids = [str(i) for i in range(len(alerts_raw))]
        new_supp = list(set(supp_ids + all_ids))
        total_newly_supp = len([i for i in all_ids if i not in supp_ids])
        return {
            "unack": 0,
            "ack":   store.get("ack", 0),
            "supp":  store.get("supp", 0) + total_newly_supp,
            "acked_ids": acked_ids,
            "supp_ids":  new_supp,
        }

    elif '"type":"alarm-row-ack"' in prop_id:
        import json
        try:
            id_part = prop_id.split(".")[0]
            alarm_index = str(json.loads(id_part)["index"])
        except Exception:
            raise dash.exceptions.PreventUpdate
        if alarm_index not in acked_ids:
            acked_ids.append(alarm_index)
            new_ack_count = store.get("ack", 0) + 1
        else:
            new_ack_count = store.get("ack", 0)
        active = len([i for i in range(len(alerts_raw))
                      if str(i) not in acked_ids and str(i) not in supp_ids])
        return {
            "unack": active,
            "ack":   new_ack_count,
            "supp":  store.get("supp", 0),
            "acked_ids": acked_ids,
            "supp_ids":  supp_ids,
        }

    elif '"type":"alarm-row-supp"' in prop_id:
        import json
        try:
            id_part = prop_id.split(".")[0]
            alarm_index = str(json.loads(id_part)["index"])
        except Exception:
            raise dash.exceptions.PreventUpdate
        if alarm_index not in supp_ids:
            supp_ids.append(alarm_index)
            new_supp_count = store.get("supp", 0) + 1
        else:
            new_supp_count = store.get("supp", 0)
        active = len([i for i in range(len(alerts_raw))
                      if str(i) not in acked_ids and str(i) not in supp_ids])
        return {
            "unack": active,
            "ack":   store.get("ack", 0),
            "supp":  new_supp_count,
            "acked_ids": acked_ids,
            "supp_ids":  supp_ids,
        }

    return store


# ── REPORT GENERATE ───────────────────────────────────────────────────────────
@app.callback(
    Output("report-gen-store",    "data"),
    Output("report-gen-feedback", "children"),
    Output("report-gen-feedback", "style"),
    Input("generate-report-btn",  "n_clicks"),
    State("report-type-select",   "value"),
    State("report-gen-store",     "data"),
    State("latest-data-store",    "data"),
    prevent_initial_call=True,
)
def generate_report(n_clicks, rtype, store, live_data):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    store = store or {"last": None, "count": 47}
    now_str  = datetime.now().strftime("%H:%M:%S")
    now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_store = {"last": now_str, "count": store.get("count", 47) + 1}
    label = rtype or "Daily Ops Summary"
    history_list = list(sensor_history)[-20:]
    csv_rows = ["Timestamp,Temperature_C,Pressure_PSI,RPM"]
    for d in history_list:
        ts = d["timestamp"].strftime("%H:%M:%S") if hasattr(d["timestamp"], "strftime") else str(d["timestamp"])[-8:]
        csv_rows.append(f"{ts},{d['temperature']:.2f},{d['pressure']:.2f},{d['rpm']:.0f}")
    csv_content = "\n".join(csv_rows)
    html_rows = ""
    for d in history_list:
        ts = d["timestamp"].strftime("%H:%M:%S") if hasattr(d["timestamp"], "strftime") else str(d["timestamp"])[-8:]
        html_rows += f"<tr><td>{ts}</td><td>{d['temperature']:.2f}</td><td>{d['pressure']:.2f}</td><td>{d['rpm']:.0f}</td></tr>"
    kpi_rows = """
        <tr><td>Overall Equipment Effectiveness (OEE)</td><td>87.4%</td><td>90%</td></tr>
        <tr><td>Mean Time Between Failures (MTBF)</td><td>612 h</td><td>720 h</td></tr>
        <tr><td>Mean Time To Repair (MTTR)</td><td>1.8 h</td><td>2.5 h</td></tr>
        <tr><td>Alarm Rate (ALM/h)</td><td>22 /h</td><td>≤30/h</td></tr>
        <tr><td>Production Yield (YIELD)</td><td>96.2%</td><td>97%</td></tr>
        <tr><td>Energy Intensity (kWh/t)</td><td>40.1</td><td>≤42</td></tr>
        <tr><td>Safety Incident Rate (SIR)</td><td>0</td><td>0</td></tr>
        <tr><td>Preventive Maintenance % (PM%)</td><td>74%</td><td>80%</td></tr>
    """
    html_content = f"""
    <html><head><title>{label}</title>
    <style>body{{font-family:sans-serif;padding:20px;}}table{{width:100%;border-collapse:collapse;margin-bottom:20px;}}th,td{{border:1px solid #ccc;padding:8px;text-align:left;}}th{{background:#f4f4f4;color:black;}}td{{color:black;}}</style>
    </head><body>
    <h1>NEXUS IQ Plant - {label}</h1><p><strong>Generated:</strong> {now_full}</p>
    <h2>KPI Scorecard</h2><table><tr><th>KPI</th><th>Current Value</th><th>Target</th></tr>{kpi_rows}</table>
    <h2>Last 20 Sensor Readings</h2><table><tr><th>Timestamp</th><th>Temperature (°C)</th><th>Pressure (PSI)</th><th>RPM</th></tr>{html_rows}</table>
    </body></html>"""
    csv_b64  = base64.b64encode(csv_content.encode()).decode()
    html_b64 = base64.b64encode(html_content.encode("utf-8")).decode()
    filename      = f"{label.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    html_filename = f"{label.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    msg = html.Div([
        html.Span(f"✓ '{label}' generated at {now_str} — ", style={"color": "#A5D6A7"}),
        html.A("⬇ Download CSV",
               href=f"data:text/csv;base64,{csv_b64}", download=filename,
               style={"color": "#00E676", "fontWeight": "700", "textDecoration": "underline", "cursor": "pointer", "marginRight": "12px"}),
        html.A("⬇ Download HTML Report",
               href=f"data:text/html;base64,{html_b64}", download=html_filename,
               style={"color": "#00E676", "fontWeight": "700", "textDecoration": "underline", "cursor": "pointer"}),
    ])
    style = {"backgroundColor": "rgba(0,230,118,0.08)", "border": "1px solid rgba(0,230,118,0.3)",
             "borderRadius": "4px", "color": "#A5D6A7", "fontSize": "12px",
             "padding": "10px 14px", "marginTop": "12px", "display": "block"}
    return new_store, msg, style


# ── SETTINGS SAVE ─────────────────────────────────────────────────────────────
@app.callback(
    Output("settings-store",         "data"),
    Output("settings-save-feedback", "children"),
    Output("settings-save-feedback", "style"),
    Input("settings-save-btn",       "n_clicks"),
    State("settings-refresh-select", "value"),
    State("settings-ai-toggle",      "value"),
    State("settings-notif-toggle",   "value"),
    State("settings-export-select",  "value"),
    State("settings-temp-warn",      "value"),
    State("settings-temp-crit",      "value"),
    State("settings-pres-warn",      "value"),
    State("settings-pres-crit",      "value"),
    State("settings-rpm-warn",       "value"),
    State("settings-rpm-crit",       "value"),
    State("settings-store",          "data"),
    prevent_initial_call=True,
)
def save_settings(n_clicks, refresh, ai, notif, export_fmt, tw, tc, pw, pc, rw, rc, store):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    new_store = {
        "refresh": refresh or 2, "ai": bool(ai), "notifications": bool(notif),
        "export_fmt": export_fmt or "CSV",
        "temp_warn": tw or 110, "temp_crit": tc or 130,
        "pres_warn": pw or 80,  "pres_crit": pc or 60,
        "rpm_warn":  rw or 1700,"rpm_crit":  rc or 2000,
    }
    style = {"backgroundColor": "rgba(0,230,118,0.08)", "border": "1px solid rgba(0,230,118,0.3)",
             "borderRadius": "4px", "color": "#A5D6A7", "fontSize": "12px",
             "padding": "10px 14px", "marginTop": "12px", "display": "block"}
    return new_store, "✓ Settings saved successfully.", style


# ═══════════════════════════════════════════════════════════════════════════════
# ── PAGE RENDERER FUNCTIONS ──────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def render_operator_overview():
    return html.Div([
        html.H3("Overview Dashboard"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("System Uptime", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                               "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("0d 0h 0m", id="uptime-display", style={"color": SUCCESS_COLOR, "fontWeight": "700", "fontSize": "24px",
                                                                 "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Since last restart", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col(stat_card("Active Alarms",  "2 CRITICAL",  "3 warnings pending",       CRITICAL_COLOR), width=3),
            dbc.Col(stat_card("Data Rate",      "1.24k pts/s", "All sensors reporting",    ACCENT_COLOR),   width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("AI Filter Rate", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                                "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("78%", id="ai-filter-display", style={"color": INFO_COLOR, "fontWeight": "700", "fontSize": "24px",
                                                               "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Noise suppressed this shift", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
        ], className="mb-3"),
        html.Div(id="overview-metrics-container"),
        html.Hr(),
        html.H4("LIVE TRENDS"),
        dcc.Graph(id="overview-trend-graph"),
        html.Hr(),
        html.H4("ALERT LOG (PRIORITIZED)"),
        html.Div(id="overview-alerts-container"),
    ])


def render_process_map():
    flow_steps = [
        ("01", "Raw Material Inlet",   "Feed pump draws raw material at 2.4 m³/h",        SUCCESS_COLOR),
        ("02", "Pre-Heat Exchanger",   "Fluid pre-heated from ambient to 75°C",            ACCENT_COLOR),
        ("03", "Reactor Vessel R-401", "Primary reaction zone — temp 110–135°C, 90 PSI",   WARNING_COLOR),
        ("04", "Cooling Loop CL-1",    "Post-reaction cooling to 40°C via chilled water",  INFO_COLOR),
        ("05", "Separator S-101",      "Gas–liquid separation; gas vented to flare header",ACCENT_COLOR),
        ("06", "Product Storage T-5",  "Final product stored in 50 kL buffer tank",        SUCCESS_COLOR),
    ]
    pipe_rows = [
        ("P-101", "Feed Line",      "2½″ CS", "2.4 m³/h", "85 PSI", "●  Active"),
        ("P-202", "Reactor Inlet",  "2″ SS",  "1.8 m³/h", "90 PSI", "●  Active"),
        ("P-303", "Cooling Return", "3″ CS",  "4.1 m³/h", "35 PSI", "●  Active"),
        ("P-404", "Product Line",   "2″ CS",  "2.1 m³/h", "20 PSI", "●  Active"),
        ("P-505", "Flare Header",   "4″ CS",  "0.3 m³/h", "5 PSI",  "●  Active"),
    ]
    return html.Div([
        html.H3("Process Map"),
        dbc.Row([
            dbc.Col(stat_card("Active Streams", "5",     "All lines flowing",  SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("Total Flow",     "10.6 m³/h","Combined output", ACCENT_COLOR),  width=3),
            dbc.Col(stat_card("Reactor Temp",   "112°C",  "Within target",     WARNING_COLOR), width=3),
            dbc.Col(stat_card("System Pressure","90 PSI", "Reactor inlet",     INFO_COLOR),    width=3),
        ], className="mb-3"),
        section_label("Process Flow"),
        html.Div([
            html.Div([
                html.Div([
                    html.Div([
                        html.Span(step[0], style={"fontSize": "9px", "fontWeight": "700", "color": step[3],
                                                   "letterSpacing": "0.1em", "marginBottom": "4px", "display": "block"}),
                        html.Span(step[1], style={"fontSize": "13px", "fontWeight": "700", "color": "var(--text-primary)",
                                                   "display": "block", "marginBottom": "4px"}),
                        html.Span(step[2], style={"fontSize": "11px", "color": "var(--text-muted)", "lineHeight": "1.5"}),
                    ], style={"padding": "16px", "flex": "1"}),
                    html.Div(style={"width": "3px", "backgroundColor": step[3], "borderRadius": "2px",
                                    "margin": "12px 0", "opacity": "0.6"}),
                ], style={"display": "flex", "backgroundColor": "var(--bg-card)",
                          "border": f"1px solid var(--border-color)", "borderLeft": f"3px solid {step[3]}",
                          "borderRadius": "6px", "marginBottom": "8px", "transition": "all 0.2s ease"})
                for step in flow_steps
            ])
        ], style={"marginBottom": "20px"}),
        section_label("Piping & Instrumentation"),
        dbc.Card(dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h, style={"color": ACCENT_COLOR, "fontSize": "9px", "fontWeight": "700",
                                       "padding": "6px 12px", "letterSpacing": "0.1em",
                                       "textTransform": "uppercase", "borderBottom": "1px solid var(--border-color)"})
                    for h in ["Line Tag", "Description", "Pipe Spec", "Flow Rate", "Pressure", "Status"]
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(r[0], style={"fontSize": "11px", "padding": "8px 12px", "fontFamily": "monospace", "color": "var(--text-dimmed)", "borderBottom": "1px solid var(--border-color)"}),
                        html.Td(r[1], style={"fontSize": "12px", "padding": "8px 12px", "color": "var(--text-primary)", "borderBottom": "1px solid var(--border-color)"}),
                        html.Td(r[2], style={"fontSize": "11px", "padding": "8px 12px", "color": "var(--text-muted)", "borderBottom": "1px solid var(--border-color)"}),
                        html.Td(r[3], style={"fontSize": "12px", "padding": "8px 12px", "color": "var(--text-primary)", "fontWeight": "600", "borderBottom": "1px solid var(--border-color)"}),
                        html.Td(r[4], style={"fontSize": "12px", "padding": "8px 12px", "color": "var(--text-primary)", "fontWeight": "600", "borderBottom": "1px solid var(--border-color)"}),
                        html.Td(html.Span(r[5], style={"fontSize": "11px", "fontWeight": "700", "color": SUCCESS_COLOR}),
                                style={"padding": "8px 12px", "borderBottom": "1px solid var(--border-color)"}),
                    ]) for r in pipe_rows
                ])
            ], style={"width": "100%", "borderCollapse": "collapse"})
        ]), style=cs()),
    ])


def render_trends():
    return html.Div([
        html.H3("Trend Analysis"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("Avg Temp (last 10)", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                                     "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("—", id="avg-temp-display", style={"color": "#FF7043", "fontWeight": "700", "fontSize": "24px",
                                                             "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Rolling average", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("Avg Pressure (last 10)", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                                          "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("—", id="avg-pres-display", style={"color": "#42A5F5", "fontWeight": "700", "fontSize": "24px",
                                                              "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Rolling average", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col([
                html.Div([
                    dbc.Button("1H",  id="trend-btn-1h",  color="primary",           size="sm", className="me-1"),
                    dbc.Button("6H",  id="trend-btn-6h",  color="outline-secondary", size="sm", className="me-1"),
                    dbc.Button("24H", id="trend-btn-24h", color="outline-secondary", size="sm", className="me-1"),
                    dbc.Button("7D",  id="trend-btn-7d",  color="outline-secondary", size="sm"),
                ], style={"display": "flex", "alignItems": "center", "height": "100%", "paddingLeft": "10px"}),
            ], width=6),
        ], className="mb-3"),
        html.P("—", id="trend-range-label", style={"fontSize": "10px", "color": "var(--text-dimmed)", "marginBottom": "8px", "letterSpacing": "0.06em"}),
        dbc.Card(dbc.CardBody([
            dcc.Graph(id="full-trend-graph", config={"displayModeBar": False}, style={"height": "360px"})
        ]), style=cs()),
    ])


def render_alarms(auth_data):
    return html.Div([
        html.H3("Alarm Management"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("Unacknowledged", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                                 "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("—", id="alarm-unack-count", style={"color": CRITICAL_COLOR, "fontWeight": "700",
                                                              "fontSize": "24px", "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Require action", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("Acknowledged", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                               "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("0", id="alarm-ack-count", style={"color": SUCCESS_COLOR, "fontWeight": "700",
                                                           "fontSize": "24px", "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Cleared this session", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("Suppressed", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                             "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("0", id="alarm-supp-count", style={"color": WARNING_COLOR, "fontWeight": "700",
                                                            "fontSize": "24px", "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Muted by operator", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col([
                html.Div([
                    html.Button("✓ ACK ALL", id="alarm-ack-all-btn", n_clicks=0,
                        style={"background": "#00E676", "border": "none", "borderRadius": "4px",
                               "color": "#09090b", "fontSize": "10px", "fontWeight": "700",
                               "padding": "8px 16px", "cursor": "pointer", "letterSpacing": "0.08em",
                               "textTransform": "uppercase", "fontFamily": "Inter, sans-serif",
                               "transition": "all 0.18s ease", "marginRight": "8px"}),
                    html.Button("⊘ SUPPRESS ALL", id="alarm-supp-btn", n_clicks=0,
                        style={"background": "transparent", "border": "1px solid #26C6DA",
                               "borderRadius": "4px", "color": "#26C6DA", "fontSize": "10px",
                               "fontWeight": "700", "padding": "8px 16px", "cursor": "pointer",
                               "letterSpacing": "0.08em", "textTransform": "uppercase",
                               "fontFamily": "Inter, sans-serif", "transition": "all 0.18s ease"}),
                ], style={"display": "flex", "alignItems": "center", "height": "100%", "paddingLeft": "10px"}),
            ], width=3),
        ], className="mb-3"),
        html.H4("LIVE ALARM LOG"),
        html.Div(id="full-alarms-container"),
    ])


def render_events():
    events = [
        ("2025-12-01 08:14", "ALARM",  "PT-202 Low Pressure alarm activated — 22.1 PSI",            CRITICAL_COLOR),
        ("2025-12-01 08:10", "ACTION", "Operator acknowledged vibration alarm on VT-401",            INFO_COLOR),
        ("2025-12-01 07:55", "ALARM",  "VT-401 Vibration elevated — 4.1 mm/s",                      WARNING_COLOR),
        ("2025-12-01 07:00", "INFO",   "Shift changeover — Day A commenced",                         SUCCESS_COLOR),
        ("2025-11-30 22:11", "INFO",   "FT-301 flow interruption auto-recovered",                    SUCCESS_COLOR),
        ("2025-11-30 20:00", "ACTION", "Operator P-202 pump inspection initiated",                   INFO_COLOR),
        ("2025-11-30 18:45", "ALARM",  "High Temperature alarm — Reactor R-401 reached 131°C",      CRITICAL_COLOR),
        ("2025-11-30 18:50", "ACTION", "Cooling loop CL-1 flow rate increased by operator",         INFO_COLOR),
        ("2025-11-30 18:55", "INFO",   "Reactor R-401 temperature normalized — 112°C",              SUCCESS_COLOR),
        ("2025-11-30 14:00", "INFO",   "Daily sensor calibration check completed — all OK",          SUCCESS_COLOR),
    ]
    return html.Div([
        html.H3("Event Log"),
        dbc.Row([
            dbc.Col(stat_card("Events Today",    "12",  "All categories",     ACCENT_COLOR),   width=3),
            dbc.Col(stat_card("Alarms Raised",   "3",   "2 critical, 1 warn", CRITICAL_COLOR), width=3),
            dbc.Col(stat_card("Operator Actions","4",   "Manual responses",   INFO_COLOR),     width=3),
            dbc.Col(stat_card("Auto-Recovered",  "2",   "System self-healed", SUCCESS_COLOR),  width=3),
        ], className="mb-3"),
        section_label("Event Timeline"),
        dbc.Card(dbc.CardBody([
            html.Div([
                html.Div([
                    html.Div(style={"width": "3px", "backgroundColor": ev[3],
                                    "borderRadius": "2px", "flexShrink": "0", "margin": "4px 16px 4px 4px"}),
                    html.Div([
                        html.Span(ev[0], style={"fontSize": "10px", "fontFamily": "monospace", "color": "var(--text-dimmed)", "marginRight": "10px"}),
                        html.Span(ev[1], style={"fontSize": "9px", "fontWeight": "700", "padding": "1px 6px",
                                                 "borderRadius": "2px", "backgroundColor": "var(--bg-surface)",
                                                 "color": ev[3], "border": f"1px solid {ev[3]}",
                                                 "letterSpacing": "0.06em", "marginRight": "10px"}),
                        html.Span(ev[2], style={"fontSize": "12px", "color": "var(--text-primary)"}),
                    ], style={"flex": "1", "padding": "6px 0"}),
                ], style={"display": "flex", "alignItems": "flex-start",
                          "padding": "8px 4px", "borderBottom": "1px solid var(--border-color)"})
                for ev in events
            ])
        ]), style=cs()),
    ])


def render_equipment(auth_data):
    return html.Div([
        html.H3("Equipment Monitor"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("Running", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                          "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("—", id="equip-running-count", style={"color": SUCCESS_COLOR, "fontWeight": "700",
                                                               "fontSize": "24px", "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Equipment active", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("Standby", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                          "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("—", id="equip-standby-count", style={"color": WARNING_COLOR, "fontWeight": "700",
                                                               "fontSize": "24px", "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("On standby", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.P("Faulted", style={"fontSize": "9px", "fontWeight": "700", "color": "var(--text-dimmed)",
                                          "textTransform": "uppercase", "letterSpacing": "0.12em", "marginBottom": "8px"}),
                html.H3("—", id="equip-fault-count", style={"color": CRITICAL_COLOR, "fontWeight": "700",
                                                             "fontSize": "24px", "letterSpacing": "-0.02em", "marginBottom": "4px"}),
                html.P("Require maintenance", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": 0}),
            ]), style=cs(), className="metric-card"), width=3),
            dbc.Col(stat_card("Fleet Health", "86%", "Average health score", SUCCESS_COLOR), width=3),
        ], className="mb-3"),
        section_label("Equipment Status"),
        dbc.Card(dbc.CardBody([
            html.Div(id="equipment-table-container")
        ]), style=cs()),
    ])


def render_ai_insights():
    return html.Div([
        html.H3("AI Insights"),
        dbc.Row([
            dbc.Col(stat_card("Anomalies Detected", "3",   "Last 50 readings",  WARNING_COLOR), width=3),
            dbc.Col(stat_card("Alerts Suppressed",  "18",  "This shift",         INFO_COLOR),   width=3),
            dbc.Col(stat_card("Prediction Accuracy","94.2%","30-day avg",        SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("AI Filter Rate",     "78%", "Noise suppressed",   ACCENT_COLOR),  width=3),
        ], className="mb-3"),
        section_label("Anomaly Detection — Live"),
        html.Div(id="ai-insights-container"),
    ])


def render_reports(role):
    return html.Div([
        html.H3(f"Reports — {role}"),
        dbc.Row([
            dbc.Col(stat_card("Reports Generated", "—", "This session",   ACCENT_COLOR),   width=3, id="reports-gen-count-wrapper"),
            dbc.Col(stat_card("Scheduled Reports", "4", "Daily/weekly",    INFO_COLOR),    width=3),
            dbc.Col(stat_card("Last Generated",    "—", "Timestamp",       SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("Export Formats",    "3", "CSV, XLSX, HTML", WARNING_COLOR), width=3),
        ], className="mb-3"),
        section_label("Generate Report"),
        dbc.Card(dbc.CardBody([
            html.Div([
                html.Label("Report Type", style={"fontSize": "10px", "fontWeight": "700", "color": "var(--text-muted)",
                                                  "textTransform": "uppercase", "marginBottom": "6px", "display": "block"}),
                dcc.Dropdown(
                    id="report-type-select",
                    options=[
                        {"label": "Daily Operations Summary", "value": "Daily Ops Summary"},
                        {"label": "Alarm Analysis Report",    "value": "Alarm Analysis"},
                        {"label": "Equipment Health Report",  "value": "Equipment Health"},
                        {"label": "Production KPI Report",   "value": "Production KPI"},
                        {"label": "Energy Efficiency Report", "value": "Energy Efficiency"},
                    ],
                    value="Daily Ops Summary", clearable=False,
                    style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)",
                           "border": "1px solid var(--border-color)", "borderRadius": "4px", "fontSize": "13px"},
                ),
            ], style={"marginBottom": "16px"}),
            html.Button("⬡  GENERATE & DOWNLOAD REPORT", id="generate-report-btn", n_clicks=0,
                style={"background": "#00E676", "border": "none", "borderRadius": "4px",
                       "color": "#09090b", "fontSize": "11px", "fontWeight": "700",
                       "padding": "10px 24px", "cursor": "pointer", "letterSpacing": "0.08em",
                       "textTransform": "uppercase", "fontFamily": "Inter, sans-serif",
                       "transition": "all 0.18s ease"}),
            html.Div(id="report-gen-feedback", style={"display": "none"}),
            html.Div(id="reports-gen-count", style={"display": "none"}),
        ]), style=cs()),
    ])


def render_settings():
    return html.Div([
        html.H3("Settings"),
        dbc.Row([
            dbc.Col([
                section_label("Display & Data"),
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Label("Refresh Interval (seconds)", style={"fontSize": "10px", "fontWeight": "700",
                                                                         "color": "var(--text-muted)", "letterSpacing": "0.1em",
                                                                         "textTransform": "uppercase", "marginBottom": "6px", "display": "block"}),
                        dcc.Dropdown(
                            id="settings-refresh-select",
                            options=[{"label": f"{s}s", "value": s} for s in [1, 2, 5, 10, 30]],
                            value=2, clearable=False,
                            style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)",
                                   "border": "1px solid var(--border-color)", "borderRadius": "4px", "fontSize": "13px"},
                        ),
                    ], style={"marginBottom": "16px"}),
                    html.Div([
                        html.Label("AI Engine", style={"fontSize": "10px", "fontWeight": "700",
                                                        "color": "var(--text-muted)", "letterSpacing": "0.1em",
                                                        "textTransform": "uppercase", "marginBottom": "6px", "display": "block"}),
                        dcc.Checklist(
                            id="settings-ai-toggle",
                            options=[{"label": "  Enable AI anomaly detection", "value": True}],
                            value=[True],
                            style={"fontSize": "12px", "color": "var(--text-primary)"},
                        ),
                    ], style={"marginBottom": "16px"}),
                    html.Div([
                        html.Label("Push Notifications", style={"fontSize": "10px", "fontWeight": "700",
                                                                  "color": "var(--text-muted)", "letterSpacing": "0.1em",
                                                                  "textTransform": "uppercase", "marginBottom": "6px", "display": "block"}),
                        dcc.Checklist(
                            id="settings-notif-toggle",
                            options=[{"label": "  Enable desktop notifications", "value": True}],
                            value=[True],
                            style={"fontSize": "12px", "color": "var(--text-primary)"},
                        ),
                    ], style={"marginBottom": "16px"}),
                    html.Div([
                        html.Label("Default Export Format", style={"fontSize": "10px", "fontWeight": "700",
                                                                     "color": "var(--text-muted)", "letterSpacing": "0.1em",
                                                                     "textTransform": "uppercase", "marginBottom": "6px", "display": "block"}),
                        dcc.Dropdown(
                            id="settings-export-select",
                            options=[{"label": x, "value": x} for x in ["CSV", "XLSX", "PDF", "JSON"]],
                            value="CSV", clearable=False,
                            style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)",
                                   "border": "1px solid var(--border-color)", "borderRadius": "4px", "fontSize": "13px"},
                        ),
                    ], style={"marginBottom": "20px"}),
                    html.Button("⬡  SAVE SETTINGS", id="settings-save-btn", n_clicks=0,
                        style={"background": "#00E676", "border": "none", "borderRadius": "4px",
                               "color": "#09090b", "fontSize": "11px", "fontWeight": "700",
                               "padding": "10px 24px", "cursor": "pointer", "letterSpacing": "0.08em",
                               "textTransform": "uppercase", "fontFamily": "Inter, sans-serif",
                               "transition": "all 0.18s ease"}),
                    html.Div(id="settings-save-feedback", style={"display": "none"}),
                ]), style=cs()),
            ], width=6),
            dbc.Col([
                section_label("Alarm Thresholds"),
                dbc.Card(dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Temp Warn (°C)", style={"fontSize": "10px", "fontWeight": "700", "color": "var(--text-muted)", "textTransform": "uppercase", "marginBottom": "4px"}),
                            dbc.Input(id="settings-temp-warn", type="number", style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)", "borderColor": "var(--border-color)", "fontSize": "12px", "marginBottom": "12px"})
                        ], width=6),
                        dbc.Col([
                            html.Label("Temp Crit (°C)", style={"fontSize": "10px", "fontWeight": "700", "color": "var(--text-muted)", "textTransform": "uppercase", "marginBottom": "4px"}),
                            dbc.Input(id="settings-temp-crit", type="number", style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)", "borderColor": "var(--border-color)", "fontSize": "12px", "marginBottom": "12px"})
                        ], width=6),
                    ]),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Pres Warn (PSI)", style={"fontSize": "10px", "fontWeight": "700", "color": "var(--text-muted)", "textTransform": "uppercase", "marginBottom": "4px"}),
                            dbc.Input(id="settings-pres-warn", type="number", style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)", "borderColor": "var(--border-color)", "fontSize": "12px", "marginBottom": "12px"})
                        ], width=6),
                        dbc.Col([
                            html.Label("Pres Crit (PSI)", style={"fontSize": "10px", "fontWeight": "700", "color": "var(--text-muted)", "textTransform": "uppercase", "marginBottom": "4px"}),
                            dbc.Input(id="settings-pres-crit", type="number", style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)", "borderColor": "var(--border-color)", "fontSize": "12px", "marginBottom": "12px"})
                        ], width=6),
                    ]),
                    dbc.Row([
                        dbc.Col([
                            html.Label("RPM Warn", style={"fontSize": "10px", "fontWeight": "700", "color": "var(--text-muted)", "textTransform": "uppercase", "marginBottom": "4px"}),
                            dbc.Input(id="settings-rpm-warn", type="number", style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)", "borderColor": "var(--border-color)", "fontSize": "12px"})
                        ], width=6),
                        dbc.Col([
                            html.Label("RPM Crit", style={"fontSize": "10px", "fontWeight": "700", "color": "var(--text-muted)", "textTransform": "uppercase", "marginBottom": "4px"}),
                            dbc.Input(id="settings-rpm-crit", type="number", style={"backgroundColor": "var(--bg-surface)", "color": "var(--text-primary)", "borderColor": "var(--border-color)", "fontSize": "12px"})
                        ], width=6),
                    ]),
                ]), style=cs()),
                html.Div(style={"height": "12px"}),
                section_label("About"),
                dbc.Card(dbc.CardBody([
                    html.P("NEXUS IQ", style={"fontSize": "16px", "fontWeight": "800", "color": ACCENT_COLOR, "marginBottom": "4px"}),
                    html.P("Industrial Intelligence Platform", style={"fontSize": "11px", "color": "var(--text-muted)", "marginBottom": "12px"}),
                    html.P("Version: 0.1 — Control Room Build — 2026", style={"fontSize": "11px", "color": "var(--text-dimmed)", "marginBottom": "4px"}),
                    html.P("Stack: Python · Dash · Plotly · Bootstrap", style={"fontSize": "11px", "color": "var(--text-dimmed)", "marginBottom": "4px"}),
                ]), style=cs()),
                html.Div(style={"height": "12px"}),
                section_label("Live System Status"),
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span(label, style={"fontSize": "11px", "color": "var(--text-primary)", "flex": "1"}),
                            html.Span(f"● {status}", style={"fontSize": "11px", "fontWeight": "700", "color": color}),
                        ], style={"display": "flex", "justifyContent": "space-between",
                                  "padding": "7px 0", "borderBottom": "1px solid var(--border-color)"})
                        for label, status, color in [
                            ("Data Ingestion",    "Live",    SUCCESS_COLOR),
                            ("AI Engine",         "Active",  SUCCESS_COLOR),
                            ("Alarm Processor",   "Running", SUCCESS_COLOR),
                            ("Report Scheduler",  "Online",  SUCCESS_COLOR),
                            ("Backend API",       "Demo" if not is_backend_available() else "Live",
                             WARNING_COLOR if not is_backend_available() else SUCCESS_COLOR),
                            ("Max Sensor History","300 pts", INFO_COLOR),
                        ]
                    ])
                ]), style=cs()),
            ], width=6),
        ]),
    ])


# ── ENGINEER PAGES ────────────────────────────────────────────────────────────
def render_engineer_overview():
    return html.Div([
        html.H3("Engineering Overview"),
        dbc.Row([
            dbc.Col(stat_card("Active Sensors",     "142 / 144","2 offline",            INFO_COLOR),    width=3),
            dbc.Col(stat_card("Calibration Due",    "6 Sensors","Within 30 days",       WARNING_COLOR), width=3),
            dbc.Col(stat_card("Open Work Orders",   "11",       "3 high priority",      CRITICAL_COLOR),width=3),
            dbc.Col(stat_card("System Signal Qual.","98.3%",    "Last 24h average",     SUCCESS_COLOR), width=3),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                section_label("Sensor Health Matrix"),
                dbc.Card(dbc.CardBody([
                    html.Table([
                        html.Thead(html.Tr([
                            html.Th(h, style={"color": INFO_COLOR, "fontSize": "9px", "fontWeight": "700",
                                               "padding": "6px 12px", "letterSpacing": "0.1em",
                                               "textTransform": "uppercase", "borderBottom": "1px solid var(--border-color)"})
                            for h in ["Sensor Tag", "Type", "Range", "Current Value", "Status", "Last Cal."]
                        ])),
                        html.Tbody([
                            html.Tr([
                                html.Td(row[0], style={"fontSize": "11px", "padding": "8px 12px", "fontFamily": "monospace", "color": "var(--text-dimmed)", "borderBottom": "1px solid var(--border-color)"}),
                                html.Td(row[1], style={"fontSize": "12px", "padding": "8px 12px", "color": "var(--text-primary)", "borderBottom": "1px solid var(--border-color)"}),
                                html.Td(row[2], style={"fontSize": "11px", "padding": "8px 12px", "color": "var(--text-muted)", "borderBottom": "1px solid var(--border-color)"}),
                                html.Td(row[3], style={"fontSize": "12px", "padding": "8px 12px", "color": "var(--text-primary)", "fontWeight": "600", "borderBottom": "1px solid var(--border-color)"}),
                                html.Td(html.Span(f"● {row[4]}", style={"fontSize": "11px", "fontWeight": "700",
                                    "color": SUCCESS_COLOR if row[4] == "OK" else WARNING_COLOR if row[4] == "Drift" else CRITICAL_COLOR}),
                                    style={"padding": "8px 12px", "borderBottom": "1px solid var(--border-color)"}),
                                html.Td(row[5], style={"fontSize": "11px", "padding": "8px 12px", "color": "var(--text-dimmed)", "fontFamily": "monospace", "borderBottom": "1px solid var(--border-color)"}),
                            ]) for row in [
                                ("TT-101","Temperature","0–200°C",   "112.4°C",  "OK",       "2025-11-01"),
                                ("TT-102","Temperature","0–200°C",   "108.1°C",  "OK",       "2025-11-01"),
                                ("PT-201","Pressure",   "0–300 PSI", "89.3 PSI", "OK",       "2025-10-15"),
                                ("PT-202","Pressure",   "0–300 PSI", "22.1 PSI", "Critical", "2025-10-15"),
                                ("FT-301","Flow",       "0–10 m³/h", "2.41 m³/h","OK",       "2025-09-20"),
                                ("VT-401","Vibration",  "0–10 mm/s", "4.1 mm/s", "Drift",    "2025-08-10"),
                                ("ST-501","Speed",      "0–3000 RPM","1432 RPM", "OK",       "2025-11-05"),
                            ]
                        ])
                    ], style={"width": "100%", "borderCollapse": "collapse"})
                ]), style=cs()),
            ], width=8),
            dbc.Col([
                section_label("I/O Bus Status"),
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span(bus, style={"fontSize": "11px", "color": "var(--text-primary)", "fontWeight": "600", "flex": "1"}),
                            html.Span(f"● {status}", style={"fontSize": "11px", "fontWeight": "700",
                                "color": SUCCESS_COLOR if status == "OK" else WARNING_COLOR}),
                            html.Span(f"  {load}", style={"fontSize": "11px", "color": "var(--text-muted)", "marginLeft": "8px"}),
                        ], style={"display": "flex", "alignItems": "center", "padding": "8px 0", "borderBottom": "1px solid var(--border-color)"})
                        for bus, status, load in [
                            ("Modbus RTU Bus A","OK","34 nodes"),
                            ("Modbus RTU Bus B","OK","28 nodes"),
                            ("HART Loop 1",     "OK","12 devices"),
                            ("HART Loop 2",  "Warning","8 devices"),
                            ("Profibus DP",     "OK","16 nodes"),
                            ("Ethernet/IP",     "OK","6 devices"),
                        ]
                    ])
                ]), style=cs()),
                html.Div(style={"height": "12px"}),
                section_label("Controller Health"),
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span(ctrl, style={"fontSize": "11px", "color": "var(--text-primary)", "fontWeight": "600", "flex": "1"}),
                            html.Span(f"CPU {cpu}", style={"fontSize": "11px", "color": INFO_COLOR}),
                        ], style={"display": "flex", "justifyContent": "space-between", "padding": "7px 0", "borderBottom": "1px solid var(--border-color)"})
                        for ctrl, cpu in [("PLC-01 (Reactor)","12%"),("PLC-02 (Cooling)","8%"),("PLC-03 (Feed)","15%"),("DCS Main Node","31%")]
                    ])
                ]), style=cs()),
            ], width=4),
        ]),
    ])


def render_engineer_diagnostics():
    faults = [
        ("F-0041","PT-202","CRITICAL","Out of range — reading 22.1 PSI (min: 60 PSI)","Active",   "2025-12-01 08:14"),
        ("F-0040","VT-401","WARNING", "Vibration drift — 4.1 mm/s (warn: 3.5 mm/s)", "Active",   "2025-12-01 07:55"),
        ("F-0039","HART L2","WARNING","Device comm error — 2 retries in last hour",   "Active",   "2025-12-01 06:30"),
        ("F-0038","TT-101","INFO",    "Calibration reminder — due within 30 days",    "Scheduled","2025-11-28 00:00"),
        ("F-0037","FT-301","CLEARED", "Brief flow interruption — auto-recovered",      "Cleared",  "2025-11-30 22:11"),
    ]
    color_map = {"CRITICAL": CRITICAL_COLOR,"WARNING": WARNING_COLOR,"INFO": INFO_COLOR,"CLEARED": SUCCESS_COLOR}
    return html.Div([
        html.H3("System Diagnostics"),
        dbc.Row([
            dbc.Col(stat_card("Active Faults",   "3","Require attention",    CRITICAL_COLOR),width=3),
            dbc.Col(stat_card("Warnings",         "2","Monitor closely",      WARNING_COLOR), width=3),
            dbc.Col(stat_card("Cleared Today",    "6","Auto or manual clear", SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("Comm Errors (24h)","14","Bus & device errors", INFO_COLOR),    width=3),
        ], className="mb-3"),
        section_label("Fault Log"),
        dbc.Card(dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h, style={"color": INFO_COLOR,"fontSize":"9px","fontWeight":"700",
                                       "padding":"6px 14px","letterSpacing":"0.1em",
                                       "textTransform":"uppercase","borderBottom":"1px solid var(--border-color)"})
                    for h in ["Fault ID","Device","Severity","Description","State","Timestamp"]
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(f[0],style={"fontSize":"11px","padding":"9px 14px","fontFamily":"monospace","color":"var(--text-dimmed)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(f[1],style={"fontSize":"12px","padding":"9px 14px","fontWeight":"600","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(html.Span(f[2],style={"fontSize":"9px","fontWeight":"700","padding":"2px 6px","borderRadius":"3px",
                                "backgroundColor":"var(--bg-surface)","color":color_map.get(f[2],"var(--text-primary)"),
                                "border":f"1px solid {color_map.get(f[2],'var(--border-color)')}","letterSpacing":"0.06em"}),
                            style={"padding":"9px 14px","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(f[3],style={"fontSize":"12px","padding":"9px 14px","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(f[4],style={"fontSize":"12px","padding":"9px 14px","color":SUCCESS_COLOR if f[4]=="Cleared" else "var(--text-primary)","fontWeight":"600","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(f[5],style={"fontSize":"11px","padding":"9px 14px","fontFamily":"monospace","color":"var(--text-dimmed)","borderBottom":"1px solid var(--border-color)"}),
                    ]) for f in faults
                ])
            ], style={"width":"100%","borderCollapse":"collapse"})
        ]),style=cs()),
    ])


def render_engineer_calibration():
    cal_items = [
        ("TT-101","Temperature","±0.2°C",  "2025-11-01","2025-12-15","Scheduled", WARNING_COLOR),
        ("TT-102","Temperature","±0.2°C",  "2025-11-01","2025-12-15","Scheduled", WARNING_COLOR),
        ("PT-201","Pressure",   "±0.5 PSI","2025-10-15","2026-01-15","OK",        SUCCESS_COLOR),
        ("PT-202","Pressure",   "±0.5 PSI","2025-10-15","2025-12-01","Overdue",   CRITICAL_COLOR),
        ("FT-301","Flow",       "±1.0%",   "2025-09-20","2026-03-20","OK",        SUCCESS_COLOR),
        ("VT-401","Vibration",  "±0.05 mm/s","2025-08-10","2025-11-10","Overdue", CRITICAL_COLOR),
        ("ST-501","Speed",      "±5 RPM",  "2025-11-05","2026-05-05","OK",        SUCCESS_COLOR),
    ]
    return html.Div([
        html.H3("Calibration Management"),
        dbc.Row([
            dbc.Col(stat_card("Calibrations Due",    "2","Within next 30 days",   WARNING_COLOR),  width=3),
            dbc.Col(stat_card("Overdue",             "2","Immediate action req'd", CRITICAL_COLOR), width=3),
            dbc.Col(stat_card("Completed This Month","4","On schedule",            SUCCESS_COLOR),  width=3),
            dbc.Col(stat_card("Next Scheduled",      "15 Dec","TT-101 / TT-102",  INFO_COLOR),     width=3),
        ], className="mb-3"),
        section_label("Calibration Register"),
        dbc.Card(dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h,style={"color":INFO_COLOR,"fontSize":"9px","fontWeight":"700",
                                      "padding":"6px 14px","letterSpacing":"0.1em",
                                      "textTransform":"uppercase","borderBottom":"1px solid var(--border-color)"})
                    for h in ["Tag","Type","Accuracy","Last Cal.","Next Cal.","Status"]
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(c[0],style={"fontSize":"11px","padding":"9px 14px","fontFamily":"monospace","color":"var(--text-dimmed)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(c[1],style={"fontSize":"12px","padding":"9px 14px","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(c[2],style={"fontSize":"11px","padding":"9px 14px","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(c[3],style={"fontSize":"11px","padding":"9px 14px","fontFamily":"monospace","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(c[4],style={"fontSize":"11px","padding":"9px 14px","fontFamily":"monospace","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(html.Span(f"● {c[5]}",style={"fontSize":"11px","fontWeight":"700","color":c[6]}),style={"padding":"9px 14px","borderBottom":"1px solid var(--border-color)"}),
                    ]) for c in cal_items
                ])
            ], style={"width":"100%","borderCollapse":"collapse"})
        ]),style=cs()),
    ])


SIGNALS_DATA = [
    ("AI-0101","TT-101","Analog Input", "4–20 mA","Temperature Reactor R-401",    "112.4°C",  "OK"),
    ("AI-0102","TT-102","Analog Input", "4–20 mA","Temperature Reactor R-401 (R)","108.1°C",  "OK"),
    ("AI-0201","PT-201","Analog Input", "4–20 mA","Pressure Reactor Inlet",        "89.3 PSI", "OK"),
    ("AI-0202","PT-202","Analog Input", "4–20 mA","Pressure Cooling Return",       "22.1 PSI", "Fault"),
    ("AI-0301","FT-301","Analog Input", "4–20 mA","Flow Feed Line P-101",          "2.41 m³/h","OK"),
    ("DI-0401","LS-401","Digital Input","24 VDC",  "Level Switch Tank T-5 High",   "0 (Clear)","OK"),
    ("DI-0402","LS-402","Digital Input","24 VDC",  "Level Switch Tank T-5 Low",    "0 (Clear)","OK"),
    ("DO-0501","SV-501","Digital Output","24 VDC", "Solenoid Valve — Feed Bypass", "0 (Closed)","OK"),
    ("AO-0601","FC-601","Analog Output","4–20 mA", "Flow Controller Output — P-101","8.3 mA",  "OK"),
    ("AI-0701","VT-401","Analog Input", "4–20 mA","Vibration Compressor K1",       "4.1 mm/s","Drift"),
]

def render_engineer_signals():
    return html.Div([
        html.H3("Signal Library"),
        dbc.Row([
            dbc.Col(stat_card("Total Signals",  "142","In database",         ACCENT_COLOR),  width=3),
            dbc.Col(stat_card("Analog Inputs",  "87", "AI channels",         INFO_COLOR),    width=3),
            dbc.Col(stat_card("Digital I/O",    "48", "DI / DO channels",    SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("Analog Outputs", "7",  "AO channels",         WARNING_COLOR), width=3),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(
                dcc.Input(id="signal-search", type="text",
                          placeholder="Filter by tag, type, or description...", debounce=True,
                          style={"width":"100%","backgroundColor":"var(--bg-surface)","color":"var(--text-primary)",
                                 "border":"1px solid var(--border-color)","borderRadius":"4px","padding":"8px 12px","fontSize":"12px"}),
                width=9
            ),
            dbc.Col([
                html.Button("⬇ Export Signal List", id="signal-export-btn",
                    style={"width":"100%","backgroundColor":"var(--bg-surface)","color":"#00E676",
                           "border":"1px solid #00E676","borderRadius":"4px","padding":"8px 12px",
                           "fontSize":"12px","fontWeight":"700","cursor":"pointer"}),
                html.Div(id="signal-export-feedback", style={"marginTop":"8px"}),
            ], width=3),
        ], className="mb-3"),
        html.Div(id="signals-status-summary", className="mb-3"),
        section_label("Signal Register"),
        dbc.Card(dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h,style={"color":INFO_COLOR,"fontSize":"9px","fontWeight":"700",
                                      "padding":"6px 12px","letterSpacing":"0.1em",
                                      "textTransform":"uppercase","borderBottom":"1px solid var(--border-color)"})
                    for h in ["Tag ID","Instrument","I/O Type","Signal","Description","Live Value","Status"]
                ])),
                html.Tbody(id="signals-table-body")
            ], style={"width":"100%","borderCollapse":"collapse"})
        ]),style=cs()),
    ])


def render_engineer_maintenance():
    work_orders = [
        ("WO-1041","P-202 Pump Repair",         "CRITICAL","Mech.",  "James T.","Active",   "2025-12-01","1"),
        ("WO-1040","VT-401 Vibration Check",    "HIGH",    "Instr.", "Sarah K.","Active",   "2025-12-02","3"),
        ("WO-1039","HART L2 Device Comm Fix",   "HIGH",    "Instr.", "TBD",     "Scheduled","2025-12-03","5"),
        ("WO-1038","Reactor R-401 Gasket Insp.","MEDIUM",  "Mech.",  "TBD",     "Scheduled","2025-12-05","7"),
        ("WO-1037","PT-202 Recalibration",      "HIGH",    "Instr.", "Sarah K.","Scheduled","2025-12-01","0"),
        ("WO-1036","Compressor K1 Oil Change",  "LOW",     "Mech.",  "TBD",     "Planned",  "2026-01-10","35"),
        ("WO-1035","E1 Tube Bundle Clean",      "LOW",     "Mech.",  "TBD",     "Planned",  "2026-02-01","56"),
    ]
    status_colors  = {"Active": CRITICAL_COLOR,"Scheduled": WARNING_COLOR,"Planned": INFO_COLOR}
    priority_colors= {"CRITICAL": CRITICAL_COLOR,"HIGH": WARNING_COLOR,"MEDIUM": INFO_COLOR,"LOW": SUCCESS_COLOR}
    return html.Div([
        html.H3("Maintenance Schedule"),
        dbc.Row([
            dbc.Col(stat_card("Active WOs",          "2","In progress now",  CRITICAL_COLOR),width=3),
            dbc.Col(stat_card("Scheduled WOs",       "3","Next 7 days",      WARNING_COLOR), width=3),
            dbc.Col(stat_card("Planned WOs",         "2","Next 30+ days",    INFO_COLOR),    width=3),
            dbc.Col(stat_card("Completed This Month","18","On schedule",      SUCCESS_COLOR), width=3),
        ], className="mb-3"),
        section_label("Work Order Queue"),
        dbc.Card(dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h,style={"color":INFO_COLOR,"fontSize":"9px","fontWeight":"700",
                                      "padding":"6px 12px","letterSpacing":"0.1em",
                                      "textTransform":"uppercase","borderBottom":"1px solid var(--border-color)"})
                    for h in ["WO #","Description","Priority","Trade","Assigned To","Status","Due Date","Days Left"]
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(wo[0],style={"fontSize":"11px","padding":"8px 12px","fontFamily":"monospace","color":"var(--text-dimmed)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(wo[1],style={"fontSize":"12px","padding":"8px 12px","fontWeight":"600","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(html.Span(wo[2],style={"fontSize":"9px","fontWeight":"700","padding":"2px 6px","borderRadius":"3px",
                                "backgroundColor":"var(--bg-surface)","color":priority_colors.get(wo[2],"var(--text-primary)"),
                                "border":f"1px solid {priority_colors.get(wo[2],'var(--border-color)')}","letterSpacing":"0.06em"}),
                            style={"padding":"8px 12px","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(wo[3],style={"fontSize":"11px","padding":"8px 12px","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(wo[4],style={"fontSize":"12px","padding":"8px 12px","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(html.Span(f"● {wo[5]}",style={"fontSize":"11px","fontWeight":"700","color":status_colors.get(wo[5],"var(--text-muted)")}),style={"padding":"8px 12px","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(wo[6],style={"fontSize":"11px","padding":"8px 12px","fontFamily":"monospace","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(wo[7],style={"fontSize":"12px","padding":"8px 12px","fontWeight":"700",
                                "color":CRITICAL_COLOR if wo[7]=="0" else WARNING_COLOR if int(wo[7])<7 else "var(--text-primary)",
                                "borderBottom":"1px solid var(--border-color)"}),
                    ]) for wo in work_orders
                ])
            ], style={"width":"100%","borderCollapse":"collapse"})
        ]),style=cs()),
    ])


# ── MANAGER PAGES ─────────────────────────────────────────────────────────────
def render_manager_executive():
    return html.Div([
        html.H3("Executive Summary"),
        dbc.Row([
            dbc.Col(stat_card("Plant OEE",         "87.4%", "This shift",      SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("Production Output", "142 t", "vs 155 t target", WARNING_COLOR), width=3),
            dbc.Col(stat_card("Downtime Today",    "34 min","2 incidents",      CRITICAL_COLOR),width=3),
            dbc.Col(stat_card("Active Workforce",  "24 / 26","2 on leave",     INFO_COLOR),    width=3),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                section_label("OEE Breakdown — This Shift"),
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span(label,style={"fontSize":"11px","color":"var(--text-muted)","width":"100px","display":"inline-block","fontWeight":"600"}),
                            html.Div(style={"display":"inline-block","height":"8px","width":f"{pct}%","background":color,"borderRadius":"2px","verticalAlign":"middle"}),
                            html.Span(f"  {val}",style={"fontSize":"12px","color":color,"fontWeight":"700","marginLeft":"8px"}),
                        ],style={"marginBottom":"16px"})
                        for label,pct,val,color in [
                            ("Availability",92,"92.1%",SUCCESS_COLOR),
                            ("Performance", 88,"88.4%",SUCCESS_COLOR),
                            ("Quality",     97,"97.2%",SUCCESS_COLOR),
                            ("OEE Total",   87,"87.4%",WARNING_COLOR),
                        ]
                    ])
                ]),style=cs()),
                html.Div(style={"height":"12px"}),
                section_label("Top Downtime Reasons Today"),
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span(f"{i+1}. {reason}",style={"fontSize":"12px","color":"var(--text-primary)","flex":"1"}),
                            html.Span(f"{mins} min",style={"fontSize":"12px","color":color,"fontWeight":"700"}),
                        ],style={"display":"flex","justifyContent":"space-between","padding":"8px 0","borderBottom":"1px solid var(--border-color)"})
                        for i,(reason,mins,color) in enumerate([
                            ("P-202 Pump Fault — Unplanned",        "21",CRITICAL_COLOR),
                            ("Reactor R-401 Temperature Stabilize", "8", WARNING_COLOR),
                            ("Shift Changeover (scheduled)",        "5", INFO_COLOR),
                        ])
                    ])
                ]),style=cs()),
            ],width=6),
            dbc.Col([
                section_label("Key Metrics vs. Target"),
                dbc.Card(dbc.CardBody([
                    html.Table([
                        html.Thead(html.Tr([
                            html.Th(h,style={"color":WARNING_COLOR,"fontSize":"9px","fontWeight":"700",
                                              "padding":"6px 10px","letterSpacing":"0.1em",
                                              "textTransform":"uppercase","borderBottom":"1px solid var(--border-color)"})
                            for h in ["KPI","Target","Actual","Variance"]
                        ])),
                        html.Tbody([
                            html.Tr([
                                html.Td(row[0],style={"fontSize":"12px","padding":"8px 10px","fontWeight":"600","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                                html.Td(row[1],style={"fontSize":"12px","padding":"8px 10px","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                                html.Td(row[2],style={"fontSize":"12px","padding":"8px 10px","color":"var(--text-primary)","fontWeight":"600","borderBottom":"1px solid var(--border-color)"}),
                                html.Td(row[3],style={"fontSize":"12px","padding":"8px 10px","fontWeight":"700",
                                        "color":SUCCESS_COLOR if row[3].startswith("+") else CRITICAL_COLOR,
                                        "borderBottom":"1px solid var(--border-color)"}),
                            ]) for row in [
                                ("Production Output","155 t",  "142 t",  "−13 t"),
                                ("OEE",             "90%",    "87.4%",  "−2.6%"),
                                ("Energy Intensity","≤ 42 kWh/t","40.1 kWh/t","+1.9 kWh/t"),
                                ("Alarm Rate",      "≤ 30/h", "22/h",   "+8/h"),
                                ("MTBF",            "720 h",  "612 h",  "−108 h"),
                                ("MTTR",            "≤ 2.5 h","1.8 h",  "+0.7 h"),
                            ]
                        ])
                    ],style={"width":"100%","borderCollapse":"collapse"})
                ]),style=cs()),
            ],width=6),
        ]),
    ])


def render_manager_performance():
    return html.Div([
        html.H3("Plant Performance"),
        dbc.Row([
            dbc.Col(stat_card("Monthly Production","3,840 t","vs 4,200 t target",   WARNING_COLOR), width=3),
            dbc.Col(stat_card("Capacity Utilization","91.4%","Average this month",  SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("Energy Consumption","154 MWh","This month",          INFO_COLOR),    width=3),
            dbc.Col(stat_card("Total Downtime",    "18.5 h","This month",           CRITICAL_COLOR),width=3),
        ], className="mb-3"),
        section_label("Daily Production — Last 7 Days"),
        dbc.Card(dbc.CardBody([
            dcc.Graph(
                figure=go.Figure(
                    data=[
                        go.Bar(name="Actual",x=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],
                               y=[148,155,140,162,145,138,142],marker_color=ACCENT_COLOR,opacity=0.85),
                        go.Scatter(name="Target",x=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],
                                   y=[155,155,155,155,155,155,155],mode="lines",
                                   line=dict(color=WARNING_COLOR,dash="dash",width=2)),
                    ],
                    layout=go.Layout(
                        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#8B949E",size=11),height=280,
                        margin=dict(l=40,r=20,t=20,b=40),
                        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
                        xaxis=dict(gridcolor="#27272a",linecolor="#27272a"),
                        yaxis=dict(gridcolor="#27272a",linecolor="#27272a",title="Tonnes"),
                    )
                ),
                config={"displayModeBar":False},
            )
        ]),style=cs()),
    ])


def render_manager_kpis():
    kpi_data = [
        ("Overall Equipment Effectiveness","OEE",   "87.4%","90%",  "−2.6%",  WARNING_COLOR),
        ("Mean Time Between Failures",     "MTBF",  "612 h","720 h","−108 h", WARNING_COLOR),
        ("Mean Time To Repair",            "MTTR",  "1.8 h","2.5 h","+0.7 h", SUCCESS_COLOR),
        ("Alarm Rate",                     "ALM/h", "22 /h","≤30/h","+8 /h",  SUCCESS_COLOR),
        ("Production Yield",               "YIELD", "96.2%","97%",  "−0.8%",  WARNING_COLOR),
        ("Energy Intensity",               "kWh/t", "40.1", "≤42",  "+1.9",   SUCCESS_COLOR),
        ("Safety Incident Rate",           "SIR",   "0",    "0",    "On target",SUCCESS_COLOR),
        ("Preventive Maintenance %",       "PM%",   "74%",  "80%",  "−6%",    WARNING_COLOR),
    ]
    return html.Div([
        html.H3("KPI Dashboard"),
        dbc.Row([
            dbc.Col(stat_card("KPIs On Target",    "5 / 8","This month",       SUCCESS_COLOR),width=3),
            dbc.Col(stat_card("KPIs Below Target", "3 / 8","Require focus",    WARNING_COLOR),width=3),
            dbc.Col(stat_card("Safety Incidents",  "0",    "This month — good!",SUCCESS_COLOR),width=3),
            dbc.Col(stat_card("PM Compliance",     "74%",  "vs 80% target",    WARNING_COLOR),width=3),
        ], className="mb-3"),
        section_label("KPI Scorecard — Current Month"),
        dbc.Card(dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Card(dbc.CardBody([
                        html.Div([
                            html.Span(k[1],style={"fontSize":"9px","fontWeight":"700","color":k[5],"letterSpacing":"0.1em"}),
                            html.H3(k[2],style={"color":k[5],"fontWeight":"700","fontSize":"22px","letterSpacing":"-0.02em","marginBottom":"2px"}),
                            html.P(k[0],style={"fontSize":"10px","color":"var(--text-muted)","marginBottom":"2px"}),
                            html.P(f"Target: {k[3]}  ·  {k[4]}",style={"fontSize":"10px","color":"var(--text-dimmed)","marginBottom":0}),
                        ])
                    ]),style={**cs(),"marginBottom":"8px"})
                    for k in kpi_data
                ],width=12)
            ])
        ]),style=cs()),
    ])


def render_manager_shifts():
    shifts = [
        ("Day A",  "06:00–14:00","2025-12-01","Sam R.",   "22 / 26","142 t","2 alarms","Normal"),
        ("Night B","22:00–06:00","2025-11-30","Maria L.", "24 / 26","138 t","5 alarms","P-202 Fault"),
        ("Day B",  "06:00–14:00","2025-11-30","Carlos M.","26 / 26","155 t","1 alarm", "Normal"),
        ("Night A","22:00–06:00","2025-11-29","Sam R.",   "25 / 26","151 t","3 alarms","Normal"),
        ("Day A",  "06:00–14:00","2025-11-29","Sam R.",   "26 / 26","158 t","0 alarms","Normal"),
    ]
    return html.Div([
        html.H3("Shift Reports"),
        dbc.Row([
            dbc.Col(stat_card("Shifts This Week","10",   "Mon–Sun",          ACCENT_COLOR),   width=3),
            dbc.Col(stat_card("Avg Production", "148 t", "Per shift",        SUCCESS_COLOR),  width=3),
            dbc.Col(stat_card("Incidents",      "1",     "P-202 pump fault", CRITICAL_COLOR), width=3),
            dbc.Col(stat_card("Avg Alarm Rate", "2.4/h", "Last 7 shifts",    INFO_COLOR),     width=3),
        ], className="mb-3"),
        section_label("Shift Handover Log"),
        dbc.Card(dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h,style={"color":WARNING_COLOR,"fontSize":"9px","fontWeight":"700",
                                      "padding":"6px 12px","letterSpacing":"0.1em",
                                      "textTransform":"uppercase","borderBottom":"1px solid var(--border-color)"})
                    for h in ["Shift","Hours","Date","Supervisor","Headcount","Output","Alarms","Notes"]
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(s[0],style={"fontSize":"12px","padding":"9px 12px","fontWeight":"600","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(s[1],style={"fontSize":"11px","padding":"9px 12px","color":"var(--text-muted)","fontFamily":"monospace","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(s[2],style={"fontSize":"11px","padding":"9px 12px","color":"var(--text-dimmed)","fontFamily":"monospace","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(s[3],style={"fontSize":"12px","padding":"9px 12px","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(s[4],style={"fontSize":"12px","padding":"9px 12px","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(s[5],style={"fontSize":"12px","padding":"9px 12px","fontWeight":"700","color":SUCCESS_COLOR,"borderBottom":"1px solid var(--border-color)"}),
                        html.Td(s[6],style={"fontSize":"12px","padding":"9px 12px","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(s[7],style={"fontSize":"12px","padding":"9px 12px",
                                "color":CRITICAL_COLOR if s[7]!="Normal" else SUCCESS_COLOR,
                                "fontWeight":"600" if s[7]!="Normal" else "400",
                                "borderBottom":"1px solid var(--border-color)"}),
                    ]) for s in shifts
                ])
            ],style={"width":"100%","borderCollapse":"collapse"})
        ]),style=cs()),
    ])


def render_manager_compliance():
    compliance_items = [
        ("Environmental Emissions",   "EPA Reg. 40 CFR 63","Compliant",   SUCCESS_COLOR,"2025-12-31","Quarterly audit passed Oct 2025"),
        ("Pressure Vessel Inspection","ASME / PED 2014",   "Due 15 Jan",  WARNING_COLOR,"2026-01-15","Reactor R-401 — schedule inspector"),
        ("Electrical Safety",         "NFPA 70E",          "Compliant",   SUCCESS_COLOR,"2026-06-01","Arc flash study current"),
        ("Process Safety Mgmt",       "OSHA 29 CFR 1910.119","Compliant", SUCCESS_COLOR,"2026-03-01","PSM review scheduled Q1 2026"),
        ("ISO 14001 Environmental",   "ISO 14001:2015",    "Certified",   SUCCESS_COLOR,"2026-09-01","Certificate expires Sep 2026"),
        ("ISO 45001 Safety",          "ISO 45001:2018",    "Under Review",WARNING_COLOR,"2025-12-20","Annual surveillance audit 20 Dec"),
    ]
    return html.Div([
        html.H3("Compliance Tracking"),
        dbc.Row([
            dbc.Col(stat_card("Compliant Items", "4","Currently met",   SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("Due for Review",  "2","Action required", WARNING_COLOR), width=3),
            dbc.Col(stat_card("Next Audit",      "20 Dec","ISO 45001",  INFO_COLOR),    width=3),
            dbc.Col(stat_card("Non-Conformances","0","This quarter",    ACCENT_COLOR),  width=3),
        ], className="mb-3"),
        section_label("Compliance Register"),
        dbc.Card(dbc.CardBody([
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h,style={"color":WARNING_COLOR,"fontSize":"9px","fontWeight":"700",
                                      "padding":"6px 12px","letterSpacing":"0.1em",
                                      "textTransform":"uppercase","borderBottom":"1px solid var(--border-color)"})
                    for h in ["Requirement","Standard / Regulation","Status","Next Due","Notes"]
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(c[0],style={"fontSize":"12px","padding":"9px 12px","fontWeight":"600","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(c[1],style={"fontSize":"11px","padding":"9px 12px","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(html.Span(f"● {c[2]}",style={"fontSize":"11px","fontWeight":"700","color":c[3]}),style={"padding":"9px 12px","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(c[4],style={"fontSize":"11px","padding":"9px 12px","fontFamily":"monospace","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                        html.Td(c[5],style={"fontSize":"12px","padding":"9px 12px","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
                    ]) for c in compliance_items
                ])
            ],style={"width":"100%","borderCollapse":"collapse"})
        ]),style=cs()),
    ])


def render_manager_budget():
    return html.Div([
        html.H3("Budget & Cost Tracking"),
        dbc.Row([
            dbc.Col(stat_card("Opex Spend MTD",  "$284k","vs $310k budget",  SUCCESS_COLOR), width=3),
            dbc.Col(stat_card("Maintenance Cost","$42k", "This month",       WARNING_COLOR), width=3),
            dbc.Col(stat_card("Energy Cost",     "$61k", "This month",       INFO_COLOR),    width=3),
            dbc.Col(stat_card("Cost per Tonne",  "$74.0","vs $73.8 target",  WARNING_COLOR), width=3),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                section_label("Opex Budget vs. Actual — By Category"),
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span(cat,style={"fontSize":"11px","color":"var(--text-muted)","width":"120px","display":"inline-block","fontWeight":"600"}),
                            html.Div(style={"display":"inline-block","height":"7px","width":f"{pct}%",
                                           "background":SUCCESS_COLOR if pct<=90 else WARNING_COLOR if pct<=100 else CRITICAL_COLOR,
                                           "borderRadius":"2px","verticalAlign":"middle"}),
                            html.Span(f"  ${spent}k / ${budget}k",style={"fontSize":"11px","color":"var(--text-primary)","marginLeft":"8px"}),
                        ],style={"marginBottom":"14px"})
                        for cat,spent,budget,pct in [
                            ("Maintenance",  42,50, 84),
                            ("Energy",       61,65, 94),
                            ("Labour",       88,90, 98),
                            ("Raw Materials",71,80, 89),
                            ("Consumables",  14,18, 78),
                            ("Overheads",    8, 7,  114),
                        ]
                    ])
                ]),style=cs()),
            ],width=7),
            dbc.Col([
                section_label("Cost Savings This Month"),
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span(item,style={"fontSize":"11px","color":"var(--text-primary)","flex":"1"}),
                            html.Span(f"${saving}k",style={"fontSize":"12px","color":SUCCESS_COLOR,"fontWeight":"700"}),
                        ],style={"display":"flex","justifyContent":"space-between","padding":"8px 0","borderBottom":"1px solid var(--border-color)"})
                        for item,saving in [
                            ("AI Alarm Noise Reduction","3.2"),
                            ("Predictive Maintenance",  "8.5"),
                            ("Energy Optimisation",     "4.1"),
                            ("Reduced Downtime (vs avg)","11.4"),
                        ]
                    ]),
                    html.Div([
                        html.Span("Total Savings",style={"fontSize":"12px","color":"var(--text-primary)","fontWeight":"700","flex":"1"}),
                        html.Span("$27.2k",style={"fontSize":"14px","color":ACCENT_COLOR,"fontWeight":"800"}),
                    ],style={"display":"flex","justifyContent":"space-between","padding":"10px 0","marginTop":"4px"}),
                ]),style=cs(ACCENT_COLOR)),
            ],width=5),
        ]),
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# ── LIVE DATA CALLBACKS ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

# FIX: Added url pathname as Input so overview updates immediately on navigation
@app.callback(
    Output("overview-trend-graph",      "figure"),
    Output("overview-metrics-container","children"),
    Output("overview-alerts-container", "children"),
    Output("ai-filter-display",         "children"),
    Input("latest-data-store",  "data"),
    Input("url",                "pathname"),
    State("settings-store",     "data"),
)
def update_overview(data, pathname, settings):
    # Only run when on the overview page and data is available
    if not data or pathname not in ("/", "/operator"):
        raise dash.exceptions.PreventUpdate

    history_list = list(sensor_history)
    times     = [d["timestamp"].strftime("%H:%M:%S") if hasattr(d["timestamp"], "strftime")
                 else str(d["timestamp"])[-8:] for d in history_list]
    temps     = [d["temperature"] for d in history_list]
    pressures = [d["pressure"]    for d in history_list]
    rpms      = [d["rpm"]         for d in history_list]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=temps,     name="Temp (°C)",  line=dict(color="#FF7043", width=1.5)))
    fig.add_trace(go.Scatter(x=times, y=pressures, name="Press (PSI)",line=dict(color="#42A5F5", width=1.5)))
    fig.add_trace(go.Scatter(x=times, y=rpms,      name="RPM",        line=dict(color="#66BB6A", width=1.5)))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8B949E", size=11), height=200,
        margin=dict(l=40, r=20, t=10, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor="#27272a", linecolor="#27272a", showticklabels=False),
        yaxis=dict(gridcolor="#27272a", linecolor="#27272a"),
    )

    temp, pressure, rpm = data["temperature"], data["pressure"], data["rpm"]
    t_color = CRITICAL_COLOR if temp > 130 else WARNING_COLOR if temp > 110 else SUCCESS_COLOR
    p_color = CRITICAL_COLOR if pressure < 60 else WARNING_COLOR if pressure < 80 else SUCCESS_COLOR
    r_color = CRITICAL_COLOR if rpm > 2000 else WARNING_COLOR if rpm > 1700 else SUCCESS_COLOR

    metrics = dbc.Row([
        dbc.Col(stat_card("Temperature", f"{temp:.1f} °C",    "Live reading", t_color), width=4),
        dbc.Col(stat_card("Pressure",    f"{pressure:.1f} PSI","Live reading", p_color), width=4),
        dbc.Col(stat_card("RPM",         f"{rpm:.0f}",         "Live reading", r_color), width=4),
    ], className="mb-3")

    alerts_raw, _ = analyze_data(data, settings)
    alert_divs = []
    for level, msg in alerts_raw:
        color = {"CRITICAL": "danger", "WARNING": "warning", "INFO": "info"}.get(level, "info")
        alert_divs.append(dbc.Alert(msg, color=color, className="mb-2"))

    recent = list(sensor_history)[-50:]
    anomaly_count = sum(1 for d in recent if d["temperature"] > 110 or d["pressure"] < 80)
    filter_pct = 100 - int((anomaly_count / max(len(recent), 1)) * 100)

    return fig, metrics, alert_divs, f"{filter_pct}%"


@app.callback(
    Output("full-trend-graph",  "figure"),
    Output("avg-temp-display",  "children"),
    Output("avg-pres-display",  "children"),
    Output("trend-range-label", "children"),
    Output("trend-btn-1h",  "color"),
    Output("trend-btn-6h",  "color"),
    Output("trend-btn-24h", "color"),
    Output("trend-btn-7d",  "color"),
    Input("latest-data-store", "data"),
    Input("trend-range-store", "data"),
)
def update_trends(data, time_range):
    if not data:
        raise dash.exceptions.PreventUpdate
    time_range = time_range or "1H"
    points_map = {"1H": 1800, "6H": 10800, "24H": 43200, "7D": 302400}
    n_points = min(points_map.get(time_range, 1800), len(sensor_history))
    history_list = list(sensor_history)[-n_points:]
    times     = [d["timestamp"].strftime("%H:%M:%S") if hasattr(d["timestamp"], "strftime")
                 else str(d["timestamp"])[-8:] for d in history_list]
    temps     = [d["temperature"] for d in history_list]
    pressures = [d["pressure"]    for d in history_list]
    rpms      = [d["rpm"]         for d in history_list]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=temps,     name="Temp (°C)",  line=dict(color="#FF7043", width=1.5)))
    fig.add_trace(go.Scatter(x=times, y=pressures, name="Press (PSI)",line=dict(color="#42A5F5", width=1.5)))
    fig.add_trace(go.Scatter(x=times, y=rpms,      name="RPM",        line=dict(color="#66BB6A", width=1.5)))
    fig.add_hline(y=130, line_dash="dot", line_color=CRITICAL_COLOR, line_width=1,
                  annotation_text="Temp CRIT", annotation_font_size=9, annotation_font_color=CRITICAL_COLOR)
    fig.add_hline(y=110, line_dash="dot", line_color=WARNING_COLOR, line_width=1,
                  annotation_text="Temp WARN", annotation_font_size=9, annotation_font_color=WARNING_COLOR)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8B949E", size=11),
        margin=dict(l=50, r=20, t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor="#27272a", linecolor="#27272a", showticklabels=False),
        yaxis=dict(gridcolor="#27272a", linecolor="#27272a"),
    )
    last10_t = temps[-10:] if len(temps) >= 10 else temps
    last10_p = pressures[-10:] if len(pressures) >= 10 else pressures
    avg_t = f"{sum(last10_t)/len(last10_t):.1f} °C" if last10_t else "—"
    avg_p = f"{sum(last10_p)/len(last10_p):.1f} PSI" if last10_p else "—"
    label_map = {
        "1H":  f"Showing last 1 hour — {len(history_list)} points",
        "6H":  f"Showing last 6 hours — {len(history_list)} points (capped at history limit)",
        "24H": f"Showing last 24 hours — {len(history_list)} points (capped at history limit)",
        "7D":  f"Showing last 7 days — {len(history_list)} points (capped at history limit)",
    }
    def btn_color(r):
        return "primary" if r == time_range else "outline-secondary"
    return fig, avg_t, avg_p, label_map.get(time_range, ""), btn_color("1H"), btn_color("6H"), btn_color("24H"), btn_color("7D")


@app.callback(
    Output("full-alarms-container","children"),
    Output("alarm-unack-count",    "children", allow_duplicate=True),
    Output("alarm-ack-count",      "children", allow_duplicate=True),
    Output("alarm-supp-count",     "children", allow_duplicate=True),
    Input("latest-data-store",  "data"),
    Input("alarm-ack-store",    "data"),
    State("settings-store",     "data"),
    prevent_initial_call=True,
)
@app.callback(
    Output("full-alarms-container","children"),
    Output("alarm-unack-count",    "children", allow_duplicate=True),
    Output("alarm-ack-count",      "children", allow_duplicate=True),
    Output("alarm-supp-count",     "children", allow_duplicate=True),
    Input("latest-data-store",  "data"),
    Input("alarm-ack-store",    "data"),
    State("settings-store",     "data"),
    prevent_initial_call=True,
)
def update_full_alarms(data, ack_store, settings):
    if not data:
        raise dash.exceptions.PreventUpdate

    alerts_raw, _ = analyze_data(data, settings)
    ack_store  = ack_store or {"unack": 0, "ack": 0, "supp": 0, "acked_ids": [], "supp_ids": []}
    acked_ids  = [str(x) for x in ack_store.get("acked_ids", [])]
    supp_ids   = [str(x) for x in ack_store.get("supp_ids",  [])]

    alert_divs = []
    active_count = 0

    for i, alert_tuple in enumerate(alerts_raw):
        level    = alert_tuple[0]
        msg      = alert_tuple[1]
        alarm_id = str(i)   # use index as stable ID within this data snapshot

        # Skip acknowledged or suppressed alarms
        if alarm_id in acked_ids:
            continue
        if alarm_id in supp_ids:
            continue

        active_count += 1
        color = {"CRITICAL": "danger", "WARNING": "warning", "INFO": "info"}.get(level, "info")
        alert_divs.append(
            html.Div([
                dbc.Alert(msg, color=color, className="mb-0",
                          style={"marginBottom": "0", "display": "inline-block",
                                 "width": "calc(100% - 180px)"}),
                html.Button("✓ ACK",  className="ack-btn",
                            id={"type": "alarm-row-ack",  "index": alarm_id},
                            n_clicks=0),
                html.Button("⊘ SUPP", className="supp-btn",
                            id={"type": "alarm-row-supp", "index": alarm_id},
                            n_clicks=0),
            ], style={"display": "flex", "alignItems": "center",
                      "marginBottom": "8px", "gap": "8px"})
        )

    if not alert_divs:
        alert_divs = [dbc.Alert("✓ All alarms acknowledged. No active alerts.",
                                color="success", className="mb-2")]

    unack_str = "0 ACTIVE" if active_count == 0 else f"{active_count} ACTIVE"
    ack_count  = str(ack_store.get("ack",  0))
    supp_count = str(ack_store.get("supp", 0))

    return alert_divs, unack_str, ack_count, supp_count


@app.callback(
    Output("ai-insights-container","children"),
    Input("latest-data-store", "data"),
)
def update_ai_insights(data):
    if not data:
        raise dash.exceptions.PreventUpdate
    insights = detect_anomalies(sensor_history)
    cards = []
    for insight in insights:
        color = insight["color"]
        badge = insight["badge"]
        title = f"{insight['param'].capitalize()} Anomaly Detection"
        desc  = insight["message"]
        c = color.lstrip('#')
        rgba_bg = f"rgba({int(c[0:2],16)},{int(c[2:4],16)},{int(c[4:6],16)},0.1)" if len(c)==6 else "rgba(255,255,255,0.1)"
        cards.append(
            dbc.Card(dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Span(badge,style={"fontSize":"9px","fontWeight":"700","padding":"2px 8px","borderRadius":"3px",
                                               "backgroundColor":rgba_bg,"color":color,
                                               "border":f"1px solid {color}","letterSpacing":"0.08em",
                                               "textTransform":"uppercase","marginBottom":"8px","display":"inline-block"}),
                        html.P(title,style={"fontWeight":"700","fontSize":"14px","color":"var(--text-primary)","marginBottom":"4px"}),
                        html.Div([
                            html.Span(f"Z-Score: {insight['z_score']:+.2f}",style={"fontSize":"11px","color":"var(--text-muted)","marginRight":"12px","fontFamily":"monospace"}),
                            html.Span(f"Slope: {insight['slope']:+.2f}",    style={"fontSize":"11px","color":"var(--text-muted)","fontFamily":"monospace"}),
                        ],style={"marginBottom":"8px"}),
                        html.P(desc,style={"fontSize":"12px","color":"var(--text-muted)","lineHeight":"1.6","marginBottom":0}),
                    ],width=10),
                    dbc.Col([html.Div("●",style={"color":color,"fontSize":"24px","textAlign":"right"})],width=2),
                ])
            ]),style={**cs(color),"marginBottom":"12px"})
        )
    return cards


@app.callback(
    Output("reports-gen-count","children"),
    Input("report-gen-store",  "data"),
    prevent_initial_call=True,
)
def update_report_count(store):
    return str(store.get("count", 47)) if store else "47"


@app.callback(
    Output("settings-refresh-select","value"),
    Output("settings-ai-toggle",     "value"),
    Output("settings-notif-toggle",  "value"),
    Output("settings-export-select", "value"),
    Output("settings-temp-warn",     "value"),
    Output("settings-temp-crit",     "value"),
    Output("settings-pres-warn",     "value"),
    Output("settings-pres-crit",     "value"),
    Output("settings-rpm-warn",      "value"),
    Output("settings-rpm-crit",      "value"),
    Input("settings-store",          "data"),
    Input("url",                     "pathname"),
)
def populate_settings(store, pathname):
    if pathname not in ["/settings", "/engineer/settings", "/manager/settings"]:
        raise dash.exceptions.PreventUpdate
    store = store or {}
    return (
        store.get("refresh", 2),
        [True] if store.get("ai", True) else [],
        [True] if store.get("notifications", True) else [],
        store.get("export_fmt", "CSV"),
        store.get("temp_warn", 110),
        store.get("temp_crit", 130),
        store.get("pres_warn", 80),
        store.get("pres_crit", 60),
        store.get("rpm_warn",  1700),
        store.get("rpm_crit",  2000),
    )


@app.callback(
    Output("interval-component","interval"),
    Input("settings-store", "data"),
)
def update_interval(store):
    return (store or {}).get("refresh", 2) * 1000


@app.callback(
    Output("signals-table-body",   "children"),
    Output("signals-status-summary","children"),
    Input("signal-search", "value"),
)
def update_signals_table(search_query):
    filtered = [s for s in SIGNALS_DATA
                if not search_query or any(search_query.lower() in s[i].lower() for i in [0,2,4])]
    ok_count    = sum(1 for s in filtered if s[6] == "OK")
    drift_count = sum(1 for s in filtered if s[6] == "Drift")
    fault_count = sum(1 for s in filtered if s[6] == "Fault")
    status_summary = dbc.Row([
        dbc.Col(stat_card("OK",    str(ok_count),    "Normal Operation",      SUCCESS_COLOR), width=4),
        dbc.Col(stat_card("Drift", str(drift_count), "Requires calibration",  WARNING_COLOR), width=4),
        dbc.Col(stat_card("Fault", str(fault_count), "Sensor error",          CRITICAL_COLOR),width=4),
    ])
    rows = [
        html.Tr([
            html.Td(s[0],style={"fontSize":"11px","padding":"7px 12px","fontFamily":"monospace","color":"var(--text-dimmed)","borderBottom":"1px solid var(--border-color)"}),
            html.Td(s[1],style={"fontSize":"11px","padding":"7px 12px","fontFamily":"monospace","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
            html.Td(s[2],style={"fontSize":"11px","padding":"7px 12px","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
            html.Td(s[3],style={"fontSize":"11px","padding":"7px 12px","color":"var(--text-muted)","borderBottom":"1px solid var(--border-color)"}),
            html.Td(s[4],style={"fontSize":"12px","padding":"7px 12px","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
            html.Td(s[5],style={"fontSize":"12px","padding":"7px 12px","fontWeight":"600","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
            html.Td(html.Span(f"● {s[6]}",style={"fontSize":"11px","fontWeight":"700",
                    "color":SUCCESS_COLOR if s[6]=="OK" else WARNING_COLOR if s[6]=="Drift" else CRITICAL_COLOR}),
                style={"padding":"7px 12px","borderBottom":"1px solid var(--border-color)"}),
        ]) for s in filtered
    ]
    return rows, status_summary


@app.callback(
    Output("signal-export-feedback","children"),
    Input("signal-export-btn", "n_clicks"),
    State("signal-search",     "value"),
    prevent_initial_call=True,
)
def export_signals(n_clicks, search_query):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    filtered = [s for s in SIGNALS_DATA
                if not search_query or any(search_query.lower() in s[i].lower() for i in [0,2,4])]
    csv_rows = ["Tag ID,Instrument,I/O Type,Signal,Description,Live Value,Status"]
    for s in filtered:
        csv_rows.append(",".join(f'"{str(col)}"' for col in s))
    csv_b64  = base64.b64encode("\n".join(csv_rows).encode()).decode()
    filename = f"Signals_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return html.Div([
        html.A("⬇ Download CSV", href=f"data:text/csv;base64,{csv_b64}", download=filename,
               style={"color":"#00E676","fontWeight":"700","textDecoration":"underline","cursor":"pointer","fontSize":"11px"}),
    ])


@app.callback(
    Output("alarm-unack-count","children", allow_duplicate=True),
    Output("alarm-ack-count",  "children", allow_duplicate=True),
    Output("alarm-supp-count", "children", allow_duplicate=True),
    Input("interval-component","n_intervals"),
    State("auth-store",        "data"),
    prevent_initial_call=True,
)
def poll_alarm_stats(n, auth_data):
    if not auth_data or not auth_data.get("token") or auth_data.get("token") == "demo":
        raise dash.exceptions.PreventUpdate
    try:
        r = requests.get(
            f"{BACKEND_URL}/api/data/alerts/stats",
            headers={"Authorization": f"Bearer {auth_data['token']}"},
            timeout=2
        )
        if r.status_code == 200:
            stats = r.json()
            unack = stats.get("unacknowledged", 0)
            return ("0 ACTIVE" if unack == 0 else f"{unack} ACTIVE",
                    str(stats.get("acknowledged", 0)),
                    str(stats.get("suppressed", 0)))
    except Exception:
        pass
    raise dash.exceptions.PreventUpdate


@app.callback(
    Output("equipment-live-store","data"),
    Input("interval-component",  "n_intervals"),
    State("auth-store",          "data"),
)
def poll_equipment(n, auth_data):
    if not n or n % 5 != 0:
        raise dash.exceptions.PreventUpdate
    return fetch_real_machines(auth_data)


@app.callback(
    Output("equipment-table-container","children"),
    Output("equip-running-count",      "children"),
    Output("equip-standby-count",      "children"),
    Output("equip-fault-count",        "children"),
    Input("equipment-live-store",      "data"),
)
def update_equipment_table(machines):
    if not machines:
        raise dash.exceptions.PreventUpdate
    equipment_data = [
        (m["name"], m["machineId"], m["status"].title(),
         SUCCESS_COLOR if m["status"]=="running" else CRITICAL_COLOR if m["status"]=="fault" else WARNING_COLOR,
         f"{m['pressure']} PSI", f"{m['vibration']} mm/s", f"{m['temperature']}°C", "Review", f"{m.get('health',100)}%")
        for m in machines
    ] or [
        ("Reactor R-401","R-401","Running",SUCCESS_COLOR,"90 PSI","1.2 mm/s","112°C","Review","94%"),
        ("Feed Pump P-101","P-101","Running",SUCCESS_COLOR,"85 PSI","0.8 mm/s","42°C","2025-12","98%"),
        ("Compressor K1","K1","Standby",WARNING_COLOR,"—","—","—","2025-10","85%"),
        ("Separator S-101","S-101","Running",SUCCESS_COLOR,"55 PSI","0.5 mm/s","38°C","2026-01","99%"),
        ("Heat Exchanger E1","E1","Running",SUCCESS_COLOR,"75 PSI","0.3 mm/s","76°C","2026-03","97%"),
        ("Pump P-202","P-202","Fault",CRITICAL_COLOR,"22 PSI","4.1 mm/s","88°C","OVERDUE","41%"),
    ]

    def parse_pct(v):
        try: return int(str(v).rstrip('%'))
        except: return 0

    table = html.Table([
        html.Thead(html.Tr([
            html.Th(h,style={"color":ACCENT_COLOR,"fontSize":"9px","fontWeight":"700",
                              "padding":"7px 12px","letterSpacing":"0.1em",
                              "textTransform":"uppercase","borderBottom":"1px solid var(--border-color)"})
            for h in ["Equipment","Tag","Status","Flow / Output","Speed","Temp","Next Maint.","Health"]
        ])),
        html.Tbody([
            html.Tr([
                html.Td(eq[0],style={"fontSize":"12px","padding":"8px 12px","fontWeight":"600","color":"var(--text-primary)","borderBottom":"1px solid var(--border-color)"}),
                html.Td(eq[1],style={"fontSize":"10px","padding":"8px 12px","fontFamily":"monospace","color":"var(--text-dimmed)","borderBottom":"1px solid var(--border-color)"}),
                html.Td(html.Span(f"● {eq[2]}",style={"fontSize":"11px","fontWeight":"700","color":eq[3]}),style={"padding":"8px 12px","borderBottom":"1px solid var(--border-color)"}),
                *[html.Td(eq[i],style={"fontSize":"12px","padding":"8px 12px",
                                       "color":CRITICAL_COLOR if eq[i]=="OVERDUE" else "var(--text-primary)",
                                       "fontWeight":"600" if eq[i]=="OVERDUE" else "400",
                                       "borderBottom":"1px solid var(--border-color)"}) for i in [4,5,6,7]],
                html.Td(
                    html.Div([
                        html.Div(style={"height":"4px","borderRadius":"2px",
                                        "width":f"{parse_pct(eq[8])}%",
                                        "background":CRITICAL_COLOR if parse_pct(eq[8])<70 else WARNING_COLOR if parse_pct(eq[8])<85 else SUCCESS_COLOR}),
                        html.Span(eq[8] if eq[8] not in ["—",""] else "N/A",
                                  style={"fontSize":"10px","color":"var(--text-muted)","marginTop":"3px","display":"block"}),
                    ],style={"width":"70px"}),
                    style={"padding":"8px 12px","borderBottom":"1px solid var(--border-color)"}
                ),
            ]) for eq in equipment_data
        ])
    ],style={"width":"100%","borderCollapse":"collapse"})

    run = str(sum(1 for e in equipment_data if e[2]=="Running"))
    stb = str(sum(1 for e in equipment_data if e[2]=="Standby"))
    flt = str(sum(1 for e in equipment_data if e[2]=="Fault"))
    return table, run, stb, flt


# FIX: Toast notifications — only show when logged in (no alerts on login page)
@app.callback(
    Output("toast-container",  "children"),
    Output("last-toast-store", "data"),
    Input("latest-data-store", "data"),
    State("auth-store",        "data"),
    State("settings-store",    "data"),
    State("last-toast-store",  "data"),
    prevent_initial_call=True,
)
def update_toast_notifications(data, auth_data, settings, last_toast):
    # FIX: Don't show toast alerts when not logged in
    if not data or not auth_data or not auth_data.get("logged_in"):
        raise dash.exceptions.PreventUpdate

    alerts_raw, _ = analyze_data(data, settings)
    critical_msgs = [msg for level, msg in alerts_raw if level == "CRITICAL"]
    warning_msgs  = [msg for level, msg in alerts_raw if level == "WARNING"]
    current_sig   = "|".join(critical_msgs + warning_msgs)
    if last_toast and last_toast.get("sig") == current_sig:
        raise dash.exceptions.PreventUpdate

    toasts = []
    for msg in critical_msgs:
        toasts.append(html.Div([
            html.Span("⚠ CRITICAL",style={"fontWeight":"700","color":"#EF5350","fontSize":"9px","letterSpacing":"0.08em","textTransform":"uppercase"}),
            html.P(msg,style={"marginBottom":0,"marginTop":"4px"})
        ],className="hmi-toast"))
    for msg in warning_msgs:
        toasts.append(html.Div([
            html.Span("⚠ WARNING",style={"fontWeight":"700","color":"#FFB300","fontSize":"9px","letterSpacing":"0.08em","textTransform":"uppercase"}),
            html.P(msg,style={"marginBottom":0,"marginTop":"4px"})
        ],className="hmi-toast hmi-toast-warn"))

    return toasts[:3], {"sig": current_sig}


@app.callback(
    Output("demo-mode-store",  "data"),
    Input("demo-mode-btn-op",  "n_clicks"),
    Input("demo-mode-btn-eng", "n_clicks"),
    Input("demo-mode-btn-mgr", "n_clicks"),
    State("demo-mode-store",   "data"),
    prevent_initial_call=True,
)
def toggle_demo_mode(op_clicks, eng_clicks, mgr_clicks, current):
    return not current


app.clientside_callback(
    """
    function(active) {
        var ids = ['demo-mode-btn-op', 'demo-mode-btn-eng', 'demo-mode-btn-mgr'];
        var label  = active ? '\u25a0  DEMO ACTIVE' : '\u2b21  DEMO MODE';
        var bcolor = active ? '#EF5350' : '#26C6DA';
        ids.forEach(function(id) {
            var btn = document.getElementById(id);
            if (btn) { btn.style.borderColor = bcolor; btn.style.color = bcolor; btn.textContent = label; }
        });
        return [label, label, label];
    }
    """,
    Output("demo-mode-btn-op",  "children"),
    Output("demo-mode-btn-eng", "children"),
    Output("demo-mode-btn-mgr", "children"),
    Input("demo-mode-store", "data"),
)


@app.callback(
    Output("uptime-display",    "children"),
    Input("interval-component", "n_intervals"),
    State("uptime-store",       "data"),
)
def update_uptime_display(n, store):
    if not store:
        raise dash.exceptions.PreventUpdate
    start      = datetime.fromisoformat(store["start"])
    delta      = datetime.now() - start
    total_secs = int(delta.total_seconds())
    days  = total_secs // 86400
    hours = (total_secs % 86400) // 3600
    mins  = (total_secs % 3600) // 60
    return f"{days}d {hours}h {mins}m"


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
