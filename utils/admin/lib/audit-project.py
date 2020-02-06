# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2020 Ministry of Education and Culture, Finland
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

import importlib.util
import sys
import os
import logging
import json
import psycopg2
import dateutil.parser
from sortedcontainers import SortedDict
from datetime import datetime, timezone
from time import strftime
from subprocess import Popen, PIPE
from stat import *


def main():

    try:

        if len(sys.argv) != 4:
            raise Exception('Invalid number of arguments')
    
        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        config.STAGING_FOLDER_SUFFIX = constants.STAGING_FOLDER_SUFFIX
        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX
        config.SCRIPT = os.path.basename(sys.argv[0])
        config.PID = os.getpid()
        config.PROJECT = sys.argv[2]
        config.START = sys.argv[3]

        if [ config.DEBUG == 'true' ]:
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO
    
        if config.DEBUG == 'true':
            sys.stderr.write("--- %s ---\n" % config.SCRIPT)
            sys.stderr.write("ROOT:          %s\n" % config.ROOT)
            sys.stderr.write("DATA_ROOT:     %s\n" % config.STORAGE_OC_DATA_ROOT)
            sys.stderr.write("LOG:           %s\n" % config.LOG)
            sys.stderr.write("LOG_LEVEL:     %s\n" % config.LOG_LEVEL)
            sys.stderr.write("DBHOST:        %s\n" % config.DBHOST)
            sys.stderr.write("DBROUSER:      %s\n" % config.DBROUSER)
            sys.stderr.write("DBNAME:        %s\n" % config.DBNAME)
            sys.stderr.write("ARGS#:         %d\n" % len(sys.argv))
            sys.stderr.write("ARGS:          %s\n" % str(sys.argv))
            sys.stderr.write("PID:           %s\n" % config.PID)
            sys.stderr.write("PROJECT:       %s\n" % config.PROJECT)
            sys.stderr.write("START:         %s\n" % config.START)
    
        # Convert START ISO timestamp strings to epoch seconds

        start_datetime = dateutil.parser.isoparse(config.START)
        config.START_TS = start_datetime.replace(tzinfo=timezone.utc).timestamp()

        if config.DEBUG == 'true':
            sys.stderr.write("START_TS:      %d\n" % config.START_TS)
            sys.stderr.write("START_DT:      %s\n" % str(start_datetime))
            start_datetime_check = datetime.fromtimestamp(config.START_TS, timezone.utc)
            sys.stderr.write("START_DT_CHK:  %s\n" % str(start_datetime_check))

        # Initialize logging
        #
        # NOTE! It is expected that the system timezone is set to UTC. No timezone 
        # conversion for log entry timestamps is performed!

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format="%s %s (%s) %s" % ('%(asctime)s', config.SCRIPT, config.PID, '%(message)s'),
            datefmt="%Y-%m-%dT%H:%M:%SZ")

        # Audit the project according to the configured values

        audit_project(config)

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("%s\n" % str(logerror))
        sys.stderr.write("%s\n" % str(error))
        sys.exit(1)


def load_configuration(pathname):
    """
    Load and return as a dict variables from the main ida configuration file
    """
    module_name = "config.variables"
    try:
        # python versions >= 3.5
        module_spec = importlib.util.spec_from_file_location(module_name, pathname)
        config = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(config)
    except AttributeError:
        # python versions < 3.5
        from importlib.machinery import SourceFileLoader
        config = SourceFileLoader(module_name, pathname).load_module()
    return config


def add_nextcloud_nodes(nodes, counts, config):
    """
    Query the Nextcloud database and add all relevant node stats to the auditing data objects
    provided and according to the configured values provided, limited to nodes modified before
    the auditing started.
    """

    # Open database connection 

    conn = psycopg2.connect(
               database=config.DBNAME,
               user=config.DBROUSER,
               password=config.DBROPASSWORD,
               host=config.DBHOST,
               port=config.DBPORT)

    cur = conn.cursor()

    # Retrieve PSO storage id for project

    cur.execute("SELECT numeric_id from %sstorages WHERE id = 'home::%s%s' LIMIT 1"
                % (config.DBTABLEPREFIX, config.PROJECT_USER_PREFIX, config.PROJECT))

    rows = cur.fetchall()

    if len(rows) != 1:
        raise Exception("Failed to retrieve storage id for project %s" % config.PROJECT)

    storage_id = rows[0][0]

    if config.DEBUG == 'true':
        sys.stderr.write("STORAGE_ID:    %d\n" % (storage_id))

    # Select all records for project nodes created and last modified before START timestamp

    cur.execute("SELECT path, mimetype, size, mtime FROM %sfilecache WHERE storage = %d AND path ~ 'files/%s\+?/' AND mtime < %d"
                 % (config.DBTABLEPREFIX, storage_id, config.PROJECT, config.START_TS))

    rows = cur.fetchall()

    # Construct auditing data object for all selected nodes

    for row in rows:

        #if config.DEBUG == 'true':
        #    sys.stderr.write("%s\n" % (str(row)))

        pathname = row[0][5:]
        project_name_len = len(config.PROJECT)
        if pathname[(project_name_len + 1)] == '+':
            pathname = "staging/%s" % pathname[(project_name_len + 3):]
        else:
            pathname = "frozen/%s" % pathname[(project_name_len + 2):]

        node_type = 'file'

        if row[1] == 2:
            node_type = 'folder'

        if node_type == 'file':
            node = {'nextcloud': {'type': node_type, 'size': row[2], 'modified': row[3]}}
        else:
            node = {'nextcloud': {'type': node_type}}

        nodes[pathname] = node

        counts['nextcloudNodeCount'] = counts['nextcloudNodeCount'] + 1

        #if config.DEBUG == 'true':
        #    sys.stderr.write("%s %s\n" % (pathname, str(nodes[pathname]['nextcloud'])))

    # Close database connection and return auditing data object

    conn.close()


