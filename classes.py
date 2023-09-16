import csv
from datetime import datetime
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)

# constants
DATE_FORMAT = "%Y-%m-%d"
MONEY_FORMAT = "{0:.2f}"


# helpers
def money_format_helper(num):
    return MONEY_FORMAT.format(num)


def load_config_helper(config_file="config.json"):
    """Load configuration from a JSON file."""
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(str(e))
        raise


# core classes
class Category(Enum):
    DINING = "Dining & Drinks"
    GROCERIES = "Groceries"
    ENTERTAINMENT = "Entertainment & Rec."


class Transaction:
    def __init__(self, date, name, account_number, amount, category):
        self.date = date
        self.name = name
        self.account_number = account_number
        self.amount = amount
        self.category = category


class Person:
    def __init__(self, name, email, account_numbers, transactions=None):
        try:
            if not isinstance(name, str):
                raise TypeError(f"name should be a string, got {type(name).__name__}")
            if not isinstance(email, str):
                raise TypeError(f"email should be a string, got {type(email).__name__}")
            if not all(isinstance(num, int) for num in account_numbers):
                raise TypeError("account_numbers should be a list of integers")
            if transactions and not all(isinstance(t, Transaction) for t in transactions):
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
            config = load_config_helper()
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
                and transaction.date.month == self.date.month
            ):
                person.add_transaction(transaction)

    def add_transactions(self, parsed_transactions):
        for person in self.people:
            self.add_persons_transactions(parsed_transactions, person)

    def calculate_2_person_difference(self, person1, person2, category=None):
        return person1.calculate_expenses(category) - person2.calculate_expenses(category)


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

                transaction = Transaction(
                    transaction_date,
                    transaction_name,
                    transaction_account_number,
                    transaction_amount,
                    transaction_category,
                )
                results.append(transaction)
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid transaction data in row {row}: {str(e)}")
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
                html += f"<td>{money_format_helper(person.calculate_expenses(category))}</td>\n"
            html += f"<td>{money_format_helper(person.calculate_expenses())}</td>\n"
            html += "</tr>\n"

        # Assuming there will always be exactly 2 people for the difference calculation
        if len(summary.people) == 2:
            person1, person2 = summary.people
            html += "<tr>\n"
            html += f"<td>Difference ({person1.name} - {person2.name})</td>\n"
            for category in Category:
                html += f"<td>{money_format_helper(summary.calculate_2_person_difference(person1, person2, category))}</td>\n"
            html += f"<td>{money_format_helper(summary.calculate_2_person_difference(person1, person2))}</td>\n"
            html += "</tr>\n"

        html += "</tbody>\n</table>\n</body>\n</html>"
        return (
            summary.owner,
            [p.email for p in summary.people],
            f"Monthly Summary for {summary.date.strftime(DATE_FORMAT)}",
            html,
        )
