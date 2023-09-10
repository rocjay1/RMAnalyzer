import csv
from datetime import datetime
from datetime import date
from enum import Enum


class Category(Enum):
    DINING = "Dining & Drinks"
    GROCERIES = "Groceries"
    ENTERTAINMENT = "Entertainment & Rec."


class Transaction:
    def __init__(
        self,
        date: date,
        name: str,
        account_number: int,
        amount: float,
        category: Category,
    ):
        self.date = date
        self.name = name
        self.account_number = account_number
        self.amount = amount
        self.category = category


class Person:
    def __init__(self, name, account_numbers):
        self.name = name
        self.account_numbers = account_numbers
        self.transactions: list[Transaction] = []

    def add_transaction(self, transaction):
        self.transactions.append(transaction)

    def calculate_expenses(self, category: Category = None):
        if category:
            return sum([t.amount for t in self.transactions if t.category == category])
        return sum([t.amount for t in self.transactions])


class MonthlySummary:
    def __init__(self, people: list[Person], date: date):
        self.people = people
        self.date = date

    def add_persons_transactions(
        self, parsed_transactions: list[Transaction], person: Person
    ):
        for transaction in parsed_transactions:
            if (
                transaction.account_number in person.account_numbers
                and transaction.date.month == self.date.month
            ):
                person.add_transaction(transaction)

    def add_all_transactions(self, parsed_transactions: list[Transaction]):
        for person in self.people:
            self.add_persons_transactions(parsed_transactions, person)


class SpreadsheetParser:
    @staticmethod
    def parse(filepath):
        results = []
        with open(filepath, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                transaction = Transaction(
                    date=datetime.strptime(row["Date"], "%Y-%m-%d").date(),
                    name=str(row["Name"]),
                    account_number=int(row["Account Number"]),
                    amount=float(row["Amount"]),
                    category=Category(row["Category"]),
                )
                results.append(transaction)
        return results


class EmailGenerator:
    @staticmethod
    def generate_summary_email(summary: MonthlySummary):
        html = """\
    <html>
        <head></head>
        <body>
    """

        display_date = summary.date.strftime("%m/%y")
        html += f"    <h1>Summary for {display_date}:</h1>\n"

        html += "        <table border='1'>\n"
        html += "            <thead>\n                <tr>\n"
        for category in Category:
            html += f"                    <th>{category.value}</th>\n"
        html += "                    <th>Total</th>\n"
        html += "                </tr>\n            </thead>\n"

        html += "            <tbody>\n"
        for person in summary.people:
            html += "                <tr>\n"
            html += f"                    <td>{person.name}</td>\n"
            for category in Category:
                html += f"                    <td>{person.calculate_expenses(category)}</td>\n"
            html += f"                    <td>{person.calculate_expenses()}</td>\n"
            html += "                </tr>\n"
        html += "            </tbody>\n        </table>\n"

        html += """\
        </body>
    </html>
    """
        return html
