import sys
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upload_to_s3(file_path):
    pass


# Event handler class
class SpreadsheetAdditionHandler(FileSystemEventHandler):
    # When the file is dropped into the directory trigger the S3 upload 
    def on_created(self, event):
        logger.info(f'File {event.src_path} added to directory')
        upload_to_s3(event.src_path)


def main():
    # Path to directory to be monitored
    path = sys.argv[1] if len(sys.argv) > 1 else '.'

    # Create observer and event handler
    observer = Observer()
    event_handler = SpreadsheetAdditionHandler()

    # Schedule the observer to watch the directory
    observer.schedule(event_handler, path, recursive=False)

    # Start the observer
    observer.start()

    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()