# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2023 Ministry of Education and Culture, Finland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# @author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
# @license  GNU Affero General Public License, version 3
# @link     https://research.csc.fi/
# --------------------------------------------------------------------------------
# This script loads a project audit error file (encoded in JSON) and for each
# timestamp error will update the timestamps in Nextcloud, IDA, # and Metax to
# match the last modified timestamp in the filesystem and the frozen timestamp
# in IDA, as appropriate.
# --------------------------------------------------------------------------------

import sys
import json
import logging
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from utils import *

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def main():

    try:

        # Arguments: ROOT ERROR_FILE

        argc = len(sys.argv)

        if argc != 3:
            raise Exception('Invalid number of arguments')
    
        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        config.STAGING_FOLDER_SUFFIX = constants.STAGING_FOLDER_SUFFIX
        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX

        if config.IDA_API.startswith("https://localhost/"):
            config.VERIFY_SSL = False
        else:
            config.VERIFY_SSL = True

        config.HEADERS = { 'IDA-Mode': 'System' }

        # Initialize logging using UTC timestamps

        if config.DEBUG:
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format=LOG_ENTRY_FORMAT,
            datefmt=TIMESTAMP_FORMAT)

        logging.Formatter.converter = time.gmtime

        # load report file data

        with open(sys.argv[2]) as f:
           data = json.load(f)

        config.PROJECT = data["project"]

        nodes = data.get("invalidNodes", {})

        logging.info("START %s %s" % (config.PROJECT, generate_timestamp()))

        # for each invalid node in audit report:
        #     if the node has any modified timestamp error:
        #         retrieve the last modified filesystem timestamp
        #         update the Nextcloud node timestamp to match the filesytem timestamp
        #         if the node is a frozen file:
        #             update the IDA frozen file timestamp to match the filesytem timestamp
        #             update the Metax frozen file timestamp to match the filesytem timestamp
        #     if the node has a frozen timestamp error:
        #         update the Metax frozen timestamp to match the IDA frozen timestamp

        for pathname in nodes:

            if config.DEBUG:
                sys.stderr.write("NODE PATHNAME: %s\n" % pathname)

            node = nodes[pathname]

            modification_timestamp_error = False
            frozen_timestamp_error = False

            for error in node.get("errors", []):
                if ("modification timestamp" in error):
                    modification_timestamp_error = True
                elif ("frozen timestamp" in error):
                    frozen_timestamp_error = True

            if modification_timestamp_error or frozen_timestamp_error:

                if config.DEBUG:
                    sys.stderr.write("MODIFICATION TIMESTAMP ERROR: %s\n" % str(modification_timestamp_error))
                    sys.stderr.write("FROZEN TIMESTAMP ERROR: %s\n" % str(frozen_timestamp_error))

                node_type = get_node_type(config, node)
                modified_timestamp = get_filesystem_modified_timestamp(config, node)

                frozen_file = False
                frozen_file_pid = None
                frozen_timestamp = None

                if node_type == "file" and pathname.startswith("frozen/"):
                    frozen_file = True
                    frozen_file_pid = get_frozen_file_pid(config, node)
                    frozen_timestamp = get_frozen_timestamp(config, node)

                if modification_timestamp_error:
                    update_nextcloud_modified_timestamp(config, pathname, modified_timestamp)
                    if frozen_file:
                        update_ida_modified_timestamp(config, pathname, frozen_file_pid, modified_timestamp)
                        if config.METAX_API_VERSION >= 3:
                            update_metax_timestamp(config, 'modified', pathname, frozen_file_pid, modified_timestamp)
                        else:
                            update_metax_timestamp(config, 'file_modified', pathname, frozen_file_pid, modified_timestamp)

                if frozen_timestamp_error:
                    if config.METAX_API_VERSION >= 3:
                        update_metax_timestamp(config, 'frozen', pathname, frozen_file_pid, frozen_timestamp)
                    else:
                        update_metax_timestamp(config, 'file_frozen', pathname, frozen_file_pid, frozen_timestamp)

        logging.info("DONE")

    except Exception as e:
        try:
            logging.error(str(e).strip())
        except Exception as le:
            sys.stderr.write("ERROR: %s\n" % str(le).strip())
        sys.stderr.write("ERROR: %s\n" % str(e).strip())
        sys.exit(1)


