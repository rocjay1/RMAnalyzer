# Desc: Unit tests for RMAnalyzer
# Author: Rocco Davino


from main import *
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
import boto3
from botocore import exceptions
from moto import mock_s3, mock_ses
from datetime import date


CONFIG_PATH = "tests/config.json"
CSV_PATH = "tests/valid.csv"

# Helper function to setup mock S3 bucket
def setup_mock_s3(bucket_name, key, data):
    s3 = boto3.client("s3")
    s3.create_bucket(Bucket=bucket_name)
    s3.put_object(Bucket=bucket_name, Key=key, Body=data)


# Helper function to setup mock SES
def setup_mock_ses():
    ses = boto3.client("ses", region_name="us-east-1")
    ses.verify_email_identity(EmailAddress="bebas@gmail.com")


# Helper function to read local file
def read_local_file(file_path):
    with open(file_path, "r") as f:
        return f.read()


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.bucket = "rm-analyzer-config"
        self.key = "config.json"
        self.data = read_local_file(CONFIG_PATH)

    @mock_s3
    def test_summary_constructor_from_config(self):
        setup_mock_s3(self.bucket, self.key, self.data)
        config = {"Bucket": self.bucket, "Key": self.key}
        summary = Summary(date.today(), load_config(config))
        self.assertEqual(summary.date, date.today())
        self.assertEqual(len(summary.people), 2)
        self.assertEqual(summary.people[0].name, "George")
        self.assertEqual(summary.people[1].name, "Tootie")

    @mock_s3
    # Test summary constructor with no config specified
    def test_summary_constructor_no_config(self):
        setup_mock_s3(self.bucket, self.key, self.data)
        summary = Summary(date.today())
        self.assertEqual(summary.date, date.today())
        self.assertEqual(len(summary.people), 2)

    def test_summary_constructor_bad_dict(self):
        bad_dict = ["bad", "dict"]
        with self.assertRaises(TypeError):
            summary = Summary(date.today(), bad_dict)

    def test_summary_constructor_bad_dict_keys(self):
        bad_dict = {"bad": "dict"}
        with self.assertRaises(KeyError):
            summary = Summary(date.today(), bad_dict)


class TestSpreadsheetSummary(unittest.TestCase):
    def setUp(self):
        self.bucket = "test-bucket"
        self.key = "test-key"
        self.data = read_local_file(CONFIG_PATH)

    @mock_s3
    def test_spreadsheet_summary_constructor(self):
        setup_mock_s3(self.bucket, self.key, self.data)
        config = {"Bucket": self.bucket, "Key": self.key}
        spreadsheet_content = read_local_file(CSV_PATH)

        summary = SpreadsheetSummary(
            date.today(),
            spreadsheet_content,
            config=load_config(config),
        )
        
        self.assertEqual(len(summary.people), 2)
        self.assertEqual(summary.people[0].name, "George")
        self.assertEqual(summary.people[1].name, "Tootie")
        # Make sure Tootie has 2 transactions and George has 0
        self.assertEqual(len(summary.people[0].transactions), 0)
        self.assertEqual(len(summary.people[1].transactions), 2)


class TestInitializePeople(unittest.TestCase):
    def test_initialize_bad_dict_keys(self):
        bad_dict_keys = {
            "People": [
                {
                    "Nme": "George",
                    "Accounts": [1234, 4321],
                    "Email": "boygeorge@gmail.com",
                },
                {
                    "Name": "Tootie",
                    "Accounts": [1313],
                    "Email": "tuttifruity@hotmail.com",
                },
            ],
            "Owner": "bebas@gmail.com",
        }
        with self.assertRaises(KeyError):
            summary = Summary(date.today(), bad_dict_keys)

    def test_initialize_bad_dict_values(self):
        bad_dict_values = {
            "People": [
                {
                    "Name": "George",
                    "Accounts": ["1234", "4321"],
                    "Email": "boygeorge@gmail.com",
                },
                {
                    "Name": "Tootie",
                    "Accounts": [1313],
                    "Email": "tuttifruity@hotmail.com",
                },
            ],
            "Owner": "bebas@gmail.com",
        }
        with self.assertRaises(TypeError):
            summary = Summary(date.today(), bad_dict_values)


