import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from faker import Faker


@pytest.fixture()
def faker_():
    return Faker()


@pytest.fixture()
def fake_service_account(faker_):
    project_id = f"fake-mobile-app"
    client_email = f"firebase-adminsdk-h18o4@{project_id}.iam.gserviceaccount.com"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return {
        "type": "service_account",
        "project_id": project_id,
        "private_key_id": faker_.uuid4(cast_to=None).hex,
        "private_key": pem.decode(),
        "client_email": client_email,
        "client_id": faker_.bothify(text="#" * 21),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
    }


@pytest.fixture()
def fake_service_account_file(fake_service_account, faker_):
    file_name = Path(f"fake-mobile-app-{faker_.pystr(min_chars=12, max_chars=18)}.json")
    with open(str(file_name), "w") as outfile:
        json.dump(fake_service_account, outfile)
    yield file_name
    file_name.unlink()
