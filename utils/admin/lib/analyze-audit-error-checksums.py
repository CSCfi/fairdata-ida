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

import os
import sys
import json
import logging
from hashlib import sha256
from sortedcontainers import SortedDict


DEBUG = False


def main():

    try:

        include_replication = False

        if DEBUG:
            print("ARGV: %s" % json.dumps(sys.argv))

        argc = len(sys.argv)

        if argc < 2 or argc > 3:
            raise Exception('Invalid number of arguments')
    
        report_file = sys.argv[1]

        if argc == 3:
            if sys.argv[2] == '--include-replication':
                include_replication = True
            else:
                raise Exception("Unknown argument:" % sys.argv[2])
            
        # load report file data

        with open(report_file) as f:
           data = json.load(f)

        project = data["project"]
        nodes = data.get("invalidNodes", {})

        # for each invalid node in log file data:
        #     get node type ("file" or "folder")
        #     get node location ("staging" or "frozen")
        #     if frozen file:
        #         validate_checksum = False
        #         for each error:
        #             if error starts with "Node size different ":
        #                 validate_checksum = True
        #         if validate_checksum == True:
        #             increment frozen file checked count
        #             get frozen file checksum
        #             get frozen file pathname
        #             construct full filesystem pathname
        #             generate new checksum for frozen file in filesystem
        #             if stored checksum equals new checksum:
        #                 report checksum matches filesystem copy
        #             else:
        #                 report checksum does not match filesystem copy
        #             if include_replication:
        #                 construct full replication pathname
        #                 generate new checksum for frozen file in replication
        #                 if stored checksum equals new checksum:
        #                     report checksum matches replication copy
        #                 else:
        #                     report checksum does not match replication copy
        # if frozen file checked count > 0:
        #     output analysis file

        frozen_files_checked = 0
        frozen_files = SortedDict()

        for pathname in nodes:
            node = nodes[pathname]
            node_type = get_node_type(node)
            if node_type == "file" and pathname.startswith("frozen/"):
                validate_checksum = False
                for error in node.get("errors", []):
                    if error.startswith("Node size different "):
                        validate_checksum = True
                if validate_checksum == True:
                    pathname = pathname[7:]
                    checksum = get_node_checksum(node)
                    frozen_file = {}
                    frozen_file['checksum'] = checksum
                    filesystem_pathname = generate_filesystem_pathname(project, pathname)
                    new_checksum = generate_checksum(filesystem_pathname)
                    frozen_file['filesystemCopyOK'] = (checksum == new_checksum)
                    if include_replication:
                        filesystem_pathname = generate_filesystem_pathname(project, pathname, replication = True)
                        new_checksum = generate_checksum(filesystem_pathname)
                        frozen_file['replicationCopyOK'] = (checksum == new_checksum)
                    frozen_files_checked += 1
                    frozen_files[pathname] = frozen_file

        if frozen_files_checked > 0:
            analysis = {}
            analysis["project"] = project
            analysis["includeReplication"] = include_replication
            analysis["frozenFilesChecked"] = frozen_files_checked
            analysis["frozenFiles"] = frozen_files
            output_analysis(analysis)

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


def get_node_checksum(node):
    checksum = node['ida']['checksum']
    if DEBUG:
        print("CHECKSUM: %s" % checksum)
    return checksum


def generate_filesystem_pathname(project, pathname, replication = False):
    filesystem_pathname = None
    if replication:
        filesystem_pathname = "%s/%s/%s" % (os.environ['DATA_REPLICATION_ROOT'], project, pathname)
        if DEBUG:
            print("REPLICATION PATHNAME: %s" % filesystem_pathname)
    else:
        filesystem_pathname = "%s/%s%s/files/%s/%s" % (os.environ['STORAGE_OC_DATA_ROOT'], os.environ['PROJECT_USER_PREFIX'], project, project, pathname)
        if DEBUG:
            print("FILESYSTEM PATHNAME: %s" % filesystem_pathname)
    return filesystem_pathname


def generate_checksum(filesystem_pathname):
    if not os.path.isfile(filesystem_pathname):
        return None
    block_size = 65536
    sha = sha256()
    with open(filesystem_pathname, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            sha.update(block)
    checksum = sha.hexdigest()
    if checksum.startswith('sha256:'):
        checksum = checksum[7:]
    if DEBUG:
        print("NEW CHECKSUM: %s" % checksum)
    return checksum


def output_analysis(analysis):

    # {
    #     "project": "oy5616",
    #     "includeReplication": true,
    #     "frozenFilesChecked": 6,
    #     "frozenFiles": {
    #         "frozen/VLF-tutkimus/Kannuslehto2021_09/VLF_20211227_000000": {
    #             "checksum": "6352650ca10ec970157940f62330051",
    #             "replicationCopyOK": true,
    #             "filesystemCopyOK": false
    #         },
    #         ...
    #     }
    # }

    print('{')
    print('    "project": "%s",' % analysis["project"])
    print('    "includeReplication": %s,' % json.dumps(analysis["includeReplication"]))
    print('    "frozenFilesChecked": %d,' % analysis["frozenFilesChecked"])
    print('    "frozenFiles": {')

    frozen_files = analysis["frozenFiles"]
    pathnames = frozen_files.keys()

    first = True

    for pathname in pathnames:
        if not first:
            print('        },')
        else:
            first = False
        frozen_file = frozen_files[pathname]
        print('        "%s": {' % pathname)
        print('            "checksum": "%s",' % frozen_file["checksum"])
        if frozen_file.get('replicationCopyOK', None) != None:
            print('            "replicationCopyOK": %s,' % json.dumps(frozen_file["replicationCopyOK"]))
        if frozen_file.get('filesystemCopyOK', None) != None:
            print('            "filesystemCopyOK": %s' % json.dumps(frozen_file["filesystemCopyOK"]))

    print('        }')
    print('    }')
    print('}')


if __name__ == "__main__":
    main()
