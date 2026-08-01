# Playwright steps executed by mcp_browser_automation for the focused GCS bug verification.

import re

async def run(page):

    network_events = []
    page.on("request", lambda req: network_events.append({"kind": "request", "method": req.method, "url": req.url}) if "/api/" in req.url else None)
    page.on("response", lambda resp: network_events.append({"kind": "response", "status": resp.status, "method": resp.request.method, "url": resp.url}) if "/api/" in resp.url else None)

    async def assert_visible(testid, label):
        locator = page.locator(f'[data-testid="{testid}"]').first
        await locator.wait_for(state="visible", timeout=15000)
        box = await locator.bounding_box()
        if not box or box["width"] <= 0 or box["height"] <= 0:
            raise AssertionError(f"{label} is not visibly rendered")
        print(f"PASS: {label} visible at {box}")
        return locator

    async def assert_text_visible(testid, expected, label):
        locator = await assert_visible(testid, label)
        text = (await locator.inner_text()).strip()
        if expected.lower() not in text.lower():
            raise AssertionError(f"{label} expected text {expected!r}, got {text!r}")
        print(f"PASS: {label} text includes {expected!r}")
        return locator

    async def assert_in_viewport(testid, label):
        locator = await assert_visible(testid, label)
        box = await locator.bounding_box()
        viewport = page.viewport_size
        if box["x"] < 0 or box["y"] < 0 or box["x"] + box["width"] > viewport["width"] + 1 or box["y"] + box["height"] > viewport["height"] + 1:
            raise AssertionError(f"{label} is clipped/outside viewport: box={box}, viewport={viewport}")
        print(f"PASS: {label} fully inside viewport")
        return locator

    async def wait_for_text(testid, expected, timeout_ms=20000):
        deadline = timeout_ms // 500
        last = None
        for _ in range(deadline):
            locator = page.locator(f'[data-testid="{testid}"]').first
            if await locator.count() > 0:
                last = (await locator.inner_text()).strip()
                if expected in last:
                    print(f"PASS: {testid} became {last!r}")
                    return last
            await page.wait_for_timeout(500)
        raise AssertionError(f"Timed out waiting for {testid} to include {expected!r}; last={last!r}")

    try:
        print("TEST PLAN: verify the reported black/unreadable GCS UI and Mission Planner-style add-drone COM/UDP flow end-to-end, including arm/takeoff and mission library modal regressions. No relevant testing skill found.")
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto("https://drone-swarm-control-1.preview.emergentagent.com", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await assert_visible("top-toolbar", "top toolbar")
        await assert_visible("drone-list-sidebar", "fleet sidebar")
        await assert_visible("map-container", "map center")
        await assert_visible("mission-planner", "bottom mission planner")
        await assert_visible("status-bar", "status bar")
        await assert_text_visible("drone-list-sidebar", "FLEET // 0", "fleet header empty state")

        toolbar_buttons = [
            ("btn-add-drone", "Add"), ("btn-remove-drone", "Remove"), ("btn-connect", "Connect"),
            ("btn-disconnect", "Disconnect"), ("btn-arm", "Arm"), ("btn-disarm", "Disarm"),
            ("btn-takeoff", "Takeoff"), ("btn-land", "Land"), ("btn-hold", "Hold"),
            ("btn-rtl", "RTL"), ("btn-mission-library", "Library"), ("btn-mission-upload", "Upload"),
            ("btn-mission-start", "Start"), ("btn-emergency-stop", "E-STOP"),
        ]
        for testid, label in toolbar_buttons:
            loc = await assert_text_visible(testid, label, f"toolbar button {label}")
            style = await loc.evaluate("el => ({color: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor, border: getComputedStyle(el).borderColor})")
            print(f"STYLE: {label} {style}")

        tile_info = await page.evaluate("""() => ({
            loaded: document.querySelectorAll('.leaflet-tile-loaded').length,
            total: document.querySelectorAll('.leaflet-tile').length,
            filter: getComputedStyle(document.querySelector('.leaflet-tile-pane')).filter,
            containerBg: getComputedStyle(document.querySelector('.leaflet-container')).backgroundColor
        })""")
        if tile_info["total"] == 0 or tile_info["loaded"] == 0:
            raise AssertionError(f"Leaflet dark map tiles did not load visibly: {tile_info}")
        if "brightness" not in tile_info["filter"]:
            raise AssertionError(f"Leaflet tile brightness filter not applied: {tile_info}")
        print(f"PASS: Leaflet dark map tiles loaded and brightened: {tile_info}")
        await page.screenshot(path="/app/test_reports/gcs_visibility_viewport.jpg", quality=40, full_page=False)
        print("PASS: captured main GCS visibility screenshot")

        await page.locator('[data-testid="btn-add-drone"]').click(force=True)
        await page.wait_for_timeout(300)
        await assert_in_viewport("add-drone-dialog", "add drone dialog")
        dialog_text = (await page.locator('[data-testid="add-drone-dialog"]').text_content()) or ""
        required_dialog_texts = [
            "CONNECT NEW DRONE", "Quick Presets", "SITL UDP :14550", "SITL TCP :5760",
            "APM/Pixhawk USB @57600", "PX4 USB @115200", "SiK Telemetry @57600",
            "Wi-Fi Drone UDP :14555", "Built-in Simulator", "Drone Name", "Sys ID",
            "Home Lat", "Home Lon", "Connection Type", "Serial", "UDP", "TCP", "Simulator", "Cancel", "Connect",
        ]
        for txt in required_dialog_texts:
            if txt not in dialog_text:
                raise AssertionError(f"Add drone dialog missing text {txt!r}")
        print("PASS: add drone dialog contains all requested labels and sections")

        preset_ids = ["preset-sitl-udp", "preset-sitl-tcp", "preset-apm-usb", "preset-px4-usb", "preset-telem-radio", "preset-wifi-udp", "preset-simulator"]
        for pid in preset_ids:
            await assert_visible(pid, f"preset {pid}")
        for tid in ["input-drone-name", "input-drone-sysid", "input-home-lat", "input-home-lon", "tab-conn-serial", "tab-conn-udp", "tab-conn-tcp", "tab-conn-sim", "btn-add-drone-cancel", "btn-add-drone-submit"]:
            await assert_visible(tid, tid)

        await assert_visible("select-serial-port", "serial port dropdown")
        await page.locator('[data-testid="select-serial-port"]').click(force=True)
        await page.wait_for_timeout(200)
        serial_options = ["COM1", "COM7", "COM8", "COM16", "/dev/ttyUSB0", "/dev/ttyUSB2", "/dev/ttyACM0", "/dev/ttyACM2"]
        body_text = await page.locator("body").inner_text()
        for opt in serial_options:
            if opt not in body_text:
                raise AssertionError(f"Serial dropdown missing option {opt}")
        await page.get_by_role("option", name="COM7", exact=True).click(force=True)
        print("PASS: serial dropdown exposes COM1..COM16 and Linux tty options")

        await assert_visible("select-baud-rate", "baud rate dropdown")
        await page.locator('[data-testid="select-baud-rate"]').click(force=True)
        await page.wait_for_timeout(200)
        body_text = await page.locator("body").inner_text()
        for opt in ["9600", "57600", "115200", "921600"]:
            if opt not in body_text:
                raise AssertionError(f"Baud dropdown missing option {opt}")
        await page.get_by_role("option", name="57600", exact=True).click(force=True)
        print("PASS: baud dropdown exposes expected rates")

        await page.locator('[data-testid="preset-apm-usb"]').click(force=True)
        await page.wait_for_timeout(200)
        serial_value = (await page.locator('[data-testid="select-serial-port"]').inner_text()).strip()
        baud_value = (await page.locator('[data-testid="select-baud-rate"]').inner_text()).strip()
        if "COM7" not in serial_value or "57600" not in baud_value:
            raise AssertionError(f"APM USB preset did not populate COM7 @57600, got {serial_value=} {baud_value=}")
        print("PASS: preset-apm-usb populated COM7 @57600")

        await page.locator('[data-testid="preset-sitl-udp"]').click(force=True)
        await page.wait_for_timeout(300)
        await assert_visible("input-udp-address", "UDP bind/host input")
        await assert_visible("select-udp-port", "UDP port dropdown")
        udp_addr = await page.locator('[data-testid="input-udp-address"]').input_value()
        udp_port = (await page.locator('[data-testid="select-udp-port"]').inner_text()).strip()
        if udp_addr != "127.0.0.1" or "14550" not in udp_port:
            raise AssertionError(f"SITL UDP preset did not populate 127.0.0.1:14550, got {udp_addr=} {udp_port=}")
        print("PASS: preset-sitl-udp switched to UDP 127.0.0.1:14550")
        await page.screenshot(path="/app/test_reports/add_drone_dialog_visible.jpg", quality=40, full_page=False)

        await page.locator('[data-testid="btn-add-drone-submit"]').click(force=True)
        await page.get_by_text("Drone Alpha added & connected", exact=False).wait_for(state="visible", timeout=20000)
        print("PASS: success toast appeared")
        row = page.locator('[data-testid^="drone-row-"]').first
        await row.wait_for(state="visible", timeout=20000)
        row_id_attr = await row.get_attribute("data-testid")
        drone_id = row_id_attr.replace("drone-row-", "")
        await wait_for_text("tlm-status", "CONNECTED", 20000)
        api_drones = await page.evaluate("""async () => {
            const r = await fetch('/api/drones');
            return await r.json();
        }""")
        if len(api_drones) != 1 or api_drones[0]["id"] != drone_id or api_drones[0]["status"] != "connected":
            raise AssertionError(f"Backend/UI drone state mismatch: ui={drone_id}, api={api_drones}")
        if api_drones[0]["connection"]["connection_type"] != "udp" or api_drones[0]["connection"]["address"] != "127.0.0.1" or api_drones[0]["connection"]["port"] != 14550:
            raise AssertionError(f"Backend connection was not SITL UDP 127.0.0.1:14550: {api_drones[0]['connection']}")
        print(f"PASS: backend created and connected drone {drone_id} via UDP 127.0.0.1:14550")

        checkbox = page.locator(f'[data-testid="checkbox-drone-{drone_id}"]').first
        if not await checkbox.is_checked():
            await checkbox.click(force=True)
        await page.locator('[data-testid="btn-arm"]').wait_for(state="visible", timeout=10000)
        if not await page.locator('[data-testid="btn-arm"]').is_enabled():
            raise AssertionError("Arm button remained disabled after connected drone selection")
        await page.locator('[data-testid="btn-arm"]').click(force=True)
        await wait_for_text("tlm-armed", "YES", 20000)
        alt_before_txt = await page.locator('[data-testid="tlm-alt-rel"]').inner_text()
        alt_before_match = re.search(r"-?\d+(?:\.\d+)?", alt_before_txt)
        alt_before = float(alt_before_match.group(0)) if alt_before_match else 0.0
        await page.locator('[data-testid="btn-takeoff"]').click(force=True)
        await wait_for_text("tlm-mode", "GUIDED", 20000)
        climbed = False
        alt_after = alt_before
        for _ in range(20):
            alt_txt = await page.locator('[data-testid="tlm-alt-rel"]').inner_text()
            m = re.search(r"-?\d+(?:\.\d+)?", alt_txt)
            if m:
                alt_after = float(m.group(0))
                if alt_after > alt_before + 0.2:
                    climbed = True
                    break
            await page.wait_for_timeout(500)
        if not climbed:
            raise AssertionError(f"Takeoff did not show altitude climbing; before={alt_before} after={alt_after}")
        print(f"PASS: arm/takeoff regression works, altitude climbed from {alt_before} to {alt_after}")

        await page.locator('[data-testid="btn-mission-library"]').click(force=True)
        await page.wait_for_timeout(500)
        await assert_in_viewport("mission-library-dialog", "mission library dialog")
        lib_text = await page.locator('[data-testid="mission-library-dialog"]').inner_text()
        if "mission library" not in lib_text.lower() or "import json" not in lib_text.lower() or "qa visibility mission" not in lib_text.lower():
            raise AssertionError(f"Mission library modal missing title/import/seed row text: {lib_text}")
        if await page.locator('[data-testid^="mission-row-"]').count() < 1:
            raise AssertionError("Mission library did not render any mission rows")
        if await page.locator('[data-testid="input-import-mission"]').count() != 1:
            raise AssertionError("Mission import file input missing from Import JSON button")
        await page.get_by_text("Import JSON", exact=False).wait_for(state="visible", timeout=10000)
        await page.screenshot(path="/app/test_reports/mission_library_dialog_visible.jpg", quality=40, full_page=False)
        print("PASS: mission library dialog visible with import button and mission rows")

        # Cleanup created drone using the same frontend/backend path.
        cleanup = await page.evaluate("""async (id) => {
            const r = await fetch(`/api/drones/${id}`, { method: 'DELETE' });
            const remaining = await fetch('/api/drones').then(x => x.json());
            return {deleteStatus: r.status, remaining};
        }""", drone_id)
        if cleanup["deleteStatus"] >= 300 or cleanup["remaining"]:
            raise AssertionError(f"Drone cleanup failed: {cleanup}")
        print("PASS: cleaned up created drone")

        api_post_create = [e for e in network_events if e["kind"] == "response" and e["method"] == "POST" and e["url"].endswith("/api/drones") and e["status"] < 300]
        api_post_connect = [e for e in network_events if e["kind"] == "response" and e["method"] == "POST" and "/connect" in e["url"] and e["status"] < 300]
        if not api_post_create or not api_post_connect:
            raise AssertionError(f"Did not observe successful POST /api/drones and /connect events: {network_events}")
        print("PASS: observed successful frontend-to-backend create and connect API calls")

        error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")
        print("RESULT: PASS focused bug verification")
    except Exception as e:
        print(f"RESULT: FAIL focused bug verification: {type(e).__name__}: {e}")
        error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")
        raise
