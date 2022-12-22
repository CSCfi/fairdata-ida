# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2022 Ministry of Education and Culture, Finland
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

import sys
import json
import logging
from pathlib import Path
from sortedcontainers import SortedList
from sortedcontainers import SortedDict


def main():

    try:

        if len(sys.argv) < 1:
            raise Exception('Invalid number of arguments')
    
        LOGFILE = sys.argv[1]

        #DEBUG = 'true' # TEMP HACK

        analysis = {}
        analysis["node_count"] = 0
        analysis["oldest"] = "9999-99-99"
        analysis["newest"] = "0000-00-00"
        analysis["errors"] = SortedDict({})

        # load log file data

        with open(LOGFILE) as f:
           data = json.load(f)

        analysis["project"] = data["project"]

        nodes = data.get("invalidNodes", {})

        # for each invalid node in log file data:
        #     get node type ("file" or "folder")
        #     get node location ("staging" or "frozen")
        #     get node pathname
        #     get date from oldest timestamp associated with node
        #     get date from newest timestamp associated with node
        #     for each error:
        #         if analysis[error][type][location]["nodes"] is None:
        #             initialize analysis[error][type][location]["nodes"] to SortedList
        #         create node object { "start": oldest, "end": newest, "pathname": pathname }
        #         append node object to analysis[error][type][location]["nodes"]
        #         if the oldest timestamp for node is older than analysis["oldest"]:
        #             set analysis["oldest"] to oldest timestamp for node
        #         if the newest timestamp for node is newer than analysis["newest"]:
        #             set analysis["newest"] to newest timestamp for node

        for pathname_key in nodes:
            node = nodes[pathname_key]
            node_type = get_node_type(node)
            if pathname_key.startswith("staging/"):
                node_location = "staging"
            else:
                node_location = "frozen"
            node_oldest_timestamp = get_oldest_timestamp(node)
            node_newest_timestamp = get_newest_timestamp(node)
            for error_key in node.get("errors", {}):
                if node_oldest_timestamp and node_newest_timestamp:
                    entry = { "start": node_oldest_timestamp, "end": node_newest_timestamp, "pathname": pathname_key }
                else:
                    entry = { "pathname": pathname_key }
                add_node_error_entry(analysis, error_key, node_type, node_location, entry)
            if node_oldest_timestamp and node_oldest_timestamp < analysis["oldest"]:
                analysis["oldest"] = node_oldest_timestamp
            if node_newest_timestamp and node_newest_timestamp > analysis["newest"]:
                analysis["newest"] = node_newest_timestamp

        if analysis["oldest"] == "9999-99-99":
            analysis["oldest"] = None

        if analysis["newest"] == "0000-00-00":
            analysis["newest"] = None

        # get all keys for errors dict objects in analysis dict:
        # for each error key:
        #     get error dict for key
        #     initialize error["node_count"] to zero
        #     get all type dict objects for all keys in error dict:
        #     for each type dict object:
        #         initialize type["node_count"] to zero
        #         get all location dict objects for all keys in type dict:
        #         for each location dict object:
        #             sort objects in location["nodes"] array first by node["start"], then by node["pathname"]
        #             count total nodes in location["nodes"] array
        #             store pathname count in location["node_count"]
        #             add location["node_count"] to type["node_count"]
        #         add type["node_count"] to error["node_count"]
        #     add error["node_count"] to analysis["node_count"]

        errors_dict = analysis.get("errors", {})
        errors_node_count = 0

        for key in errors_dict:
            error_dict = errors_dict.get(key, {})
            for node_type_group in [ "files", "folders" ]:
                group_dict = error_dict.get(node_type_group)
                if group_dict:
                    group_node_count = 0
                    for location in [ "staging", "frozen" ]:
                        location_dict = group_dict.get(location)
                        if location_dict:
                            location_node_count = 0
                            nodes_dict = location_dict.get("nodes")
                            if nodes_dict:
                                location_node_count = len(nodes_dict)
                            location_dict["node_count"] = location_node_count
                            group_dict[location] = location_dict
                            group_node_count += location_node_count
                    group_dict["node_count"] = group_node_count
                    error_dict[node_type_group] = group_dict
                    errors_node_count += group_node_count
        analysis["node_count"] = errors_node_count
        analysis["errors"] = errors_dict

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
            return node_type
    raise Exception("Failed to determine node type")


def get_oldest_timestamp(node):
    oldest_timestamp = None
    for context in [ "filesystem", "nextcloud", "ida", "metax" ]:
        context_details = node.get(context)
        if context_details:
            node_modified = context_details.get("modified")
            if node_modified and (oldest_timestamp == None or node_modified < oldest_timestamp):
                oldest_timestamp = node_modified
    if oldest_timestamp:
        return oldest_timestamp[:10]
    else:
        return None


def get_newest_timestamp(node):
    newest_timestamp = None
    for context in [ "filesystem", "nextcloud", "ida", "metax" ]:
        context_details = node.get(context)
        if context_details:
            node_modified = context_details.get("modified")
            if node_modified and (newest_timestamp == None or node_modified > newest_timestamp):
                newest_timestamp = node_modified
    if newest_timestamp:
        return newest_timestamp[:10]
    else:
        return None


def get_node_key(node):
    return "%s_%s" % (node.get("start", "0000-00-00"), node["pathname"])


