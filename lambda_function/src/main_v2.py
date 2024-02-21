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
logger = logging.getLogger(__name__)


# Constants
DATE_FORMAT = "%Y-%m-%d"
DISPLAY_DATE_FORMAT = "%m/%d/%y"
MONEY_FORMAT = "{0:.2f}"
CONFIG_BUCKET, CONFIG_KEY = "rmanalyzer-config", "config.json"


# Functions
def read_s3_file(bucket: str, key: str) -> str:
    s3: S3Client = boto3.client("s3")
    try:
        response: GetObjectOutputTypeDef = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except exceptions.ClientError as ex:
        logger.error("Error reading S3 file: %s", ex)
        raise


def get_config_json(bucket: str, key: str) -> dict:
    config = read_s3_file(bucket, key)
    try:
        return json.loads(config)
    except json.JSONDecodeError as ex:
        logger.error("Error loading config: %s", ex)
        raise


def to_transaction(row: dict) -> Transaction | None:
    try:
        transaction_date: date = datetime.strptime(row["Date"], DATE_FORMAT).date()
        transaction_name: str = row["Name"]
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
    content = read_s3_file(bucket, key)
    # DictReader is essentially a list of dicts representing rows
    rows = csv.DictReader(content.splitlines())
    transactions: list[Transaction] = list()
    for row in rows:
        transaction = to_transaction(row)
        if transaction:
            transactions.append(transaction)
    return transactions


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

    def calculate_expenses(self, category: Category | None = None) -> float:
        if not self.transactions:
            return 0
        if not category:
            return sum(t.amount for t in self.transactions)
        return sum(t.amount for t in self.transactions if t.category == category)


class People:
    def __init__(self, people: list[Person]) -> None:
        self.people = people

    def add_transactions(self, transactions: list[Transaction]) -> None:
        for t in transactions:
            skipped = True
            for p in self.people:
                if (
                    t.account_number in p.account_numbers
                    and t.ignore == IgnoredFrom.NOTHING
                ):
                    p.add_transaction(t)
                    skipped = False

            if skipped:
                logger.warning("Skipped transaction: %s on %s", t.name, t.date)

    def get_oldest_transaction(self) -> date:
        return min(p.get_oldest_transaction() for p in self.people)

    def get_newest_transaction(self) -> date:
        return max(p.get_newest_transaction() for p in self.people)

    def calculate_expenses_difference(
        self, p1: Person, p2: Person, category: Category | None = None
    ) -> float:
        if not [p for p in [p1, p2] if p in self.people]:
            logger.error(
                "%s and %s are not both in the list of people", p1.name, p2.name
            )
            raise

        return p1.calculate_expenses(category) - p2.calculate_expenses(category)


class SummaryEmail:
    pass