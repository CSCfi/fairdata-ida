# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2024 Ministry of Education and Culture, Finland
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
import time
import json
import logging
import psycopg2
from collections import OrderedDict
from sortedcontainers import SortedDict
from datetime import datetime, timedelta
from utils import *

# Use UTC
os.environ['TZ'] = 'UTC'
time.tzset()


def main():

    try:

        # Arguments: ROOT MONTHS

        if len(sys.argv) < 3 or len(sys.argv) > 4:
            raise Exception('Invalid number of arguments')

        # Load service configuration and constants, and add essential definitions

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX
        config.SCRIPT = os.path.basename(sys.argv[0])
        config.PID = os.getpid()
        config.MONTHS = int(sys.argv[2])

        config.DEBUG = True # TEMP HACK

        # Initialize logging using UTC timestamps

        if config.DEBUG:
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format=LOG_ENTRY_FORMAT,
            datefmt=TIMESTAMP_FORMAT
        )
        logging.Formatter.converter = time.gmtime
        logging.info("START %s" % config.MONTHS)

        # Query the Nextcloud database and return a list of project-user-mode patterns
        # based on all change events newer than the specified number of months, if defined,
        # else for all change events.

        patterns = list()
    
        # Open database connection
    
        conn = psycopg2.connect(database=config.DBNAME,
                                user=config.DBROUSER,
                                password=config.DBROPASSWORD,
                                host=config.DBHOST,
                                port=config.DBPORT)
    
        cur = conn.cursor()
    
        # Retrieve essential details of all events newer than timestamp, if specified, else for all events
    
        query = "SELECT DISTINCT project, \"user\", mode, COUNT(*) OVER (PARTITION BY project, \"user\", mode) AS events FROM %sida_data_change" % config.DBTABLEPREFIX
    
        if config.MONTHS and config.MONTHS > 0:
            timestamp = (datetime.utcnow() - timedelta(days=int(config.MONTHS) * 30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            query = "%s WHERE timestamp > '%s'" % (query, timestamp)
    
        logging.debug("QUERY %s" % query)
    
        cur.execute(query)
        rows = cur.fetchall()
    
        logging.debug("QUERY RESULT COUNT %d" % len(rows))
    
        for row in rows:
            pattern = {
                "project": row[0],
                "user":    row[1],
                "mode":    row[2],
                "events":  row[3]
            }
            patterns.append(pattern)
    
        cur.close()
        conn.close()

        # Analyze patterns and report results

        modes = SortedDict({
            "api": OrderedDict({ "events": 0, "projects": set(), "users": set()}),
            "cli": OrderedDict({ "events": 0, "projects": set(), "users": set()}),
            "gui": OrderedDict({ "events": 0, "projects": set(), "users": set()})
        })
        projects = SortedDict()
        users = SortedDict()

        for pattern in patterns:

            project = pattern['project']
            user    = pattern['user']
            mode    = pattern['mode']
            events  = pattern['events']

            if mode not in ['system', 'unknown'] and user not in ['service', 'unknown']:

                if project not in projects:
                    projects[project] = OrderedDict({ "api": 0, "cli": 0, "gui": 0 })

                if user not in users:
                    users[user] = OrderedDict({ "api": 0, "cli": 0, "gui": 0 })

                modes[mode]['projects'].add(project)
                modes[mode]['users'].add(user)
                modes[mode]['events'] += events
                projects[project][mode] += events
                users[user][mode] += events

        # Convert sets to sorted lists suitable for for json.dumps() output and purge zero event count

        for mode, data in modes.items():
            data['projects'] = sorted(data['projects'])
            data['users'] = sorted(data['users'])
            if data['events'] == 0:
                data.pop('events')

        for project, data in projects.items():
            if data['api'] == 0:
                data.pop('api')
            if data['cli'] == 0:
                data.pop('cli')
            if data['gui'] == 0:
                data.pop('gui')

        for user, data in users.items():
            if data['api'] == 0:
                data.pop('api')
            if data['cli'] == 0:
                data.pop('cli')
            if data['gui'] == 0:
                data.pop('gui')

        # Report results

        results = {
            "counts": {
                "api": {
                    "events": modes['api']['events'],
                    "projects": len(modes['api']['projects']),
                    "users": len(modes['api']['users'])
                },
                "cli": {
                    "events": modes['cli']['events'],
                    "projects": len(modes['cli']['projects']),
                    "users": len(modes['cli']['users'])
                },
                "gui": {
                    "events": modes['gui']['events'],
                    "projects": len(modes['gui']['projects']),
                    "users": len(modes['gui']['users'])
                }
            },
            "modes": modes,
            "projects": projects,
            "users": users
        }

        print(json.dumps(results, indent=4))

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("ERROR: %s\n" % str(logerror))
        sys.stderr.write("ERROR: %s\n" % str(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
