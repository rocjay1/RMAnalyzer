# pylint: disable-all

from __future__ import annotations
import logging
from datetime import datetime, date
import csv
from enum import Enum
import json
import re
from typing import Any
import urllib.parse
from typeguard import typechecked
import boto3
from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.type_defs import GetObjectOutputTypeDef
from mypy_boto3_ses.client import SESClient
from mypy_boto3_ses.type_defs import SendEmailResponseTypeDef
from botocore import exceptions
import yattag


# Logging
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


# Constants
DATE_FORMAT: str = "%Y-%m-%d"
DISPLAY_DATE_FORMAT: str = "%m/%d/%y"
MONEY_FORMAT: str = "{0:.2f}"
CONFIG = "rmanalyzer-config/config.json"


# Helpers
def read_s3_file(bucket: str, key: str) -> str:
    s3: S3Client = boto3.client("s3")
    try:
        response: GetObjectOutputTypeDef = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except exceptions.ClientError as ex:
        logger.error("Error reading S3 file: %s", ex)
        raise


# Config
class ConfigParser:

    @staticmethod
    def read_config(self, path: str) -> str:
        bucket, key = path.split("/")
        config = read_s3_file(bucket, key)
        return config

    @staticmethod
    def to_json(self, config: str) -> dict:
        try:
            return json.loads(config)
        except json.JSONDecodeError as ex:
            logger.error("Error loading config: %s", ex)
            raise
