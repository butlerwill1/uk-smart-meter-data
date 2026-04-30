# Summary: Shared utility helpers for Spark/Glue setup, S3 path handling, and metadata.
"""Shared helpers used by multiple pipeline scripts.

This module includes:
- time/id helpers for logging and run metadata,
- S3 URI parsing/building utilities,
- Spark session creation that prefers AWS Glue runtime and falls back locally.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from pyspark import SparkContext
from pyspark.sql import SparkSession


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    """Generate a unique run identifier."""
    return str(uuid.uuid4())


def get_git_sha(default: str = "unknown") -> str:
    """Return current git short SHA when available, otherwise a fallback value."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return default


def ensure_s3_uri(path: str) -> str:
    """Normalize a path to an s3:// URI."""
    if path.startswith("s3://"):
        return path
    return f"s3://{path.lstrip('/')}"


def partition_uri(base_uri: str, partition_key: str, partition_value: str) -> str:
    """Build a partition path such as .../collection_date=YYYY-MM-DD."""
    return f"{base_uri.rstrip('/')}/{partition_key}={partition_value}"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Split an s3:// URI into (bucket, key_prefix)."""
    parsed = urlparse(uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Expected s3:// URI, got: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def to_json(data: dict) -> str:
    """Serialize dictionary values to stable JSON for logs/metadata."""
    return json.dumps(data, sort_keys=True, default=str)


def get_spark(app_name: str, aws_region: str | None = None) -> SparkSession:
    """Return a Spark session for Glue or local development.

    Behavior:
    - In AWS Glue, use GlueContext-backed Spark session.
    - Outside Glue, construct a standard SparkSession builder.
    """
    try:
        from awsglue.context import GlueContext

        sc = SparkContext.getOrCreate()
        glue_context = GlueContext(sc)
        spark = glue_context.spark_session

        # Apply shared runtime settings in Glue.
        spark.sparkContext.setLogLevel(os.getenv("SPARK_LOG_LEVEL", "WARN"))
        spark.conf.set("spark.sql.session.timeZone", "UTC")
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
        if aws_region:
            spark.conf.set("spark.hadoop.fs.s3a.aws.region", aws_region)
        return spark
    except Exception:
        # Local fallback path for development and tests.
        builder = SparkSession.builder.appName(app_name)
        builder = builder.config("spark.sql.session.timeZone", "UTC")
        builder = builder.config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        if aws_region:
            builder = builder.config("spark.hadoop.fs.s3a.aws.region", aws_region)
        if os.getenv("SPARK_MASTER"):
            builder = builder.master(os.getenv("SPARK_MASTER"))
        return builder.getOrCreate()
