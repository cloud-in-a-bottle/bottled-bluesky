import time

from openhost_test_harness import OpenhostStack


def test_app_serves_owner(stack: OpenhostStack) -> None:
    # The app is marked running once its health check passes; "/" can take a little longer to come up.
    deadline = time.monotonic() + 60
    while True:
        response = stack.owner_session.get(f"{stack.url}/", timeout=30)
        if response.status_code < 400 or time.monotonic() > deadline:
            break
        time.sleep(2)
    assert response.status_code < 400, (
        f"GET / returned {response.status_code}: {response.text[:500]}\n\napp logs:\n{stack.app_logs()[-5000:]}"
    )


def test_owner_account_created(stack: OpenhostStack) -> None:
    # The owner account is bootstrapped in the background after the PDS comes up; if that fails, the app exits.
    deadline = time.monotonic() + 120
    while True:
        response = stack.owner_session.get(
            f"{stack.url}/xrpc/com.atproto.identity.resolveHandle",
            params={"handle": "bluesky.harness.test"},
            timeout=30,
        )
        if response.status_code == 200 or time.monotonic() > deadline:
            break
        time.sleep(2)
    assert response.status_code == 200, (
        f"resolveHandle returned {response.status_code}: {response.text[:500]}\n\n"
        f"app logs:\n{stack.app_logs()[-5000:]}"
    )
