# pylint: disable-all
# Description: Unit tests for RMAnalyzer
# Author: Rocco Davino


import unittest
from unittest.mock import MagicMock
from unittest.mock import patch
import boto3
from botocore import exceptions
from moto import mock_aws
import main_v2


# Test get_s3_content output
CONTENT = 'Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible\n2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,150,MADCATS DANCE,Entertainment & Rec.,,,\n2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,,\n2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,budget,\n2023-09-12,2023-09-12,Cash,Spending Account,2121,Ally Bank,FISH MARKET,,47.71,FISH MARKET,Groceries,,,\n2023-09-15,2023-09-15,Credit Card,SavorOne,1313,Capital One,TIKICAT BAR,,17,TIKICAT BAR,Dining & Drinks,,,\n'

# Test get_config output 
CONFIG = {
    "People": [
        {
            "Name": "George", 
            "Accounts": [1234], 
            "Email": "boygeorge@gmail.com"
        },
        {
            "Name": "Tootie",
            "Accounts": [1313],
            "Email": "tuttifruity@hotmail.com",
        },
    ],
    "OwnerEmail": "bebas@gmail.com",
}


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.bucket = "rmanalyzer-sheets-tst"
        self.key = "2023-09-18T15.csv"
        self.content = CONTENT
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

    def test_lambda_handler_body(self):
        mock_get_config = MagicMock(return_value=self.config)
        mock_get_s3_content = MagicMock(return_value=self.content)
        mock_send = MagicMock()
        with patch(
                "main_v2.get_config", mock_get_config
            ), patch(
                "main_v2.get_s3_content", mock_get_s3_content
            ), patch(
                "main_v2.SummaryEmail.send", mock_send
            ):

            # lambda_handler body
            ###############################
            bucket: str = self.event["Records"][0]["s3"]["bucket"]["name"]
            key: str = self.event["Records"][0]["s3"]["object"]["key"]

             # Read data from buckets
            config = main_v2.get_config(main_v2.CONFIG_BUCKET, main_v2.CONFIG_KEY)
            main_v2.validate_config(config)
            transactions = main_v2.get_transactions(bucket, key)

            # Construct group and add transactions
            members = main_v2.get_members(config["People"])
            group = main_v2.Group(members)
            group.add_transactions(transactions)

            # Construct and send email
            email = main_v2.SummaryEmail(config["OwnerEmail"], [p.email for p in group.members])
            email.add_body(group)
            email.add_subject(group)
            email.send()
            ###############################
            
            # Check mock calls
            mock_get_config.assert_called_once_with(main_v2.CONFIG_BUCKET, main_v2.CONFIG_KEY)
            mock_get_s3_content.assert_called_once_with(self.bucket, self.key)
            mock_send.assert_called_once()

            # Check items relevant to the email body
            self.assertEqual(len(transactions), 4)
            self.assertEqual(len(group.members), 2)
            g = group.members[0]
            t = group.members[1]
            self.assertEqual(g.name, "George")
            self.assertEqual(t.name, "Tootie")
            for c in main_v2.Category:
                if c == main_v2.Category.DINING:
                    self.assertEqual(main_v2.to_currency(g.get_expenses(c)), '12.66')
                    self.assertEqual(main_v2.to_currency(t.get_expenses(c)), '17.00')
                    self.assertEqual(main_v2.to_currency(group.get_expenses_difference(g, t, c)), '-4.34')
                else:
                    self.assertEqual(main_v2.to_currency(g.get_expenses(c)), '0.00')
                    self.assertEqual(main_v2.to_currency(t.get_expenses(c)), '0.00')
                    self.assertEqual(main_v2.to_currency(group.get_expenses_difference(g, t, c)), '0.00')
            self.assertEqual(main_v2.to_currency(g.get_expenses()), '12.66')
            self.assertEqual(main_v2.to_currency(t.get_expenses()), '17.00')
            self.assertEqual(main_v2.to_currency(group.get_expenses_difference(g, t)), '-4.34')
            self.assertEqual(email.sender, "bebas@gmail.com")
            self.assertEqual(email.to, ["boygeorge@gmail.com", "tuttifruity@hotmail.com"])
            self.assertEqual(email.subject, "Transactions Summary: 09/04/23 - 09/15/23")


def main():
    unittest.main()


if __name__ == "__main__":
    main()
