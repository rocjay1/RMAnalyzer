"""
This script is used to generate a monthly summary of expenses from a spreadsheet.

Author: Rocco Davino
"""

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


logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


# CONSTANTS
DATE_FORMAT: str = "%Y-%m-%d"
DISPLAY_DATE_FORMAT: str = "%m/%d/%y"
MONEY_FORMAT: str = "{0:.2f}"
CONFIG_DICT: dict = {"bucket": "rmanalyzer-config", "key": "config.json"}


# HELPER FUNCTIONS
@typechecked
def format_money_helper(num: float) -> str:
    """
    Formats a given number as a string in the format specified by the MONEY_FORMAT constant.
    """
    return MONEY_FORMAT.format(num)


@typechecked
def load_config(config_dict: dict | None = None) -> dict:
    """
    Load configuration from a JSON file.
    """
    if config_dict is None:
        config_dict = CONFIG_DICT
    try:
        return json.loads(read_s3_file(config_dict["bucket"], config_dict["key"]))
    except json.JSONDecodeError as ex:
        logger.error("Error loading config: %s", ex)
        raise


def read_s3_file(bucket: str, key: str) -> str:
    """
    Reads a file from an S3 bucket.
    """
    s3: S3Client = boto3.client("s3")
    try:
        response: GetObjectOutputTypeDef = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except exceptions.ClientError as ex:
        logger.error("Error reading S3 file: %s", ex)
        raise


