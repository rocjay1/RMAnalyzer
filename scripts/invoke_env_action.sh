#!/bin/bash
# Description: This script builds or tears down the AWS environment for the application
# Usage: ./invoke_env_action.sh <action>
# Actions: build, teardown
# Example: ./invoke_env_action.sh build
# Prerequisites:
# - User created in AWS IAM with admin access
# - AWS CLI installed and configured with default profile
# - config.json file in config directory filled out with the correct values
# Author: Rocco Davino

# Change to the directory of this script
cd "$(dirname "$0")"  

# ------- CONSTANTS ------- 
readonly FUNCTION_DIR="../lambda_function/src"  # Dirs relative to scripts/
readonly POLICY_DIR="../policies"
readonly DIST_DIR="../dist"
readonly LOG_FILE="../logs/invoke_env_action.log"
readonly CONFIG_FILE="../config/config.json"
readonly LAMBDA_EXE_ROLE="rm-analyzer-exec-role"
readonly MAIN_S3_BUCKET="rm-analyzer-sheets-prd"
readonly CONFIG_S3_BUCKET="rm-analyzer-config-prd"  # Needs to be set in main.py as well
readonly LAMBDA_FUNCTION="RMAnalyzer-prd"
readonly POLICY_ARNS=(
    "arn:aws:iam::aws:policy/AmazonSESFullAccess"
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
)

# ------- FUNCTIONS ------- 
# Log a message to the log file
# $1: Message to log
function log() {
    local message="$1"
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $message" | tee -a "$LOG_FILE"
}

# Handle errors
# $1: Line number of error
function handle_error() {
    local exit_code="$?"
    local line_number="$1"
    log "An error occurred on line $line_number of the script" 
    log "Exiting with status code $exit_code"
    exit "$exit_code"
}

# Check if AWS resources exist and create them if they don't. Redirect output to logs/setup.txt.
# $1: AWS CLI command to check if resource exists
# $2: AWS CLI command to create resource
function check_and_create_resource() {
    local check_cmd="$1"
    local create_cmd="$2"
    if eval "$check_cmd" > /dev/null 2>&1; then
        log "Resource already exists"
    else
        eval "$create_cmd" >> "$LOG_FILE" 2>&1
        log "Resource created"
    fi
}

# Wait for AWS resources to be created
# $1: AWS CLI command to check if resource exists
function wait_for_resource() {
    local check_cmd="$1"
    while ! eval "$check_cmd" >/dev/null 2>&1; do
        log "Waiting for resource to be created..."
        sleep 5
    done
}

# Check if AWS resources exist and delete them if they do 
# $1: AWS CLI command to check if resource exists
# $2: AWS CLI command to process resource
function check_and_delete_resource() {
    local check_cmd="$1"
    local process_cmd="$2"
    if eval "$check_cmd" > /dev/null 2>&1; then
        eval "$process_cmd" >> "$LOG_FILE" 2>&1
        log "Resource deleted"
    else
        log "Resource does not exist"
    fi
}

# Build the AWS environment for the application
function build_env() {
    log "Building the application..."

    # Initialize cmd variables
    local check_cmd=""
    local create_cmd=""

    # Get the AWS region and account ID
    local aws_region=$(aws configure get region)
    local aws_account=$(aws sts get-caller-identity --query Account --output text)

    # Create the lamba execution role and set max session duration to 1 hour
    log "Creating role $LAMBDA_EXE_ROLE..."
    check_cmd="aws iam get-role --role-name $LAMBDA_EXE_ROLE"
    create_cmd="aws iam create-role --role-name $LAMBDA_EXE_ROLE --assume-role-policy-document file://$POLICY_DIR/trusted-entities.json --max-session-duration 3600"
    check_and_create_resource "$check_cmd" "$create_cmd"
    wait_for_resource "$check_cmd"

    # Attach the managed policies to the role
    for policy_arn in "${POLICY_ARNS[@]}"; do
        log "Attaching policy $policy_arn to role $LAMBDA_EXE_ROLE..."
        check_cmd="aws iam list-attached-role-policies --role-name $LAMBDA_EXE_ROLE | grep -q $policy_arn"
        create_cmd="aws iam attach-role-policy --role-name $LAMBDA_EXE_ROLE --policy-arn $policy_arn"
        check_and_create_resource "$check_cmd" "$create_cmd"
        wait_for_resource "$check_cmd"
    done

    # Create the S3 buckets
    for bucket in $MAIN_S3_BUCKET $CONFIG_S3_BUCKET; do
        log "Creating S3 bucket $bucket..."
        check_cmd="aws s3api head-bucket --bucket $bucket"
        create_cmd="aws s3api create-bucket --bucket $bucket --region $aws_region"
        check_and_create_resource "$check_cmd" "$create_cmd"
        wait_for_resource "$check_cmd"
    done

    # Upload the config file to the config S3 bucket
    log "Uploading config file to S3 bucket $CONFIG_S3_BUCKET..."
    check_cmd="aws s3api head-object --bucket $CONFIG_S3_BUCKET --key config.json"
    create_cmd="aws s3api put-object --bucket $CONFIG_S3_BUCKET --key config.json --body $CONFIG_FILE"
    check_and_create_resource "$check_cmd" "$create_cmd"
    wait_for_resource "$check_cmd"

    # ZIP the lambda function main.py up to create the deployment package
    log "Zipping up lambda function..."
    (
        cd $FUNCTION_DIR
        zip -FS ../$DIST_DIR/rm-analyzer.zip main.py >> "../$LOG_FILE" 2>&1
    )

    # Create the lambda function
    log "Creating lambda function $LAMBDA_FUNCTION..."
    check_cmd="aws lambda get-function --function-name $LAMBDA_FUNCTION"
    create_cmd="aws lambda create-function --function-name $LAMBDA_FUNCTION --runtime python3.11 --timeout 10 --role arn:aws:iam::${aws_account}:role/${LAMBDA_EXE_ROLE} --handler main.lambda_handler --zip-file fileb://$DIST_DIR/rm-analyzer.zip"
    check_and_create_resource "$check_cmd" "$create_cmd"
    wait_for_resource "$check_cmd" 

    # Attach the resource-based policy to the lambda function
    log "Adding invoke permissions to lambda function $LAMBDA_FUNCTION..."
    check_cmd="aws lambda get-policy --function-name $LAMBDA_FUNCTION | grep -q s3invoke"
    create_cmd="aws lambda add-permission --function-name $LAMBDA_FUNCTION --statement-id s3invoke --action lambda:InvokeFunction --principal s3.amazonaws.com --source-arn arn:aws:s3:::$MAIN_S3_BUCKET --source-account $aws_account"
    check_and_create_resource "$check_cmd" "$create_cmd"
    wait_for_resource "$check_cmd"

    # Set up the S3 bucket to trigger the lambda function
    log "Setting up S3 bucket $MAIN_S3_BUCKET to trigger lambda function $LAMBDA_FUNCTION..."
    check_cmd="aws s3api get-bucket-notification-configuration --bucket $MAIN_S3_BUCKET | grep -q $LAMBDA_FUNCTION"
    create_cmd="aws s3api put-bucket-notification-configuration --bucket $MAIN_S3_BUCKET --notification-configuration '{
        \"LambdaFunctionConfigurations\": [
            {
                \"LambdaFunctionArn\": \"arn:aws:lambda:${aws_region}:${aws_account}:function:${LAMBDA_FUNCTION}\",
                \"Events\": [\"s3:ObjectCreated:Put\"],
                \"Id\": \"1\"
            }
        ]
    }'"
    check_and_create_resource "$check_cmd" "$create_cmd"
    wait_for_resource "$check_cmd"

    log "Build complete!"
    log "Use 'aws s3 cp <CSV path> s3://$MAIN_S3_BUCKET/' to get started" 
}

