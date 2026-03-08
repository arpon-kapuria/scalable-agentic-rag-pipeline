import boto3
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from boto3.s3.transfer import TransferConfig
from tqdm import tqdm

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


def upload_directory(dir_path: str, bucket_name: str, max_workers: int = 10):
    """
    High-performance parallel uploader for S3.
    Recursively uploads a directory while preserving folder structure.
    """

    s3 = boto3.client("s3")

    # Multipart upload configuration
    config = TransferConfig(
        multipart_threshold=25 * 1024 * 1024,   # 25MB
        multipart_chunksize=25 * 1024 * 1024,
        max_concurrency=20,
        use_threads=True
    )

    files_to_upload = []

    # Discover files
    for root, _, files in os.walk(dir_path):
        for file in files:
            local_path = os.path.join(root, file)
            s3_path = os.path.relpath(local_path, dir_path)
            files_to_upload.append((local_path, s3_path))

    if not files_to_upload:
        logger.warning("No files found to upload.")
        return

    logger.info(f"Found {len(files_to_upload)} files. Starting upload...")

    def upload_file(local_path, s3_path, retries=3):
        """
        Upload a single file with retry logic.
        """
        for attempt in range(retries):
            try:
                s3.upload_file(
                    Filename=local_path,
                    Bucket=bucket_name,
                    Key=s3_path,
                    Config=config
                )
                return True

            except Exception as e:
                logger.warning(
                    f"Retry {attempt + 1}/{retries} failed for {s3_path}: {e}"
                )

        logger.error(f"Upload failed permanently: {s3_path}")
        return False

    success_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = [
            executor.submit(upload_file, local, remote)
            for local, remote in files_to_upload
        ]

        for future in tqdm(as_completed(futures), total=len(futures), desc="Uploading"):
            if future.result():
                success_count += 1

    logger.info(f"Upload complete: {success_count}/{len(files_to_upload)} successful")


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("Usage: python bulk_upload_s3.py <local_dir> <bucket_name>")
        sys.exit(1)

    local_dir = sys.argv[1]
    bucket = sys.argv[2]

    upload_directory(local_dir, bucket)