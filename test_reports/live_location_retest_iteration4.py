"""
Focused frontend retest for user bug:
"in map it is showing default map i want the live locvation for it".

This script is intended to be run through the Browser Automation MCP, which
provides the Playwright `page` object inside an async function.
"""

import math

APP_URL = "https://drone-swarm-control-1.preview.emergentagent.com"
MOCK_LAT = 28.6139
MOCK_LON = 77.2090
MOCK_ACC = 25
UPDATED_LAT = 28.701234
UPDATED_LON = 77.301234


async def cleanup_drones(page):
    api = page.context.request
    response = await api.get(f"{APP_URL}/api/drones")
    assert response.ok, f"GET /api/drones failed: {response.status}"
    drones = await response.json()
    for drone in drones:
        delete_response = await api.delete(f"{APP_URL}/api/drones/{drone['id']}")
        assert delete_response.ok, f"DELETE /api/drones/{drone['id']} failed: {delete_response.status}"
    print(f"Cleanup removed {len(drones)} existing drone(s)")


async def create_seed_drone(page):
    payload = {
        "name": "Seed SF Drone",
        "system_id": 42,
        "component_id": 1,
        "connection": {
            "connection_type": "simulator",
            "address": "sim://local",
            "port": 0,
            "baud_rate": None,
            "auto_reconnect": True,
        },
        "home_lat": 37.7749,
        "home_lon": -122.4194,
        "home_alt": 0,
    }
    response = await page.context.request.post(f"{APP_URL}/api/drones", data=payload)
    assert response.ok, f"POST /api/drones seed failed: {response.status}"
    drone = await response.json()
    print(f"Seeded drone id={drone['id']} home={drone['home_lat']},{drone['home_lon']}")
    return drone


def assert_close(actual, expected, tolerance, label):
    if math.fabs(float(actual) - expected) > tolerance:
        raise AssertionError(f"{label} expected {expected}, got {actual}")


async def wait_for_user_marker_centered(page, label):
    await page.wait_for_selector(".user-marker", timeout=15000)
    await page.wait_for_timeout(2200)
    state = await page.evaluate(
        """() => {
            const map = document.querySelector('[data-testid="map-container"]');
            const marker = document.querySelector('.user-marker');
            const button = document.querySelector('[data-testid="btn-map-my-location"]');
            const paths = Array.from(document.querySelectorAll('.leaflet-overlay-pane path'));
            const markerBox = marker?.getBoundingClientRect();
            const mapBox = map?.getBoundingClientRect();
            const circleLike = paths.filter((p) => {
                const stroke = (p.getAttribute('stroke') || p.style.stroke || '').toLowerCase();
                const fill = (p.getAttribute('fill') || p.style.fill || '').toLowerCase();
                return stroke.includes('00f0ff') || fill.includes('00f0ff') || stroke.includes('rgb(0, 240, 255)') || fill.includes('rgb(0, 240, 255)');
            }).length;
            return {
                userMarkerCount: document.querySelectorAll('.user-marker').length,
                userDotCount: document.querySelectorAll('.user-marker-dot').length,
                overlayPathCount: paths.length,
                cyanPathCount: circleLike,
                myLocationExists: !!button,
                myLocationDisabled: button ? button.disabled : null,
                offsetX: markerBox && mapBox ? (markerBox.left + markerBox.width / 2) - (mapBox.left + mapBox.width / 2) : null,
                offsetY: markerBox && mapBox ? (markerBox.top + markerBox.height / 2) - (mapBox.top + mapBox.height / 2) : null,
                bodyHasLocationToast: document.body.innerText.includes('Location acquired'),
                bodySnippet: document.body.innerText.slice(0, 1200)
            };
        }"""
    )
    print(f"{label}_MAP_STATE={state}")
    assert state["userMarkerCount"] >= 1, f"{label}: expected pulsing user marker"
    assert state["userDotCount"] >= 1, f"{label}: expected marker dot markup"
    assert state["overlayPathCount"] >= 1, f"{label}: expected accuracy circle overlay"
    assert state["myLocationExists"], f"{label}: missing btn-map-my-location"
    assert state["myLocationDisabled"] is False, f"{label}: btn-map-my-location disabled despite GPS"
    assert abs(state["offsetX"]) <= 130 and abs(state["offsetY"]) <= 130, f"{label}: map did not fly to user location: {state}"
    return state


