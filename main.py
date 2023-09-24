"""
This script is used to generate a monthly summary of expenses from a spreadsheet.
It is meant to be run as an AWS Lambda function triggered by an S3 event.
The spreadsheet should be an export from Rocket Money.
The configuration file should be stored in an S3 bucket.
The Lambda function should have access to the S3 bucket and SES.

The script defines several helper functions for loading configuration files from S3,
reading files from S3, and sending emails using Amazon SES. It also defines two classes:
Category and Transaction.

Category is an enumeration representing the different categories of expenses, and
Transaction is a class representing a single transaction, with attributes for the date,
name, account number, amount, category, and whether or not to ignore the transaction.

The script also defines a Person class, with attributes for the person's name, email,
account numbers, and a list of transactions (if available).

Author: Rocco Davino
"""


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
    """
    Formats a given number as a string in the format specified by the MONEY_FORMAT constant.

    Args:
        num (float): The number to format.

    Returns:
        str: The formatted string.
    """
    return MONEY_FORMAT.format(num)


def load_config(config=None):
    """
    Loads the configuration file from an S3 bucket and returns it as a dictionary.

    Args:
        config (dict): A dictionary containing the S3 bucket and key where the
        configuration file is stored.

    Returns:
        dict: A dictionary containing the configuration settings.

    Raises:
        ClientError: If there is an error accessing the S3 bucket.
        JSONDecodeError: If there is an error decoding the JSON configuration file.
    """
    if config is None:
        config = CONFIG
    try:
        file_content = read_s3_file(config["Bucket"], config["Key"])
        return json.loads(file_content)
    except (exceptions.ClientError, json.JSONDecodeError) as ex:
        logger.error("Error loading config: %s", ex)
        raise


def read_s3_file(bucket, key):
    """
    Reads a file from an S3 bucket.

    Args:
        bucket (str): The name of the S3 bucket.
        key (str): The key of the file to read.

    Returns:
        str: The contents of the file as a string.

    Raises:
        botocore.exceptions.ClientError: If there was an error reading the file.
    """
    s3 = boto3.client("s3")
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except exceptions.ClientError as ex:
        logger.error("Error reading S3 file: %s", ex)
        raise


def send_email(source, to_addresses, subject, html_body, text_body=None):
    """
    Sends an email using Amazon SES (Simple Email Service).

    :param source: The email address that the email will be sent from.
    :param to_addresses: A list of email addresses that the email will be sent to.
    :param subject: The subject line of the email.
    :param html_body: The HTML body of the email.
    :param text_body: The plain text body of the email. If not provided,
        the HTML body will be used as the text body.
    :return: The response from the SES service.
    :raises: botocore.exceptions.ClientError: If there was an error sending the email.
    """
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
    except exceptions.ClientError as ex:
        logger.error("Error sending email: %s", ex)
        raise


# CLASSES
class Category(Enum):
    """
    A class representing the different categories of expenses.

    Attributes
    ----------
    DINING : str
        The category for dining and drinks expenses.
    GROCERIES : str
        The category for groceries expenses.
    PETS : str
        The category for pets expenses.
    BILLS : str
        The category for bills and utilities expenses.
    OTHER : str
        The category for other shared expenses.
    """

    DINING = "Dining & Drinks"
    GROCERIES = "Groceries"
    PETS = "Pets"
    BILLS = "Bills & Utilities"
    OTHER = "R & T Shared"


class NotIgnoredFrom(Enum):
    """
    An enumeration representing the different types of objects that should not be ignored 
    by the RMAnalyzer.

    Attributes:
        NOT_IGNORED (str): A string representing the type of object that should not be ignored.
    """
    NOT_IGNORED = str()


class Transaction:
    """
    Represents a financial transaction.

    Attributes:
        date (datetime.date): The date of the transaction.
        name (str): The name of the transaction.
        account_number (int): The account number associated with the transaction.
        amount (float): The amount of the transaction.
        category (Category): The category of the transaction.
        ignore (NotIgnoredFrom): The source of the transaction.
    """

    def __init__(self, transact_date, name, account_number, amount, category, ignore):
        # Make sure the date is a datetime.date object
        if not isinstance(transact_date, date):
            raise TypeError("date should be a datetime.date object")
        # Make sure the name is a string
        if not isinstance(name, str):
            raise TypeError("name should be a string")
        # Make sure the account number is an integer
        if not isinstance(account_number, int):
            raise TypeError("account_number should be an integer")
        # Make sure the amount is a float
        if not isinstance(amount, float):
            raise TypeError("amount should be a float")
        # Make sure the category is a Category object
        if not isinstance(category, Category):
            raise TypeError("category should be a Category object")
        # Make sure the ignore is a NotIgnoredFrom object
        if not isinstance(ignore, NotIgnoredFrom):
            raise TypeError("ignore should be a NotIgnoredFrom object")

        self.date = transact_date
        self.name = name
        self.account_number = account_number
        self.amount = amount
        self.category = category
        self.ignore = ignore

    @staticmethod
    def from_row(row):
        """
        Creates a Transaction object from a row in a spreadsheet.

        Args:
            row (dict): A dictionary representing a row in a spreadsheet.

        Returns:
            Transaction: A Transaction object created from the given row.
        """
        try:
            transaction_date = datetime.strptime(row["Date"], DATE_FORMAT).date()
            transaction_name = row["Name"]
            transaction_account_number = int(row["Account Number"])
            transaction_amount = float(row["Amount"])
            transaction_category = Category(row["Category"])
            transaction_ignore = NotIgnoredFrom(row["Ignored From"])

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


class Person:
    """
    A class representing a person with a name, email, account numbers, and transactions.

    Attributes:
        name (str): The name of the person.
        email (str): The email address of the person.
        account_numbers (List[int]): A list of account numbers associated with the person.
        transactions (List[Transaction]): A list of Transaction objects representing the person's 
            transactions.
    """

    def __init__(self, name, email, account_numbers, transactions=None):
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

    def add_transaction(self, transaction):
        """
        Adds a transaction to the list of transactions for this account.

        Args:
            transaction (Transaction): The transaction to add.
        """
        self.transactions.append(transaction)

    def calculate_expenses(self, category=None):
        """
        Calculates the total expenses for the given category or for all 
        categories if no category is specified.

        Args:
            category (str, optional): The category for which to calculate expenses. 
                Defaults to None.

        Returns:
            float: The total expenses for the given category or for all categories 
                if no category is specified.
        """
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
            transaction = Transaction.from_row(row)
            if transaction:
                results.append(transaction)
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
