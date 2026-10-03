"""Shared setup for integration tests that call the real FCM API.

Set the environment variable ``FIREBASE_SERVICE_ACCOUNT_KEY`` to the path of a service-account JSON file.
When credentials are absent the tests are skipped automatically.
"""

import json
import os

import pytest


SERVICE_ACCOUNT_PATH = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")


def _has_valid_credentials() -> bool:
    """Check that the service account file exists and contains valid JSON."""
    if not SERVICE_ACCOUNT_PATH or not os.path.isfile(SERVICE_ACCOUNT_PATH):
        return False
    try:
        with open(SERVICE_ACCOUNT_PATH) as f:
            json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    return True


requires_firebase_credentials = pytest.mark.skipif(
    not _has_valid_credentials(),
    reason="FIREBASE_SERVICE_ACCOUNT_KEY not set or not valid JSON (expected in Dependabot runs)",
)
