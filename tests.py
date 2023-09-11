from main import *


def test_email_generation():
    with open("test_transactions.csv", "r") as f:
        file_content = f.read()

    config = load_config()

    people = []
    for person_config in config["People"]:
        name = person_config["Name"]
        accounts = person_config["Accounts"]
        email = person_config["Email"]
        people.append(Person(name, email, accounts, []))

    summary = MonthlySummary(people, date.today())
    parsed_transactions = SpreadsheetParser.parse(file_content)
    summary.add_all_transactions(parsed_transactions)

    html_body = EmailGenerator.generate_summary_email(summary)

    print(html_body)


def main():
    test_email_generation()


if __name__ == "__main__":
    main()
