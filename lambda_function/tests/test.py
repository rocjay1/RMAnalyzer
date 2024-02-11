# pylint: disable-all
# Description: Unit tests for RMAnalyzer
# Author: Rocco Davino
# Notes: To run coverage, run the following command from the root directory:
#        coverage run -m lambda_function.tests.test
#        coverage report -m lambda_function\src\main.py


import json
from datetime import date
import typeguard
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch
import boto3
from botocore import exceptions
from moto import mock_aws
from lambda_function.src.main import *


CONFIG = {
    "People": [
        {"Name": "George", "Accounts": [1234, 4321], "Email": "boygeorge@gmail.com"},
        {
            "Name": "Tootie",
            "Accounts": [1313, 2121],
            "Email": "tuttifruity@hotmail.com",
        },
    ],
    "OwnerEmail": "bebas@gmail.com",
    "Categories": {
        "DINING": "Dining & Drinks",
        "GROCERIES": "Groceries",
        "PETS": "Pets",
        "BILLS": "Bills & Utilities",
        "PURCHASES": "Shared Purchases",
        "SUBSCRIPTIONS": "Shared Subscriptions",
    },
}


# Test helper functions
# Test the load_config function
class TestLoadConfig(unittest.TestCase):
    def setUp(self):
        self.config = CONFIG

    def test_load_config_bad_json(self):
        # Mock the JSON fetched from S3
        mock_read_s3 = MagicMock(return_value="bad_JSON")

        with patch("lambda_function.src.main.read_s3_file", mock_read_s3):
            with self.assertRaises(json.JSONDecodeError):
                load_config()

    def test_load_config_good_json(self):
        result_str = '{\n    "People": [\n        {\n            "Name": "George",\n            "Accounts": [\n                1234,\n                4321\n            ],\n            "Email": "boygeorge@gmail.com"\n        },\n        {\n            "Name": "Tootie",\n            "Accounts": [\n                1313,\n                2121\n            ],\n            "Email": "tuttifruity@hotmail.com"\n        }\n    ],\n    "OwnerEmail": "bebas@gmail.com",\n    "Categories": {\n        "DINING": "Dining & Drinks",\n        "GROCERIES": "Groceries",\n        "PETS": "Pets",\n        "BILLS": "Bills & Utilities",\n        "PURCHASES": "Shared Purchases",\n        "SUBSCRIPTIONS": "Shared Subscriptions"\n    }\n}'
        mock_read_s3 = MagicMock(return_value=result_str)
        with patch("lambda_function.src.main.read_s3_file", mock_read_s3):
            result = load_config()
            self.assertEqual(result, self.config)