class TestParse(unittest.TestCase):
    def test_parse_bad_spreadsheet(self):
        bad_spreadsheet_content = read_local_file("tests/garbage.csv")
        test_result = SpreadsheetParser.parse(bad_spreadsheet_content)
        self.assertEqual(test_result, [])

    def test_parse_good_spreadsheet(self):
        good_spreadsheet_content = read_local_file(CSV_PATH)
        test_result = SpreadsheetParser.parse(good_spreadsheet_content)
        correct_result = [
            Transaction(
                date(2023, 8, 31),
                "MADCATS DANCE",
                1313,
                17,
                Category.OTHER,
                False
            ),
            Transaction(
                date(2023, 9, 4),
                "TIKICAT BAR",
                1234,
                12.66,
                Category.DINING,
                True
            ),
            Transaction(
                date(2023, 9, 12),
                "FISH MARKET",
                1313,
                47.71,
                Category.GROCERIES,
                False
            ),
        ]
        for i in range(len(test_result)):
            self.assertEqual(test_result[i].date, correct_result[i].date)
            self.assertEqual(test_result[i].name, correct_result[i].name)
            self.assertEqual(test_result[i].account_number, correct_result[i].account_number)
            self.assertEqual(test_result[i].amount, correct_result[i].amount)
            self.assertEqual(test_result[i].category, correct_result[i].category)
            self.assertEqual(test_result[i].ignore, correct_result[i].ignore)


class TestCalculateExpenses(unittest.TestCase):
    def test_calculate_expenses_no_trans(self):
        person = Person("George", "boygeorge@gmail.com", [1234, 4321])
        self.assertEqual(person.calculate_expenses(), 0)

    def test_calculate_expenses_trans(self):
        person = Person(
            "Tootie",
            "tuttifruity@hotmail.com",
            [1313, 2121],
            [
                Transaction(
                    date(2023, 8, 31), 
                    "MADCATS DANCE", 
                    1313, 
                    17, 
                    Category.OTHER,
                    False
                ),
                Transaction(
                    date(2023, 9, 4),
                    "MADCATS DANCE",
                    1313,
                    12.66,
                    Category.OTHER,
                    False
                ),
            ],
        )
        self.assertEqual(person.calculate_expenses(Category.OTHER), 29.66)


# Make unit tests for calculate_2_person_difference
class TestCalculate2PersonDifference(unittest.TestCase):
    def setUp(self):
        self.bucket = "rm-analyzer-config"
        self.key = "config.json"
        self.data = read_local_file(CONFIG_PATH)

    @mock_s3
    def test_calculate_2_person_difference(self):
        setup_mock_s3(self.bucket, self.key, self.data)
        config = {"Bucket": self.bucket, "Key": self.key}
        spreadsheet_content = read_local_file(CSV_PATH)
        summary = SpreadsheetSummary(
            date.today(),
            spreadsheet_content,
            config=load_config(config),
        )
        self.assertEqual(summary.calculate_2_person_difference(summary.people[0], summary.people[1], Category.OTHER), -17)


class TestReadS3File(unittest.TestCase):
    def setUp(self):
        self.bucket = "test-bucket"
        self.key = "test-key"
        self.data = "Hello, World!"

    @mock_s3
    def test_read_s3_file_success(self):
        setup_mock_s3(self.bucket, self.key, self.data)
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


class TestSendEmail(unittest.TestCase):
    @mock_ses
    def test_send_email(self):
        setup_mock_ses()
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


