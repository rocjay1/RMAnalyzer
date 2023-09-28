#!/usr/bin/env zsh

# Check if an argument is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <CSV name>"
    exit 1
fi

CSV_NAME=$1

# Check if the file exists before proceeding
if [[ ! -f "Downloads/$CSV_NAME" ]]; then
    echo "Error: File Downloads/$CSV_NAME does not exist."
    exit 1
fi

# Copy the file to S3
aws s3 cp "Downloads/$CSV_NAME" "s3://rm-analyzer-sheets/"

# Check the exit status of the aws s3 cp command
if [ $? -eq 0 ]; then
    echo "File successfully copied to s3://rm-analyzer-sheets/"
else
    echo "Error: Failed to copy the file to S3."
    exit 1
fi
