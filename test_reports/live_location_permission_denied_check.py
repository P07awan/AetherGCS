APP_URL = "https://drone-swarm-control-1.preview.emergentagent.com"


async def run(page):
    await page.set_viewport_size({"width": 1920, "height": 1080})
    context = page.context
    await context.clear_permissions()
    await page.goto(APP_URL, wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="map-container"]', timeout=15000)
    await page.wait_for_timeout(3000)
    state = await page.evaluate(
        """() => {
            const btn = document.querySelector('[data-testid="btn-map-my-location"]');
            const toasts = Array.from(document.querySelectorAll('[data-sonner-toast], [data-title], [data-description]')).map(el => el.textContent).join(' | ');
            return {
                markerCount: document.querySelectorAll('.user-marker').length,
                buttonExists: !!btn,
                buttonDisabled: btn ? btn.disabled : null,
                buttonOpacity: btn ? getComputedStyle(btn).opacity : null,
                bodyHasLocationDenied: document.body.innerText.includes('Location permission denied'),
                bodyTextSnippet: document.body.innerText.slice(0, 1000),
                toastText: toasts
            };
        }"""
    )
    print(f"DENIED_STATE={state}")
    assert state["buttonExists"], "My Location button should still exist when permission denied"
    assert state["buttonDisabled"], "My Location button should be disabled when no geolocation is available"
    assert state["markerCount"] == 0, "User marker should not render without geolocation"
    assert state["bodyHasLocationDenied"] or "Location permission denied" in state["toastText"], "Expected permission denied warning toast"
