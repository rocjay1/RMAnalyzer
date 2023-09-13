import csv
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


DATE_FORMAT = "%Y-%m-%d"


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
        self.name = name
        self.email = email
        self.account_numbers = account_numbers
        self.transactions = transactions or []

    def add_transaction(self, transaction):
        self.transactions.append(transaction)

    def calculate_expenses(self, category=None):
        if category:
            return round(
                sum(t.amount for t in self.transactions if t.category == category), 2
            )
        return round(sum(t.amount for t in self.transactions), 2)


class MonthlySummary:
    def __init__(self, people, current_date, owner):
        self.people = people
        self.date = current_date
        self.owner = owner

    def add_persons_transactions(self, parsed_transactions, person):
        for transaction in parsed_transactions:
            if (
                transaction.account_number in person.account_numbers
                and transaction.date.month == self.date.month
            ):
                person.add_transaction(transaction)

    def add_all_transactions(self, parsed_transactions):
        for person in self.people:
            self.add_persons_transactions(parsed_transactions, person)

    def calculate_difference(self, person1, person2, category=None):
        return person1.calculate_expenses(category) - person2.calculate_expenses(
            category
        )


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
        html = """<html><head></head><body>"""
        display_date = summary.date.strftime("%m/%y")
        html += (
            f"<h1>Summary for {display_date}:</h1>\n<table border='1'>\n<thead>\n<tr>\n"
        )
        for category in Category:
            html += f"<th>{category.value}</th>\n"
        html += "<th><strong>Total</strong></th>\n</tr>\n</thead>\n<tbody>\n"
        for person in summary.people:
            html += "<tr>\n"
            html += f"<td>{person.name}</td>\n"
            for category in Category:
                html += f"<td>{person.calculate_expenses(category)}</td>\n"
            html += f"<td>{person.calculate_expenses()}</td>\n"
            html += "</tr>\n"
        # Assuming there will always be exactly 2 people for the difference calculation
        if len(summary.people) == 2:
            person1, person2 = summary.people
            html += "<tr>\n"
            html += f"<td>Diff ({person1.name} - {person2.name})</td>\n"
            for category in Category:
                html += f"<td>{summary.calculate_difference(person1, person2, category)}</td>\n"
            html += f"<td>{summary.calculate_difference(person1, person2)}</td>\n"
            html += "</tr>\n"
        html += "</tbody>\n</table>\n</body>\n</html>"
        return (
            summary.owner,
            [p.email for p in summary.people],
            f"Monthly Summary for {display_date}",
            html
        )
