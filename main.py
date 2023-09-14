import json
import logging
from datetime import date
import boto3
from botocore import exceptions
from classes import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_s3_file(bucket, key):
    s3 = boto3.client("s3")
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except exceptions.ClientError as e:
        logger.error(f"Error reading S3 file: {str(e)}")
        raise


def send_email(source, to_addresses, subject, html_body, text_body=None):
    ses = boto3.client("ses", region_name="us-east-1")
    if not text_body:
        text_body = html_body
    try:
        response = ses.send_email(
            Source=source,
            Destination={"ToAddresses": to_addresses},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": html_body}, "Text": {"Data": text_body}},
            },
        )
        return response
    except exceptions.ClientError as e:
        logger.error(f"Error sending email: {str(e)}")
        raise


def load_config(config_file="config.json"):
    """Load configuration from a JSON file."""
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(str(e))
        raise


def process_file(file_path):
    bucket, key = file_path.replace("s3://", "").split("/", 1)
    file_content = read_s3_file(bucket, key)
    config = load_config()
    summary = SpreadsheetSummary(config, date.today(), file_content)
    source, to_addresses, subject, html_body = EmailGenerator.generate_summary_email(
        summary
    )
    send_email(source, to_addresses, subject, html_body)


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    file_path = f"s3://{bucket}/{key}"
    process_file(file_path)
