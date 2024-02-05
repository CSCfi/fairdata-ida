#--------------------------------------------------------------------------------
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
#--------------------------------------------------------------------------------

import sys
import dateutil.parser
import importlib.util
import logging
import logging.handlers
from datetime import datetime
from copy import deepcopy
from base64 import b64encode
from agents.settings import test as test_settings
from agents.settings import development as development_settings
from agents.settings import production as production_settings

LOG_ENTRY_FORMAT = '%(asctime)s %(name)s (%(process)d) %(levelname)s %(message)s'
TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ' # ISO 8601 UTC


def _load_module_from_file(made_up_module_name, file_path):
    try:
        # python versions >= 3.5
        module_spec = importlib.util.spec_from_file_location(made_up_module_name, file_path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    except AttributeError:
        # python versions < 3.5
        from importlib.machinery import SourceFileLoader
        module = SourceFileLoader(made_up_module_name, file_path).load_module()
    return module


def construct_file_path(_uida_conf_vars, node_data, replication=False):
    try:
        PROJECT_NAME = node_data['project']
    except KeyError:
        raise Exception('Trying to build file path for node, but the field "project" is missing. Node: %s' % str(node_data))

    try:
        PATHNAME = node_data['pathname']
    except KeyError:
        raise Exception('Trying to build file path for node, but the field "pathname" is missing. Node: %s' % str(node_data))

    if replication:
        DATA_REPLICATION_ROOT = _uida_conf_vars['DATA_REPLICATION_ROOT']
        full_file_path = '%(DATA_REPLICATION_ROOT)s/projects/%(PROJECT_NAME)s%(PATHNAME)s' % locals()
    else:
        STORAGE_OC_DATA_ROOT = _uida_conf_vars['STORAGE_OC_DATA_ROOT']
        PROJECT_USER_PREFIX  = _uida_conf_vars['PROJECT_USER_PREFIX']
        full_file_path = '%(STORAGE_OC_DATA_ROOT)s/%(PROJECT_USER_PREFIX)s%(PROJECT_NAME)s' \
                         '/files/%(PROJECT_NAME)s%(PATHNAME)s' % locals()
    return full_file_path


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


def normalize_logging():
    """
    Normalize all logging to use UTC ISO8601 timestamp formats and a constent layout
    """
    loggers = [logging.getLogger()]  # get the root logger
    loggers = loggers + [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for logger in loggers:
        for handler in logger.handlers:
            handler.setFormatter(logging.Formatter(LOG_ENTRY_FORMAT, TIMESTAMP_FORMAT))


def executing_test_case():
    return "unittest" in sys.modules


def get_logger(logger_name='logger', uida_conf_vars=None):
    """
    Configure and return a logger which writes to a different file
    when running inside test cases.
    """
    settings = get_settings(uida_conf_vars)
    logger = logging.getLogger(logger_name)
    file_handler = logging.handlers.WatchedFileHandler(load_variables_from_uida_conf_files()['RABBIT_WORKER_LOG_FILE'])
    logger.addHandler(file_handler)
    logger.setLevel(logging.getLevelName(settings['log_level']))
    normalize_logging()
    return logger


def get_settings(uida_conf_vars=None):
    """
    Automatically return either production, development, or test settings depending on
    if the code is currently being executed inside a test case, development environment,
    or production environment.
    """
    if executing_test_case():
        return deepcopy(test_settings)

    # If in TEST or DEV environment, always use DEBUG level logging
    if uida_conf_vars != None and uida_conf_vars.get('IDA_ENVIRONMENT', False) in ('TEST', 'DEV'):
        dev_settings = deepcopy(development_settings)
        dev_settings['log_level'] = 'DEBUG'
        return dev_settings

    return deepcopy(production_settings)


def load_variables_from_uida_conf_files():
    """
    Load and return as a dict variables from the following uida conf files:
    - server instance configuration file
    - service constants configuration file

    Load all confs from real production configuration, then replace relevant
    configuration with test env configuration as necesary.
    """
    server_conf = _load_module_from_file(
        "server_configuration.variables", production_settings['server_configuration_path']
    )
    service_constants = _load_module_from_file(
        "service_constants.variables", production_settings['service_constants_path']
    )

    uida_conf_vars = {
        'ROOT': server_conf.ROOT,
        'OCC': server_conf.OCC,
        'DEBUG': server_conf.DEBUG,
        'IDA_ENVIRONMENT': server_conf.IDA_ENVIRONMENT,
        'IDA_API': server_conf.IDA_API,
        'METAX_API': server_conf.METAX_API,
        'METAX_PASS': server_conf.METAX_PASS,
        'METAX_AVAILABLE': server_conf.METAX_AVAILABLE,
        'NC_ADMIN_USER': server_conf.NC_ADMIN_USER,
        'NC_ADMIN_PASS': server_conf.NC_ADMIN_PASS,
        'STORAGE_OC_DATA_ROOT': server_conf.STORAGE_OC_DATA_ROOT,
        'DATA_REPLICATION_ROOT': server_conf.DATA_REPLICATION_ROOT,
        'RABBIT_HOST': server_conf.RABBIT_HOST,
        'RABBIT_PORT': server_conf.RABBIT_PORT,
        'RABBIT_WEB_API_PORT': server_conf.RABBIT_WEB_API_PORT,
        'RABBIT_VHOST': server_conf.RABBIT_VHOST,
        'RABBIT_ADMIN_USER': server_conf.RABBIT_ADMIN_USER,
        'RABBIT_ADMIN_PASS': server_conf.RABBIT_ADMIN_PASS,
        'RABBIT_WORKER_USER': server_conf.RABBIT_WORKER_USER,
        'RABBIT_WORKER_PASS': server_conf.RABBIT_WORKER_PASS,
        'RABBIT_WORKER_LOG_FILE': server_conf.RABBIT_WORKER_LOG_FILE,
        'RABBIT_HEARTBEAT': server_conf.RABBIT_HEARTBEAT,
        'RABBIT_MONITORING_DIR': server_conf.RABBIT_MONITORING_DIR,
        'PROJECT_USER_PASS': server_conf.PROJECT_USER_PASS,
        'PROJECT_USER_PREFIX':  service_constants.PROJECT_USER_PREFIX,
        'MAX_FILE_COUNT':  service_constants.MAX_FILE_COUNT
    }

    if '/rest/' in server_conf.METAX_API:
        uida_conf_vars['METAX_API_VERSION'] = 1
    else:
        uida_conf_vars['METAX_API_VERSION'] = 3

    try:
        uida_conf_vars['RABBIT_PROTOCOL'] = server_conf.RABBIT_PROTOCOL
    except:
        uida_conf_vars['RABBIT_PROTOCOL'] = 'http'

    if hasattr(server_conf, 'METAX_USER'):
        uida_conf_vars['METAX_USER'] = server_conf.METAX_USER

    if hasattr(server_conf, 'METAX_FILE_STORAGE_ID'):
        uida_conf_vars['METAX_FILE_STORAGE_ID'] = server_conf.METAX_FILE_STORAGE_ID

    if hasattr(server_conf, 'DMF_SERVER'):
        uida_conf_vars['DMF_SERVER'] = server_conf.DMF_SERVER

    if hasattr(server_conf, 'DMF_STATUS'):
        uida_conf_vars['DMF_STATUS'] = server_conf.DMF_STATUS

    if executing_test_case():
        test_server_conf = _load_module_from_file(
            "server_configuration.variables", test_settings['server_configuration_path']
        )

        for conf_field in uida_conf_vars:
            if hasattr(test_server_conf, conf_field):
                uida_conf_vars[conf_field] = getattr(test_server_conf, conf_field)

    return uida_conf_vars


def make_ba_http_header(username, password):
    return 'Basic %s' % b64encode(bytes('%s:%s' % (username, password), 'utf-8')).decode('utf-8')
