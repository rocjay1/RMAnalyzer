# pylint: disable-all
# Description: RMAnalyzer AWS Lambda Function
# Author: Rocco Davino


from __future__ import annotations
import logging
from datetime import datetime, date
import csv
from enum import Enum
import json
from typing import Any
import boto3
from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.type_defs import GetObjectOutputTypeDef
from mypy_boto3_ses.client import SESClient
from botocore import exceptions
import yattag


# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Constants
DATE = "%Y-%m-%d"
DISPLAY_DATE = "%m/%d/%y"
MONEY_FORMAT = "{0:.2f}"
CONFIG_BUCKET, CONFIG_KEY = "rmanalyzer-config", "config.json"


# Functions
def get_s3_content(bucket: str, key: str) -> str:
    s3: S3Client = boto3.client("s3")
    try:
        response: GetObjectOutputTypeDef = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except exceptions.ClientError as ex:
        logger.error("Error reading S3 file: %s", ex)
        raise


def get_config(bucket: str, key: str) -> dict:
    config = get_s3_content(bucket, key)
    try:
        return json.loads(config)
    except json.JSONDecodeError as ex:
        logger.error("Error loading config: %s", ex)
        raise


def validate_config(config: dict) -> None:
    # So far, only checks for non-empty dict values
    try:
        people: list[dict] = config["People"]
        for p in people:
            if not (p["Name"] and p["Email"] and p["Accounts"]):
                raise ValueError("Invalid people values")
        owner: str = config["Owner"]
        if not owner:
            raise ValueError("Invalid owner value")
    except (KeyError, ValueError) as ex:
        logger.error("Invalid configuration: %s", ex)
        raise


def to_transaction(row: dict) -> Transaction | None:
    try:
        transaction_date = datetime.strptime(row["Date"], DATE).date()
        transaction_name = row["Name"]
        transaction_account_number = int(row["Account Number"])
        transaction_amount = float(row["Amount"])
        transaction_category = Category(row["Category"])
        transaction_ignore = IgnoredFrom(row["Ignored From"])
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


def get_transactions(bucket: str, key: str) -> list[Transaction]:
    content = get_s3_content(bucket, key)
    rows = csv.DictReader(content.splitlines())
    transactions = list()
    for row in rows:
        transaction = to_transaction(row)
        if transaction:
            transactions.append(transaction)
    return transactions


def to_currency(num: float) -> str:
    return MONEY_FORMAT.format(num)


def get_members(people_config: list[dict]) -> list[Person]:
    return [
        Person(
            p["Name"],
            p["Email"],
            p["Accounts"],
            list(),
        )
        for p in people_config
    ]


# Classes
class Category(Enum):
    DINING = "Dining & Drinks"
    GROCERIES = "Groceries"
    PETS = "Pets"
    BILLS = "Bills & Utilities"
    PURCHASES = "Shared Purchases"
    SUBSCRIPTIONS = "Shared Subscriptions"
    TRAVEL = "Travel & Vacation"


class IgnoredFrom(Enum):
    BUDGET = "budget"
    EVERYTHING = "everything"
    NOTHING = str()


class Transaction:
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


class Person:
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
        self.transactions.append(transaction)

    def get_oldest_transaction(self) -> date:
        return min(t.date for t in self.transactions)

    def get_newest_transaction(self) -> date:
        return max(t.date for t in self.transactions)

    def get_expenses(self, category: Category | None = None) -> float:
        if not self.transactions:
            return 0
        if not category:
            return sum(t.amount for t in self.transactions)
        return sum(t.amount for t in self.transactions if t.category == category)


class Group:
    def __init__(self, members: list[Person]) -> None:
        self.members = members

    def add_transactions(self, transactions: list[Transaction]) -> None:
        for t in transactions:
            for p in self.members:
                if (
                    t.account_number in p.account_numbers
                    and t.ignore == IgnoredFrom.NOTHING
                ):
                    p.add_transaction(t)

    def get_oldest_transaction(self) -> date:
        return min(p.get_oldest_transaction() for p in self.members)

    def get_newest_transaction(self) -> date:
        return max(p.get_newest_transaction() for p in self.members)

    def get_expenses_difference(
        self, p1: Person, p2: Person, category: Category | None = None
    ) -> float:
        try:
            missing = [p for p in [p1, p2] if p not in self.members]
            if missing:
                raise ValueError("People args missing from group")
            return p1.get_expenses(category) - p2.get_expenses(category)
        except ValueError as ex:
            logger.error("Invalid input (%s, %s): %s", p1.name, p2.name, ex)
            raise


class SummaryEmail:
    def __init__(self, sender: str, to: list[str]) -> None:
        self.sender = sender
        self.to = to
        self.subject = str()
        self.body = str()

    def add_body(self, group: Group) -> None:
        doc, tag, text = yattag.Doc().tagtext()
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
                # Table
                with tag("table", border="1"):
                    # Table header
                    with tag("thead"):
                        with tag("tr"):
                            with tag("th"):
                                text("")
                            for c in Category:
                                with tag("th"):
                                    text(c.value)
                            with tag("th"):
                                text("Total")
                    # Table body
                    with tag("tbody"):
                        # Create a row for each person
                        for p in group.members:
                            with tag("tr"):
                                with tag("td"):
                                    text(p.name)
                                for c in Category:
                                    with tag("td"):
                                        text(to_currency(p.get_expenses(c)))
                                with tag("td"):
                                    text(to_currency(p.get_expenses()))
                        # If there are only two people, create a row for the differences
                        if len(group.members) == 2:
                            p1, p2 = group.members
                            with tag("tr"):
                                with tag("td"):
                                    text("Difference")
                                for c in Category:
                                    with tag("td"):
                                        text(
                                            to_currency(
                                                group.get_expenses_difference(p1, p2, c)
                                            )
                                        )
                                with tag("td"):
                                    text(
                                        to_currency(
                                            group.get_expenses_difference(p1, p2)
                                        )
                                    )
        self.body = doc.getvalue()

    def add_subject(self, group: Group) -> None:
        min_date = group.get_oldest_transaction()
        max_date = group.get_newest_transaction()
        self.subject = f"Transactions Summary: {min_date.strftime(DISPLAY_DATE)} - {max_date.strftime(DISPLAY_DATE)}"

    def send(self) -> None:
        ses: SESClient = boto3.client("ses", region_name="us-east-1")
        try:
            ses.send_email(
                Source=self.sender,
                Destination={"ToAddresses": self.to},
                Message={
                    "Subject": {"Data": self.subject},
                    "Body": {"Html": {"Data": self.body}, "Text": {"Data": self.body}},
                },
            )
        except exceptions.ClientError as ex:
            logger.error("Error sending email: %s", ex)
            raise


# Main
def lambda_handler(event: Any, context: Any) -> None:
    bucket: str = event["Records"][0]["s3"]["bucket"]["name"]
    key: str = event["Records"][0]["s3"]["object"]["key"]

    # Read data from buckets
    config = get_config(CONFIG_BUCKET, CONFIG_KEY)
    validate_config(config)
    transactions = get_transactions(bucket, key)

    # Construct group and add transactions
    members = get_members(config["People"])
    group = Group(members)
    group.add_transactions(transactions)

    # Construct and send email
    email = SummaryEmail(config["Owner"], [p.email for p in group.members])
    email.add_body(group)
    email.add_subject(group)
    email.send()