class TestLoadConfig(unittest.TestCase):
    def setUp(self):
        self.bucket = "test-bucket"
        self.key = "test-key"
        self.data = "Hello, World!"

    # Test load_config on a bad S3 key
    @mock_s3
    def test_load_config_bad_key(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        config = {"Bucket": self.bucket, "Key": "bad-key"}
        with self.assertRaises(exceptions.ClientError):
            load_config(config)

    # Test load_config on a bad S3 bucket
    @mock_s3
    def test_load_config_bad_bucket(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        config = {"Bucket": "bad-bucket", "Key": self.key}
        with self.assertRaises(exceptions.ClientError):
            load_config(config)

    # Test load_config on a bad JSON file
    @mock_s3
    def test_load_config_bad_json(self):
        setup_mock_s3(self.bucket, self.key, self.data)
        config = {"Bucket": self.bucket, "Key": self.key}
        with self.assertRaises(json.decoder.JSONDecodeError):
            load_config(config)


# Test EmailGenerator
# Test generate_summary_email on a valid summary
# The result should be a tuple matching
#   summary.owner,[p.email for p in summary.people],f"Monthly Summary - {summary.date.strftime(DISPLAY_DATE_FORMAT)}",
#   html
# where html starts with "<html>" and ends with "</html>"
class TestEmailGenerator(unittest.TestCase):
    def setUp(self):
        self.bucket = "rm-analyzer-config"
        self.key = "config.json"
        self.data = read_local_file(CONFIG_PATH)

    @mock_s3
    def test_generate_summary_email(self):
        setup_mock_s3(self.bucket, self.key, self.data)
        config = {"Bucket": self.bucket, "Key": self.key}
        spreadsheet_content = read_local_file(CSV_PATH)
        summary = SpreadsheetSummary(
            date.today(),
            spreadsheet_content,
            config=load_config(config),
        )
        result = EmailGenerator.generate_summary_email(summary)
        self.assertEqual(result[0], summary.owner)
        self.assertEqual(result[1], [p.email for p in summary.people])
        self.assertEqual(
            result[2],
            f"Monthly Summary - {summary.date.strftime(DISPLAY_DATE_FORMAT)}",
        )
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
        mock_summary = "mocked_summary"
        mock_source = "mocked_source"
        mock_to_addresses = "mocked_to_addresses"
        mock_subject = "mocked_subject"
        mock_html_body = "mocked_html_body"
        mock_email_generator.generate_summary_email.return_value = (
                mock_source, 
                mock_to_addresses, 
                mock_subject, 
                mock_html_body
            )
        # Use patch to replace the real function/class with our mocks
        with patch('main.read_s3_file', mock_read_s3_file), \
            patch('main.SpreadsheetSummary', mock_spreadsheet_summary), \
            patch('main.EmailGenerator', mock_email_generator), \
            patch('main.send_email', mock_send_email):

            mock_read_s3_file.return_value = mock_file_content
            mock_spreadsheet_summary.return_value = mock_summary

            analyze_file(file_path)

            # Assert the function and classes were called with the expected arguments
            mock_read_s3_file.assert_called_once_with("some_bucket", "some_key")
            mock_spreadsheet_summary.assert_called_once_with(date.today(), mock_file_content)
            mock_email_generator.generate_summary_email.assert_called_once_with(mock_summary)
            mock_send_email.assert_called_once_with(mock_source, mock_to_addresses, mock_subject, mock_html_body)


class TestLambdaHandler(unittest.TestCase):
    def test_lambda_handler(self):
        mock_analyze_file = MagicMock()
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {
                            "name": "test-bucket"
                        },
                        "object": {
                            "key": "test-key"
                        }
                    }
                }
            ]
        }
        with patch('main.analyze_file', mock_analyze_file):
            lambda_handler(event, None)
            mock_analyze_file.assert_called_once_with("s3://test-bucket/test-key")


def main():
    unittest.main()


if __name__ == "__main__":
    main()
