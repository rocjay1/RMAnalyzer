# Desc: Unit tests for RMAnalyzer
# Author: Rocco Davino


import json
from datetime import date
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch
import boto3
from botocore import exceptions
from moto import mock_s3, mock_ses
from main import (
    Summary,
    Person,
    Transaction,
    Category,
    load_config,
    SpreadsheetSummary,
    SpreadsheetParser,
    DISPLAY_DATE_FORMAT,
    EmailGenerator,
    send_email,
    analyze_file,
    lambda_handler,
    read_s3_file,
    DATE_FORMAT,
    MONEY_FORMAT,
    CONFIG,
    format_money_helper,
    NotIgnoredFrom,
)


CONFIG = {
    "People": [
        {"Name": "George", "Accounts": [1234, 4321], "Email": "boygeorge@gmail.com"},
        {
            "Name": "Tootie",
            "Accounts": [1313, 2121],
            "Email": "tuttifruity@hotmail.com",
        },
    ],
    "Owner": "bebas@gmail.com",
}
GARBAGE = "***THIS IS A GARBAGE SPREADSHEET***"


# Test the Transaction class constructor
class TestTransactionConstructor(unittest.TestCase):
    def test_constructor(self):
        # Test valid input
        transact_date = date(2022, 1, 1)
        name = "John Doe"
        account_number = 123456
        amount = 100.0
        category = Category("Groceries")
        ignore = NotIgnoredFrom("")
        transaction = Transaction(
            transact_date, name, account_number, amount, category, ignore
        )
        self.assertEqual(transaction.date, transact_date)
        self.assertEqual(transaction.name, name)
        self.assertEqual(transaction.account_number, account_number)
        self.assertEqual(transaction.amount, amount)
        self.assertEqual(transaction.category, category)
        self.assertEqual(transaction.ignore, ignore)

        # Test invalid input
        with self.assertRaises(TypeError):
            Transaction(
                "2022-01-01",
                "John Doe",
                123456,
                100.0,
                Category("Groceries"),
                NotIgnoredFrom(""),
            )
        with self.assertRaises(TypeError):
            Transaction(
                date(2022, 1, 1),
                123456,
                123456,
                100.0,
                Category("Groceries"),
                NotIgnoredFrom(""),
            )
        with self.assertRaises(TypeError):
            Transaction(
                date(2022, 1, 1),
                "John Doe",
                "123456",
                100.0,
                Category("Groceries"),
                NotIgnoredFrom(""),
            )
        with self.assertRaises(TypeError):
            Transaction(
                date(2022, 1, 1),
                "John Doe",
                123456,
                "100.0",
                Category("Groceries"),
                NotIgnoredFrom(""),
            )
        with self.assertRaises(TypeError):
            Transaction(
                date(2022, 1, 1),
                "John Doe",
                123456,
                100.0,
                "Groceries",
                NotIgnoredFrom(""),
            )
        with self.assertRaises(TypeError):
            Transaction(
                date(2022, 1, 1),
                "John Doe",
                123456,
                100.0,
                Category("Groceries"),
                "budget",
            )


# Test the Person class constructor
class TestPersonConstructor(unittest.TestCase):
    def test_constructor(self):
        # Test valid input
        name = "John Doe"
        email = "johndoe@example.com"
        account_numbers = [123456, 789012]
        transactions = [
            Transaction(
                date(2022, 1, 1),
                "John Doe",
                123456,
                100.0,
                Category("Groceries"),
                NotIgnoredFrom(""),
            ),
            Transaction(
                date(2022, 1, 2),
                "Jane Doe",
                789012,
                50.0,
                Category("Dining & Drinks"),
                NotIgnoredFrom(""),
            ),
        ]
        person = Person(name, email, account_numbers, transactions)
        self.assertEqual(person.name, name)
        self.assertEqual(person.email, email)
        self.assertEqual(person.account_numbers, account_numbers)
        self.assertEqual(person.transactions, transactions)

        # Test invalid input
        with self.assertRaises(TypeError):
            Person(123456, "johndoe@example.com", [123456, 789012], transactions)
        with self.assertRaises(TypeError):
            Person("John Doe", 123456, [123456, 789012], transactions)
        with self.assertRaises(TypeError):
            Person("John Doe", "johndoe@example.com", [123456, "789012"], transactions)
        with self.assertRaises(TypeError):
            Person(
                "John Doe",
                "johndoe@example.com",
                [123456, 789012],
                ["invalid transaction"],
            )