def get_node_type(config, node):
    node_type = None
    for context in [ "filesystem", "nextcloud", "ida", "metax" ]:
        context_details = node.get(context)
        if context_details:
            node_type = context_details.get("type")
        if node_type:
            if config.DEBUG:
                sys.stderr.write("NODE TYPE: %s\n" % node_type)
            return node_type
    raise Exception("Failed to determine node type")


def get_filesystem_modified_timestamp(config, node):
    timestamp = node['filesystem']['modified']
    if config.DEBUG:
        sys.stderr.write("MODIFICATION TIMESTAMP: %s\n" % timestamp)
    return timestamp


def get_frozen_timestamp(config, node):
    timestamp = node['ida']['frozen']
    if config.DEBUG:
        sys.stderr.write("FROZEN TIMESTAMP: %s\n" % timestamp)
    return timestamp


def get_frozen_file_pid(config, node):
    pid = node['ida']['pid']
    if config.DEBUG:
        sys.stderr.write("FROZEN FILE PID: %s\n" % pid)
    return pid


def update_nextcloud_modified_timestamp(config, pathname, timestamp):

    url = "%s/repairNodeTimestamp" % config.IDA_API
    data = { "pathname": pathname, "modified": timestamp }
    auth = ("%s%s" % (config.PROJECT_USER_PREFIX, config.PROJECT), config.PROJECT_USER_PASS)

    response = requests.post(url, auth=auth, headers=config.HEADERS, json=data, verify=config.VERIFY_SSL)

    if response.status_code < 200 or response.status_code > 299:
        msg = "Warning: Failed to update modified timestamp in Nextcloud to %s for %s: %d" % (
            timestamp,
            get_project_pathname(config.PROJECT, pathname),
            response.status_code
        )
        logging.warning(msg)
    else:
        msg = "Updated modified timestamp in Nextcloud to %s for %s" % (timestamp, get_project_pathname(config.PROJECT, pathname))
        logging.info(msg)
    sys.stdout.write("%s\n" % msg)


def update_ida_modified_timestamp(config, pathname, file_pid, timestamp):

    url = "%s/files/%s" % (config.IDA_API, file_pid)
    data = { "modified": timestamp }
    auth = ("%s%s" % (config.PROJECT_USER_PREFIX, config.PROJECT), config.PROJECT_USER_PASS)

    response = requests.post(url, auth=auth, headers=config.HEADERS, json=data, verify=config.VERIFY_SSL)

    if response.status_code < 200 or response.status_code > 299:
        msg = "Warning: Failed to update modified timestamp in IDA to %s for %s: %d" % (
            timestamp,
            get_project_pathname(config.PROJECT, pathname),
            response.status_code
        )
        logging.warning(msg)
    else:
        msg = "Updated modified timestamp in IDA to %s for %s" % (timestamp, get_project_pathname(config.PROJECT, pathname))
        logging.info(msg)
    sys.stdout.write("%s\n" % msg)


def update_metax_timestamp(config, field_name, pathname, file_pid, timestamp):

    if config.METAX_API_VERSION >= 3:
        url = "%s/files/patch-many" % config.METAX_API
        data = [{ "storage_service": "ida", "storage_identifier": file_pid, field_name: timestamp }]
        headers = { "Authorization": "Token %s" % config.METAX_PASS }
        response = requests.post(url, headers=headers, json=data)
    else:
        url = "%s/files/%s" % (config.METAX_API, file_pid)
        data = { field_name: timestamp }
        auth = ( config.METAX_USER, config.METAX_PASS )
        response = requests.patch(url, auth=auth, headers=config.HEADERS, json=data)

    if response.status_code < 200 or response.status_code > 299:
        msg = "Warning: Failed to update %s timestamp in Metax to %s for %s: %d" % (
            field_name,
            timestamp,
            get_project_pathname(config.PROJECT, pathname),
            response.status_code
        )
        logging.warning(msg)
    else:
        msg = "Updated %s timestamp in Metax to %s for %s" % (field_name, timestamp, get_project_pathname(config.PROJECT, pathname))
        logging.info(msg)
    sys.stdout.write("%s\n" % msg)


if __name__ == "__main__":
    main()
