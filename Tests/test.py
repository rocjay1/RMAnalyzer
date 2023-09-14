from main import *
import unittest
import boto3
from botocore import exceptions
from moto import mock_s3, mock_ses


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
        subject = "Monthly Summary for 09/23"
        html_body = """<html><head></head><body><h1>Summary for 09/23:</h1>
<table border='1'>
<thead>
<tr>
<th>Dining & Drinks</th>
<th>Groceries</th>
<th>Entertainment & Rec.</th>
<th><strong>Total</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td>Rocco</td>
<td>148.58</td>
<td>0</td>
<td>0</td>
<td>148.58</td>
</tr>
<tr>
<td>Tori</td>
<td>0</td>
<td>0</td>
<td>0</td>
<td>0</td>
</tr>
<tr>
<td>Diff (Rocco - Tori)</td>
<td>148.58</td>
<td>0</td>
<td>0</td>
<td>148.58</td>
</tr>
</tbody>
</table>
</body>
</html>"""

        # Call the function
        response = send_email(source, to_addresses, subject, html_body)

        self.assertIn("MessageId", response)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
