# RMAnalyzer

This script is designed to generate a monthly summary of expenses from a spreadsheet. It is intended to be run as an AWS Lambda function triggered by an S3 event. Here are the key points:

## Overview

- **Author**: Rocco Davino

## Usage

This script analyzes a CSV file containing financial transaction data and sends an email summary of expenses to specified recipients. The email includes a breakdown of expenses by category and calculates the difference in expenses between two people if applicable.

### Configuration

Before using this script, make sure to configure the following settings:

1. **S3 Bucket**: The script assumes that the configuration file and CSV files are stored in an S3 bucket. You can specify the bucket name and file keys in the `CONFIG` dictionary.

```python
CONFIG = {"Bucket": "rm-analyzer-config", "Key": "config.json"}
```

2. **Email Configuration**: Ensure that the AWS SES (Simple Email Service) is set up and that the Lambda function has access to send emails using SES.

3. **People Configuration**: In the configuration file (`config.json`), you can specify the people involved, their names, email addresses, and associated account numbers. Make sure to update this configuration with your data.

```json
"Owner": "YourEmail",
"People": [
    {
        "Name": "Person1",
        "Email": "person1@example.com",
        "Accounts": [12345, 67890]
    },
    {
        "Name": "Person2",
        "Email": "person2@example.com",
        "Accounts": [54321, 98765]
    }
]
```

### Trigger

This script is designed to be triggered by an S3 event. When a new CSV file is uploaded to the specified S3 bucket, the Lambda function is triggered automatically.

## Script Structure

- **Constants**: Definitions of date formats, money formatting, and configuration settings.
- **Helper Functions**: Functions for formatting money, loading configuration, reading files from S3, and sending emails using SES.
- **Classes**: Definitions of several classes, including `Category`, `NotIgnoredFrom`, `Transaction`, `Person`, `Summary`, `SpreadsheetSummary`, `SpreadsheetParser`, and `EmailGenerator`. These classes are used for data modeling, parsing, and generating email summaries.
- **Main Function**: The `analyze_file` function is the main entry point for analyzing the uploaded CSV file, generating a summary, and sending emails.
- **Lambda Handler**: The `lambda_handler` function is the entry point for the AWS Lambda function. It retrieves information about the triggered S3 event and calls `analyze_file` to process the uploaded file.

## Example Usage

To use this script, follow these steps:

1. Upload a CSV file containing financial transaction data to the specified S3 bucket.
2. The Lambda function will be triggered automatically when the file is uploaded.
3. The script will parse the CSV data, generate a summary, and send an email to the specified recipients.
4. Recipients will receive an email with a breakdown of expenses by category and any applicable differences between individuals.
