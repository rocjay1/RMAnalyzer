import csv
import json


class Transaction:
    def __init__(self, date, name, account_number, amount, category):
        self.date = date
        self.name = name
        self.account_number = account_number
        self.amount = amount
        self.category = category


class Member:
    def __init__(self, name, account_numbers):
        self.name = name
        self.account_numbers = account_numbers
        self.transactions: list[Transaction] = []

    def add_transaction(self, transaction):
        self.transactions.append(transaction)

    def calculate_expenses(self, category=None):
        if category:
            return sum([t.amount for t in self.transactions if t.category == category])
        return sum([t.amount for t in self.transactions])
    

class MemberSummary:
    def __init__(self):
        self.members: list[Member] = []
    
    def open(self, config_file="config.json"):
        config, error = ()
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            error = "Configuration file not found."
        except json.JSONDecodeError:
            error = "Failed to decode JSON from configuration file."

        if config != None:
            for member in config['Members']:
                name = member['Name'][0]
                account_numbers = member['Accounts']
                self.members.append(Member(name, account_numbers))
            return
        print(error)

    def add_transactions(self, parsed_transactions: list[Transaction]):
        for transaction in parsed_transactions:
            for member in self.members:
                if transaction.account_number in member.account_numbers:
                    member.add_transaction(transaction)

        
class SpreadsheetParser:
    def parse(self, filepath):
        results = []
        with open(filepath, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                transaction = Transaction(
                    date=row['Date'],
                    name=row['Name'],
                    account_number=int(row['Account Number']),
                    amount=float(row['Amount']),
                    category=row['Category']
                )
                results.append(transaction)
        return results

                
# class EmailGenerator:
#     @staticmethod
#     def generate_summary_email(person):
#         email_body = f"Summary for {person.name}:\n\n"
#         categories = {t.category for t in person.transactions}
#         for category in categories:
#             email_body += f"Amount spent on {category}: {person.total_spent(category)}\n"
#         return email_body
