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

import importlib.util
import sys
import os
import time
import requests
import dateutil.parser
from datetime import datetime
from hashlib import sha256
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Use UTC
os.environ['TZ'] = 'UTC'
time.tzset()

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

LOG_ENTRY_FORMAT = '%(asctime)s %(name)s (%(process)d) %(levelname)s %(message)s'
TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
IDA_MIGRATION = '2018-11-01T00:00:00Z'
IDA_MIGRATION_TS = 1541030400


def load_configuration(filesystem_pathname):
    """
    Load and return all defined variables from the specified configuration file
    """

    module_name = 'config.variables'
    
    try:
        # python versions >= 3.5
        module_spec = importlib.util.spec_from_file_location(module_name, filesystem_pathname)
        config = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(config)
    except AttributeError:
        # python versions < 3.5
        from importlib.machinery import SourceFileLoader
        config = SourceFileLoader(module_name, filesystem_pathname).load_module()

    # Define Metax version if Metax URL defined
    if config.METAX_API_ROOT_URL:
        if '/rest/' in config.METAX_API_ROOT_URL:
            config.METAX_API_VERSION = 1
        else:
            config.METAX_API_VERSION = 3

    # Allow environment setting to override configuration for debug output
    if os.environ.get('DEBUG'):
        config.DEBUG = os.environ['DEBUG']

    if config.DEBUG and config.DEBUG.lower() == 'true':
        config.DEBUG = True
    else:
        config.DEBUG = False

    return config


def generate_checksum(filesystem_pathname):
    if not os.path.isfile(filesystem_pathname):
        sys.stderr.write("ERROR: Pathname %s not found or not a file\n" % filesystem_pathname)
        return None
    try:
        block_size = 65536
        sha = sha256()
        with open(filesystem_pathname, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                sha.update(block)
        checksum = str(sha.hexdigest()).lower()
    except Exception as e:
        sys.stderr.write("ERROR: Failed to generate checksum for %s: %s\n" % (filesystem_pathname, str(e)))
        return None
    return checksum


def normalize_timestamp(timestamp):
    """
    Returns the input timestamp as a normalized ISO 8601 UTC timestamp string YYYY-MM-DDThh:mm:ssZ
    """

    # Sniff the input timestamp value and convert to a datetime instance as needed
    if isinstance(timestamp, str):
        timestamp = datetime.utcfromtimestamp(dateutil.parser.parse(timestamp).timestamp())
    elif isinstance(timestamp, float) or isinstance(timestamp, int):
        timestamp = datetime.utcfromtimestamp(timestamp)
    elif not isinstance(timestamp, datetime):
        raise Exception("Invalid timestamp value")

    # Return the normalized ISO UTC timestamp string
    return timestamp.strftime(TIMESTAMP_FORMAT)


def generate_timestamp():
    """
    Get current time as normalized ISO 8601 UTC timestamp string
    """
    return normalize_timestamp(datetime.utcnow().replace(microsecond=0))

