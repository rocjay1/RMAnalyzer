from classes import SpreadsheetParser, MonthlySummary, Person, EmailGenerator
import json
import logging
import sys
from datetime import date
import boto3

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def load_config(config_file="config.json"):
    """Load configuration from a JSON file."""
    try:
        with open(config_file, "r") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "Configuration file not found."
    except json.JSONDecodeError:
        return None, "Failed to decode JSON from configuration file."


def read_s3_file(bucket, key):
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


def send_email(source, to_addresses, subject, html_body, text_body=None):
    ses = boto3.client("ses")
    if not text_body:
        text_body = html_body
    response = ses.send_email(
        Source=source,
        Destination={"ToAddresses": to_addresses},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Html": {"Data": html_body}, "Text": {"Data": text_body}},
        },
    )
    return response


def process_file(file_path):
    bucket, key = file_path.replace("s3://", "").split("/", 1)
    file_content = read_s3_file(bucket, key)

    config, error_msg = load_config()
    if config is None:
        logging.error(f"{error_msg}. Exiting.")
        sys.exit(1)

    people = []
    for person in config["People"]:
        name = person["Name"][0]
        accounts = person["Accounts"]
        transactions = []
        people.append(Person(name, accounts, transactions))

    summary = MonthlySummary(people, date.today())
    parsed_transactions = SpreadsheetParser.parse(file_content)
    summary.add_all_transactions(parsed_transactions)

    html_body = EmailGenerator.generate_summary_email(summary)


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    file_path = f"s3://{bucket}/{key}"
    process_file(file_path)