# Test the read_s3_file function
class TestReadS3File(unittest.TestCase):
    def setUp(self):
        self.bucket = "test-bucket"
        self.key = "test-key"
        self.data = "Hello, World!"

    @mock_aws
    def test_read_s3_file_success(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)
        result = read_s3_file(self.bucket, self.key)
        self.assertEqual(result, self.data)

    @mock_aws
    def test_read_s3_file_key_failure(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        with self.assertRaises(exceptions.ClientError):
            read_s3_file(self.bucket, "nonexistent-key")

    @mock_aws
    def test_read_s3_file_bucket_failure(self):
        s3 = boto3.client("s3")
        with self.assertRaises(exceptions.ClientError):
            read_s3_file("nonexistent-bucket", self.key)


# Test the send_email function
class TestSendEmail(unittest.TestCase):
    def setUp(self):
        self.source = "bebas@gmail.com"
        self.to_addresses = ["boygeorge@gmail.com", "tuttifruity@hotmail.com"]
        self.subject = "Test"
        self.html_body = "<p>Test</p>"

    @mock_aws
    def test_send_email(self):
        ses = boto3.client("ses", region_name="us-east-1")
        ses.verify_email_identity(EmailAddress="bebas@gmail.com")
        response = send_email(
            self.source, self.to_addresses, self.subject, self.html_body
        )
        self.assertIn("MessageId", response)

    @mock_aws
    def test_send_email_bad_source(self):
        ses = boto3.client("ses", region_name="us-east-1")
        with self.assertRaises(exceptions.ClientError):
            send_email(self.source, self.to_addresses, self.subject, self.html_body)


# Test the parse_date_from_filename function
class TestParseDateFromFilename(unittest.TestCase):
    def test_parse_date_from_filename(self):
        f1 = "2022-01-31.csv"
        expected_date = date(2022, 1, 31)
        self.assertEqual(parse_date_from_filename(f1), expected_date)

        f2 = "2023-09-23T15_17_14.839Z-transactions.csv"
        expected_date = date(2023, 9, 23)
        self.assertEqual(parse_date_from_filename(f2), expected_date)

    def test_parse_date_from_filename_bad_filename(self):
        f = "expenses_2021-12.csv"
        self.assertEqual(parse_date_from_filename(f), date.today())


# Test the Transaction class constructor
class TestTransactionConstructor(unittest.TestCase):
    def setUp(self):
        self.transact_date = date(2022, 1, 1)
        self.name = "John Doe"
        self.account_number = 123456
        self.amount = 100.0
        self.category = Category("Groceries")
        self.ignore = IgnoredFrom("")
        self.transaction = Transaction(
            self.transact_date,
            self.name,
            self.account_number,
            self.amount,
            self.category,
            self.ignore,
        )

    def test_constructor(self):
        # Test valid input
        self.assertEqual(self.transaction.date, self.transact_date)
        self.assertEqual(self.transaction.name, self.name)
        self.assertEqual(self.transaction.account_number, self.account_number)
        self.assertEqual(self.transaction.amount, self.amount)
        self.assertEqual(self.transaction.category, self.category)
        self.assertEqual(self.transaction.ignore, self.ignore)

        # Test invalid input
        with self.assertRaises(typeguard.TypeCheckError):
            Transaction(
                "2022-01-01",
                self.name,
                self.account_number,
                self.amount,
                self.category,
                self.ignore,
            )
        with self.assertRaises(typeguard.TypeCheckError):
            Transaction(
                self.transact_date,
                123456,
                self.account_number,
                self.amount,
                self.category,
                self.ignore,
            )
        with self.assertRaises(typeguard.TypeCheckError):
            Transaction(
                self.transact_date,
                self.name,
                "123456",
                self.amount,
                self.category,
                self.ignore,
            )
        with self.assertRaises(typeguard.TypeCheckError):
            Transaction(
                self.transact_date,
                self.name,
                self.account_number,
                "100.0",
                self.category,
                self.ignore,
            )
        with self.assertRaises(typeguard.TypeCheckError):
            Transaction(
                self.transact_date,
                self.name,
                self.account_number,
                self.amount,
                "Groceries",
                self.ignore,
            )
        with self.assertRaises(typeguard.TypeCheckError):
            Transaction(
                self.transact_date,
                self.name,
                self.account_number,
                self.amount,
                self.category,
                "budget",
            )


# Test the from_row function
class TestFromRow(unittest.TestCase):
    # Test that a typical row is parsed correctly as a Transaction object
    def test_from_row(self):
        r = {
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
            "Category": "Shared Purchases",
            "Note": "",
            "Ignored From": "everything",
            "Tax Deductible": "",
        }

        test_result = Transaction.from_row(r)
        expected_result = Transaction(
            date(2023, 8, 31),
            "MADCATS DANCE",
            1313,
            17.0,
            Category.PURCHASES,
            IgnoredFrom.EVERYTHING,
        )

        test_result_attrs = []
        for attr in dir(test_result):
            if not attr.startswith("__"):
                test_result_attrs.append(attr)

        expected_result_attrs = []
        for attr in dir(expected_result):
            if not attr.startswith("__"):
                expected_result_attrs.append(attr)

        self.assertListEqual(test_result_attrs, expected_result_attrs)


# Test the Person class constructor
class TestPersonConstructor(unittest.TestCase):
    def setUp(self):
        self.name = "John Doe"
        self.email = "johndoe@example.com"
        self.account_numbers = [123456, 789012]
        self.transactions = [
            Transaction(
                date(2022, 1, 1),
                "Apples",
                123456,
                100.0,
                Category("Groceries"),
                IgnoredFrom(""),
            ),
            Transaction(
                date(2022, 1, 2),
                "Joe's Bar",
                789012,
                50.0,
                Category("Dining & Drinks"),
                IgnoredFrom(""),
            ),
        ]
        self.person = Person(
            self.name, self.email, self.account_numbers, self.transactions
        )

    def test_constructor(self):
        # Test valid input
        self.assertEqual(self.person.name, self.name)
        self.assertEqual(self.person.email, self.email)
        self.assertEqual(self.person.account_numbers, self.account_numbers)
        self.assertEqual(self.person.transactions, self.transactions)

        # Test invalid input
        with self.assertRaises(typeguard.TypeCheckError):
            Person(123456, self.email, self.account_numbers, self.transactions)
        with self.assertRaises(typeguard.TypeCheckError):
            Person(self.name, 123456, self.account_numbers, self.transactions)
        with self.assertRaises(typeguard.TypeCheckError):
            Person(self.name, self.email, ["789012"], self.transactions)
        with self.assertRaises(typeguard.TypeCheckError):
            Person(self.name, self.email, self.account_numbers, ["invalid transaction"])


# Test the Summary class constructor with different types of config
class TestSummaryConstructor(unittest.TestCase):
    def setUp(self):
        self.good_config = CONFIG

        self.bad_config_type = ["bad", "config"]  # Config must be a dict
        self.bad_config_keys = {
            "bad": "config"
        }  # Config must have People and Owner keys

        self.bad_people_dict_keys = {
            "People": [
                {
                    "Nme": "George",
                    "Accounts": [1234, 4321],
                    "Email": "boygeorge@gmail.com",
                }
            ],
            "OwnerEmail": "bebas@gmail.com",
        }
        self.bad_people_dict_values = {
            "People": [
                {
                    "Name": "George",
                    "Accounts": ["1234", "4321"],
                    "Email": "boygeorge@gmail.com",
                }
            ],
            "OwnerEmail": "bebas@gmail.com",
        }

    def test_summary_constructor_from_config(self):
        summary = Summary(date.today(), config=self.good_config)
        self.assertEqual(summary.date, date.today())
        # Summary should contain 2 people, George and Tootie
        self.assertEqual(len(summary.people), 2)
        self.assertEqual(summary.people[0].name, "George")
        self.assertEqual(summary.people[1].name, "Tootie")

    def test_summary_constructor_no_config(self):
        # Mock load_config to return self.good_config
        mock_load_config = MagicMock(return_value=self.good_config)
        with patch("lambda_function.src.main.load_config", mock_load_config):
            summary = Summary(date.today())
            mock_load_config.assert_called_once()
            self.assertEqual(summary.date, date.today())
            self.assertEqual(len(summary.people), 2)
            self.assertEqual(summary.people[0].name, "George")
            self.assertEqual(summary.people[1].name, "Tootie")

    def test_summary_constructor_bad_config_type(self):
        with self.assertRaises(typeguard.TypeCheckError):
            summary = Summary(date.today(), config=self.bad_config_type)

    def test_summary_constructor_bad_config_keys(self):
        with self.assertRaises(KeyError):
            summary = Summary(date.today(), config=self.bad_config_keys)

    def test_summary_constructor_bad_people_dict_keys(self):
        with self.assertRaises(KeyError):
            summary = Summary(date.today(), config=self.bad_people_dict_keys)

    def test_summary_constructor_bad_people_dict_values(self):
        with self.assertRaises(typeguard.TypeCheckError):
            summary = Summary(date.today(), config=self.bad_people_dict_values)


# Test the calculate_expenses function
class TestCalculateExpenses(unittest.TestCase):
    def setUp(self):
        self.p1 = Person("George", "boygeorge@gmail.com", [1234, 4321], [])
        self.p2 = Person(
            "Tootie",
            "tuttifruity@hotmail.com",
            [1313, 2121],
            [
                Transaction(
                    date(2023, 8, 31),
                    "MADCATS DANCE",
                    1313,
                    17.0,
                    Category.PURCHASES,  # just for the OTHER category
                    IgnoredFrom.NOTHING,
                ),
                Transaction(
                    date(2023, 9, 1),
                    "MADCATS DANCE",
                    1313,
                    17.0,
                    Category.PURCHASES,
                    IgnoredFrom.NOTHING,
                ),
            ],
        )

    def test_calculate_expenses_no_trans(self):
        self.assertEqual(self.p1.calculate_expenses(), 0)

    def test_calculate_expenses_with_trans(self):
        self.assertEqual(self.p2.calculate_expenses(Category.PURCHASES), 34)


# Make unit tests for calculate_2_person_difference
class TestCalculate2PersonDifference(unittest.TestCase):
    def setUp(self):
        self.file_content = """Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-09-02,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,17,MADCATS DANCE,Shared Purchases,,,
2023-09-14,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,,"""
        self.config = CONFIG
        self.date = datetime(2023, 9, 1)

    def test_calculate_2_person_difference(self):
        summary = SpreadsheetSummary(self.date, self.file_content, config=self.config)
        self.assertEqual(
            summary.calculate_2_person_difference(summary.people[0], summary.people[1]),
            -4.34,
        )


# Test the SpreadsheetSummary class constructor
class TestSpreadsheetSummaryConstructor(unittest.TestCase):
    def setUp(self):
        self.file_content = """Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-09-02,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,17,MADCATS DANCE,Shared Purchases,,,
2023-09-14,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,budget,"""
        self.config = CONFIG
        self.date = datetime(2023, 9, 1)

    def test_spreadsheet_summary_constructor(self):
        summary = SpreadsheetSummary(
            self.date, self.file_content, config=self.config
        )  # bypass load_config
        # Make sure there are 2 people in the summary
        self.assertEqual(len(summary.people), 2)
        self.assertEqual(summary.people[0].name, "George")
        self.assertEqual(summary.people[1].name, "Tootie")
        # Make sure Tootie has 1 transaction and George has 0
        # This implicitly tests add_transactions_from_spreadsheet, add_transactions,
        # and add_persons_transactions
        self.assertEqual(len(summary.people[0].transactions), 0)
        self.assertEqual(len(summary.people[1].transactions), 1)


# Test the SpreadsheetParser.parse function
class TestParse(unittest.TestCase):
    def setUp(self):
        self.file_content = """Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,17,MADCATS DANCE,R & T Shared,,,"""
        self.garbage = "***THIS IS A GARBAGE SPREADSHEET***"

    # Test that a garbage spreadsheet is parsed as an empty list
    def test_parse_bad_spreadsheet(self):
        test_result = SpreadsheetParser.parse(self.garbage)
        self.assertEqual(test_result, [])

    # Test that a typical row is parsed correctly as a Transaction object
    # We already tested the from_row function, so we just need to check from_row was called with the proper arguments
    def test_parse_good_row(self):
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
            Category.PURCHASES,
            IgnoredFrom.NOTHING,
        )
        mock_from_row = MagicMock(return_value=mock_transaction)
        with patch("lambda_function.src.main.Transaction.from_row", mock_from_row):
            test_result = SpreadsheetParser.parse(self.file_content)
            mock_from_row.assert_called_once_with(mock_row)
            # Confirm test_result is a list of length 1 and contains a Transaction object
            self.assertEqual(len(test_result), 1)
            self.assertIsInstance(test_result[0], Transaction)