# Test the Summary class constructor with different types of config
class TestSummaryConstructor(unittest.TestCase):
    def setUp(self):
        self.good_config = CONFIG
        self.bad_config_type = ["bad", "config"]  # config must be a dict
        self.bad_config_values = {
            "bad": "config"
        }  # config must have People and Owner keys

    def test_summary_constructor_from_config(self):
        summary = Summary(date.today(), config=self.good_config)
        self.assertEqual(summary.date, date.today())
        # summary should contain 2 people, George and Tootie
        self.assertEqual(len(summary.people), 2)
        self.assertEqual(summary.people[0].name, "George")
        self.assertEqual(summary.people[1].name, "Tootie")

    def test_summary_constructor_no_config(self):
        # Mock load_config to return self.good_config
        mock_load_config = MagicMock(return_value=self.good_config)
        with patch("main.load_config", mock_load_config):
            summary = Summary(date.today())
            self.assertEqual(summary.date, date.today())
            self.assertEqual(len(summary.people), 2)
            self.assertEqual(summary.people[0].name, "George")
            self.assertEqual(summary.people[1].name, "Tootie")

    def test_summary_constructor_bad_config_type(self):
        with self.assertRaises(TypeError):
            summary = Summary(date.today(), config=self.bad_config_type)

    def test_summary_constructor_bad_config_values(self):
        with self.assertRaises(KeyError):
            summary = Summary(date.today(), config=self.bad_config_values)


# Test the load_config function
class TestLoadConfig(unittest.TestCase):
    # Test load_config assuming read_s3_file threw an exception
    def test_load_config_s3_error(self):
        mock_read_s3_file = MagicMock(
            side_effect=exceptions.ClientError({"Error": {}}, "test")
        )
        with patch("main.read_s3_file", mock_read_s3_file):
            with self.assertRaises(exceptions.ClientError):
                load_config()

    # Test load_config assuming read_s3_file returned a bad string
    def test_load_config_bad_json(self):
        mock_read_s3_file = MagicMock(return_value="bad config")
        with patch("main.read_s3_file", mock_read_s3_file):
            with self.assertRaises(json.decoder.JSONDecodeError):
                load_config()

    # Assuming read_s3_file returned a good string, assert load_config returned the correct dict
    # Assert read_s3_file was called with "Bucket": "rm-analyzer-config", "Key": "config.json"
    def test_load_config_valid_read(self):
        mock_read_s3_file = MagicMock(return_value=json.dumps(CONFIG))
        with patch("main.read_s3_file", mock_read_s3_file):
            result = load_config()
            self.assertEqual(result, CONFIG)
            mock_read_s3_file.assert_called_once_with(
                "rm-analyzer-config", "config.json"
            )


# Test the SpreadsheetSummary class constructor
class TestSpreadsheetSummaryConstructor(unittest.TestCase):
    def test_spreadsheet_summary_constructor(self):
        csv_string = """Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,17,MADCATS DANCE,R & T Shared,,,
2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,budget,"""
        summary = SpreadsheetSummary(
            date.today(), csv_string, config=CONFIG
        )  # bypass load_config
        # Make sure there are 2 people in the summary
        self.assertEqual(len(summary.people), 2)
        self.assertEqual(summary.people[0].name, "George")
        self.assertEqual(summary.people[1].name, "Tootie")
        # Make sure Tootie has 1 transaction and George has 0
        # This implicitly tests add_transactions_from_spreadsheet and add_transactions
        self.assertEqual(len(summary.people[0].transactions), 0)
        self.assertEqual(len(summary.people[1].transactions), 1)


