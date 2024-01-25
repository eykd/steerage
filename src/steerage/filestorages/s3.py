"""An AWS S3 implementation of file storage."""
# NOTE: We have complete test coverage for all file storages, but
# commonly want to skip slow tests, and file storages are slow, so we
# mark this with nocover.
from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import BufferedIOBase
from typing import TYPE_CHECKING, ClassVar

import aioboto3
from convoke.configs import BaseConfig, Secret, env_field

from steerage.filestorages.base import AbstractFileStorage

if TYPE_CHECKING:  # pragma: nocover
    from pytest import FixtureRequest


class S3Config(BaseConfig):  # pragma: nocover
    """Connection configuration for an AWS S3 interface"""

    AWS_ACCESS_KEY_ID: Secret = env_field(
        doc="""
        AWS Access Key ID

        An Access Key ID with access permissions to

        Create an access key on the AWS IAM Console:

        https://us-east-1.console.aws.amazon.com/iam/home#/home
        """
    )
    AWS_SECRET_ACCESS_KEY: Secret = env_field(
        doc="""
        AWS Secret Access Key

        The Secret Access Key is paired with Access Key ID. Get yours
        on the AWS IAM Console:

        https://us-east-1.console.aws.amazon.com/iam/home#/home
        """
    )
    AWS_REGION: str = env_field(
        default="us-east-1",
        doc="""
        AWS region to use for S3

        This should match the region that your bucket has been created in.
        """,
    )

    AWS_S3_URL_PATTERN: str = env_field(
        default="https://s3.%(AWS_REGION)s.amazonaws.com",
        doc="""
        %-formatted URL pattern for accessing an S3-compatible HTTP interface
        """,
    )

    @property
    def AWS_S3_URL(self):
        """Provide an S3 API URL from the configured parts."""
        return self.AWS_S3_URL_PATTERN % self.asdict()


@dataclass
class S3FileStorage(AbstractFileStorage):  # pragma: nocover
    """An AWS S3-backed implementation of file storage"""

    bucket_name: str

    protocol: ClassVar[str] = "s3"
    config_class: ClassVar[S3Config] = S3Config

    async def write(self, key: str, buffer: BufferedIOBase):
        """Write a bytestream to S3.

        The `key` parameter corresponds to a filename.
        """
        async with self._get_s3_client() as s3:
            await s3.upload_fileobj(Fileobj=buffer, Bucket=self.bucket_name, Key=key)

    async def read(self, key: str) -> bytes:
        """Read bytes from S3.

        The `key` parameter corresponds to a filename.

        If the key does not exist, raise `NotFound`.
        """
        async with self._get_s3_client() as s3:
            try:
                s3_obj = await s3.get_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
            except s3.exceptions.NoSuchKey as exc:
                raise self.NotFound from exc
            return await s3_obj["Body"].read()

    async def delete(self, key: str) -> None:
        """Delete a stored file corresponding with the given key.

        The `key` parameter corresponds to a filename.

        If the key does not exist, calling delete(key) should be a
        no-op.
        """
        async with self._get_s3_client() as s3:
            await s3.delete_object(Bucket=self.bucket_name, Key=key)

    @asynccontextmanager
    async def _get_s3_client(self):
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.config.AWS_S3_URL,
            region_name=self.config.AWS_REGION,
            aws_access_key_id=self.config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.config.AWS_SECRET_ACCESS_KEY,
        ) as s3_client:
            yield s3_client


DATABASE = {}


@asynccontextmanager
async def build_s3_test_repo(request: "FixtureRequest"):  # pragma: nocover
    """Async context manager to build and tear down an S3FileStorage

    This also ensures that a threaded Moto S3 server is running; first
    startup is rather slow.
    """
    request.getfixturevalue("moto_s3_server")

    yield S3FileStorage(bucket_name=request.getfixturevalue("s3_bucket_name"))

    DATABASE.clear()
