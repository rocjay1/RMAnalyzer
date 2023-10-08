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
import re
import boto3
from botocore import exceptions


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# CONSTANTS
DATE_FORMAT = "%Y-%m-%d"
DISPLAY_DATE_FORMAT = "%m/%d/%y"
MONEY_FORMAT = "{0:.2f}"
CONFIG_PATH = "config\\config.json"


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


def load_config(config_path=None):
    """
    Load configuration from a JSON file.

    :param config: Path to the JSON configuration file. If None, the default CONFIG_PATH will be used.
    :type config: str or None
    :return: A dictionary containing the configuration data.
    :rtype: dict
    :raises FileNotFoundError: If the specified configuration file does not exist.
    :raises json.JSONDecodeError: If the specified configuration file is not a valid JSON file.
    """
    if config_path is None:
        config_path = CONFIG_PATH
    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError) as ex:
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


# Parse the date from the filename
def parse_date_from_filename(filename):
    """
    Parses a date string from a given filename using a regular expression.

    Args:
        filename (str): The name of the file to parse the date from.

    Returns:
        datetime.date: The date parsed from the filename.

    Raises:
        AttributeError: If the regular expression fails to match the filename.
    """
    date_regex = re.compile(r"\d{4}-\d{2}-\d{2}")
    try:
        return datetime.strptime(
            date_regex.search(filename).group(0), "%Y-%m-%d"
        ).date()
    except AttributeError as ex:
        logger.error("Error parsing date from filename: %s", ex)
        raise


def build_category_enum(config=None):
    """
    Builds an enumeration representing the different categories of expenses.
    """
    if config is None:
        config = load_config()
    try:
        categories = config["Categories"]
        if not isinstance(categories, dict):
            raise TypeError("Categories should be a dictionary")
        # If the categories dict values are not strings raise a TypeError
        if not all(isinstance(v, str) for v in categories.values()):
            raise TypeError("Categories should be a dictionary of strings")
        return Enum("Category", config["Categories"])
    except (KeyError, TypeError):
        logger.error("Invalid or missing 'Categories' in configuration.")
        raise


# CLASSES
Category = build_category_enum()


