# Desc: This script is used to generate a monthly summary of expenses from a spreadsheet.
#       It is meant to be run as an AWS Lambda function triggered by an S3 event.
#       The spreadsheet should be an export from Rocket Money.
#       The configuration file should be stored in an S3 bucket.
#       The Lambda function should have access to the S3 bucket and SES.
# Usage: python Repos/RMAnalyzer/main.py s3://<bucket>/<key>
# Author: Rocco Davino


import sys
import logging
from datetime import datetime, date
import csv
from enum import Enum
import json
import boto3
from botocore import exceptions


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# CONSTANTS
DATE_FORMAT = "%Y-%m-%d"
DISPLAY_DATE_FORMAT = "%m/%y"
MONEY_FORMAT = "{0:.2f}"
CONFIG = {"Bucket": "rm-analyzer-config", "Key": "config.json"}


# HELPER FUNCTIONS
def format_money_helper(num):
    return MONEY_FORMAT.format(num)


def load_config(config=CONFIG):
    try:
        file_content = read_s3_file(config["Bucket"], config["Key"])
        return json.loads(file_content)
    except (exceptions.ClientError, json.JSONDecodeError) as e:
        logger.error(f"Error loading config: {str(e)}")
        raise


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


# CLASSES
class Category(Enum):
    DINING = "Dining & Drinks"
    GROCERIES = "Groceries"
    PETS = "Pets"
    BILLS = "Bills & Utilities"
    OTHER = "R & T Shared"


class Transaction:
    def __init__(self, date, name, account_number, amount, category, ignore):
        self.date = date
        self.name = name
        self.account_number = account_number
        self.amount = amount
        self.category = category
        self.ignore = ignore


class Person:
    def __init__(self, name, email, account_numbers, transactions=None):
        try:
            if not isinstance(name, str):
                raise TypeError(f"name should be a string, got {type(name).__name__}")
            if not isinstance(email, str):
                raise TypeError(f"email should be a string, got {type(email).__name__}")
            if not all(isinstance(num, int) for num in account_numbers):
                raise TypeError("account_numbers should be a list of integers")
            if transactions and not all(
                isinstance(t, Transaction) for t in transactions
            ):
                raise TypeError("transactions should be a list of Transaction objects")

            self.name = name
            self.email = email
            self.account_numbers = account_numbers
            self.transactions = transactions or []
        except TypeError as e:
            logger.error(f"Invalid person data: {str(e)}")
            raise

    def add_transaction(self, transaction):
        self.transactions.append(transaction)

    def calculate_expenses(self, category=None):
        if category:
            return sum(t.amount for t in self.transactions if t.category == category)
        return sum(t.amount for t in self.transactions)


class Summary:
    def __init__(self, date, config=None):
        if not config:
            config = load_config()
        self.date = date

        try:
            self.owner = config["Owner"]
        except (KeyError, TypeError):
            logger.error("Invalid or missing 'Owner' in configuration.")
            raise

        try:
            people_config = config["People"]
            self.people = self.initialize_people(people_config)
        except (KeyError, TypeError):
            logger.error("Invalid or missing 'People' in configuration.")
            raise

    def initialize_people(self, people_config):
        try:
            return [
                Person(
                    p["Name"],
                    p["Email"],
                    p["Accounts"],
                    [],
                )
                for p in people_config
            ]
        except (TypeError, KeyError) as e:
            logger.error(f"Invalid people configuration: {str(e)}")
            raise

    def add_transactions_from_spreadsheet(self, spreadsheet_content):
        parsed_transactions = SpreadsheetParser.parse(spreadsheet_content)
        self.add_transactions(parsed_transactions)

    def add_persons_transactions(self, parsed_transactions, person):
        for transaction in parsed_transactions:
            if (
                transaction.account_number in person.account_numbers
                and not transaction.ignore
                # Commenting out the following line will include transactions from previous months
                # and transaction.date.month == self.date.month
            ):
                person.add_transaction(transaction)

    def add_transactions(self, parsed_transactions):
        for person in self.people:
            self.add_persons_transactions(parsed_transactions, person)

    def calculate_2_person_difference(self, person1, person2, category=None):
        return person1.calculate_expenses(category) - person2.calculate_expenses(
            category
        )


class SpreadsheetSummary(Summary):
    def __init__(self, date, spreadsheet_content, config=None):
        super().__init__(date, config)
        super().add_transactions_from_spreadsheet(spreadsheet_content)


class SpreadsheetParser:
    @staticmethod
    def parse(file_content):
        results = []
        reader = csv.DictReader(file_content.splitlines())
        for row in reader:
            try:
                transaction_date = datetime.strptime(row["Date"], DATE_FORMAT).date()
                transaction_name = row["Name"]
                transaction_account_number = int(row["Account Number"])
                transaction_amount = float(row["Amount"])
                transaction_category = Category(row["Category"])
                transaction_ignore = bool(row["Ignored From"])

                transaction = Transaction(
                    transaction_date,
                    transaction_name,
                    transaction_account_number,
                    transaction_amount,
                    transaction_category,
                    transaction_ignore
                )
                results.append(transaction)
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid transaction data in row {row}: {str(e)}")
                continue
        return results


class EmailGenerator:
    @staticmethod
    def generate_summary_email(summary):
        html = """<html>
        <head>
            <style>
                table {
                    border-collapse: collapse;
                    width: 100%;
                }
                
                th, td {
                    border: 1px solid black;
                    padding: 8px 12px;  /* Add padding to table cells */
                    text-align: left;
                }

                th {
                    background-color: #f2f2f2;  /* A light background color for headers */
                }
            </style>
        </head>
        <body>"""

        html += "<table border='1'>\n<thead>\n<tr>\n<th></th>\n"
        for category in Category:
            html += f"<th>{category.value}</th>\n"
        html += "<th>Total</th>\n</tr>\n</thead>\n<tbody>\n"

        for person in summary.people:
            html += "<tr>\n"
            html += f"<td>{person.name}</td>\n"
            for category in Category:
                html += f"<td>{format_money_helper(person.calculate_expenses(category))}</td>\n"
            html += f"<td>{format_money_helper(person.calculate_expenses())}</td>\n"
            html += "</tr>\n"

        # Assuming there will always be exactly 2 people for the difference calculation
        if len(summary.people) == 2:
            person1, person2 = summary.people
            html += "<tr>\n"
            html += f"<td>Difference ({person1.name} - {person2.name})</td>\n"
            for category in Category:
                html += f"<td>{format_money_helper(summary.calculate_2_person_difference(person1, person2, category))}</td>\n"
            html += f"<td>{format_money_helper(summary.calculate_2_person_difference(person1, person2))}</td>\n"
            html += "</tr>\n"

        html += "</tbody>\n</table>\n</body>\n</html>"
        return (
            summary.owner,
            [p.email for p in summary.people],
            f"Monthly Summary - {summary.date.strftime(DISPLAY_DATE_FORMAT)}",
            html,
        )


# MAIN
def analyze_file(file_path):
    bucket, key = file_path.replace("s3://", "").split("/", 1)
    file_content = read_s3_file(bucket, key)
    summary = SpreadsheetSummary(date.today(), file_content)
    source, to_addresses, subject, html_body = EmailGenerator.generate_summary_email(
        summary
    )
    send_email(source, to_addresses, subject, html_body)


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    file_path = f"s3://{bucket}/{key}"
    analyze_file(file_path)


if __name__ == "__main__":
    pass
