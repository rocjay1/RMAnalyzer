#!/usr/bin/env zsh

# cd to the directory of this script
cd "$(dirname "$0")"

# User for running CLI commands
# Create in IAM and configure with aws configure --profile rm-analyzer-test before running this script
$USER = "svc_rm_analyzer_test"

# Create a group and attach AmazonS3FullAccess and AWSLambdaFullAccess policies to it
aws iam create-group --group-name rm-analyzer-service-group-test
aws iam attach-group-policy --group-name rm-analyzer-full-access-test --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam attach-group-policy --group-name rm-analyzer-full-access-test --policy-arn arn:aws:iam::aws:policy/AWSLambda_FullAccess

# Add the user to the group
aws iam add-user-to-group --user-name $USER --group-name rm-analyzer-service-group-test

# Create the AWSLambdaBasicExecutionRole policy
aws iam create-policy --policy-name AWSLambdaBasicExecutionRole-test --policy-document file://AWSLambdaBasicExecutionRole.json

# Create the role and set max session duration to 1 hour
aws iam create-role --role-name RMAnalyzer-role-test --assume-role-policy-document file://RMAnalyzer-role.json --max-session-duration 3600

# Attach the policies to the role
aws iam attach-role-policy --role-name RMAnalyzer-role-test --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole-test
aws iam attach-role-policy --role-name RMAnalyzer-role-test --policy-arn arn:aws:iam::aws:policy/AmazonSESFullAccess

# ZIP the lambda function main.py up to create the deployment package
zip -FS ../dist/rm-analyzer.zip ../lambda_function/src/main.py