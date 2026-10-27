import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from openhost_test_harness import OpenhostStack

APP_DIR = Path(__file__).resolve().parent.parent

# The harness zone is "harness.localhost:<port>", which can't be a Bluesky handle (start.sh refuses it), so the app
# under test gets a fixed port-less hostname on the .test TLD, which the PDS accepts.
TEST_ENV = """
ENV PDS_HOSTNAME=bluesky.harness.test
ENV PDS_SERVICE_HANDLE_DOMAINS=.harness.test
"""


def _app_copy_with_test_env(dest: Path) -> Path:
    """Copies the working tree (minus gitignored files) to ``dest`` and appends TEST_ENV to its Dockerfile."""
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=APP_DIR,
        capture_output=True,
        check=True,
    )
    for rel in listing.stdout.decode().split("\0"):
        if rel and (APP_DIR / rel).is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(APP_DIR / rel, dest / rel)
    with (dest / "Dockerfile").open("a") as f:
        f.write(TEST_ENV)
    return dest


@pytest.fixture(scope="session")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[OpenhostStack]:
    """Builds the Dockerfile and deploys the app through the real router; returns once the app is running."""
    app_dir = _app_copy_with_test_env(tmp_path_factory.mktemp("app"))
    # The image builds Bluesky's social-app web client and Go server from source, well over the default 5 minutes on CI.
    with OpenhostStack(app_dir=app_dir, deploy_timeout=1800) as s:
        yield s