# Test Summary.generate_email_data
# Test generate_email_data on a valid summary
# The result should be a tuple matching
#   summary.owner,[p.email for p in summary.people],f"Monthly Summary - {summary.date.strftime(DISPLAY_DATE_FORMAT)}",
#   html
# where html starts with "<!DOCTYPE html>" and ends with "</html>"
class TestGenerateEmailData(unittest.TestCase):
    def setUp(self):
        self.file_content = """Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,17,MADCATS DANCE,R & T Shared,,,"""
        self.config = CONFIG

    def test_generate_email_data(self):
        summary = SpreadsheetSummary(
            date.today(), self.file_content, config=self.config
        )
        result = summary.generate_email_data()
        self.assertEqual(result[0], summary.owner)
        self.assertEqual(result[1], [p.email for p in summary.people])
        self.assertEqual(
            result[2],
            f"Monthly Summary - {summary.date.strftime(DISPLAY_DATE_FORMAT)}",
        )
        # We've tested the other functions, so just test that the html starts and ends with the correct strings
        self.assertTrue(result[3].startswith("<!DOCTYPE html>"))
        self.assertTrue(result[3].endswith("</html>"))


# Test analyze_s3_sheet
# Already tested most of the functionality in other tests
# Just need to confirm the various functions are called
# Since send_email called within analyze_file uses ses.send_email, mock_ses must be used
class TestAnalyzeS3Sheet(unittest.TestCase):
    def setUp(self):
        self.file_content = "Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible"
        self.config = CONFIG
        self.date = datetime(2023, 8, 1)

    def test_analyze_s3_sheet(self):
        mock_read_s3_file = MagicMock(return_value=self.file_content)
        mock_send_email = MagicMock()

        mock_bucket, mock_key = "some_bucket", "2023-09-23T.csv"
        mock_source = "mocked_source"
        mock_to_addresses = ["mocked_to_addresses"]
        mock_subject = "mocked_subject"
        mock_html_body = "mocked_html_body"

        # Here we patch only the 'generate_email_data' method, not the entire class
        with patch("lambda_function.src.main.read_s3_file", mock_read_s3_file), patch(
            "lambda_function.src.main.SpreadsheetSummary.generate_email_data",
            MagicMock(
                return_value=(
                    mock_source,
                    mock_to_addresses,
                    mock_subject,
                    mock_html_body,
                )
            ),
        ), patch("lambda_function.src.main.send_email", mock_send_email), patch(
            "lambda_function.src.main.load_config", MagicMock(return_value=self.config)
        ):
            analyze_s3_sheet(mock_bucket, mock_key)

            # Assert the functions were called with the expected arguments
            mock_read_s3_file.assert_called_once_with("some_bucket", "2023-09-23T.csv")
            mock_send_email.assert_called_once_with(
                mock_source, mock_to_addresses, mock_subject, mock_html_body
            )


# Test lambda_handler
class TestLambdaHandler(unittest.TestCase):
    def test_lambda_handler(self):
        mock_analyze_s3_sheet = MagicMock()
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
        with patch("lambda_function.src.main.analyze_s3_sheet", mock_analyze_s3_sheet):
            lambda_handler(event, None)
            mock_analyze_s3_sheet.assert_called_once_with("test-bucket", "test-key")


def main():
    unittest.main()


if __name__ == "__main__":
    main()