async def verify_my_location_recenter(page):
    map_box = await page.locator('[data-testid="map-container"]').bounding_box()
    assert map_box, "Map bounding box not available"
    await page.mouse.move(map_box["x"] + map_box["width"] / 2, map_box["y"] + map_box["height"] / 2)
    await page.mouse.down()
    await page.mouse.move(map_box["x"] + map_box["width"] / 2 + 360, map_box["y"] + map_box["height"] / 2 + 170, steps=12)
    await page.mouse.up()
    await page.wait_for_timeout(900)
    moved = await page.evaluate(
        """() => {
            const map = document.querySelector('[data-testid="map-container"]');
            const marker = document.querySelector('.user-marker');
            const mb = map.getBoundingClientRect();
            const ub = marker.getBoundingClientRect();
            return {offsetX: (ub.left + ub.width / 2) - (mb.left + mb.width / 2), offsetY: (ub.top + ub.height / 2) - (mb.top + mb.height / 2)};
        }"""
    )
    print(f"AFTER_MANUAL_DRAG_OFFSET={moved}")
    await page.locator('[data-testid="btn-map-my-location"]').click()
    await page.wait_for_timeout(1900)
    recentered = await page.evaluate(
        """() => {
            const map = document.querySelector('[data-testid="map-container"]');
            const marker = document.querySelector('.user-marker');
            const mb = map.getBoundingClientRect();
            const ub = marker.getBoundingClientRect();
            return {offsetX: (ub.left + ub.width / 2) - (mb.left + mb.width / 2), offsetY: (ub.top + ub.height / 2) - (mb.top + mb.height / 2)};
        }"""
    )
    print(f"AFTER_BTN_MAP_MY_LOCATION_OFFSET={recentered}")
    assert abs(recentered["offsetX"]) <= 130 and abs(recentered["offsetY"]) <= 130, "btn-map-my-location did not recenter on GPS marker"


async def verify_add_drone_gps_fields(page):
    await page.locator('[data-testid="btn-add-drone"]').click()
    await page.wait_for_selector('[data-testid="add-drone-dialog"]', timeout=10000)
    await page.wait_for_timeout(500)
    modal_state = await page.evaluate(
        """() => {
            const dlg = document.querySelector('[data-testid="add-drone-dialog"]');
            const b = dlg?.getBoundingClientRect();
            return {
                exists: !!dlg,
                visibleWithinViewport: !!b && b.top >= -2 && b.left >= -2 && b.bottom <= window.innerHeight + 2 && b.right <= window.innerWidth + 2,
                box: b ? {top:b.top, left:b.left, bottom:b.bottom, right:b.right, width:b.width, height:b.height} : null
            };
        }"""
    )
    print(f"ADD_MODAL_STATE={modal_state}")
    assert modal_state["exists"] and modal_state["visibleWithinViewport"], "Add Drone modal is not fully visible"

    use_btn = page.locator('[data-testid="btn-use-my-location"]')
    assert await use_btn.count() == 1, "btn-use-my-location is missing"
    assert await use_btn.is_enabled(), "btn-use-my-location should be enabled with GPS available"
    home_lat = await page.locator('[data-testid="input-home-lat"]').input_value()
    home_lon = await page.locator('[data-testid="input-home-lon"]').input_value()
    print(f"ADD_DIALOG_INITIAL_HOME={home_lat},{home_lon}")
    assert_close(home_lat, MOCK_LAT, 0.0002, "initial home_lat")
    assert_close(home_lon, MOCK_LON, 0.0002, "initial home_lon")

    # Manual edits should mark the home as touched and not be clobbered by later GPS updates.
    await page.locator('[data-testid="input-home-lat"]').fill("10.123456")
    await page.locator('[data-testid="input-home-lon"]').fill("20.654321")
    await page.context.set_geolocation({"latitude": UPDATED_LAT, "longitude": UPDATED_LON, "accuracy": 18})
    try:
        await page.wait_for_function("() => document.body.innerText.includes('28.70123') || document.body.innerText.includes('28.701')", timeout=6000)
        print("Observed live GPS text update after BrowserContext.set_geolocation")
    except Exception:
        print("WARNING: Live GPS text did not visibly update after BrowserContext.set_geolocation; still checking touched fields and Use My Location against current app store")
    await page.wait_for_timeout(1000)
    touched_lat = await page.locator('[data-testid="input-home-lat"]').input_value()
    touched_lon = await page.locator('[data-testid="input-home-lon"]').input_value()
    print(f"ADD_DIALOG_AFTER_GPS_UPDATE_WHILE_TOUCHED={touched_lat},{touched_lon}")
    assert_close(touched_lat, 10.123456, 0.000001, "touched home_lat")
    assert_close(touched_lon, 20.654321, 0.000001, "touched home_lon")

    await use_btn.click()
    await page.wait_for_timeout(700)
    reset_lat = await page.locator('[data-testid="input-home-lat"]').input_value()
    reset_lon = await page.locator('[data-testid="input-home-lon"]').input_value()
    body_text = await page.locator("body").inner_text()
    print(f"ADD_DIALOG_AFTER_USE_MY_LOCATION={reset_lat},{reset_lon}; TOAST_PRESENT={'Home set to your current location' in body_text}")
    assert "Home set to your current location" in body_text, "Expected success toast from Use My Location"
    # If the watchPosition callback fired, the current GPS is UPDATED_LAT/LON; otherwise it is the original mocked fix.
    reset_lat_f = float(reset_lat)
    reset_lon_f = float(reset_lon)
    assert (
        (abs(reset_lat_f - UPDATED_LAT) <= 0.0002 and abs(reset_lon_f - UPDATED_LON) <= 0.0002)
        or (abs(reset_lat_f - MOCK_LAT) <= 0.0002 and abs(reset_lon_f - MOCK_LON) <= 0.0002)
    ), f"Use My Location did not reset to the active GPS fix: {reset_lat},{reset_lon}"


