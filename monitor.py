import sys
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import boto3
from botocore.exceptions import ClientError
import os



# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html will do
def upload_to_s3(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logger.error(e)
        return False
    return True


# Event handler class
class SpreadsheetAdditionHandler(FileSystemEventHandler):
    # When the file is dropped into the directory trigger the S3 upload 
    def on_created(self, event):
        logger.info('File %s added to directory', event.src_path)
        result = upload_to_s3(event.src_path)
        if result:
            logger.info('File %s uploaded to S3', event.src_path)
        else:
            logger.info('File %s failed to upload to S3', event.src_path)


# Start observer consisting of event handler and observer
# Path is the directory to watch
# Return a pointer to the observer so it can be stopped
def start_directory_observer(path):
    logger.info('Starting observer on directory %s', path)
    # Create observer and event handler
    observer = Observer()
    event_handler = SpreadsheetAdditionHandler()
    # Schedule the observer to watch the directory
    observer.schedule(event_handler, path, recursive=False)
    # Start the observer
    observer.start()
    return observer


# Stop the observer
def stop_directory_observer(observer):
    if observer.is_alive():
        logger.info('Stopping observer')
        observer.stop()
        observer.join()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    # Start the observer
    observer = start_directory_observer(path)
    try:
        while True:
            pass
    except KeyboardInterrupt:
        stop_directory_observer(observer)
    logger.info('Done')