def add_node_error_entry(analysis, node_error, node_type, node_location, node_entry):
    node_errors_dict = analysis.get("errors", {})
    node_error_dict = node_errors_dict.get(node_error, {})
    if node_type == "file":
        node_type_dict = node_error_dict.get("files", {})
    else:
        node_type_dict = node_error_dict.get("folders", {})
    if node_location == "staging":
        node_location_dict = node_type_dict.get("staging", {})
    else:
        node_location_dict = node_type_dict.get("frozen", {})
    nodes = node_location_dict.get("nodes", SortedList([], key=get_node_key))
    nodes.add(node_entry)
    node_location_dict["nodes"] = nodes
    node_type_dict[node_location] = node_location_dict
    if node_type == "file":
        node_error_dict["files"] = node_type_dict
    else:
        node_error_dict["folders"] = node_type_dict
    node_errors_dict[node_error] = node_error_dict
    analysis["errors"] = node_errors_dict


# {
#     "total": 0,
#     "oldest": "YYYY-MM-DD",
#     "newest": "YYYY-MM-DD",
#     "errors": {
#         "Node ...": {
#             "node_count": 0,
#             "files": {
#                 "node_count": 0,
#                 "staging": {
#                     "node_count": 0,
#                     "nodes": [
#                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "abc.dat" },
#                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "def.dat" }
#                     ]
#                 },
#                 "frozen": {
#                     "node_count": 0,
#                     "nodes": [
#                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "ghi.dat" }
#                     ]
#                 }
#             },
#             "folders": {
#                 "node_count": 0,
#                 "staging": {
#                     "node_count": 0,
#                     "nodes": [
#                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "abc" },
#                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "def" }
#                     ]
#                 },
#                 "frozen": {
#                     "node_count": 0,
#                     "nodes": [
#                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "ghi" }
#                     ]
#                 }
#             }
#         }
#     }
# }

def output_analysis(analysis):

    sys.stdout.write('{\n')
    sys.stdout.write('    "project": "%s",\n' % analysis["project"])
    sys.stdout.write('    "node_count": %d,\n' % analysis["node_count"])
    oldest = analysis.get("oldest")
    newest = analysis.get("newest")
    if oldest and newest:
        sys.stdout.write('    "oldest": "%s",\n' % oldest)
        sys.stdout.write('    "newest": "%s",\n' % newest)
    sys.stdout.write('    "errors": {\n')

    errors = analysis["errors"]
    keys = errors.keys()

    first = True
    for key in keys:
        if "timestamp" not in key:
            output_error(key, errors[key], first)
            first = False

    for key in keys:
        if "timestamp" in key:
            output_error(key, errors[key], first)
            first = False

    if not first:
        sys.stdout.write('\n')

    sys.stdout.write('    }\n')
    sys.stdout.write('}\n')


def output_error(name, error, first):
    files = error.get("files")
    files_staging = None
    files_frozen = None
    if files:
        files_staging = files.get("staging")
        if files_staging:
            files_staging_nodes = files_staging["nodes"]
        files_frozen = files.get("frozen")
        if files_frozen:
            files_frozen_nodes = files_frozen["nodes"]
    folders = error.get("folders")
    folders_staging = None
    folders_frozen = None
    if folders:
        folders_staging = folders.get("staging")
        if folders_staging:
            folders_staging_nodes = folders_staging["nodes"]
        folders_frozen = folders.get("frozen")
        if folders_frozen:
            folders_frozen_nodes = folders_frozen["nodes"]

    if not first:
        sys.stdout.write(',\n')

    sys.stdout.write('        "%s": {\n' % name)
    if files:
        sys.stdout.write('            "files": {\n')
        sys.stdout.write('                "node_count": %d,\n' % files.get("node_count", 0))
    if files_staging:
        sys.stdout.write('                "staging": {\n')
        sys.stdout.write('                    "node_count": %d,\n' % files_staging.get("node_count", 0))
        output_nodes(files_staging_nodes)
        sys.stdout.write('                }')
    if files_frozen:
        if files_staging:
            sys.stdout.write(',\n')
        sys.stdout.write('                "frozen": {\n')
        sys.stdout.write('                    "node_count": %d,\n' % files_frozen.get("node_count", 0))
        output_nodes(files_frozen_nodes)
        sys.stdout.write('                }')
    if files:
        sys.stdout.write('\n            }')
    if folders:
        if files:
            sys.stdout.write(',\n')
        sys.stdout.write('            "folders": {\n')
        sys.stdout.write('                "node_count": %d,\n' % folders.get("node_count", 0))
    if folders_staging:
        sys.stdout.write('                "staging": {\n')
        sys.stdout.write('                    "node_count": %d,\n' % folders_staging.get("node_count", 0))
        output_nodes(folders_staging_nodes)
        sys.stdout.write('                }')
    if folders_frozen:
        if folders_staging:
            sys.stdout.write(',\n')
        sys.stdout.write('                "frozen": {\n')
        sys.stdout.write('                    "node_count": %d,\n' % folders_frozen.get("node_count", 0))
        output_nodes(folders_frozen_nodes)
        sys.stdout.write('                }')
    if folders:
        sys.stdout.write('\n            }\n')
    elif files:
        sys.stdout.write('\n')
    sys.stdout.write('        }')


def output_nodes(nodes):
    sys.stdout.write('                    "nodes": [\n')
    for node in nodes:
        node_start = node.get("start")
        node_end = node.get("end")
        if node_start and node_end:
            sys.stdout.write('                        { "start": "%s", "end": "%s", "pathname": "%s" },\n' % ( node_start, node_end, node["pathname"]))
        else:
            sys.stdout.write('                        { "pathname": "%s" },\n' % node["pathname"])
    sys.stdout.write('                    ]\n')


if __name__ == "__main__":
    main()
