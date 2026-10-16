import requests, time

r = requests.get('http://localhost:8000/api/drones')
drones = r.json()
print(f"Connecting {len(drones)} drone(s)...")
for d in drones:
    if d['status'] != 'connected':
        c = requests.post(f"http://localhost:8000/api/drones/{d['id']}/connect")
        print(f"Connecting {d['name']} ({d['connection']['address']}): {c.status_code}")

print("Waiting for MAVLink telemetry packets...")
time.sleep(3)

r = requests.get('http://localhost:8000/api/drones')
data = r.json()
for d in data:
    t = d['telemetry']
    print(f"[{d['name']}] Status: {d['status']} | FW: {d['firmware']} | SysID: {d['system_id']} | GPS Fix: {t.get('gps_fix')} | Sats: {t.get('satellites')} | Lat: {t.get('latitude')} | Lon: {t.get('longitude')} | Trail pts: {len(d.get('trail', []))} | Home: {d['home_lat']}, {d['home_lon']}")
