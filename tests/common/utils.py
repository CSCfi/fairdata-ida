# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2018 Ministry of Education and Culture, Finland
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
import os
import time
import subprocess
import dateutil.parser
from datetime import datetime, timezone

# Use UTC
os.environ["TZ"] = "UTC"
time.tzset()

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ' # ISO 8601 UTC


def _load_module_from_file(module_name, file_path):
    try:
        # python versions >= 3.5
        module_spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    except AttributeError:
        # python versions < 3.5
        from importlib.machinery import SourceFileLoader
        module = SourceFileLoader(module_name, file_path).load_module()
    return module


def get_settings():
    paths = {"server_configuration_path": "config/config.sh", "service_constants_path": "lib/constants.sh"}
    return paths


def load_configuration():
    """
    Load and return as a dict variables from the following ida configuration files:
    - server instance configuration file
    - service constants configuration file
    """
    settings = get_settings()
    server_configuration = _load_module_from_file("server_configuration.variables", settings['server_configuration_path'])
    service_constants = _load_module_from_file("service_constants.variables", settings['service_constants_path'])
    config = {
        'ROOT':                   server_configuration.ROOT,
        'OCC':                    server_configuration.OCC,
        'IDA_API_ROOT_URL':       server_configuration.IDA_API_ROOT_URL,
        'URL_BASE_SHARE':         server_configuration.URL_BASE_SHARE,
        'URL_BASE_FILE':          server_configuration.URL_BASE_FILE,
        'NC_ADMIN_USER':          server_configuration.NC_ADMIN_USER,
        'NC_ADMIN_PASS':          server_configuration.NC_ADMIN_PASS,
        'PROJECT_USER_PASS':      server_configuration.PROJECT_USER_PASS,
        'PROJECT_USER_PREFIX':    service_constants.PROJECT_USER_PREFIX,
        'TEST_USER_PASS':         server_configuration.TEST_USER_PASS,
        'BATCH_ACTION_TOKEN':     server_configuration.BATCH_ACTION_TOKEN,
        'LOG':                    server_configuration.LOG,
        'LOG_ROOT':               os.path.dirname(server_configuration.LOG),
        'STAGING_FOLDER_SUFFIX':  service_constants.STAGING_FOLDER_SUFFIX,
        'STORAGE_OC_DATA_ROOT':   server_configuration.STORAGE_OC_DATA_ROOT,
        'DATA_REPLICATION_ROOT':  server_configuration.DATA_REPLICATION_ROOT,
        'MAX_FILE_COUNT':         service_constants.MAX_FILE_COUNT,
        'DBTYPE':                 server_configuration.DBTYPE,
        'DBNAME':                 server_configuration.DBNAME,
        'DBUSER':                 server_configuration.DBUSER,
        'DBPASSWORD':             server_configuration.DBPASSWORD,
        'DBROUSER':               server_configuration.DBROUSER,
        'DBROPASSWORD':           server_configuration.DBROPASSWORD,
        'DBHOST':                 server_configuration.DBHOST,
        'DBPORT':                 server_configuration.DBPORT,
        'DBTABLEPREFIX':          server_configuration.DBTABLEPREFIX,
        'RABBIT_HOST':            server_configuration.RABBIT_HOST,
        'RABBIT_PORT':            server_configuration.RABBIT_PORT,
        'RABBIT_WEB_API_PORT':    server_configuration.RABBIT_WEB_API_PORT,
        'RABBIT_VHOST':           server_configuration.RABBIT_VHOST,
        'RABBIT_ADMIN_USER':      server_configuration.RABBIT_ADMIN_USER,
        'RABBIT_ADMIN_PASS':      server_configuration.RABBIT_ADMIN_PASS,
        'RABBIT_WORKER_USER':     server_configuration.RABBIT_WORKER_USER,
        'RABBIT_WORKER_PASS':     server_configuration.RABBIT_WORKER_PASS,
        'RABBIT_WORKER_LOG_FILE': server_configuration.RABBIT_WORKER_LOG_FILE,
        'METAX_AVAILABLE':        server_configuration.METAX_AVAILABLE,
        'METAX_API_ROOT_URL':     server_configuration.METAX_API_ROOT_URL,
        'METAX_API_USER':         server_configuration.METAX_API_USER,
        'METAX_API_PASS':         server_configuration.METAX_API_PASS,
        'IDA_MIGRATION':          service_constants.IDA_MIGRATION,
        'IDA_MIGRATION_TS':       service_constants.IDA_MIGRATION_TS,
        'START':                  generate_timestamp()
    }

    if hasattr(server_configuration, 'DOWNLOAD_SERVICE_ROOT'):
        config['DOWNLOAD_SERVICE_ROOT'] = server_configuration.DOWNLOAD_SERVICE_ROOT

    if hasattr(server_configuration, 'METAX_API_RPC_URL'):
        config['METAX_API_RPC_URL'] = server_configuration.METAX_API_RPC_URL

    if '/rest/' in server_configuration.METAX_API_ROOT_URL:
        config['METAX_API_VERSION'] = 1
    else:
        config['METAX_API_VERSION'] = 3

    try:
        config['RABBIT_PROTOCOL'] = server_configuration.RABBIT_PROTOCOL
    except:
        config['RABBIT_PROTOCOL'] = 'http'

    try:
        config['NO_FLUSH_AFTER_TESTS'] = server_configuration.NO_FLUSH_AFTER_TESTS
    except:
        config['NO_FLUSH_AFTER_TESTS'] = 'false'

    if os.path.exists("/etc/httpd/"):
        config['HTTPD_USER'] = "apache"
    else:
        config['HTTPD_USER'] = "www-data"

    return config


def restart_rabbitmq_server():
    """
    Restart rabbitmq-consumer systemd service.
    """
    try:
        subprocess.check_call("sudo service rabbitmq-server restart".split())
        return True
    except subprocess.CalledProcessError as e:
        return False


def start_agents():
    """
    Start postprocessing agents systemd service.
    """
    try:
        subprocess.check_call("sudo systemctl start rabbitmq-metadata-agent".split())
        subprocess.check_call("sudo systemctl start rabbitmq-replication-agent".split())
        return True
    except subprocess.CalledProcessError as e:
        return False


def stop_agents():
    """
    Stop postprocessing agents systemd service.
    """
    try:
        subprocess.check_call("sudo systemctl stop rabbitmq-metadata-agent".split())
        subprocess.check_call("sudo systemctl stop rabbitmq-replication-agent".split())
        return True
    except subprocess.CalledProcessError as e:
        return False


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

