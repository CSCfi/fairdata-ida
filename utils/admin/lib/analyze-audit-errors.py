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

        # initialize analysis dict
        # initialize analysis["count"] to zero
        # initialize analysis["oldest"] to "9999-99-99"
        # initialize analysis["newest"] to "0000-00-00"
        # initialize analysis["errors"] to SortedDict
        # load log file data
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
        # get all error dict objects for all keys in analysis dict:
        # for each error dict object:
        #     initialize error["count"] to zero
        #     get all type dict objects for all keys in error dict:
        #     for each type dict object:
        #         initialize type["count"] to zero
        #         get all location dict objects for all keys in type dict:
        #         for each location dict object:
        #             sort objects in location["nodes"] array first by node["start"], then by node["pathname"]
        #             count total nodes in location["nodes"] array
        #             store pathname count in location["count"]
        #             add location["count"] to type["count"]
        #         add type["count"] to error["count"]
        #     add error["count"] to analysis["count"]
        # output analysis results as pretty printed json with sorted errors, but with timestamp errors last, and pathnames and fields ordered as below
        #
        # {
        #     "total": 0,
        #     "oldest": "YYYY-MM-DD",
        #     "newest": "YYYY-MM-DD",
        #     "errors": {
        #         "Node ...": {
        #             "count": 0,
        #             "files": {
        #                 "count": 0,
        #                 "staging": {
        #                     "count": 0,
        #                     "nodes": [
        #                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "abc.dat" },
        #                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "def.dat" }
        #                     ]
        #                 },
        #                 "frozen": {
        #                     "count": 0,
        #                     "nodes": [
        #                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "ghi.dat" }
        #                     ]
        #                 }
        #             },
        #             "folders": {
        #                 "count": 0,
        #                 "staging": {
        #                     "count": 0,
        #                     "nodes": [
        #                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "abc" },
        #                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "def" }
        #                     ]
        #                 },
        #                 "frozen": {
        #                     "count": 0,
        #                     "nodes": [
        #                         { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "pathname": "ghi" }
        #                     ]
        #                 }
        #             }
        #         }
        #     }
        # }

        analysis = {}
        analysis["count"] = 0
        analysis["oldest"] = "9999-99-99"
        analysis["newest"] = "0000-00-00"
        analysis["errors"] = SortedDict({})

        # TODO...

        outputAnalysis(analysis)

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("ERROR: %s\n" % str(logerror))
        sys.stderr.write("ERROR: %s\n" % str(error))
        sys.exit(1)


def nodeKey(node):
    return "%s_%s" % (node["start"], node["pathname"])


def outputAnalysis(analysis):

    sys.stdout.write('{\n')
    sys.stdout.write('    "count": %d,\n' % analysis["count"])
    sys.stdout.write('    "oldest": "%s",\n' % analysis["oldest"])
    sys.stdout.write('    "newest": "%s",\n' % analysis["newest"])
    sys.stdout.write('    "errors": {\n')

    errors = analysis["errors"]
    keys = errors.keys()

    for key in keys:
        if "timestamp" not in key:
            outputError(errors[key])

    for key in keys:
        if "timestamp" in key:
            outputError(errors[key])

    sys.stdout.write('    }\n')
    sys.stdout.write('}\n')


def outputError(error):
    return


if __name__ == "__main__":
    main()