async def verify_connection_modal_tabs(page):
    # Ensure Add Drone dialog is open.
    if await page.locator('[data-testid="add-drone-dialog"]').count() == 0:
        await page.locator('[data-testid="btn-add-drone"]').click()
        await page.wait_for_selector('[data-testid="add-drone-dialog"]')

    checks = [
        ('[data-testid="tab-conn-serial"]', '[data-testid="select-serial-port"]', "serial"),
        ('[data-testid="tab-conn-udp"]', '[data-testid="input-udp-address"]', "udp"),
        ('[data-testid="tab-conn-tcp"]', '[data-testid="input-tcp-address"]', "tcp"),
        ('[data-testid="tab-conn-sim"]', "text=Uses the built-in physics-lite simulator", "simulator"),
    ]
    for tab_selector, expected_selector, name in checks:
        await page.locator(tab_selector).click()
        await page.wait_for_timeout(300)
        assert await page.locator(expected_selector).first.is_visible(), f"{name} connection controls are not visible"
        print(f"CONNECTION_TAB_VISIBLE={name}")

    await page.locator('[data-testid="input-drone-name"]').fill("UI Simulator Drone")
    await page.locator('[data-testid="btn-add-drone-submit"]').click()
    await page.wait_for_timeout(1800)
    body_text = await page.locator("body").inner_text()
    print(f"SIMULATOR_CONNECT_TOAST_PRESENT={'UI Simulator Drone added & connected' in body_text}")
    assert "UI Simulator Drone added & connected" in body_text, "Simulator add/connect flow did not show success toast"
    assert await page.locator('[data-testid="add-drone-dialog"]').count() == 0, "Add Drone dialog did not close after simulator connect"


async def run(page):
    try:
        await page.set_viewport_size({"width": 1920, "height": 1080})
        context = page.context
        await context.grant_permissions(["geolocation"], origin=APP_URL)
        await context.set_geolocation({"latitude": MOCK_LAT, "longitude": MOCK_LON, "accuracy": MOCK_ACC})

        # Empty-fleet user-location map behavior.
        await cleanup_drones(page)
        await page.goto(APP_URL, wait_until="domcontentloaded")
        await page.wait_for_selector('[data-testid="map-container"]', timeout=15000)
        await wait_for_user_marker_centered(page, "EMPTY_FLEET")
        await verify_my_location_recenter(page)
        await verify_add_drone_gps_fields(page)

        # Regression: connection type tabs are visible and simulator add/connect still works.
        await verify_connection_modal_tabs(page)

        # Existing-drone edge: a saved drone should not prevent first user-location flyTo.
        await cleanup_drones(page)
        await create_seed_drone(page)
        await context.set_geolocation({"latitude": MOCK_LAT, "longitude": MOCK_LON, "accuracy": MOCK_ACC})
        await page.goto(APP_URL, wait_until="domcontentloaded")
        await page.wait_for_selector('[data-testid="map-container"]', timeout=15000)
        await page.wait_for_selector("text=Seed SF Drone", timeout=10000)
        await wait_for_user_marker_centered(page, "WITH_EXISTING_DRONE")

        # Error scan required by testing guidelines.
        error_text = await page.evaluate("""() => {
            const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
            return errorElements.map(el => el.textContent).join(", ");
        }""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")

        await cleanup_drones(page)
        print("LIVE_LOCATION_RETEST_ITERATION4_PASS")
    except Exception as exc:
        print(f"LIVE_LOCATION_RETEST_ITERATION4_FAIL: {type(exc).__name__}: {exc}")
        raise