def add_filesystem_nodes(nodes, counts, config):
    """
    Crawl the filesystem and add all relevant node stats to the auditing data objects
    provided and according to the configured values provided, limited to nodes modified
    before the start of the auditing
    """

    pso_root = "%s/%s%s/" % (config.STORAGE_OC_DATA_ROOT, config.PROJECT_USER_PREFIX, config.PROJECT)

    command = "cd %s; find files -mindepth 2" % (pso_root)

    #if config.DEBUG == 'true':
    #    sys.stderr.write("FIND_COMMAND:  %s\n" % command)

    pipe = Popen(command, shell=True, stdout=PIPE)

    for line in pipe.stdout:

        pathname = line.strip().decode(sys.stdout.encoding)
        full_pathname = "%s%s" % (pso_root, pathname)

        fsstat = os.stat(full_pathname)

        fsmodts = int(fsstat.st_mtime)

        if fsmodts < config.START_TS:

            pathname = pathname[5:]
            project_name_len = len(config.PROJECT)
            if pathname[(project_name_len + 1)] == '+':
                pathname = "staging/%s" % pathname[(project_name_len + 3):]
            else:
                pathname = "frozen/%s" % pathname[(project_name_len + 2):]

            node_type = 'file'

            if S_ISDIR(fsstat.st_mode):
                node_type = 'folder'

            if node_type == 'file':
                node_details = {'type': node_type, 'size': fsstat.st_size, 'modified': fsmodts}
            else:
                node_details = {'type': node_type}

            try:
                node = nodes[pathname]
                node['filesystem'] = node_details
            except KeyError:
                node = {}
                node['filesystem'] = node_details
                nodes[pathname] = node
    
            counts['filesystemNodeCount'] = counts['filesystemNodeCount'] + 1

            #if config.DEBUG == 'true':
            #    sys.stderr.write("%s %s\n" % (pathname, str(nodes[pathname]['filesystem'])))


def add_frozen_files(nodes, counts, config):
    """
    Query the IDA API and add all relevant frozen file stats to the auditing data objects
    provided and according to the configured values provided, limited to actively frozen files
    which have no pending metadata postprocessing (i.e. only frozen files with metadata timestamps
    and no cleared or removed timestamps, and a metadata timestamp less than the start timestamp)
    """
    # TODO


def add_metax_files(nodes, counts, config):
    """
    Query the Metax API and add all relevant frozen file stats to the auditing data objects
    provided and according to the configured values provided, limited to actively frozen files
    published to metax before the start timestamp.
    """
    # TODO


