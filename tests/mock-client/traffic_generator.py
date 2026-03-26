import asyncio
import aiohttp
import random
import time
import os
import glob
import re

# --- Configuration ---
MAIN_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://main-api-gateway:80")
CONF_DIR = os.getenv("CONF_DIR", "/confs")
REQUEST_INTERVAL = float(os.getenv("REQUEST_INTERVAL", "0.5"))

# --- Traffic Personas ---
PERSONAS = [
    {"id": "user-stable-001", "weight": 0.6, "behavior": "normal"},
    {"id": "user-heavy-999", "weight": 0.2, "behavior": "heavy"},
    {"id": "user-malicious-666", "weight": 0.1, "behavior": "attacker"},
    {"id": "user-scanner-000", "weight": 0.1, "behavior": "scanner"}
]

def discover_endpoints():
    """Scans Nginx conf files to find active zones and apps."""
    endpoints = []
    conf_files = glob.glob(os.path.join(CONF_DIR, "*.conf"))
    
    for f in conf_files:
        zone_id = os.path.basename(f).replace(".conf", "")
        for app in ["app1", "app2"]:
            endpoints.append(f"/{zone_id}/{app}")
    
    return endpoints

async def make_request(session, endpoint, persona):
    url = f"{MAIN_GATEWAY_URL}{endpoint}"
    
    # Behavior logic
    path = "/products"
    headers = {"X-CONSUMER-ID": persona["id"]}
    
    if persona["behavior"] == "attacker":
        if random.random() < 0.5:
            path = "/api/error"
        else:
            headers["X-API-KEY"] = "invalid-key"
            path = "/api/secure-data"
            
    elif persona["behavior"] == "scanner":
        path = f"/not-found-{random.randint(1, 1000)}"

    full_url = f"{url}{path}"
    
    start_time = time.time()
    try:
        async with session.get(full_url, headers=headers, timeout=10) as response:
            duration = (time.time() - start_time) * 1000
            print(f"[{persona['id']}] GET {full_url} -> {response.status} ({duration:.2f}ms)")
    except Exception as e:
        print(f"[{persona['id']}] ERROR {full_url}: {str(e)}")

async def worker(endpoint):
    """A worker that generates traffic for a specific endpoint."""
    async with aiohttp.ClientSession() as session:
        while True:
            persona = random.choices(PERSONAS, weights=[p["weight"] for p in PERSONAS])[0]
            await make_request(session, endpoint, persona)
            
            sleep_time = REQUEST_INTERVAL
            if persona["behavior"] == "heavy":
                sleep_time /= 5
            elif persona["behavior"] == "normal":
                sleep_time *= random.uniform(0.5, 2.0)
            
            await asyncio.sleep(sleep_time)

async def main():
    print("🔍 Discovering endpoints...")
    endpoints = discover_endpoints()
    if not endpoints:
        print("❌ No endpoints found. Are zones deployed?")
        return

    print(f"🚀 Starting traffic generator for {len(endpoints)} endpoints: {endpoints}")
    tasks = [asyncio.create_task(worker(ep)) for ep in endpoints]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Traffic generator stopped.")
