import time
import math
import random
import requests
from datetime import datetime

URL = "http://localhost:8000/api/sensor/ingest"

print("Starting PLC simulation... Press Ctrl+C to stop.")

t_start = time.time()
pressure = 100.0
anomaly_counter = 0
last_anomaly_window = 0

try:
    while True:
        t_now = time.time()
        elapsed = t_now - t_start
        
        # Temp: sine wave 95-125 (mean 110, amp 15), period 120s
        temp = 110.0 + 15.0 * math.sin(2 * math.pi * elapsed / 120.0)
        
        # Pressure: random walk 65-145 PSI
        pressure += random.uniform(-3.0, 3.0)
        pressure = max(65.0, min(145.0, pressure))
        
        # RPM: steps between 1200/1500/1800 RPM every 30s
        step = int(elapsed // 30) % 3
        if step == 0:
            rpm = 1200.0
        elif step == 1:
            rpm = 1500.0
        else:
            rpm = 1800.0
            
        # Inject anomaly spike every 5 minutes (300 seconds) for 3 readings
        window = int(elapsed // 300)
        if window > last_anomaly_window:
            anomaly_counter = 3
            last_anomaly_window = window
            
        if anomaly_counter > 0:
            temp = 140.0
            anomaly_counter -= 1
            
        payload = {
            "temperature": round(temp, 2),
            "pressure": round(pressure, 2),
            "rpm": float(rpm),
            "source": "plc-sim-v1"
        }
        
        try:
            resp = requests.post(URL, json=payload, timeout=2)
            status = resp.status_code
        except requests.exceptions.RequestException as e:
            status = "FAIL"
            
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] Sent: Temp={payload['temperature']:>6.2f}°C, "
              f"Pres={payload['pressure']:>6.2f} PSI, RPM={payload['rpm']:>6.0f} | Status: {status}")
              
        time.sleep(2)
        
except KeyboardInterrupt:
    print("\nStopping PLC simulation.")