def audit_project(config):
    """
    Audit a project according to the configured values provided
    """

    logging.info("START %s %s" % (config.PROJECT, config.START))

    counts = {'nextcloudNodeCount': 0, 'filesystemNodeCount': 0, 'frozenFileCount': 0, 'metaxFileCount': 0}
    nodes = SortedDict({})

    # Populate auditing data objects for all nodes in scope according to the configured values provided

    add_nextcloud_nodes(nodes, counts, config)
    add_filesystem_nodes(nodes, counts, config)
    add_frozen_files(nodes, counts, config)
    add_metax_files(nodes, counts, config)

    # Iterate over all nodes, logging and reporting all errors

    invalidNodes = SortedDict({})
    invalidNodeCount = 0

    for pathname, node in nodes.items():

        errors = []

        # Determine whether the node is in the frozen area based on the pathname
    
        is_frozen_area_pathname = False

        if pathname[:1] == 'f':
            is_frozen_area_pathname = True

        # Determine where the node exists

        try:
            filesystem = node['filesystem']
        except:
            filesystem = False

        try:
            nextcloud = node['nextcloud']
        except:
            nextcloud = False

        try:
            frozen = node['frozen']
        except:
            frozen = False

        try:
            metax = node['metax']
        except:
            metax = False

        # Check that node exists in both filesystem and Nextcloud, and with same type

        if filesystem and not nextcloud:
            errors.append('Node exists in filesystem but not in Nextcloud')

        if nextcloud and not filesystem:
            errors.append('Node exists in Nextcloud but not in filesystem')

        if filesystem and nextcloud and filesystem['type'] != nextcloud['type']:
            errors.append('Node type different for filesystem and Nextcloud')

        # If filesystem and nextcloud agree node is a file, apply further checks...        

        if filesystem and filesystem['type'] == 'file' and nextcloud and nextcloud['type'] == 'file':

            if filesystem and nextcloud and filesystem['size'] != nextcloud['size']:
                errors.append('Node size different for filesystem and Nextcloud')

            if filesystem and nextcloud and filesystem['modified'] != nextcloud['modified']:
                errors.append('Node modification timestamp different for filesystem and Nextcloud')

        # If pathname is in the frozen area, and is known to either IDA or Metax, check that
        # the file is registered both as frozen and is published to metax, is also known as a
        # file by the filesystem and Nextcloud, is replicated properly, and that all relevant
        # file details agree

        if is_frozen_area_pathname:

            # TODO: incorporate checks for IDA-Metax-Replication agreement for frozen files:
            # check if frozen details exist
            # check if metax details exist
            # check if known as file in filesystem
            # check if known as file in Nextcloud

            # if known in both frozen and filesystem, check if file details agree (size, modified)
            if frozen and filesystem:
                pass
                # TODO

            # if known in both frozen and Nextcloud, check if file details agree (size, modified)
            if frozen and nextcloud:
                pass
                # TODO

            # if known in both frozen and metax, check if file details agree (type, size, modified, checksum)
            if frozen and metax:
                pass
                # TODO

            # if known in frozen and replication timestamp defined in frozen details
            try:
                replicated = node['frozen']['replicated']
                # check if replicated file exists
                # check if frozen and replicated file sizes agree
                # TODO
            except:
                pass
    
        # If any errors were detected, add the node to the set of invalid nodes
        # and increment the invalid node count

        if len(errors) > 0:
            node['errors'] = errors
            invalidNodes[pathname] = node
            invalidNodeCount = invalidNodeCount + 1

    # Output report

    sys.stdout.write("{\n")
    sys.stdout.write("\"project\": %s,\n" % str(json.dumps(config.PROJECT)))
    sys.stdout.write("\"start\": %s,\n" % str(json.dumps(config.START)))
    sys.stdout.write("\"end\": %s,\n" % str(json.dumps(strftime("%Y-%m-%dT%H:%M:%SZ"))))
    sys.stdout.write("\"nextcloudNodeCount\": %d,\n" % counts['nextcloudNodeCount'])
    sys.stdout.write("\"filesystemNodeCount\": %d,\n" % counts['filesystemNodeCount'])
    """
    # TODO include in report once auditing of frozen files is completed
    sys.stdout.write("\"frozenFileCount\": %d,\n" % counts['frozenFileCount'])
    sys.stdout.write("\"metaxFileCount\": %d,\n" % counts['metaxFileCount'])
    """
    sys.stdout.write("\"invalidNodeCount\": %d" % invalidNodeCount)

    if invalidNodeCount > 0:

        first = True

        sys.stdout.write(",\n\"invalidNodes\": {\n")

        for pathname, node in invalidNodes.items():

            if not first:
                sys.stdout.write(",\n")

            first = False

            sys.stdout.write("%s: {" % str(json.dumps(pathname)))
            sys.stdout.write("\n\"errors\": %s" % str(json.dumps(node['errors'])))

            try:
                json_out = json.dumps(node['filesystem'], sort_keys=True)
                sys.stdout.write(",\n\"filesystem\": %s" % str(json_out))
            except:
                pass

            try:
                json_out = json.dumps(node['nextcloud'], sort_keys=True)
                sys.stdout.write(",\n\"nextcloud\": %s" % str(json_out))
            except:
                pass

            """
            # TODO include in report once auditing of frozen files is completed
            try:
                json_out = json.dumps(node['frozen'], sort_keys=True)
                sys.stdout.write(",\n\"frozen\": %s" % str(json_out))
            except:
                pass

            try:
                json_out = json.dumps(node['metax'], sort_keys=True)
                sys.stdout.write(",\n\"metax\": %s" % str(json_out))
            except:
                pass

            try:
                json_out = json.dumps(node['replication'], sort_keys=True)
                sys.stdout.write(",\n\"replication\": %s" % str(json_out))
            except:
                pass
            """
        
            sys.stdout.write("\n}")

        sys.stdout.write("\n}\n")

    sys.stdout.write("}\n")

    logging.info("DONE")


if __name__ == "__main__":
    main()