# Test the from_row function
class TestFromRow(unittest.TestCase):
    # Test that a typical row is parsed correctly as a Transaction object
    def test_from_row(self):
        row = {
            "Date": "2023-08-31",
            "Original Date": "2023-08-31",
            "Account Type": "Credit Card",
            "Account Name": "SavorOne",
            "Account Number": "1313",
            "Institution Name": "Capital One",
            "Name": "MADCATS DANCE",
            "Custom Name": "",
            "Amount": "17",
            "Description": "MADCATS DANCE",
            "Category": "R & T Shared",
            "Note": "",
            "Ignored From": "",
            "Tax Deductible": "",
        }
        test_result = Transaction.from_row(row)
        test_result_attrs = []
        for attr in dir(test_result):
            if not attr.startswith("__"):
                test_result_attrs.append(attr)

        expected_result = Transaction(
            date(2023, 8, 31),
            "MADCATS DANCE",
            1313,
            17.0,
            Category.OTHER,
            NotIgnoredFrom.NOT_IGNORED,
        )
        expected_result_attrs = []
        for attr in dir(expected_result):
            if not attr.startswith("__"):
                expected_result_attrs.append(attr)

        self.assertListEqual(test_result_attrs, expected_result_attrs)

    # Test that a row with an invalid category is ignored
    def test_from_row_bad_category(self):
        row = {
            "Date": "2023-09-17",
            "Original Date": "2023-09-17",
            "Account Type": "Cash",
            "Account Name": "Savings Account",
            "Account Number": "2121",
            "Institution Name": "Ally Bank",
            "Name": "SURPISE SAVINGS",
            "Custom Name": "",
            "Amount": "-10",
            "Description": "SURPISE SAVINGS",
            "Category": "Internal Transfers",
            "Note": "",
            "Ignored From": "",
            "Tax Deductible": "",
        }
        test_result = Transaction.from_row(row)
        self.assertIsNone(test_result)

    # Test that a row with an Ignored From value is ignored
    def test_from_row_ignored(self):
        row = {
            "Date": "2023-09-04",
            "Original Date": "2023-09-04",
            "Account Type": "Credit Card",
            "Account Name": "CREDIT CARD",
            "Account Number": "1234",
            "Institution Name": "Chase",
            "Name": "TIKICAT BAR",
            "Custom Name": "",
            "Amount": "12.66",
            "Description": "TIKICAT BAR",
            "Category": "Dining & Drinks",
            "Note": "",
            "Ignored From": "budget",
            "Tax Deductible": "",
        }
        test_result = Transaction.from_row(row)
        self.assertIsNone(test_result)

        row = {
            "Date": "2023-09-04",
            "Original Date": "2023-09-04",
            "Account Type": "Credit Card",
            "Account Name": "CREDIT CARD",
            "Account Number": "1234",
            "Institution Name": "Chase",
            "Custom Name": "",
            "Amount": "12.66",
            "Description": "TIKICAT BAR",
            "Category": "Dining & Drinks",
            "Note": "",
            "Ignored From": "",
            "Tax Deductible": "",
        }
        test_result = Transaction.from_row(row)
        self.assertIsNone(test_result)


# Test the initialize_people function
class TestInitializePeople(unittest.TestCase):
    def test_initialize_config_keys(self):
        bad_config_keys = {
            "People": [
                {
                    "Nme": "George",
                    "Accounts": [1234, 4321],
                    "Email": "boygeorge@gmail.com",
                }
            ],
            "Owner": "bebas@gmail.com",
        }
        with self.assertRaises(KeyError):
            summary = Summary(date.today(), bad_config_keys)

    def test_initialize_bad_config_values(self):
        bad_config_values = {
            "People": [
                {
                    "Name": "George",
                    "Accounts": ["1234", "4321"],
                    "Email": "boygeorge@gmail.com",
                }
            ],
            "Owner": "bebas@gmail.com",
        }
        with self.assertRaises(TypeError):
            summary = Summary(date.today(), bad_config_values)


