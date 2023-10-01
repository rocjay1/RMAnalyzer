#!/usr/bin/env zsh

# Change to the directory of this script
cd "$(dirname "$0")"

# ------- CONSTANTS ------- 
readonly POLICY_DIR="../policies"
readonly LOG_FILE="../logs/teardown.log"
readonly LAMBDA_EXE_ROLE="rm-analyzer-exec-role-test"
readonly MAIN_S3_BUCKET="rm-analyzer-sheets-test"
readonly CONFIG_S3_BUCKET="rm-analyzer-config-test"
readonly LAMBDA_FUNCTION="RMAnalyzer-test"

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
    if eval "$1" > /dev/null 2>&1; then
        eval "$2" >> "$LOG_FILE" 2>&1
        echo "Done"
    else
        echo "Resource does not exist"
    fi
}

# ------- TEARDOWN ------- 
log "Tearing down the environment..."

# Set up error handling
set -e 

handle_error() {
    local exit_code="$?"
    log "An error occurred on line $1 of the script. Exiting with status code $exit_code"
    exit "$exit_code"
}

trap 'handle_error $LINENO' ERR

# Delete Lambda function
echo "Deleting Lambda function $LAMBDA_FUNCTION..."
CHECK_CMD="aws lambda get-function --function-name $LAMBDA_FUNCTION"
DELETE_CMD="aws lambda delete-function --function-name $LAMBDA_FUNCTION"
check_and_process_resource "$CHECK_CMD" "$DELETE_CMD"

# Check if role exists
CHECK_ROLE_CMD="aws iam get-role --role-name $LAMBDA_EXE_ROLE"
if eval "$CHECK_ROLE_CMD" > /dev/null 2>&1; then
    # Detach specific policies from the role
    declare -a POLICY_ARNS=(
        "arn:aws:iam::aws:policy/AmazonSESFullAccess"
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
    )
    for policy_arn in "${POLICY_ARNS[@]}"; do
        echo "Detaching policy $policy_arn from role $LAMBDA_EXE_ROLE..."
        CHECK_CMD="aws iam list-attached-role-policies --role-name $LAMBDA_EXE_ROLE --query \"AttachedPolicies[?PolicyArn=='$policy_arn'].PolicyArn\" --output text"
        PROCESS_CMD="aws iam detach-role-policy --role-name $LAMBDA_EXE_ROLE --policy-arn \"$policy_arn\""
        check_and_process_resource "$CHECK_CMD" "$PROCESS_CMD"
    done

    # Delete the role
    echo "Deleting role $LAMBDA_EXE_ROLE..."
    DELETE_ROLE_CMD="aws iam delete-role --role-name $LAMBDA_EXE_ROLE"
    eval "$DELETE_ROLE_CMD" >> "$LOG_FILE" 2>&1
    echo "Done"
else
    echo "Role $LAMBDA_EXE_ROLE does not exist"
fi

# Empty and delete S3 buckets
for bucket in $MAIN_S3_BUCKET $CONFIG_S3_BUCKET; do
    echo "Deleting S3 bucket $bucket..."
    CHECK_CMD="aws s3api head-bucket --bucket $bucket"
    DELETE_CMD="aws s3 rm s3://$bucket --recursive && aws s3api delete-bucket --bucket $bucket"
    check_and_process_resource "$CHECK_CMD" "$DELETE_CMD"
done

echo "Teardown complete!"

exit 0
