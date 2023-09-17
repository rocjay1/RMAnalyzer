# Create a deployment script to upload deployment package to Lambda fuction


# Dependencies located at /Users/roccodavino/.pyenv/versions/3.11.5/envs/rm_analyzer/lib/python3.11/site-packages,
# need to be zipped as in (https://docs.aws.amazon.com/lambda/latest/dg/python-package.html):
#     ~/my_function$ cd my_virtual_env/lib/python3.11/site-packages
#     ~/my_function/my_virtual_env/lib/python3.11/site-packages$ zip -r ../../../../my_deployment_package.zip
# Include main.py, classes.py, config.json in zip root as well, for example:
#     ~/my_function/my_virtual_env/lib/python3.11/site-packages$ cd ../../../../
#     ~/my_function$ zip my_deployment_package.zip lambda_function.py
#
# Use Python zipfile module to create and manage the zip file
import os
import zipfile


# Zip dependencies at /Users/roccodavino/.pyenv/versions/3.11.5/envs/rm_analyzer/lib/python3.11/site-packages
# to RMAnalyzer.zip
def zip_dependencies():
    # Get current working directory
    cwd = os.getcwd()
    # Change directory to dependencies
    os.chdir(
        "/Users/roccodavino/.pyenv/versions/3.11.5/envs/rm_analyzer/lib/python3.11/site-packages"
    )
    # Create zip file
    zipf = zipfile.ZipFile(
        cwd + "/Deployment/RMAnalyzer.zip", "w", zipfile.ZIP_DEFLATED
    )
    # Add all files in directory to zip file
    for root, dirs, files in os.walk("."):
        for file in files:
            zipf.write(os.path.join(root, file))
    # Close zip file
    zipf.close()
    # Change directory back to original
    os.chdir(cwd)


# Zip main.py, classes.py, config.json files to Deployment/RMAnalyzer.zip
def zip_main():
    with zipfile.ZipFile("Deployment/RMAnalyzer.zip", "a") as zipObj:
        # Add multiple files to the zip
        zipObj.write("main.py")
        zipObj.write("classes.py")
        zipObj.write("config.json")


def inspect_zip_contents(zip_file_path, temp_extract_dir):
    # Extract zip file to a temporary directory
    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(temp_extract_dir)

    # Print the contents of the temporary directory
    for root, dirs, files in os.walk(temp_extract_dir):
        for dir in dirs:
            print(
                os.path.join(root, dir)[len(temp_extract_dir) :]
            )  # Print relative path
        for file in files:
            print(
                os.path.join(root, file)[len(temp_extract_dir) :]
            )  # Print relative path


zip_dependencies()
zip_main()
# For testing, use:
# inspect_zip_contents('Deployment/RMAnalyzer.zip', 'Deployment/Temp')


# Update AWS Lambda function using the following command:
#     aws lambda update-function-code --function-name RMAnalyzer --zip-file fileb://RMAnalyzer.zip --profile my-dev-profile
# To handle the case where token has expired, run the following:
#     aws sso login --profile my-dev-profile
import subprocess


# Execute aws lambda update-function-code --function-name RMAnalyzer --zip-file fileb://RMAnalyzer.zip --profile my-dev-profile
# from the command line to update the Lambda function
def update_lambda_function():
    process = subprocess.Popen(
        [
            "aws",
            "lambda",
            "update-function-code",
            "--function-name",
            "RMAnalyzer",
            "--zip-file",
            "fileb://Deployment/RMAnalyzer.zip",
            "--profile",
            "my-dev-profile",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        error_message = f"{stderr.decode('utf-8')}: run 'aws sso login --profile my-dev-profile' and try again."
        print(error_message)
    else:
        success_message = stdout.decode("utf-8")
        print(success_message)


update_lambda_function()
