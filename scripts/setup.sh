#!/usr/bin/env zsh
# Prerequisites:
# - User created in AWS IAM
# - AWS CLI installed 
# - AWS CLI configured with a profile for the user, e.g.: aws configure --profile rm-analyzer-test

# Change to the directory of this script
cd "$(dirname "$0")"  

# ------- CONSTANTS ------- 
readonly FUNCTION_DIR="../lambda_function/src"
readonly POLICY_DIR="../policies"
readonly DIST_DIR="../dist"
readonly LOG_FILE="../logs/setup.log"
readonly CONFIG_FILE="../config/config.json"
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

# Check if AWS resources exist and create them if they don't. Redirect output to logs/setup.txt.
# $1: AWS CLI command to check if resource exists
# $2: AWS CLI command to create resource
function check_and_create_resource() {
    if eval "$1" > /dev/null 2>&1; then
        echo "Resource already created"
    else
        eval "$2" >> "$LOG_FILE" 2>&1
        echo "Done"
    fi
}

# Wait for AWS resources to be created
# $1: AWS CLI command to check if resource exists
function wait_for_resource {
    while ! eval "$1" >/dev/null 2>&1; do
        echo "Waiting for resource to be created..."
        sleep 2
    done
}

# ------- SETUP ------- 
log "Setting up the environment..."

# Set up error handling
set -e  # Exit on error

handle_error() {
    local exit_code="$?"
    log "An error occurred on line $1 of the script. Exiting with status code $exit_code"
    exit "$exit_code"
}

trap 'handle_error $LINENO' ERR

# Check that the CLI is installed
if command -v aws >/dev/null 2>&1; then
    echo "AWS CLI is installed"
else
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Check that the default profile is configured
if aws configure get aws_access_key_id >/dev/null 2>&1; then
    echo "The default AWS profile exists"
else
    echo "Error: Configure a default profile for the AWS CLI"
    exit 1
fi

# Check that the policy and role files still exist
if [ ! -f "$POLICY_DIR/trusted-entities.json" ]; then  # Check trusted-entities.json for now
    echo "Files are missing from policies directory"
    exit 1
fi

# Check that the lambda function file still exists
if [ ! -f "$FUNCTION_DIR/main.py" ]; then
    echo "File lambda_function/src/main.py does not exist"
    exit 1
fi

# Check that the dist directory exists
if [ ! -d "$DIST_DIR" ]; then
    echo "Directory dist does not exist"
    exit 1
fi

# ------- DEPLOYMENT ------- 
log "Deploying the application..."

# Get the AWS region and account ID
readonly AWS_REGION=$(aws configure get region)
readonly AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

# Create the lamba execution role and set max session duration to 1 hour
echo "Creating role $LAMBDA_EXE_ROLE..."
CHECK_CMD="aws iam get-role --role-name $LAMBDA_EXE_ROLE"
CREATE_CMD="aws iam create-role --role-name $LAMBDA_EXE_ROLE --assume-role-policy-document file://$POLICY_DIR/trusted-entities.json --max-session-duration 3600"
check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
wait_for_resource "$CHECK_CMD"

declare -a POLICY_ARNS=(
    "arn:aws:iam::aws:policy/AmazonSESFullAccess"
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
)
for policy_arn in "${POLICY_ARNS[@]}"; do
    # Check if the policy is already attached to the role
    echo "Checking if policy $policy_arn is attached to role $LAMBDA_EXE_ROLE..."
    CHECK_CMD="aws iam list-attached-role-policies --role-name $LAMBDA_EXE_ROLE | grep -q $policy_arn"
    CREATE_CMD="aws iam attach-role-policy --role-name $LAMBDA_EXE_ROLE --policy-arn \"$policy_arn\""
    check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
    wait_for_resource "$CHECK_CMD"
done

# # Attach the execution policy to the role
# echo "Attaching the AWSLambdaBasicExecutionRole policy to role $LAMBDA_EXE_ROLE..."
# CHECK_CMD="aws iam list-attached-role-policies --role-name $LAMBDA_EXE_ROLE | grep -q AWSLambdaBasicExecutionRole"
# CREATE_CMD="aws iam attach-role-policy --role-name $LAMBDA_EXE_ROLE --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
# check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
# wait_for_resource "$CHECK_CMD"

# # Attach the SES policy to the role
# echo "Attaching the AmazonSESFullAccess policy to role $LAMBDA_EXE_ROLE..."
# CHECK_CMD="aws iam list-attached-role-policies --role-name $LAMBDA_EXE_ROLE | grep -q AmazonSESFullAccess"
# CREATE_CMD="aws iam attach-role-policy --role-name $LAMBDA_EXE_ROLE --policy-arn arn:aws:iam::aws:policy/AmazonSESFullAccess"
# check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
# wait_for_resource "$CHECK_CMD"

