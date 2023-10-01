#!/bin/bash
# Description: Cleans up the AWS environment for the application
# Prerequisites: Same as setup.sh
# Author: Rocco Davino

# Change to the directory of this script
cd "$(dirname "$0")"

# ------- CONSTANTS ------- 
readonly POLICY_DIR="../policies"
readonly LOG_FILE="../logs/cleanup.log"
# The following variables need to match the values in setup.sh
readonly LAMBDA_EXE_ROLE="rm-analyzer-exec-role"
readonly MAIN_S3_BUCKET="rm-analyzer-sheets"
readonly CONFIG_S3_BUCKET="rm-analyzer-config"
readonly LAMBDA_FUNCTION="RMAnalyzer"

# ------- FUNCTIONS ------- 
# Log a message to the log file
# $1: Message to log
function log() {
    local message="$1"
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $message" | tee -a "$LOG_FILE"
}

# Check if AWS resources exist and process them if they do. 
# $1: AWS CLI command to check if resource exists
# $2: AWS CLI command to process resource
function check_and_process_resource() {
    local check_cmd="$1"
    local process_cmd="$2"
    if eval "$check_cmd" > /dev/null 2>&1; then
        eval "$process_cmd" >> "$LOG_FILE" 2>&1
        log "Resource deleted"
    else
        log "Resource does not exist"
    fi
}

# Handle errors
# $1: Line number of error
handle_error() {
    local exit_code="$?"
    local line_number="$1"
    log "An error occurred on line $line_number of the script" 
    log "Exiting with status code $exit_code"
    exit "$exit_code"
}

# ------- TEARDOWN ------- 
log "Cleaning up the environment..."

# Set up error handling
set -e 
trap 'handle_error $LINENO' ERR

# Delete Lambda function
log "Deleting Lambda function $LAMBDA_FUNCTION..."
CHECK_CMD="aws lambda get-function --function-name $LAMBDA_FUNCTION"
DELETE_CMD="aws lambda delete-function --function-name $LAMBDA_FUNCTION"
check_and_process_resource "$CHECK_CMD" "$DELETE_CMD"

# Check if role exists
CHECK_ROLE_CMD="aws iam get-role --role-name $LAMBDA_EXE_ROLE"
if eval "$CHECK_ROLE_CMD" > /dev/null 2>&1; then

    declare -a POLICY_ARNS=(
        "arn:aws:iam::aws:policy/AmazonSESFullAccess"
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
    )
    for policy_arn in "${POLICY_ARNS[@]}"; do
        log "Detaching policy $policy_arn from role $LAMBDA_EXE_ROLE..."
        CHECK_CMD="aws iam list-attached-role-policies --role-name $LAMBDA_EXE_ROLE | grep -q $policy_arn"
        PROCESS_CMD="aws iam detach-role-policy --role-name $LAMBDA_EXE_ROLE --policy-arn $policy_arn"
        check_and_process_resource "$CHECK_CMD" "$PROCESS_CMD"
    done

    log "Deleting role $LAMBDA_EXE_ROLE..."
    DELETE_ROLE_CMD="aws iam delete-role --role-name $LAMBDA_EXE_ROLE"
    eval "$DELETE_ROLE_CMD" >> "$LOG_FILE" 2>&1
    log "Resource deleted"

else
    log "Role $LAMBDA_EXE_ROLE does not exist"
fi

# Empty and delete S3 buckets
for bucket in $MAIN_S3_BUCKET $CONFIG_S3_BUCKET; do
    log "Deleting S3 bucket $bucket..."
    CHECK_CMD="aws s3api head-bucket --bucket $bucket"
    DELETE_CMD="aws s3 rm s3://$bucket --recursive && aws s3api delete-bucket --bucket $bucket"
    check_and_process_resource "$CHECK_CMD" "$DELETE_CMD"
done

log "Cleanup complete!"

exit 0