# Test the SpreadsheetParser.parse function
class TestParse(unittest.TestCase):
    # Test that a garbage spreadsheet is parsed as an empty list
    def test_parse_bad_spreadsheet(self):
        test_result = SpreadsheetParser.parse(GARBAGE)
        self.assertEqual(test_result, [])

    # Test that a typical row is parsed correctly as a Transaction object
    # We already tested the from_row function, so we just need to check from_row was called with the proper arguments
    def test_parse_good_row(self):
        csv_string = """Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,17,MADCATS DANCE,R & T Shared,,,"""
        mock_row = {
            "Date": "2023-08-31",
            "Original Date": "2023-08-31",
            "Account Type": "Credit Card",
            "Account Name": "SavorOne",
            "Account Number": "1313",
            "Institution Name": "Capital One",
            "Name": "MADCATS DANCE",
            "Custom Name": "",
            "Amount": "17",
            "Description": "MADCATS DANCE",
            "Category": "R & T Shared",
            "Note": "",
            "Ignored From": "",
            "Tax Deductible": "",
        }
        mock_transaction = Transaction(
            date(2023, 8, 31),
            "MADCATS DANCE",
            1313,
            17.0,
            Category.OTHER,
            NotIgnoredFrom.NOT_IGNORED,
        )
        mock_from_row = MagicMock(return_value=mock_transaction)
        with patch("main.Transaction.from_row", mock_from_row):
            test_result = SpreadsheetParser.parse(csv_string)
            mock_from_row.assert_called_once_with(mock_row)
            # Confirm test_result is a list of length 1 and contains a Transaction object
            self.assertEqual(len(test_result), 1)
            self.assertIsInstance(test_result[0], Transaction)


# Test the calculate_expenses function
class TestCalculateExpenses(unittest.TestCase):
    def test_calculate_expenses_no_trans(self):
        person = Person("George", "boygeorge@gmail.com", [1234, 4321])
        self.assertEqual(person.calculate_expenses(), 0)

    def test_calculate_expenses_with_trans(self):
        person = Person(
            "Tootie",
            "tuttifruity@hotmail.com",
            [1313, 2121],
            [
                Transaction(
                    date(2023, 8, 31),
                    "MADCATS DANCE",
                    1313,
                    17.0,
                    Category.OTHER,  # just for the OTHER category
                    NotIgnoredFrom.NOT_IGNORED,
                ),
                Transaction(
                    date(2023, 9, 1),
                    "MADCATS DANCE",
                    1313,
                    17.0,
                    Category.OTHER,
                    NotIgnoredFrom.NOT_IGNORED,
                ),
            ],
        )
        self.assertEqual(person.calculate_expenses(Category.OTHER), 34)


# Make unit tests for calculate_2_person_difference
class TestCalculate2PersonDifference(unittest.TestCase):
    def setUp(self):
        # Must be called on a valid SpreadsheetSummary object
        # Removing "budget" from "Ignored From" to make the calculation more interesting
        csv_string = """Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,17,MADCATS DANCE,R & T Shared,,,
2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,,"""
        self.summary = SpreadsheetSummary(date.today(), csv_string, config=CONFIG)

    def test_calculate_2_person_difference(self):
        self.assertEqual(
            self.summary.calculate_2_person_difference(
                self.summary.people[0], self.summary.people[1]
            ),
            -4.34,
        )


