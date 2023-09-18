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

import os
import sys
import json
import logging
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


DEBUG = False

METAX_API_ROOT_URL = os.environ['METAX_API_ROOT_URL']
METAX_API_USER = os.environ['METAX_API_USER']
METAX_API_PASS = os.environ['METAX_API_PASS']
METAX_API_VERSION = int(os.environ['METAX_API_VERSION'])


def main():

    try:

        if DEBUG:
            print("ARGV: %s" % json.dumps(sys.argv))

        argc = len(sys.argv)

        if argc != 2:
            raise Exception('Invalid number of arguments')
    
        report_file = sys.argv[1]

        # load report file data

        with open(report_file) as f:
           data = json.load(f)

        project = data["project"]

        nodes = data.get("invalidNodes", {})

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

            if DEBUG:
                print("NODE PATHNAME: %s" % pathname)

            node = nodes[pathname]

            modification_timestamp_error = False
            frozen_timestamp_error = False

            for error in node.get("errors", []):
                if ("modification timestamp" in error):
                    modification_timestamp_error = True
                elif ("frozen timestamp" in error):
                    frozen_timestamp_error = True

            if modification_timestamp_error or frozen_timestamp_error:

                if DEBUG:
                    print("MODIFICATION TIMESTAMP ERROR: %s" % str(modification_timestamp_error))
                    print("FROZEN TIMESTAMP ERROR: %s" % str(frozen_timestamp_error))

                node_type = get_node_type(node)
                modified_timestamp = get_filesystem_modified_timestamp(node)

                frozen_file = False
                frozen_file_pid = None
                frozen_timestamp = None

                if node_type == "file" and pathname.startswith("frozen/"):
                    frozen_file = True
                    frozen_file_pid = get_frozen_file_pid(node)
                    frozen_timestamp = get_frozen_timestamp(node)

                if modification_timestamp_error:
                    update_nextcloud_modified_timestamp(project, pathname, modified_timestamp)
                    if frozen_file:
                        update_ida_modified_timestamp(project, frozen_file_pid, modified_timestamp)
                        if METAX_API_VERSION >= 3:
                            update_metax_timestamp('modified', frozen_file_pid, modified_timestamp)
                        else:
                            update_metax_timestamp('file_modified', frozen_file_pid, modified_timestamp)

                if frozen_timestamp_error:
                    if METAX_API_VERSION >= 3:
                        update_metax_timestamp('frozen', frozen_file_pid, frozen_timestamp)
                    else:
                        update_metax_timestamp('file_frozen', frozen_file_pid, frozen_timestamp)

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("ERROR: %s\n" % str(logerror))
        sys.stderr.write("ERROR: %s\n" % str(error))
        sys.exit(1)


def get_node_type(node):
    node_type = None
    for context in [ "filesystem", "nextcloud", "ida", "metax" ]:
        context_details = node.get(context)
        if context_details:
            node_type = context_details.get("type")
        if node_type:
            if DEBUG:
                print("NODE TYPE: %s" % node_type)
            return node_type
    raise Exception("Failed to determine node type")


def get_filesystem_modified_timestamp(node):
    timestamp = node['filesystem']['modified']
    if DEBUG:
        print("MODIFICATION TIMESTAMP: %s" % timestamp)
    return timestamp


def get_frozen_timestamp(node):
    timestamp = node['ida']['frozen']
    if DEBUG:
        print("FROZEN TIMESTAMP: %s" % timestamp)
    return timestamp


def get_frozen_file_pid(node):
    pid = node['ida']['pid']
    if DEBUG:
        print("FROZEN FILE PID: %s" % pid)
    return pid


def update_nextcloud_modified_timestamp(project, pathname, timestamp):

    if DEBUG:
        print("UPDATING NEXTCLOUD MODIFIED TIMESTAMP: %s %s %s" % (project, pathname, timestamp))

    url = "%s/repairNodeTimestamp" % os.environ['IDA_API_ROOT_URL']
    data = { "pathname": pathname, "modified": timestamp }
    auth = ("%s%s" % (os.environ['PROJECT_USER_PREFIX'], project), os.environ['PROJECT_USER_PASS'])

    response = requests.post(url, auth=auth, json=data)

    if response.status_code < 200 or response.status_code > 299:
        print("Warning: Failed to update modified timestamp in Nextcloud for pathname %s: %d %s"
              % (pathname, response.status_code, response.content.decode(sys.stdout.encoding)))


def update_ida_modified_timestamp(project, file_pid, timestamp):

    if DEBUG:
        print("UPDATING IDA MODIFIED TIMESTAMP: %s %s %s" % (project, file_pid, timestamp))

    url = "%s/files/%s" % (os.environ['IDA_API_ROOT_URL'], file_pid)
    data = { "modified": timestamp }
    auth = ("%s%s" % (os.environ['PROJECT_USER_PREFIX'], project), os.environ['PROJECT_USER_PASS'])

    response = requests.post(url, auth=auth, json=data)

    if response.status_code < 200 or response.status_code > 299:
        print("Warning: Failed to update modified timestamp in IDA for pid %s: %d %s"
              % (file_pid, response.status_code, response.content.decode(sys.stdout.encoding)))


def update_metax_timestamp(field_name, file_pid, timestamp):

    if DEBUG:
        print("UPDATING METAX TIMESTAMP: %s %s %s" % (field_name, file_pid, timestamp))

    if METAX_API_VERSION >= 3:
        url = "%s/files/patch-many" % METAX_API_ROOT_URL
        data = [{ "storage_service": "ida", "storage_identifier": file_pid, field_name: timestamp }]
        # TODO: add bearer token header when supported
        response = requests.post(url, json=data)
    else:
        url = "%s/files/%s" % (METAX_API_ROOT_URL, file_pid)
        data = { field_name: timestamp }
        auth = ( METAX_API_USER, METAX_API_PASS )
        response = requests.patch(url, auth=auth, json=data)

    if response.status_code < 200 or response.status_code > 299:
        print("Warning: Failed to update %s timestamp in Metax for pid %s: %d %s"
              % (field_name, file_pid, response.status_code, response.content.decode(sys.stdout.encoding)))


if __name__ == "__main__":
    main()
