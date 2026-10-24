from collections.abc import Iterator

import pytest
from openhost_test_harness import OpenhostStack


@pytest.fixture(scope="session")
def stack() -> Iterator[OpenhostStack]:
    """Builds the Dockerfile and deploys the app through the real router; returns once the app is running."""
    # The image builds Bluesky's social-app web client and Go server from source, well over the default 5 minutes on CI.
    with OpenhostStack(deploy_timeout=1800) as s:
        yield s
