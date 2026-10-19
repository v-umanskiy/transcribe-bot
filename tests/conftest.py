import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Modules create boto3 clients at import time. Dummy region and credentials let them
# import without AWS access, and test URLs stand in for the deployment's real links.
os.environ.pop("AWS_PROFILE", None)
os.environ.update(
    {
        "AWS_DEFAULT_REGION": "eu-west-1",
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "PRIVACY_URL": "https://example.test/privacy",
        "CONTACT_URL": "https://example.test/contact",
    }
)