# Tear down the AWS environment for the application
function teardown_env() {
    log "Tearing down the environment..."

    # Initialize cmd variables
    local check_cmd=""
    local delete_cmd=""

    # Delete Lambda function
    log "Deleting Lambda function $LAMBDA_FUNCTION..."
    check_cmd="aws lambda get-function --function-name $LAMBDA_FUNCTION"
    delete_cmd="aws lambda delete-function --function-name $LAMBDA_FUNCTION"
    check_and_delete_resource "$check_cmd" "$delete_cmd"

    # Check if role exists
    local check_role_cmd="aws iam get-role --role-name $LAMBDA_EXE_ROLE"
    if eval "$check_role_cmd" > /dev/null 2>&1; then

        for policy_arn in "${POLICY_ARNS[@]}"; do
            log "Detaching policy $policy_arn from role $LAMBDA_EXE_ROLE..."
            check_cmd="aws iam list-attached-role-policies --role-name $LAMBDA_EXE_ROLE | grep -q $policy_arn"
            delete_cmd="aws iam detach-role-policy --role-name $LAMBDA_EXE_ROLE --policy-arn $policy_arn"
            check_and_delete_resource "$check_cmd" "$delete_cmd"
        done

        log "Deleting role $LAMBDA_EXE_ROLE..."
        local delete_role_cmd="aws iam delete-role --role-name $LAMBDA_EXE_ROLE"
        eval "$delete_role_cmd" >> "$LOG_FILE" 2>&1
        log "Resource deleted"

    else
        log "Role $LAMBDA_EXE_ROLE does not exist"
    fi

    # Empty and delete S3 buckets
    for bucket in $MAIN_S3_BUCKET $CONFIG_S3_BUCKET; do
        log "Deleting S3 bucket $bucket..."
        check_cmd="aws s3api head-bucket --bucket $bucket"
        delete_cmd="aws s3 rm s3://$bucket --recursive && aws s3api delete-bucket --bucket $bucket"
        check_and_delete_resource "$check_cmd" "$delete_cmd"
    done

    log "Teardown complete!"
}

# Set up the script environment
function setup() {
    log "Setting up the script environment..."

    set -e  # Exit on error
    trap 'handle_error $LINENO' ERR  # Handle errors

    # Check that the CLI is installed
    if command -v aws >/dev/null 2>&1; then
        log "AWS CLI is installed"
    else
        log "Error: AWS CLI is not installed"
        exit 1
    fi

    # Check that the default profile is configured
    if aws configure get aws_access_key_id >/dev/null 2>&1; then
        log "The default AWS profile exists"
    else
        log "Error: Configure a default profile for the AWS CLI"
        exit 1
    fi

    # Check trusted-entities.json still exists
    if [ ! -f "$POLICY_DIR/trusted-entities.json" ]; then
        log "File policies/trusted-entities.json does not exist"
        exit 1
    fi

    # Check that the lambda function file still exists
    if [ ! -f "$FUNCTION_DIR/main.py" ]; then
        log "File lambda_function/src/main.py does not exist"
        exit 1
    fi

    # Check that the dist directory still exists
    if [ ! -d "$DIST_DIR" ]; then
        log "Directory dist does not exist"
        exit 1
    fi
}

# ------- MAIN -------
setup
# Require at least one argument
# If no arguments are passed, or the first argument "build", build the environment
# If the first argument is "teardown", tear down the environment
if [ $# -eq 0 ] || [ "$1" == "build" ]; then
    build_env
elif [ "$1" == "teardown" ]; then
    teardown_env
else
    log "Error: Invalid argument"
    exit 1
fi

exit 0