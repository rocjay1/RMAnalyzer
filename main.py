from classes import SpreadsheetParser, MonthlySummary, Person, EmailGenerator
import json
import logging
import sys
from datetime import date

# Initialize logging
logging.basicConfig(level=logging.INFO)


def load_config(config_file="config.json"):
    """Load configuration from a JSON file."""
    try:
        with open(config_file, "r") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "Configuration file not found."
    except json.JSONDecodeError:
        return None, "Failed to decode JSON from configuration file."

# <function to send email>

def main():
    config, error_msg = load_config()
    if config is None:
        logging.error(f"{error_msg}. Exiting.")
        sys.exit(1)

    people = []
    for person in config["People"]:
        name = person["Name"][0]
        accounts = person["Accounts"]
        transactions = []
        people.append(Person(name, accounts, transactions))

    summary = MonthlySummary(
        people, date.today()
    )  # pass in date to the script? In case analyzing last month
    parsed_transactions = SpreadsheetParser.parse(
        "test_transactions.csv"
    )  # CSV will likely be script arg as well
    summary.add_all_transactions(parsed_transactions)

    email_content = EmailGenerator.generate_summary_email(summary)
    print(email_content)


if __name__ == "__main__":
    main()