class NotIgnoredFrom(Enum):
    """
    An enumeration representing the different types of objects that should not be ignored
    by the RMAnalyzer.

    Attributes:
        NOT_IGNORED (str): A string representing the type of object that should not be ignored.
    """

    # Rows with an empty string in the Ignored From column should not be ignored
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
        try:
            if not isinstance(transact_date, date):
                raise TypeError(
                    f"date should be a datetime.date object, got {type(transact_date).__name__}"
                )
            if not isinstance(name, str):
                raise TypeError(f"name should be a string, got {type(name).__name__}")
            if not isinstance(account_number, int):
                raise TypeError(
                    f"account_number should be an integer, got {type(account_number).__name__}"
                )
            if not isinstance(amount, float):
                raise TypeError(
                    f"amount should be a float, got {type(amount).__name__}"
                )
            if not isinstance(category, Category):
                raise TypeError(
                    f"category should be a Category object, got {type(category).__name__}"
                )
            if not isinstance(ignore, NotIgnoredFrom):
                raise TypeError(
                    f"ignore should be a NotIgnoredFrom object, got {type(ignore).__name__}"
                )

            self.date = transact_date
            self.name = name
            self.account_number = account_number
            self.amount = amount
            self.category = category
            self.ignore = ignore
        except TypeError as ex:
            logger.error("Invalid transaction data: %s", ex)
            raise

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
        except TypeError as ex:
            logger.error("Invalid person data: %s", ex)
            raise

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
    """
    A class representing a summary of transaction data for a given date.

    Attributes:
        date (datetime.date): The date of the summary.
        owner (str): The owner of the transaction data.
        people (list): A list of `Person` objects representing the people involved
            in the transactions.

    Methods:
        __init__(self, summary_date, config=None): Initializes a new `Summary` object.
        initialize_people(self, people_config): Initializes a list of `Person` objects based on the
            provided people configuration.
        add_transactions_from_spreadsheet(self, spreadsheet_content): Parses transaction data from a
            spreadsheet and adds it to the analyzer.
        add_persons_transactions(self, parsed_transactions, person): Adds a list of parsed
            transactions to a given person's account.
        add_transactions(self, parsed_transactions): Adds parsed transactions to each person's
            transaction history.
        calculate_2_person_difference(self, person1, person2, category=None): Calculates the
            difference in expenses between two people for a given category.
    """

    def __init__(self, summary_date, config=None):
        if not config:
            config = load_config()
        self.date = summary_date

        try:
            self.owner = config["OwnerEmail"]
        except (KeyError, TypeError):
            logger.error("Invalid or missing 'OwnerEmail' in configuration.")
            raise

        try:
            people_config = config["People"]
        except (KeyError, TypeError):
            logger.error("Invalid or missing 'People' in configuration.")
            raise
        self.people = self.initialize_people(people_config)

    def initialize_people(self, people_config):
        """
        Initializes a list of Person objects based on the provided people configuration.

        Args:
            people_config (list): A list of dictionaries containing the configuration
                for each person.

        Returns:
            list: A list of Person objects initialized with the provided configuration.

        Raises:
            TypeError: If the provided people configuration is not a list.
            KeyError: If the provided people configuration is missing a required key.
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
        except (TypeError, KeyError) as ex:
            logger.error("Invalid people configuration: %s", ex)
            raise

    def add_transactions_from_spreadsheet(self, spreadsheet_content):
        """
        Parses transaction data from a spreadsheet and adds it to the analyzer.

        Args:
            spreadsheet_content (str): The contents of the spreadsheet to parse.

        Returns:
            None
        """
        parsed_transactions = SpreadsheetParser.parse(spreadsheet_content)
        self.add_transactions(parsed_transactions)

    def add_persons_transactions(self, parsed_transactions, person):
        """
        Adds a list of parsed transactions to a given person's account.

        :param parsed_transactions: A list of `Transaction` objects to add to the person's account.
        :type parsed_transactions: list[Transaction]
        :param person: The `Person` object to add the transactions to.
        :type person: Person
        """
        for transaction in parsed_transactions:
            if (
                transaction.account_number
                in person.account_numbers
                # Commenting out the following line will include transactions from previous months
                # and transaction.date.month == self.date.month
            ):
                person.add_transaction(transaction)

    def add_transactions(self, parsed_transactions):
        """
        Adds parsed transactions to each person's transaction history.

        :param parsed_transactions: A list of dictionaries containing parsed transaction data.
        """
        for person in self.people:
            self.add_persons_transactions(parsed_transactions, person)

    def calculate_2_person_difference(self, person1, person2, category=None):
        """
        Calculates the difference in expenses between two people for a given category.

        Args:
            person1 (Person): The first person to compare.
            person2 (Person): The second person to compare.
            category (str, optional): The category of expenses to compare.
                If None, all expenses are compared.

        Returns:
            float: The difference in expenses between person1 and person2 for the given category.
        """
        return person1.calculate_expenses(category) - person2.calculate_expenses(
            category
        )


class SpreadsheetSummary(Summary):
    """
    A class representing a summary of transactions from a spreadsheet.

    Attributes:
        date (datetime): The date of the summary.
        spreadsheet_content (list): A list of dictionaries representing the spreadsheet content.
        config (dict, optional): A dictionary of configuration options.

    Methods:
        __init__(self, date, spreadsheet_content, config=None): Initializes a new instance of the
            SpreadsheetSummary class.
    """

    def __init__(self, summary_date, spreadsheet_content, config=None):
        super().__init__(summary_date, config)
        super().add_transactions_from_spreadsheet(spreadsheet_content)


class SpreadsheetParser:
    """
    A class for parsing CSV files and returning a list of Transaction objects.
    """

    @staticmethod
    def parse(file_content):
        """
        Parses a CSV file and returns a list of Transaction objects.

        Args:
            file_content (str): The contents of the CSV file as a string.

        Returns:
            list: A list of Transaction objects parsed from the CSV file.
        """
        results = []
        reader = csv.DictReader(file_content.splitlines())
        for row in reader:
            transaction = Transaction.from_row(row)
            if transaction:
                results.append(transaction)
        return results


class EmailGenerator:
    """
    A class for generating HTML emails containing a summary of expenses for each person in a given
    summary object.
    """

    @staticmethod
    def generate_summary_email(summary):
        """
        Generates an HTML email containing a summary of expenses for each person in the given
        summary object.

        Args:
            summary (Summary): The summary object containing the data to be included in the email.

        Returns:
            Tuple[str, List[str], str, str]: A tuple containing the email sender, recipients,
            subject, and HTML body.
        """
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
    """
    Analyzes a file located at the given S3 file path, generates a summary of its contents,
    and sends an email with the summary to a list of recipients.

    Args:
        file_path (str): The S3 file path of the file to be analyzed.

    Returns:
        None
    """
    bucket, key = file_path.replace("s3://", "").split("/", 1)
    file_content = read_s3_file(bucket, key)
    summary_date = parse_date_from_filename(key)
    summary = SpreadsheetSummary(summary_date, file_content)
    source, to_addresses, subject, html_body = EmailGenerator.generate_summary_email(
        summary
    )
    send_email(source, to_addresses, subject, html_body)


def lambda_handler(event, context):
    """
    This function is the entry point for the AWS Lambda function. It is triggered by an S3 event
    and analyzes the file that triggered the event.

    :param event: The S3 event that triggered the Lambda function.
    :type event: dict
    :param context: The context object for the Lambda function.
    :type context: object
    """
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    file_path = f"s3://{bucket}/{key}"
    analyze_file(file_path)


if __name__ == "__main__":
    pass