# # Attach the S3 read access policy to the role
# echo "Attaching the AmazonS3ReadOnlyAccess policy to role $LAMBDA_EXE_ROLE..."
# CHECK_CMD="aws iam list-attached-role-policies --role-name $LAMBDA_EXE_ROLE | grep -q AmazonS3ReadOnlyAccess"
# CREATE_CMD="aws iam attach-role-policy --role-name $LAMBDA_EXE_ROLE --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
# check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
# wait_for_resource "$CHECK_CMD"

for bucket in $MAIN_S3_BUCKET $CONFIG_S3_BUCKET; do
    # Check if the bucket exists
    echo "Checking if S3 bucket $bucket exists..."
    CHECK_CMD="aws s3api head-bucket --bucket $bucket"
    CREATE_CMD="aws s3api create-bucket --bucket $bucket --region $AWS_REGION"
    check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
    wait_for_resource "$CHECK_CMD"
done

# # Create the main S3 bucket
# echo "Creating S3 bucket $MAIN_S3_BUCKET..."
# CHECK_CMD="aws s3api head-bucket --bucket $MAIN_S3_BUCKET"
# CREATE_CMD="aws s3api create-bucket --bucket $MAIN_S3_BUCKET --region $AWS_REGION"
# check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
# wait_for_resource "$CHECK_CMD"

# # Create the config S3 bucket
# echo "Creating S3 bucket $CONFIG_S3_BUCKET..."
# CHECK_CMD="aws s3api head-bucket --bucket $CONFIG_S3_BUCKET"
# CREATE_CMD="aws s3api create-bucket --bucket $CONFIG_S3_BUCKET --region $AWS_REGION"
# check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
# wait_for_resource "$CHECK_CMD"

# Upload the config file to the config S3 bucket
echo "Uploading config file to S3 bucket $CONFIG_S3_BUCKET..."
CHECK_CMD="aws s3api head-object --bucket $CONFIG_S3_BUCKET --key config.json"
CREATE_CMD="aws s3api put-object --bucket $CONFIG_S3_BUCKET --key config.json --body $CONFIG_FILE"
check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
wait_for_resource "$CHECK_CMD"

# ZIP the lambda function main.py up to create the deployment package
echo "Zipping up lambda function..."
(
  cd $FUNCTION_DIR
  zip -FS ../../dist/rm-analyzer.zip main.py
)

# Create the lambda function
echo "Creating lambda function $LAMBDA_FUNCTION..."
CHECK_CMD="aws lambda get-function --function-name $LAMBDA_FUNCTION"
CREATE_CMD="aws lambda create-function --function-name $LAMBDA_FUNCTION --runtime python3.11 --timeout 10 --role arn:aws:iam::${AWS_ACCOUNT}:role/${LAMBDA_EXE_ROLE} --handler main.lambda_handler --zip-file fileb://$DIST_DIR/rm-analyzer.zip"
check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
wait_for_resource "$CHECK_CMD" 

# Attach the resource-based policy to the lambda function
echo "Adding invoke permissions to lambda function $LAMBDA_FUNCTION..."
CHECK_CMD="aws lambda get-policy --function-name $LAMBDA_FUNCTION | grep -q s3invoke"
CREATE_CMD="aws lambda add-permission --function-name $LAMBDA_FUNCTION --statement-id s3invoke --action lambda:InvokeFunction --principal s3.amazonaws.com --source-arn arn:aws:s3:::$MAIN_S3_BUCKET --source-account $AWS_ACCOUNT"
check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
wait_for_resource "$CHECK_CMD"

# Set up the S3 bucket to trigger the lambda function
echo "Setting up S3 bucket $MAIN_S3_BUCKET to trigger lambda function $LAMBDA_FUNCTION..."
CHECK_CMD="aws s3api get-bucket-notification-configuration --bucket $MAIN_S3_BUCKET | grep -q $LAMBDA_FUNCTION"
CREATE_CMD="aws s3api put-bucket-notification-configuration --bucket $MAIN_S3_BUCKET --notification-configuration '{
    \"LambdaFunctionConfigurations\": [
        {
            \"LambdaFunctionArn\": \"arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT}:function:${LAMBDA_FUNCTION}\",
            \"Events\": [\"s3:ObjectCreated:Put\"],
            \"Id\": \"1\"
        }
    ]
}'"
check_and_create_resource "$CHECK_CMD" "$CREATE_CMD"
wait_for_resource "$CHECK_CMD"

echo "Setup complete!"

exit 0
