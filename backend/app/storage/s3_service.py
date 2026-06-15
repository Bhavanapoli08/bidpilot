"""
Object storage for tender PDFs.

Uses AWS S3 when credentials are configured. When they are NOT (local dev),
it transparently falls back to a local filesystem backend rooted at
LOCAL_STORAGE_DIR (default: <backend>/.local_storage). The public interface is
identical in both modes, so the rest of the app is unaware of which is active.
"""
import os
import shutil
import hashlib
import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME
        # Local mode whenever AWS credentials are missing.
        self.local_mode = not (settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)

        if self.local_mode:
            self.s3_client = None
            self.local_root = Path(
                os.environ.get("LOCAL_STORAGE_DIR", Path(__file__).resolve().parents[2] / ".local_storage")
            ).resolve()
            self.local_root.mkdir(parents=True, exist_ok=True)
            logger.warning(
                "S3Service in LOCAL mode (no AWS credentials) — storing files under %s",
                self.local_root,
            )
        else:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )

    @staticmethod
    def _key(org_id: str, tender_id: str) -> str:
        return f"organizations/{org_id}/tenders/{tender_id}/original.pdf"

    def _local_file(self, org_id: str, tender_id: str) -> Path:
        return self.local_root / self._key(org_id, tender_id)

    async def upload_tender_pdf(self, org_id: str, tender_id: str, file_path: str, file_size: int) -> dict:
        """Store a tender PDF and return its storage descriptor."""
        s3_key = self._key(org_id, tender_id)
        file_hash = self.compute_file_hash(file_path)

        if self.local_mode:
            dest = self._local_file(org_id, tender_id)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file_path, dest)
            logger.info("Stored %s locally (%d bytes)", s3_key, file_size)
        else:
            try:
                self.s3_client.upload_file(
                    file_path,
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        "ServerSideEncryption": "AES256",
                        "Metadata": {
                            "org_id": org_id,
                            "tender_id": tender_id,
                            "file_hash": file_hash,
                        },
                    },
                )
                logger.info("Uploaded %s", s3_key)
            except ClientError as e:
                logger.error("S3 upload failed: %s", e)
                raise

        return {
            "s3_key": s3_key,
            "file_hash": file_hash,
            "file_size": file_size,
            "bucket": "local" if self.local_mode else self.bucket_name,
        }

    def download_bytes(self, org_id: str, tender_id: str) -> bytes:
        """Synchronous read of stored PDF bytes (used by Celery workers)."""
        if self.local_mode:
            return self._local_file(org_id, tender_id).read_bytes()
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=self._key(org_id, tender_id))
        return response["Body"].read()

    async def download_file(self, org_id: str, tender_id: str) -> bytes:
        return self.download_bytes(org_id, tender_id)

    def generate_signed_url(self, org_id: str, tender_id: str, expiration: int = 3600) -> str:
        """Time-limited download URL. In local mode, points at the streaming endpoint."""
        if self.local_mode:
            return f"{settings.BACKEND_URL}/api/tenders/{tender_id}/download"
        s3_key = self._key(org_id, tender_id)
        try:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
        except ClientError as e:
            logger.error("Failed to generate signed URL: %s", e)
            raise

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


s3_service = S3Service()
