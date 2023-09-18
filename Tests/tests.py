from RMAnalyzer.main import *
import unittest
import boto3
from botocore import exceptions
from moto import mock_s3, mock_ses
from datetime import date


class TestSummaryConstructor(unittest.TestCase):
    def setUp(self):
        self.bucket = "test-bucket"
        self.key = "test-key"
        with open("tests/config.json", "r") as f:
            self.data = f.read()

    @mock_s3
    def test_summary_constructor_from_config(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)
        config = {"Bucket": self.bucket, "Key": self.key}

        summary = Summary(date.today(), load_config_helper(config))
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


class TestGenerateSummaryEmail(unittest.TestCase):
    def setUp(self):
        self.bucket = "test-bucket"
        self.key = "test-key"
        with open("tests/config.json", "r") as f:
            self.data = f.read()

    @mock_s3
    def test_generate_summary_email(self):
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.data)
        config = {"Bucket": self.bucket, "Key": self.key}

        with open("Tests/valid.csv", "r") as f:
            spreadsheet_content = f.read()
        summary = SpreadsheetSummary(
            date.today(),
            spreadsheet_content,
            config=load_config_helper(config),
        )
        (
            source,
            to_addresses,
            subject,
            html_body,
        ) = EmailGenerator.generate_summary_email(summary)
        correct_source = "bebas@gmail.com"
        correct_to_addresses = ["boygeorge@gmail.com", "tuttifruity@hotmail.com"]
        correct_subject = f"Monthly Summary for {summary.date.strftime(DATE_FORMAT)}"
        correct_html_body = "<html>\n        <head>\n            <style>\n                table {\n                    border-collapse: collapse;\n                    width: 100%;\n                }\n                \n                th, td {\n                    border: 1px solid black;\n                    padding: 8px 12px;  /* Add padding to table cells */\n                    text-align: left;\n                }\n\n                th {\n                    background-color: #f2f2f2;  /* A light background color for headers */\n                }\n            </style>\n        </head>\n        <body><table border='1'>\n<thead>\n<tr>\n<th></th>\n<th>Dining & Drinks</th>\n<th>Groceries</th>\n<th>Entertainment & Rec.</th>\n<th>Total</th>\n</tr>\n</thead>\n<tbody>\n<tr>\n<td>George</td>\n<td>12.66</td>\n<td>0.00</td>\n<td>0.00</td>\n<td>12.66</td>\n</tr>\n<tr>\n<td>Tootie</td>\n<td>0.00</td>\n<td>47.71</td>\n<td>0.00</td>\n<td>47.71</td>\n</tr>\n<tr>\n<td>Difference (George - Tootie)</td>\n<td>12.66</td>\n<td>-47.71</td>\n<td>0.00</td>\n<td>-35.05</td>\n</tr>\n</tbody>\n</table>\n</body>\n</html>"
        self.assertEqual(
            (source, to_addresses, subject, html_body),
            (correct_source, correct_to_addresses, correct_subject, correct_html_body),
        )


def main():
    unittest.main()


if __name__ == "__main__":
    main()
