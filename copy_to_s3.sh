#!/usr/bin/env zsh
# Desc: Copies a CSV file to S3
# Author: Rocco Davino
# Usage: ~/Scripts/copy_to_s3.sh <CSV name>

# Check if an argument is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <CSV name>"
    exit 1
fi

# Set the CSV name to the first argument
CSV_NAME=$1

# Check if the file exists before proceeding
if [[ ! -f "Downloads/$CSV_NAME" ]]; then
    echo "Error: File Downloads/$CSV_NAME does not exist."
    exit 1
fi

# Set the S3 bucket name
BUCKET_NAME="rm-analyzer-sheets"

# Copy the file to S3
aws s3 cp "Downloads/$CSV_NAME" "s3://$BUCKET_NAME/"

# Check the exit status of the aws s3 cp command
if [ $? -eq 0 ]; then
    echo "File successfully copied to s3://$BUCKET_NAME/"
else
    echo "Error: Failed to copy the file to S3."
    exit 1
fi
