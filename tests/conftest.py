# ruff: noqa: D103
"""Global pytest fixtures"""
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import boto3
import httpx
import pytest
import pytz
from faker import Faker
from moto.server import ThreadedMotoServer

from steerage.repositories import memdb
from steerage.repositories.sqldb import TESTING_DATABASE_URL
from convoke.configs import BaseConfig


@pytest.fixture
def tempdir() -> str:
    with tempfile.TemporaryDirectory() as tempdir:
        yield Path(tempdir)


@pytest.fixture(scope="session")
def s3_bucket_name():
    return "my-bucket"


@pytest.fixture(scope="session")
def aws_access_key_id():
    return "AKFOO"


@pytest.fixture(scope="session")
def aws_secret_access_key():
    return "SKFOO"


@pytest.fixture(scope="session")
def aws_region():
    return "us-east-1"


@pytest.fixture(scope="session")
def shelve_db_path() -> Path:
    with tempfile.TemporaryDirectory() as tempdir:
        return Path(tempdir) / "shelve.db"


@pytest.fixture(autouse=True)
def shelve_db_path_clear(shelve_db_path: Path) -> None:
    yield None
    if shelve_db_path.exists():
        shelve_db_path.unlink()


@pytest.fixture(scope="session", autouse=True)
def auto_env_base(
    s3_bucket_name: str, aws_access_key_id: str, aws_secret_access_key: str, aws_region: str, shelve_db_path: Path
):
    old_environ = dict(os.environ)
    os.environ.clear()
    for key, value in old_environ.items():
        if key.startswith("PYTEST"):
            os.environ[key] = value

    os.environ.update(
        {
            "DEBUG": "True",
            "TESTING": "True",
            "DATABASE_URL": TESTING_DATABASE_URL,
            "DATABASE_ECHO": "False",
            "SHELVE_DB_PATH": str(shelve_db_path),
            # AWS Secrets
            "AWS_S3_BUCKET": s3_bucket_name,
            "AWS_ACCESS_KEY_ID": aws_access_key_id,
            "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
            "AWS_REGION": aws_region,
        }
    )
    yield os.environ
    os.environ.clear()
    os.environ.update(old_environ)


@pytest.fixture
def config(tempdir) -> BaseConfig:
    return BaseConfig()


@pytest.fixture(autouse=True)
def clear_in_memory_database():
    memdb.Database.clear()


@pytest.fixture
def uuid(faker: Faker) -> UUID:
    return faker.uuid4()


@pytest.fixture
def known_datetime() -> datetime:
    return datetime(year=2023, month=10, day=24, hour=12, minute=30, second=30, tzinfo=pytz.timezone("US/Pacific"))


@pytest.fixture(scope="session")
def s3_host():
    return "127.0.0.1"


@pytest.fixture(scope="session")
def s3_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture(scope="session")
def s3_url(s3_host, s3_port):
    url = f"http://{s3_host}:{s3_port}"
    with patch.dict(os.environ, AWS_S3_URL_PATTERN=url):
        yield url


@pytest.fixture(scope="session")
def session_moto_s3_server(s3_host, s3_port, s3_url):
    server = ThreadedMotoServer(
        ip_address=s3_host,
        port=s3_port,
    )
    server.start()

    yield server

    # httpx.post(f"{s3_url}/moto-api/reset")

    server.stop()


@pytest.fixture(scope="session")
def moto_api_client(session_moto_s3_server, s3_url):
    # This reset call is necessary for the test client to get set up correctly:
    httpx.post(f"{s3_url}/moto-api/reset")
    return session_moto_s3_server._server.app.app_instances["moto_api"].test_client()


@pytest.fixture(scope="session")
def s3_client(s3_url, aws_region, aws_access_key_id, aws_secret_access_key):
    return boto3.client(
        "s3",
        endpoint_url=s3_url,
        region_name=aws_region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


@pytest.fixture
def moto_s3_server(session_moto_s3_server, moto_api_client, s3_url, s3_client, s3_bucket_name):
    s3_client.create_bucket(
        Bucket=s3_bucket_name,
        ACL="public-read-write",
    )
    yield session_moto_s3_server

    moto_api_client.post("/moto-api/reset")
