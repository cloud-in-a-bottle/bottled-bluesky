import time

import requests
from openhost_test_harness import OpenhostStack
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

OWNER_HANDLE = "bluesky.harness.test"

# Only the account fields we compare; never the tokens.
STORED_ACCOUNT_JS = """() => {
  try {
    const a = JSON.parse(localStorage.getItem('BSKY_STORAGE')).session.currentAccount;
    return a ? {did: a.did, handle: a.handle} : null;
  } catch (e) { return null; }
}"""


def _owner_did(stack: OpenhostStack) -> str:
    # The owner account is bootstrapped in the background after the PDS comes up.
    deadline = time.monotonic() + 180
    while True:
        try:
            response = requests.get(
                f"{stack.url}/xrpc/com.atproto.identity.resolveHandle", params={"handle": OWNER_HANDLE}, timeout=30
            )
            if response.status_code == 200:
                return str(response.json()["did"])
        except requests.ConnectionError:
            pass
        if time.monotonic() > deadline:
            raise AssertionError(f"owner handle never resolved\n\n{stack.app_logs()[-5000:]}")
        time.sleep(3)


def test_owner_lands_signed_in_in_browser(stack: OpenhostStack, page: Page) -> None:
    # auth_proxy.py answers the owner's first navigation with a page that seeds the web client's session store and
    # reloads; the client must then accept that session and render signed in, with no sign-in screen.
    did = _owner_did(stack)
    stack.playwright_login(page)
    # The SSO app-password is written by the background bootstrap; until then "/" is the signed-out client, so
    # navigate again (after the reload-loop cookie expires) until the owner's profile link shows in the nav.
    profile_link = page.locator(f'a[href="/profile/{OWNER_HANDLE}"], a[href="/profile/{did}"]')
    deadline = time.monotonic() + 240
    while True:
        page.context.clear_cookies(name="oh_sso")
        page.goto(f"{stack.url}/", wait_until="domcontentloaded")
        try:
            profile_link.first.wait_for(state="attached", timeout=45_000)
            break
        except PlaywrightTimeoutError:
            if time.monotonic() > deadline:
                text = page.locator("body").inner_text()[:1500]
                raise AssertionError(
                    f"owner not signed in at {page.url}; stored account {page.evaluate(STORED_ACCOUNT_JS)}\n"
                    f"page text:\n{text}\n\napp logs:\n{stack.app_logs()[-5000:]}"
                ) from None
    assert page.evaluate(STORED_ACCOUNT_JS) == {"did": did, "handle": OWNER_HANDLE}
    assert page.get_by_test_id("signInButton").count() == 0, page.locator("body").inner_text()[:1500]