# Test the read_s3_file function
class TestReadS3File(unittest.TestCase):
    def setUp(self):
        self.bucket = "test-bucket"
        self.key = "test-key"
        self.data = "Hello, World!"

    @mock_s3
    def test_read_s3_file_success(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)
        result = read_s3_file(self.bucket, self.key)
        self.assertEqual(result, self.data)

    @mock_s3
    def test_read_s3_file_key_failure(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        with self.assertRaises(exceptions.ClientError):
            read_s3_file(self.bucket, "nonexistent-key")

    @mock_s3
    def test_read_s3_file_bucket_failure(self):
        s3 = boto3.client("s3")
        with self.assertRaises(exceptions.ClientError):
            read_s3_file("nonexistent-bucket", self.key)


# Test the send_email function
class TestSendEmail(unittest.TestCase):
    @mock_ses
    def test_send_email(self):
        ses = boto3.client("ses", region_name="us-east-1")
        ses.verify_email_identity(EmailAddress="bebas@gmail.com")
        source = "bebas@gmail.com"
        to_addresses = ["boygeorge@gmail.com", "tuttifruity@hotmail.com"]
        subject = "Test"
        html_body = "<p>Test</p>"
        response = send_email(source, to_addresses, subject, html_body)
        self.assertIn("MessageId", response)

    @mock_ses
    def test_send_email_bad_source(self):
        ses = boto3.client("ses", region_name="us-east-1")
        bad_source = "bebas@gmail.com"
        to_addresses = ["boygeorge@gmail.com", "tuttifruity@hotmail.com"]
        subject = "Test"
        html_body = "<p>Test</p>"
        with self.assertRaises(exceptions.ClientError):
            send_email(bad_source, to_addresses, subject, html_body)


# Test EmailGenerator
# Test generate_summary_email on a valid summary
# The result should be a tuple matching
#   summary.owner,[p.email for p in summary.people],f"Monthly Summary - {summary.date.strftime(DISPLAY_DATE_FORMAT)}",
#   html
# where html starts with "<html>" and ends with "</html>"
class TestEmailGenerator(unittest.TestCase):
    def setUp(self):
        # Must be called on a valid Summary object
        csv_string = """Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,17,MADCATS DANCE,R & T Shared,,,"""
        self.summary = SpreadsheetSummary(date.today(), csv_string, config=CONFIG)

    def test_generate_summary_email(self):
        result = EmailGenerator.generate_summary_email(self.summary)
        self.assertEqual(result[0], self.summary.owner)
        self.assertEqual(result[1], [p.email for p in self.summary.people])
        self.assertEqual(
            result[2],
            f"Monthly Summary - {self.summary.date.strftime(DISPLAY_DATE_FORMAT)}",
        )
        # We've tested the other functions, so just test that the html starts and ends with the correct strings
        self.assertTrue(result[3].startswith("<html>"))
        self.assertTrue(result[3].endswith("</html>"))


# Test analyze_file
# Already tested most of the functionality in other tests
# Just need to confirm the various functions are called
# Also test
#   bucket, key = file_path.replace("s3://", "").split("/", 1)
# On a path like "s3://test-bucket/test-key" sets
# bucket = "test-bucket" and key = "test-key"
# Since send_email called within analyze_file uses ses.send_email, mock_ses must be used
class TestAnalyzeFile(unittest.TestCase):
    def test_analyze_file(self):
        # Mock the function and classes being used in the function
        mock_read_s3_file = MagicMock()
        mock_spreadsheet_summary = MagicMock()
        mock_email_generator = MagicMock()
        mock_send_email = MagicMock()

        file_path = "s3://some_bucket/some_key"
        mock_file_content = "mocked_file_content"
        mock_read_s3_file.return_value = mock_file_content

        mock_summary = "mocked_summary"
        mock_spreadsheet_summary.return_value = mock_summary

        mock_source = "mocked_source"
        mock_to_addresses = "mocked_to_addresses"
        mock_subject = "mocked_subject"
        mock_html_body = "mocked_html_body"
        mock_email_generator.generate_summary_email.return_value = (
            mock_source,
            mock_to_addresses,
            mock_subject,
            mock_html_body,
        )

        # Use patch to replace the real function/class with our mocks
        with patch("main.read_s3_file", mock_read_s3_file), patch(
            "main.SpreadsheetSummary", mock_spreadsheet_summary
        ), patch("main.EmailGenerator", mock_email_generator), patch(
            "main.send_email", mock_send_email
        ):
            analyze_file(file_path)

            # Assert the function and classes were called with the expected arguments
            mock_read_s3_file.assert_called_once_with("some_bucket", "some_key")
            mock_spreadsheet_summary.assert_called_once_with(
                date.today(), mock_file_content
            )
            mock_email_generator.generate_summary_email.assert_called_once_with(
                mock_summary
            )
            mock_send_email.assert_called_once_with(
                mock_source, mock_to_addresses, mock_subject, mock_html_body
            )


# Test lambda_handler
class TestLambdaHandler(unittest.TestCase):
    def test_lambda_handler(self):
        mock_analyze_file = MagicMock()
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "test-key"},
                    }
                }
            ]
        }
        with patch("main.analyze_file", mock_analyze_file):
            lambda_handler(event, None)
            mock_analyze_file.assert_called_once_with("s3://test-bucket/test-key")


def main():
    unittest.main()


if __name__ == "__main__":
    main()