def send_email(
    source: str,
    to_addresses: list[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> SendEmailResponseTypeDef:
    """
    Sends an email using Amazon SES (Simple Email Service).
    """
    ses: SESClient = boto3.client("ses", region_name="us-east-1")
    if not text_body:
        text_body = html_body
    try:
        response: SendEmailResponseTypeDef = ses.send_email(
            Source=source,
            Destination={"ToAddresses": to_addresses},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": html_body}, "Text": {"Data": text_body}},
            },
        )
        return response
    except exceptions.ClientError as ex:
        logger.error("Error sending email: %s", ex)
        raise


@typechecked
def parse_date_from_filename(filename: str) -> date:
    """
    Parses a date string from a given filename using a regular expression.
    """
    # decode filename if URL encoded
    decoded_name: str = urllib.parse.unquote_plus(filename)

    date_regex: re.Pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
    search_results: re.Match[str] | None = date_regex.search(decoded_name)
    if search_results:
        return datetime.strptime(search_results.group(0), DATE_FORMAT).date()
    return date.today()


# CLASSES
class Category(Enum):
    """
    An enumeration of possible values for the `Category` column of the spreadsheet.
    """

    DINING = "Dining & Drinks"
    GROCERIES = "Groceries"
    PETS = "Pets"
    BILLS = "Bills & Utilities"
    PURCHASES = "Shared Purchases"
    SUBSCRIPTIONS = "Shared Subscriptions"
    TRAVEL = "Travel & Vacation"


class IgnoredFrom(Enum):
    """
    An enumeration of possible values for the `Ignored From` column of the spreadsheet.
    """

    BUDGET = "budget"
    EVERYTHING = "everything"
    NOTHING = str()


@typechecked
class Transaction:
    """
    Represents a financial transaction.
    """

    def __init__(
        self,
        transact_date: date,
        name: str,
        account_number: int,
        amount: float,
        category: Category,
        ignore: IgnoredFrom,
    ) -> None:
        self.date = transact_date
        self.name = name
        self.account_number = account_number
        self.amount = amount
        self.category = category
        self.ignore = ignore

    @staticmethod
    def from_row(row: dict) -> Transaction | None:
        """
        Creates a Transaction object from a row in a spreadsheet.
        """

        try:
            transaction_date: date = datetime.strptime(row["Date"], DATE_FORMAT).date()
            transaction_name: str = row["Name"]
            transaction_account_number: int = int(row["Account Number"])
            transaction_amount: float = float(row["Amount"])
            transaction_category: Category = Category(row["Category"])
            transaction_ignore: IgnoredFrom = IgnoredFrom(row["Ignored From"])

            return Transaction(
                transaction_date,
                transaction_name,
                transaction_account_number,
                transaction_amount,
                transaction_category,
                transaction_ignore,
            )
        except (ValueError, KeyError) as ex:
            logger.warning("Invalid transaction data in row %s: %s", row, ex)
            return None


@typechecked
class Person:
    """
    A class representing a person with a name, email, account numbers, and transactions.
    """

    def __init__(
        self,
        name: str,
        email: str,
        account_numbers: list[int],
        transactions: list[Transaction],
    ) -> None:
        self.name = name
        self.email = email
        self.account_numbers = account_numbers
        self.transactions = transactions

    def add_transaction(self, transaction: Transaction) -> None:
        """
        Adds a transaction to the list of transactions for this account.
        """
        self.transactions.append(transaction)

    def calculate_expenses(self, category: Category | None = None) -> float:
        """
        Calculates the total expenses for the given category or for all
        categories if no category is specified.
        """

        if not self.transactions:
            return 0
        if not category:
            return sum(t.amount for t in self.transactions)
        return sum(t.amount for t in self.transactions if t.category == category)


@typechecked
class Summary:
    """
    A class representing a summary of transaction data for a given date.
    """

    def __init__(self, summary_date: date, config: dict | None = None) -> None:
        if not config:
            config = load_config()

        try:
            owner: str = config["OwnerEmail"]
            people_config: list[dict] = config["People"]
        except KeyError:
            logger.error("Invalid or missing key in configuration.")
            raise

        self.date = summary_date
        self.start_date = date.max
        self.end_date = date.min
        self.owner = owner
        self.people = self.initialize_people(people_config)

    def initialize_people(self, people_config: list[dict]) -> list[Person]:
        """
        Initializes a list of Person objects based on the provided people configuration.
        """
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
        except KeyError as ex:
            logger.error("Invalid people configuration: %s", ex)
            raise

    def add_transactions_from_spreadsheet(self, spreadsheet_content: str) -> None:
        """
        Parses transaction data from a spreadsheet and adds it to the analyzer.
        """
        self.add_transactions(SpreadsheetParser.parse(spreadsheet_content))

    def add_persons_transactions(
        self, parsed_transactions: list[Transaction], person: Person
    ) -> None:
        """
        Adds a list of parsed transactions to a given person's account.
        """
        for transaction in parsed_transactions:
            if (
                transaction.account_number in person.account_numbers
                and transaction.ignore == IgnoredFrom.NOTHING
                # and transaction.date.month == self.date.month
            ):
                if transaction.date < self.start_date:
                    self.start_date = transaction.date
                if transaction.date > self.end_date:
                    self.end_date = transaction.date
                person.add_transaction(transaction)

    def add_transactions(self, parsed_transactions: list[Transaction]) -> None:
        """
        Adds parsed transactions to each person's transaction history.
        """
        for person in self.people:
            self.add_persons_transactions(parsed_transactions, person)

    def calculate_2_person_difference(
        self, person1: Person, person2: Person, category: Category | None = None
    ) -> float:
        """
        Calculates the difference in expenses between two people for a given category.
        """
        return person1.calculate_expenses(category) - person2.calculate_expenses(
            category
        )

    def generate_email_data(self) -> tuple[str, list[str], str, str]:
        """
        Generates email data for the monthly summary report.
        """
        doc_tuple: tuple[yattag.SimpleDoc, Any, Any] = (
            yattag.Doc().tagtext()
        )  # type gotten from yattag source
        doc, tag, text = doc_tuple
        doc.asis("<!DOCTYPE html>")
        with tag("html"):
            # HTML head
            with tag("head"):
                doc.asis(
                    "<style>table {border-collapse: collapse; width: 100%} \
                    th, td {border: 1px solid black; padding: 8px 12px; text-align: left;} \
                    th {background-color: #f2f2f2;}</style>"
                )
            # HTML body
            with tag("body"):
                # Body consists of a table
                with tag("table", border="1"):
                    # Table header
                    with tag("thead"):
                        with tag("tr"):
                            with tag("th"):
                                text("")
                            for category in Category:
                                with tag("th"):
                                    text(category.value)
                            with tag("th"):
                                text("Total")
                    # Table body
                    with tag("tbody"):
                        # Create a row for each person
                        for person in self.people:
                            with tag("tr"):
                                with tag("td"):
                                    text(person.name)
                                for category in Category:
                                    with tag("td"):
                                        text(
                                            format_money_helper(
                                                person.calculate_expenses(category)
                                            )
                                        )
                                with tag("td"):
                                    text(
                                        format_money_helper(person.calculate_expenses())
                                    )
                        # If there are only two people, create a row for the differences
                        if len(self.people) == 2:
                            person1, person2 = self.people
                            with tag("tr"):
                                with tag("td"):
                                    text("Difference")
                                for category in Category:
                                    with tag("td"):
                                        text(
                                            format_money_helper(
                                                self.calculate_2_person_difference(
                                                    person1, person2, category
                                                )
                                            )
                                        )
                                with tag("td"):
                                    text(
                                        format_money_helper(
                                            self.calculate_2_person_difference(
                                                person1, person2
                                            )
                                        )
                                    )
        return (
            self.owner,
            [p.email for p in self.people],
            f"Transactions Summary: {self.start_date.strftime(DISPLAY_DATE_FORMAT)} - {self.end_date.strftime(DISPLAY_DATE_FORMAT)}",
            doc.getvalue(),
        )


@typechecked
class SpreadsheetSummary(Summary):
    """
    A class representing a summary of transactions from a spreadsheet.
    """

    def __init__(
        self,
        summary_date: date,
        spreadsheet_content: str,
        config: dict | None = None,
    ) -> None:
        super().__init__(summary_date, config)
        super().add_transactions_from_spreadsheet(spreadsheet_content)


@typechecked
class SpreadsheetParser:
    """
    A class for parsing CSV files and returning a list of Transaction objects.
    """

    @staticmethod
    def parse(file_content: str) -> list[Transaction]:
        """
        Parses a CSV file and returns a list of Transaction objects.
        """
        results: list[Transaction] = []
        reader: csv.DictReader = csv.DictReader(file_content.splitlines())
        for row in reader:
            transaction: Transaction | None = Transaction.from_row(row)
            if transaction:
                results.append(transaction)
        return results


# MAIN
@typechecked
def analyze_s3_sheet(bucket: str, key: str) -> None:
    """
    Analyzes a file located at the given S3 file path, generates a summary of its contents,
    and sends an email with the summary to a list of recipients.
    """
    file_content: str = read_s3_file(bucket, key)
    summary_date: date = parse_date_from_filename(key)
    summary: SpreadsheetSummary = SpreadsheetSummary(summary_date, file_content)
    email_data: tuple[str, list[str], str, str] = summary.generate_email_data()
    source, to_addresses, subject, html_body = email_data
    send_email(source, to_addresses, subject, html_body)


@typechecked
def lambda_handler(event: Any, context: Any) -> None:
    """
    This function is the entry point for the AWS Lambda function. It is triggered by an S3 event
    and analyzes the file that triggered the event.
    """
    bucket: str = event["Records"][0]["s3"]["bucket"]["name"]
    key: str = event["Records"][0]["s3"]["object"]["key"]
    analyze_s3_sheet(bucket, key)


if __name__ == "__main__":
    pass
