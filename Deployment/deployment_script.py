import os
import zipfile
import subprocess
import argparse


# Change these variables to match your environment
PKG_DIR = "/Users/roccodavino/Repos/RMAnalyzer"
DEPL_ZIP = "/Users/roccodavino/Repos/RMAnalyzer/Deployment/RMAnalyzer.zip"
DEPS_DIR = "/Users/roccodavino/.pyenv/versions/3.11.5/envs/rm_analyzer/lib/python3.11/site-packages"


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
        zipObj.write("main.py")
        zipObj.write("classes.py")
        zipObj.write("config.json")
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
            "RMAnalyzer",
            "--zip-file",
            f"fileb://{DEPL_ZIP}",
            "--profile",
            "my-dev-profile",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(
            f"{stderr.decode('utf-8')}: run 'aws sso login --profile my-dev-profile' and try again."
        )
    else:
        print(stdout.decode("utf-8"))


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
