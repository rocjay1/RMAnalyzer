import csv


class Transaction:
    def __init__(self, date, name, account_number, amount, category):
        self.date = date
        self.name = name
        self.account_number = account_number
        self.amount = amount
        self.category = category


class Person:

    def __init__(self, name, account_numbers):
        self.name = name
        self.account_numbers = account_numbers
        self.transactions = []

    def add_transaction(self, transaction):
        self.transactions.append(transaction)

    def total_spent(self, category=None):
        if category:
            return sum([t.amount for t in self.transactions if t.category == category])
        return sum([t.amount for t in self.transactions])


class SpreadsheetParser:
    def __init__(self, filepath, people):
        self.filepath = filepath
        self.people = people

    def parse(self):
        with open(self.filepath, 'r') as file:
            reader = csv.DictReader(file)

            for row in reader:
                transaction = Transaction(
                    date=row['Date'],
                    name=row['Name'],
                    account_number=int(row['Account Number']),
                    amount=float(row['Amount']),
                    category=row['Category']
                )

                for person in self.people:
                    if transaction.account_number in person.account_numbers:
                        person.add_transaction(transaction)


# class EmailGenerator:
#     @staticmethod
#     def generate_summary_email(person):
#         email_body = f"Summary for {person.name}:\n\n"
#         categories = {t.category for t in person.transactions}
#         for category in categories:
#             email_body += f"Amount spent on {category}: {person.total_spent(category)}\n"
#         return email_body
