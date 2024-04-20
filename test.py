# pylint: disable-all
# Description: Tests for RMAnalyzer
# Author: Rocco Davino


import unittest
import boto3
from moto import mock_aws
from main import (
    get_config,
    validate_config,
    get_transactions,
    get_members,
    Group,
    SummaryEmail,
    Category,
    to_currency,
)


# Test get_s3_content output
CONTENT = "Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible\n2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,150,MADCATS DANCE,Entertainment & Rec.,,,\n2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,,\n2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,budget,\n2023-09-12,2023-09-12,Cash,Spending Account,2121,Ally Bank,FISH MARKET,,47.71,FISH MARKET,Groceries,,,\n2023-09-15,2023-09-15,Credit Card,SavorOne,1313,Capital One,TIKICAT BAR,,17,TIKICAT BAR,Dining & Drinks,,,\n"

# Test get_config output
CONFIG = '{\n    "People": [\n        {\n            "Name": "George",\n            "Accounts": [\n                1234\n            ],\n            "Email": "boygeorge@gmail.com"\n        },\n        {\n            "Name": "Tootie",\n            "Accounts": [\n                1313\n            ],\n            "Email": "tuttifruity@hotmail.com"\n        }\n    ],\n    "Owner": "bebas@gmail.com"\n}'


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.bucket = "rmanalyzer-config"
        self.key = "test.csv"
        self.content = CONTENT
        self.config_bucket = "rmanalyzer-config"
        self.config_key = "config-test.json"
        self.config = CONFIG
        self.event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": self.bucket},
                        "object": {"key": self.key},
                    }
                }
            ]
        }

    @mock_aws
    def test_lambda_handler_body(self):
        # Mock AWS setup
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=self.bucket)
        s3.put_object(Bucket=self.bucket, Key=self.key, Body=self.content)
        s3.create_bucket(Bucket=self.config_bucket)
        s3.put_object(Bucket=self.config_bucket, Key=self.config_key, Body=self.config)
        # Mock the email send; no exception == success
        ses = boto3.client("ses", region_name="us-east-1")
        ses.verify_email_identity(EmailAddress="bebas@gmail.com")

        # lambda_handler body
        ###############################
        bucket: str = self.event["Records"][0]["s3"]["bucket"]["name"]
        key: str = self.event["Records"][0]["s3"]["object"]["key"]

        # Read data from buckets
        config = get_config(self.config_bucket, self.config_key)
        validate_config(config)
        transactions = get_transactions(bucket, key)

        # Construct group and add transactions
        members = get_members(config["People"])
        group = Group(members)
        group.add_transactions(transactions)

        # Construct and send email
        email = SummaryEmail(config["Owner"], [p.email for p in group.members])
        email.add_body(group)
        email.add_subject(group)
        email.send()
        ###############################

        # Check items relevant to the email body
        self.assertEqual(len(transactions), 4)
        self.assertEqual(len(group.members), 2)
        g = group.members[0]
        t = group.members[1]
        self.assertEqual(g.name, "George")
        self.assertEqual(t.name, "Tootie")
        for c in Category:
            if c == Category.DINING:
                self.assertEqual(to_currency(g.get_expenses(c)), "12.66")
                self.assertEqual(to_currency(t.get_expenses(c)), "17.00")
                self.assertEqual(
                    to_currency(group.get_expenses_difference(g, t, c)), "-4.34"
                )
            else:
                self.assertEqual(to_currency(g.get_expenses(c)), "0.00")
                self.assertEqual(to_currency(t.get_expenses(c)), "0.00")
                self.assertEqual(
                    to_currency(group.get_expenses_difference(g, t, c)), "0.00"
                )
        self.assertEqual(to_currency(g.get_expenses()), "12.66")
        self.assertEqual(to_currency(t.get_expenses()), "17.00")
        self.assertEqual(to_currency(group.get_expenses_difference(g, t)), "-4.34")
        self.assertEqual(to_currency(group.get_debt(g, t, 0.47)), "1.28")
        self.assertEqual(email.sender, "bebas@gmail.com")
        self.assertEqual(email.to, ["boygeorge@gmail.com", "tuttifruity@hotmail.com"])
        self.assertEqual(email.subject, "Transactions Summary: 09/04/23 - 09/15/23")

        # Manually review the email body to make sure it looks reasonable
        # Use https://html.onlineviewer.net/
        print(email.body)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
