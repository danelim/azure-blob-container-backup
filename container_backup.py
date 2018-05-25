#!/usr/bin/env python3
"""Script for backing up Azure blob storage containers."""

import datetime
import logging
import os
import pathlib
import subprocess
import azure.storage.blob
import yaml

# Config file relative path
CONFIG_FILE_PATH = "config.yaml"

# Maximum number of characters for a container name
MAX_CONTAINER_CHARS = 63

def get_blob_container_url(storage_account, container):
    """Gets a blob container's URL."""
    return "https://" + storage_account + ".blob.core.windows.net/" + container

def generate_destination_container_name(source_container_name,
                                        extra_identifier="",
                                        datetimeobj=datetime.datetime.today()):
    """Generates the name of the backup container.

    To meet the length restrictions on container names imposed by Azure, feed
    the output of this function into the shorten_destination_container_name
    function.

    Args:
        source_container_name: A string containing the source container's name.
        extra_identifier: An optional string containing extra identifying
            characteristics for a destination container, used to resolve
            possible container name uniqueness issues.
        datetimeobj: A datetime object.
    Returns:
        A string containing the destination container's name.
    """
    return (datetimeobj.strftime('%Y%m%d-%H%M')
            + '-backup-'
            + extra_identifier
            + source_container_name
           )

def shorten_destination_container_name(container_name):
    """Ensures that a container name is short enough for Azure."""
    return container_name[:MAX_CONTAINER_CHARS]


# Make sure we have azcopy available
if subprocess.Popen(["bash", "-c", "type azcopy"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL).wait():
    # Non-zero return code! No good!
    print("azcopy not found")
    print("Aborting")

# Move to the directory containing the script file. Necessary for relative
# imports, while maintaining simplicity. Emphasis on simplicity. See
# https://stackoverflow.com/questions/1432924/python-change-the-scripts-working-directory-to-the-scripts-own-directory
# for details on the specific commands used.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Load YAML config file
with open(CONFIG_FILE_PATH, 'r') as yamlfile:
    config = yaml.load(yamlfile)

# Make sure the logs directory exists, and create it if so
pathlib.Path(config['relative_log_path']).mkdir(parents=True, exist_ok=True)

# Load an object that lets us interface with containers
destination_blob_service = azure.storage.blob.BlockBlobService(
    account_name=config['destination_storage_account']['storage_account'],
    account_key=config['destination_storage_account']['storage_key'],)

# For the purposes of this program the azure.storage logging to stdout isn't
# desirable, so only let it log messages when it's really important
logging.getLogger("azure.storage").setLevel(logging.CRITICAL)

# Backup each container
for source_container in config['source_containers']:
    # Make the name
    destination_container_name = generate_destination_container_name(
        source_container['container_name'])

    # Ensure that it meets the name length restrictions of Azure containers
    destination_container_name_tiny = shorten_destination_container_name(
        destination_container_name)

    # Check first if the destination container already exists. Shortening the
    # destination container name as above can cause, mostly in pathological cases,
    # non-uniqueness problems, which makes this necessary.

    # If a destination container already exists, iterate through numbers to add
    # to the container name identifier until we get a name that doesn't already
    # exist. Assume this *always* works, which is close enough to be being
    # true.
    count = 0
    while destination_blob_service.exists(
            container_name=destination_container_name_tiny):
        # Make a new name
        destination_container_name_tiny = shorten_destination_container_name(
            generate_destination_container_name(
                source_container['container_name'],
                '-' + str(count) + '-',
                ))

        # Increment the unique identifier count
        count += 1

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
             "--dest-key",
             source_container['storage_key'],
             "--recursive",                   # copy everything
             "--quiet",                       # say yes to everything
             "--verbose",                     # be verbose
            ],
            stdout=logfile,                   # output to a log file
            stderr=subprocess.STDOUT,         # combine stdout and stderr
            )
