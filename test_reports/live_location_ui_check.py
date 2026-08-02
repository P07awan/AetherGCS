import math

MOCK_LAT = 28.6139
MOCK_LON = 77.2090
APP_URL = "https://drone-swarm-control-1.preview.emergentagent.com"


async def run(page):
    await page.set_viewport_size({"width": 1920, "height": 1080})
    context = page.context
    await context.grant_permissions(["geolocation"], origin=APP_URL)
    await context.set_geolocation({"latitude": MOCK_LAT, "longitude": MOCK_LON, "accuracy": 25})
    await page.goto(APP_URL, wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="map-container"]', timeout=15000)
    await page.wait_for_timeout(5000)

    user_marker_count = await page.locator(".user-marker").count()
    center_info = await page.evaluate(
        """() => {
            const map = document.querySelector('[data-testid="map-container"]');
            const marker = document.querySelector('.user-marker');
            const button = document.querySelector('[data-testid="btn-map-my-location"]');
            const paths = Array.from(document.querySelectorAll('.leaflet-overlay-pane path'));
            if (!map || !marker) return {missing: true, userMarkerCount: document.querySelectorAll('.user-marker').length};
            const mr = map.getBoundingClientRect();
            const ur = marker.getBoundingClientRect();
            return {
                missing: false,
                userMarkerCount: document.querySelectorAll('.user-marker').length,
                markerCenterX: ur.left + ur.width / 2,
                markerCenterY: ur.top + ur.height / 2,
                mapCenterX: mr.left + mr.width / 2,
                mapCenterY: mr.top + mr.height / 2,
                offsetX: (ur.left + ur.width / 2) - (mr.left + mr.width / 2),
                offsetY: (ur.top + ur.height / 2) - (mr.top + mr.height / 2),
                myLocationDisabled: button ? button.disabled : null,
                overlayPathCount: paths.length,
                cyanPathCount: paths.filter(p => (p.getAttribute('stroke') || p.style.stroke || '').includes('00F0FF') || (p.getAttribute('fill') || p.style.fill || '').includes('00F0FF')).length,
                buttonOpacity: button ? getComputedStyle(button).opacity : null
            };
        }"""
    )
    print(f"GRANTED_CENTER_INFO={center_info}")
    if user_marker_count < 1:
        raise AssertionError("Expected pulsing user marker after granted geolocation")
    if abs(center_info["offsetX"]) > 120 or abs(center_info["offsetY"]) > 120:
        raise AssertionError(f"User marker not near map center after geolocation flyTo: {center_info}")
    if center_info["myLocationDisabled"]:
        raise AssertionError("My Location button is disabled even though geolocation is available")
    if center_info["overlayPathCount"] < 1:
        raise AssertionError("Expected an accuracy circle/path for user location")

    # Drag map away and verify the My Location button recenters on the mock GPS marker.
    map_box = await page.locator('[data-testid="map-container"]').bounding_box()
    await page.mouse.move(map_box["x"] + map_box["width"] / 2, map_box["y"] + map_box["height"] / 2)
    await page.mouse.down()
    await page.mouse.move(map_box["x"] + map_box["width"] / 2 + 350, map_box["y"] + map_box["height"] / 2 + 150, steps=10)
    await page.mouse.up()
    await page.wait_for_timeout(800)
    moved_offset = await page.evaluate(
        """() => {
            const map = document.querySelector('[data-testid="map-container"]');
            const marker = document.querySelector('.user-marker');
            const mr = map.getBoundingClientRect();
            const ur = marker.getBoundingClientRect();
            return {offsetX: (ur.left + ur.width / 2) - (mr.left + mr.width / 2), offsetY: (ur.top + ur.height / 2) - (mr.top + mr.height / 2)};
        }"""
    )
    print(f"AFTER_DRAG_OFFSET={moved_offset}")
    await page.locator('[data-testid="btn-map-my-location"]').click()
    await page.wait_for_timeout(1800)
    recentered_offset = await page.evaluate(
        """() => {
            const map = document.querySelector('[data-testid="map-container"]');
            const marker = document.querySelector('.user-marker');
            const mr = map.getBoundingClientRect();
            const ur = marker.getBoundingClientRect();
            return {offsetX: (ur.left + ur.width / 2) - (mr.left + mr.width / 2), offsetY: (ur.top + ur.height / 2) - (mr.top + mr.height / 2)};
        }"""
    )
    print(f"AFTER_MY_LOCATION_CLICK_OFFSET={recentered_offset}")
    if abs(recentered_offset["offsetX"]) > 120 or abs(recentered_offset["offsetY"]) > 120:
        raise AssertionError("My Location button did not recenter the map on the mock GPS marker")

    # Add Drone dialog should prefill home coordinates from geolocation and expose Use My Location.
    await page.locator('[data-testid="btn-add-drone"]').click()
    await page.wait_for_selector('[data-testid="add-drone-dialog"]', timeout=10000)
    home_lat = await page.locator('[data-testid="input-home-lat"]').input_value()
    home_lon = await page.locator('[data-testid="input-home-lon"]').input_value()
    use_my_location_count = await page.locator('[data-testid="btn-use-my-location"]').count()
    print(f"ADD_DIALOG_HOME={home_lat},{home_lon}; USE_MY_LOCATION_BUTTON_COUNT={use_my_location_count}")
    if abs(float(home_lat) - MOCK_LAT) > 0.0002 or abs(float(home_lon) - MOCK_LON) > 0.0002:
        raise AssertionError(f"Home coordinates not prefilled from mock geolocation: {home_lat},{home_lon}")
    if use_my_location_count != 1:
        raise AssertionError("Expected btn-use-my-location in Add Drone dialog")

    error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")
