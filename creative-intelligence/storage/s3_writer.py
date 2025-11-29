"""S3 storage integration for creative data.

This module provides async S3 operations for storing
creative assets and metadata.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Writer:
    """Async S3 client for creative data storage.

    Supports uploading creative metadata, assets, and reports
    to S3 with proper organization and lifecycle management.

    Attributes:
        bucket_name: The S3 bucket name.
        prefix: Key prefix for all objects (default: 'rtbcat/').
    """

    DEFAULT_PREFIX = "rtbcat/"

    def __init__(
        self,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None,
        prefix: str = DEFAULT_PREFIX,
    ) -> None:
        """Initialize the S3 writer.

        Args:
            bucket_name: S3 bucket name.
            access_key_id: AWS access key ID.
            secret_access_key: AWS secret access key.
            region: AWS region (default: us-east-1).
            endpoint_url: Custom endpoint URL (for S3-compatible storage).
            prefix: Key prefix for all objects.
        """
        self.bucket_name = bucket_name
        self.prefix = prefix
        self._region = region
        self._endpoint_url = endpoint_url

        config = Config(
            region_name=region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
            config=config,
        )

    def _make_key(self, *parts: str) -> str:
        """Construct an S3 key from parts.

        Args:
            *parts: Key path components.

        Returns:
            Full S3 key with prefix.
        """
        return self.prefix + "/".join(parts)

    async def upload_json(
        self,
        data: dict[str, Any],
        *key_parts: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        """Upload JSON data to S3.

        Args:
            data: Dictionary to serialize and upload.
            *key_parts: Key path components.
            metadata: Optional S3 object metadata.

        Returns:
            The S3 key of the uploaded object.
        """
        key = self._make_key(*key_parts)
        body = json.dumps(data, default=str, indent=2)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
                Metadata=metadata or {},
            ),
        )

        logger.debug(f"Uploaded JSON to s3://{self.bucket_name}/{key}")
        return key

    async def upload_file(
        self,
        file_path: Path,
        *key_parts: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        """Upload a file to S3.

        Args:
            file_path: Local file path to upload.
            *key_parts: Key path components.
            content_type: MIME type (auto-detected if not provided).
            metadata: Optional S3 object metadata.

        Returns:
            The S3 key of the uploaded object.
        """
        key = self._make_key(*key_parts)

        extra_args = {"Metadata": metadata or {}}
        if content_type:
            extra_args["ContentType"] = content_type

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.upload_file(
                str(file_path),
                self.bucket_name,
                key,
                ExtraArgs=extra_args,
            ),
        )

        logger.debug(f"Uploaded file to s3://{self.bucket_name}/{key}")
        return key

    async def upload_bytes(
        self,
        data: bytes,
        *key_parts: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict[str, str]] = None,
    ) -> str:
        """Upload raw bytes to S3.

        Args:
            data: Bytes to upload.
            *key_parts: Key path components.
            content_type: MIME type.
            metadata: Optional S3 object metadata.

        Returns:
            The S3 key of the uploaded object.
        """
        key = self._make_key(*key_parts)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=metadata or {},
            ),
        )

        logger.debug(f"Uploaded bytes to s3://{self.bucket_name}/{key}")
        return key

    async def upload_creative(
        self,
        creative_id: str,
        data: dict[str, Any],
        asset: Optional[bytes] = None,
        asset_type: str = "image/png",
    ) -> dict[str, str]:
        """Upload creative metadata and optional asset.

        Args:
            creative_id: Unique creative identifier.
            data: Creative metadata dictionary.
            asset: Optional binary asset data.
            asset_type: MIME type of the asset.

        Returns:
            Dictionary with 'metadata_key' and optionally 'asset_key'.
        """
        date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
        result = {}

        # Upload metadata
        metadata_key = await self.upload_json(
            data,
            "creatives",
            date_prefix,
            f"{creative_id}.json",
            metadata={"creative_id": creative_id},
        )
        result["metadata_key"] = metadata_key

        # Upload asset if provided
        if asset:
            ext = asset_type.split("/")[-1]
            asset_key = await self.upload_bytes(
                asset,
                "assets",
                date_prefix,
                f"{creative_id}.{ext}",
                content_type=asset_type,
                metadata={"creative_id": creative_id},
            )
            result["asset_key"] = asset_key

        return result

    async def download_json(self, *key_parts: str) -> dict[str, Any]:
        """Download and parse JSON from S3.

        Args:
            *key_parts: Key path components.

        Returns:
            Parsed JSON data.

        Raises:
            ClientError: If the object doesn't exist or download fails.
        """
        key = self._make_key(*key_parts)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.get_object(
                Bucket=self.bucket_name,
                Key=key,
            ),
        )

        body = response["Body"].read().decode("utf-8")
        return json.loads(body)

    async def list_objects(
        self,
        *prefix_parts: str,
        max_keys: int = 1000,
    ) -> list[dict[str, Any]]:
        """List objects under a prefix.

        Args:
            *prefix_parts: Prefix path components.
            max_keys: Maximum number of keys to return.

        Returns:
            List of object metadata dictionaries.
        """
        prefix = self._make_key(*prefix_parts) if prefix_parts else self.prefix

        loop = asyncio.get_event_loop()
        objects = []
        continuation_token = None

        while len(objects) < max_keys:
            params = {
                "Bucket": self.bucket_name,
                "Prefix": prefix,
                "MaxKeys": min(1000, max_keys - len(objects)),
            }
            if continuation_token:
                params["ContinuationToken"] = continuation_token

            response = await loop.run_in_executor(
                None,
                lambda p=params: self._client.list_objects_v2(**p),
            )

            contents = response.get("Contents", [])
            objects.extend(
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                }
                for obj in contents
            )

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")

        return objects

    async def delete_object(self, *key_parts: str) -> bool:
        """Delete an object from S3.

        Args:
            *key_parts: Key path components.

        Returns:
            True if deleted successfully.
        """
        key = self._make_key(*key_parts)

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key,
                ),
            )
            logger.debug(f"Deleted s3://{self.bucket_name}/{key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {key}: {e}")
            return False

    async def object_exists(self, *key_parts: str) -> bool:
        """Check if an object exists in S3.

        Args:
            *key_parts: Key path components.

        Returns:
            True if the object exists.
        """
        key = self._make_key(*key_parts)

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.head_object(
                    Bucket=self.bucket_name,
                    Key=key,
                ),
            )
            return True
        except ClientError:
            return False

    async def generate_presigned_url(
        self,
        *key_parts: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned URL for an object.

        Args:
            *key_parts: Key path components.
            expires_in: URL expiration time in seconds.

        Returns:
            Presigned URL string.
        """
        key = self._make_key(*key_parts)

        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            ),
        )

        return url
