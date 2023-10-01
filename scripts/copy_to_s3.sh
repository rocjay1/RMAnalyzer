#!/bin/bash
# Desc: Copies a file to S3
# Author: Rocco Davino

readonly S3_BUCKET="rm-analyzer-sheets-test"

# Check if an argument is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <file name>"
    exit 1
fi

# Set the CSV name to the first argument
FILE_PATH=$1

# Check if the file exists before proceeding
if [[ ! -f "$FILE_PATH" ]]; then
    echo "Error: File $FILE_PATH does not exist."
    exit 1
fi

# Copy the file to S3
aws s3 cp "$FILE_PATH" "s3://$S3_BUCKET/"

# Check the exit status of the aws s3 cp command
if [ $? -eq 0 ]; then
    echo "File successfully copied to s3://$S3_BUCKET/"
else
    echo "Error: Failed to copy the file to S3."
    exit 1
fi
