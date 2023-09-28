#!/usr/bin/env zsh
# Desc: Updates the AWS Lambda function code.
# Assumptions:
#   - The AWS CLI is installed and configured
#   - The AWS Lambda function has been created and configured
#   - All the necessary files are in the same directory as this script (which is the case if you cloned the repo)
# Author: Rocco Davino
# Usage: ./update_function.sh
# Notes: Make the script executable with chmod +x update_function.sh

# Get the directory path of the current script
DIR_PATH="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

# Change to that directory
cd "$DIR_PATH"

# Define the file and the target ZIP name
FILE_NAME="main.py"
ZIP_NAME="rm.zip"

# Check if the file exists
if [[ ! -f "$FILE_NAME" ]]; then
    echo "Error: $FILE_NAME does not exist."
    exit 1
fi

# Zip the file
zip -FS "$ZIP_NAME" "$FILE_NAME"

# Check the success of the ZIP operation
if [[ $? -eq 0 ]]; then
    echo "$FILE_NAME added to $ZIP_NAME successfully!"
else
    echo "Error: Failed to add $FILE_NAME to $ZIP_NAME."
    exit 1
fi

# Set the function name
FUNCTION_NAME="RMAnalyzer"

# Deploy the ZIP file to AWS Lambda
aws lambda update-function-code --function-name "$FUNCTION_NAME" --zip-file "fileb://$ZIP_NAME"

# Check the success of the deployment
if [[ $? -eq 0 ]]; then
    echo "$ZIP_NAME deployed to AWS Lambda successfully!"
else
    echo "Error: Failed to deploy $ZIP_NAME to AWS Lambda."
    exit 1
fi