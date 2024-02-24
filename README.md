# RMAnalyzer

## Description

This script is designed to generate a summary of expenses from a spreadsheet containing transaction data. It is intended to be run as an AWS Lambda function triggered by an S3 event.

The data (typically the current month's transactions) is exported from my finanical app as a CSV list of raw transaction data. I wanted to summarize the data (in this case a summary of expenses per category, per person) and send a summary email in as few steps as possible.

### Goals

- **AWS**. Leverage AWS, and in particular, SES to make sending emails simple. An AWS Lambda function triggered by an S3 event was also a natural choice for this use case.
- **Python**. I wanted to convert the raw transaction data into data types and be able to enforce type safety to ensure accuracy. I implemented `mypy` to help with this. I tried to leverage object-oriented programming where appropriate to allow for a robust design that could be built upon later.
- **Tests**. Write _some_ kind of test to further ensure integrity. I settled on an integration test implemented with `unittest`. The `moto` package was very helpful. This is just a personal project, and I essentially wanted to perform a single end-to-end test to make sure the main functionality is intact before pushing to production.
- **CI/CD**. Logging into AWS to upload new Lambda function code every time I made a change quickly became tedious. My goal was to create a pipeline such that on push to `main` the code automatically deploys to AWS Lambda. I ended up achieving this with `GitHub Actions` and the Serverless Framework (`serverless`). I also use this pipeline to run the tests and check types with `mypy` before deploying as an added benefit.

### Links

- https://mypy.readthedocs.io/en/stable/getting_started.html
- https://docs.getmoto.org/en/latest/docs/getting_started.html
- https://realpython.com/python-testing/
- https://www.serverless.com/framework/docs/tutorial

## Workflow

1. The transaction data CSV is uploaded to an S3 bucket using a shell script (for now). Transaction data for some cats might look like:

```csv
Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,150,MADCATS DANCE,Entertainment & Rec.,,,
2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,,
2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,budget,
2023-09-12,2023-09-12,Cash,Spending Account,2121,Ally Bank,FISH MARKET,,47.71,FISH MARKET,Groceries,,,
2023-09-15,2023-09-15,Credit Card,SavorOne,1313,Capital One,TIKICAT BAR,,17,TIKICAT BAR,Dining & Drinks,,,
```

3. This `PUT` event triggers the Lambda function.

```python
def lambda_handler(event: Any, context: Any) -> None:
    bucket: str = event["Records"][0]["s3"]["bucket"]["name"]
    key: str = event["Records"][0]["s3"]["object"]["key"]
    ...
```

3. Config necessary for the summary is read in from a separate S3 bucket. It might look like:

```json
{
    "People": [
        {
            "Name": "George",
            "Accounts": [
                1234
            ],
            "Email": "boygeorge@gmail.com"
        },
        {
            "Name": "Tootie",
            "Accounts": [
                1313
            ],
            "Email": "tuttifruity@hotmail.com"
        }
    ],
    "Owner": "bebas@gmail.com"
}
```

It's validated, and then the transaction data is read in and parsed.

```python
...
# Read data from buckets
config = get_config(CONFIG_BUCKET, CONFIG_KEY)
validate_config(config)
transactions = get_transactions(bucket, key)
...
```

4. A `Group` of `Person` objects is constructed. Each `Person` contains a `Transaction` list. The parsed transaction data is assigned to the right people.

```python
...
# Construct group and add transactions
members = get_members(config["People"])
group = Group(members)
group.add_transactions(transactions)
...
```

5. A `SummaryEmail` is constructed and sent.

```python
...
# Construct and send email
email = SummaryEmail(config["Owner"], [p.email for p in group.members])
email.add_body(group)
email.add_subject(group)
email.send()
...
```
