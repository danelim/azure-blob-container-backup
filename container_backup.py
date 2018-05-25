#!/usr/bin/env python3
"""Script for backing up Azure blob storage containers."""

import datetime
import os
import subprocess
import azure.storage.blob
import yaml

# Config file relative path
CONFIG_FILE_PATH = "config.yaml"

# Maximum number of characters for a container name
MAX_CONTAINER_CHARS = 63

def get_blob_container_url(storage_account, container):
    """Get's a blob container's URL."""
    return "https://" + storage_account + ".blob.core.windows.net/" + container


# Make sure we have azcopy available
if subprocess.Popen(["bash", "-c", "type azcopy"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL).wait():
    # Non-zero return code! No good!
    print("azcopy not found")
    print("Aborting")

# Move to the directory containing the script file. Necessary for
# relative imports, while maintaining simplicity. See
# https://stackoverflow.com/questions/1432924/python-change-the-scripts-working-directory-to-the-scripts-own-directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Load YAML config file
with open(CONFIG_FILE_PATH, 'r') as yamlfile:
    config = yaml.load(yamlfile)

# Get today's datetime
today = datetime.datetime.today()

# Load an object that lets us create new containers
destination_blob_service = azure.storage.blob.BlockBlobService(
    account_name=config['destination_storage_account']['storage_account'],
    account_key=config['destination_storage_account']['storage_key'],)

# Backup each container
for source_container in config['source_containers']:
    # Make the name
    destination_container_name = (today.strftime('%Y%m%d-%H%M')
                                  + '-'
                                  + '-backup'
                                  + '-'
                                  + source_container['container_name']
                                 )

    # Ensure that it meets the name length restrictions of Azure containers
    destination_container_name_tiny = (
        destination_container_name[:MAX_CONTAINER_CHARS])

    # Make the container
    destination_blob_service.create_container(destination_container_name_tiny)

    # Get the log file
    logpath = os.path.join(config['relative_log_path'],
                           destination_container_name + '-log.txt')

    with open(logpath, 'w') as logfile:
        # Backup the container
        subprocess.run(
            ["azcopy",
             "--source",
             get_blob_container_url(source_container['storage_account'],
                                    source_container['container_name']),
             "--source-key",
             config['destination_storage_account']['storage_key'],
             "--destination",
             get_blob_container_url(
                 config['destination_storage_account']['storage_account'],
                 destination_container_name_tiny),
             "--destination-key",
             source_container['storage_key'],
             "--recursive",                   # copy everything
             "--quiet",                       # say yes to everything
             "--verbose",                     # be verbose
            ],
            stdout=logfile,                   # output to a log file
            stderr=subprocess.STDOUT,         # combine stdout and stderr
            )
