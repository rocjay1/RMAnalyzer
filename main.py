from classes import SpreadsheetParser, MemberSummary


def main():
    summary = MemberSummary()
    summary.open()

    parser = SpreadsheetParser()
    parsed_transactions = parser.parse('test_transactions.csv')

    summary.add_transactions(parsed_transactions)



if __name__ == "__main__":
    main()
