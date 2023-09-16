from main import *
from classes import *
import unittest
import boto3
from botocore import exceptions
from moto import mock_s3, mock_ses


class TestSummaryConstructor(unittest.TestCase):
    def test_summary_constructor_from_config(self):
        summary = Summary(date.today(), config=load_config_helper("Tests/config.json"))
        self.assertEqual(summary.date, date.today())
        self.assertEqual(len(summary.people), 2)
        self.assertEqual(summary.people[0].name, "George")
        self.assertEqual(summary.people[1].name, "Tootie")

    def test_summary_constructor_bad_dict(self):
        bad_dict = ["bad", "dict"]
        with self.assertRaises(TypeError):
            summary = Summary(date.today(), bad_dict)

    def test_summary_constructor_bad_dict_keys(self):
        bad_dict = {"bad": "dict"}
        with self.assertRaises(KeyError):
            summary = Summary(date.today(), bad_dict)


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
                Category.ENTERTAINMENT,
            ),
            Transaction(
                date(2023, 9, 4),
                "TIKICAT BAR",
                1234,
                12.66,
                Category.DINING,
            ),
            Transaction(
                date(2023, 9, 12),
                "FISH MARKET",
                1313,
                47.71,
                Category.GROCERIES,
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
                    date(2023, 8, 31), "MADCATS DANCE", 1313, 17, Category.ENTERTAINMENT
                ),
                Transaction(
                    date(2023, 9, 4),
                    "MADCATS DANCE",
                    1313,
                    12.66,
                    Category.ENTERTAINMENT,
                ),
            ],
        )
        self.assertEqual(person.calculate_expenses(Category.ENTERTAINMENT), 29.66)


class TestReadS3File(unittest.TestCase):
    def setUp(self):
        self.bucket = "test-bucket"
        self.key = "test-key"
        self.data = "Hello, World!"

    @mock_s3
    def test_read_s3_file_success(self):
        # Create the S3 client and the mock resources
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)

        # Call the function and check the result
        result = read_s3_file(self.bucket, self.key)
        self.assertEqual(result, self.data)

    @mock_s3
    def test_read_s3_file_failure(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)

        # Test for non-existing key
        with self.assertRaises(exceptions.ClientError):
            read_s3_file(self.bucket, "nonexistent-key")


class TestSendEmail(unittest.TestCase):
    @mock_ses
    def test_send_email(self):
        ses = boto3.client("ses", region_name="us-east-1")
        # Moto's mock SES requires a verified identity (email or domain)
        ses.verify_email_identity(EmailAddress="jasonroc19@gmail.com")

        source = "jasonroc19@gmail.com"
        to_addresses = ["jasonroc19@gmail.com", "vcbarr1@gmail.com"]
        subject = "Test"
        html_body = "<p>Test email</p>"

        # Call the function
        response = send_email(source, to_addresses, subject, html_body)

        self.assertIn("MessageId", response)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
