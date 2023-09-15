from main import *
import unittest
import boto3
from botocore import exceptions
from moto import mock_s3, mock_ses


class TestParse(unittest.TestCase):
    def setUp(self):
        with open("Tests/garbage.csv", "r") as f:
            self.bad_spreadsheet_content = f.read()

    def test_parse_bad_spreadsheet(self):
        result = SpreadsheetParser.parse(self.bad_spreadsheet_content)
        self.assertEqual(result, [])


class TestAddTransactsFromSP(unittest.TestCase):
    def setUp(self):
        with open("Tests/garbage.csv", "r") as f:
            self.bad_spreadsheet_content = f.read()
        self.summary = Summary(load_config(), date.today())

    def test_add_transactions_from_spreadsheet_empty(self):
        self.summary.add_transactions_from_spreadsheet(self.bad_spreadsheet_content)
        transactions = sum([p.transactions for p in self.summary.people], [])
        self.assertEqual(transactions, [])


class TestCalculateExpenses(unittest.TestCase):
    def setUp(self):
        with open("Tests/garbage.csv", "r") as f:
            self.bad_spreadsheet_content = f.read()
        self.summary = Summary(load_config(), date.today())

    def test_calculate_expenses_with_no_trans(self):
        expenses = self.summary.people[0].calculate_expenses()
        self.assertEqual(expenses, 0)

    def test_calculate_expenses_with_no_trans_cat(self):
        expenses = self.summary.people[0].calculate_expenses(Category.DINING)
        self.assertEqual(expenses, 0)


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
