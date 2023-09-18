# Desc: Deployment script to update AWS Lambda function
# Author: Rocco Davino
# Usage: python3 Repos/RMAnalyzer/Deployment/deployment_script.py -z -d


import os
import zipfile
import subprocess
import argparse


# Path to the root of the project
PKG_DIR = "/Users/roccodavino/Repos/RMAnalyzer/RMAnalyzer"
# Path to the zip file to be uploaded to AWS Lambda
DEPL_ZIP = "/Users/roccodavino/Repos/RMAnalyzer/deployment/RMAnalyzer.zip"
# Path to the dependencies directory
DEPS_DIR = "/Users/roccodavino/.pyenv/versions/3.11.5/envs/rm_analyzer/lib/python3.11/site-packages"
# Name of the Lambda function
LAMBDA_NAME = "RMAnalyzer"


def zip_dependencies():
    print("Zipping dependencies...")
    cwd = os.getcwd()
    os.chdir(DEPS_DIR)
    with zipfile.ZipFile(DEPL_ZIP, "w") as zipObj:
        for root, dirs, files in os.walk("."):
            for file in files:
                zipObj.write(os.path.join(root, file))
    os.chdir(cwd)
    print("Done.")


def zip_main():
    cwd = os.getcwd()
    os.chdir(PKG_DIR)
    mode = (
        "w" if not args.zip_deps else "a"
    )  # Change "w" to "a" to append to existing zip file
    print("Zipping main files...")
    with zipfile.ZipFile(DEPL_ZIP, mode) as zipObj:
        for root, dirs, files in os.walk("."):
            for file in files:
                zipObj.write(os.path.join(root, file))
    os.chdir(cwd)
    print("Done.")


def update_lambda_function():
    print("Updating Lambda function...")
    process = subprocess.Popen(
        [
            "aws",
            "lambda",
            "update-function-code",
            "--function-name",
            LAMBDA_NAME,
            "--zip-file",
            f"fileb://{DEPL_ZIP}",
            "--profile",
            "my-dev-profile",  # Change this to the name of your AWS profile if needed
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(
            f"{stderr.decode('utf-8')}: may need to run 'aws sso login --profile my-dev-profile'."
        )
    else:
        print(stdout.decode("utf-8"))
        print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Update Lambda function.")
    parser.add_argument(
        "-z",
        "--zip",
        action="store_true",
        dest="zip_main",
        help="Zip main files.",
    )
    parser.add_argument(
        "-d",
        "--deps",
        action="store_true",
        dest="zip_deps",
        help="Zip dependencies.",
    )
    global args
    args = parser.parse_args()
    if args.zip_deps:
        zip_dependencies()
    if args.zip_main:
        zip_main()

    update_lambda_function()


if __name__ == "__main__":
    main()
