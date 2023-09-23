# Desc: Unit tests for RMAnalyzer
# Author: Rocco Davino


from main import *
import unittest
import boto3
from botocore import exceptions
from moto import mock_s3, mock_ses
from datetime import date


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.bucket = "rm-analyzer-config"
        self.key = "config.json"
        with open("tests/config.json", "r") as f:
            self.data = f.read()

    @mock_s3
    def test_summary_constructor_from_config(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)
        config = {"Bucket": self.bucket, "Key": self.key}

        summary = Summary(date.today(), load_config(config))
        self.assertEqual(summary.date, date.today())
        self.assertEqual(len(summary.people), 2)
        self.assertEqual(summary.people[0].name, "George")
        self.assertEqual(summary.people[1].name, "Tootie")

    @mock_s3
    # Test summary constructor with no config specified
    def test_summary_constructor_no_config(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)

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
        with open("tests/config.json", "r") as f:
            self.data = f.read()

    @mock_s3
    def test_spreadsheet_summary_constructor(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)
        config = {"Bucket": self.bucket, "Key": self.key}

        with open("Tests/valid.csv", "r") as f:
            spreadsheet_content = f.read()

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
        with open("Tests/garbage.csv", "r") as f:
            bad_spreadsheet_content = f.read()
        test_result = SpreadsheetParser.parse(bad_spreadsheet_content)
        self.assertEqual(test_result, [])

    def test_parse_good_spreadsheet(self):
        with open("Tests/valid.csv", "r") as f:
            good_spreadsheet_content = f.read()
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
        flag = True
        for i in range(len(test_result)):
            if (
                test_result[i].date != correct_result[i].date
                or test_result[i].name != correct_result[i].name
                or test_result[i].account_number != correct_result[i].account_number
                or test_result[i].amount != correct_result[i].amount
                or test_result[i].category != correct_result[i].category
            ):
                flag = False
                break
        self.assertEqual(flag, True)


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
        with open("tests/config.json", "r") as f:
            self.data = f.read()

    @mock_s3
    def test_calculate_2_person_difference(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)
        config = {"Bucket": self.bucket, "Key": self.key}

        with open("Tests/valid.csv", "r") as f:
            spreadsheet_content = f.read()

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


class TestSendEmail(unittest.TestCase):
    @mock_ses
    def test_send_email(self):
        ses = boto3.client("ses", region_name="us-east-1")
        # Moto's mock SES requires a verified identity (email or domain)
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
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)
        config = {"Bucket": self.bucket, "Key": self.key}
        with self.assertRaises(json.decoder.JSONDecodeError):
            load_config(config)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
