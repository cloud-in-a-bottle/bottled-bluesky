import json
import re
import time

import requests
from openhost_test_harness import OpenhostStack

OWNER_HANDLE = "bluesky.harness.test"
# auth_proxy.py embeds the seeded account as `var ACCT={"account": {...}}.account;`.
SEEDED_ACCOUNT = re.compile(r"var ACCT=(\{.*\})\.account;")


def _owner_sso_page(stack: OpenhostStack) -> requests.Response:
    # The SSO app-password is written by the background owner bootstrap, so poll until the proxy can use it.
    deadline = time.monotonic() + 180
    while True:
        try:
            response = stack.owner_session.get(
                f"{stack.url}/", headers={"Accept": "text/html"}, allow_redirects=False, timeout=30
            )
            if "BSKY_STORAGE" in response.text:
                return response
        except requests.ConnectionError:
            response = None
        if time.monotonic() > deadline:
            got = "no response" if response is None else f"{response.status_code}: {response.text[:500]}"
            raise AssertionError(f"owner never got the SSO page; last {got}\n\n{stack.app_logs()[-5000:]}")
        time.sleep(3)


def test_owner_is_signed_in(stack: OpenhostStack) -> None:
    # The owner's first page load is answered by auth_proxy.py with a page that seeds the web client's session
    # store with a fresh PDS session for the owner account, so they land signed in without a login form.
    response = _owner_sso_page(stack)
    match = SEEDED_ACCOUNT.search(response.text)
    assert match, f"no seeded account in SSO page: {response.text[:1000]}"
    account = json.loads(match.group(1))["account"]
    assert account["handle"] == OWNER_HANDLE, account["handle"]
    # The seeded token is a real session for the owner on our PDS.
    session = requests.get(
        f"{stack.url}/xrpc/com.atproto.server.getSession",
        headers={"Authorization": f"Bearer {account['accessJwt']}"},
        timeout=30,
    )
    assert session.status_code == 200, f"{session.status_code}: {session.text[:500]}"
    assert session.json()["did"] == account["did"]
    assert session.json()["handle"] == OWNER_HANDLE


def test_anonymous_access(stack: OpenhostStack) -> None:
    # The federation paths in public_paths must work without an owner login (relays, AppViews and other servers
    # call them), while the web client stays owner-only.
    deadline = time.monotonic() + 180
    while True:
        resolved = requests.get(
            f"{stack.url}/xrpc/com.atproto.identity.resolveHandle", params={"handle": OWNER_HANDLE}, timeout=30
        )
        if resolved.status_code == 200 or time.monotonic() > deadline:
            break
        time.sleep(3)
    assert resolved.status_code == 200, f"{resolved.status_code}: {resolved.text[:500]}"
    assert resolved.json()["did"].startswith("did:")

    describe = requests.get(f"{stack.url}/xrpc/com.atproto.server.describeServer", timeout=30)
    assert describe.status_code == 200, f"{describe.status_code}: {describe.text[:500]}"

    private = requests.get(f"{stack.url}/", headers={"Accept": "text/html"}, allow_redirects=False, timeout=30)
    assert private.status_code in (302, 303, 307, 401, 403), f"{private.status_code}: {private.text[:500]}"
    assert "BSKY_STORAGE" not in private.text


def test_pds_data_in_app_data(stack: OpenhostStack) -> None:
    # start.sh points the PDS's databases and blob store at the app data dir, so they're backed up.
    account_db = stack.data_dir / "pds" / "account.sqlite"
    deadline = time.monotonic() + 180
    while not account_db.is_file() and time.monotonic() < deadline:
        time.sleep(3)
    assert account_db.is_file(), f"{account_db} missing\n\n{stack.app_logs()[-3000:]}"
    assert (stack.data_dir / "pds" / "blocks").is_dir()
