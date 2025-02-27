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
import sys
import time
import requests
import subprocess
import dateutil.parser
import json
from pathlib import Path
from datetime import datetime, timezone
from base64 import b64encode
from datetime import datetime

# Use UTC
os.environ["TZ"] = "UTC"
time.tzset()

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ' # ISO 8601 UTC

DATASET_TEMPLATE_V3 = {
    "generate_pid_on_publish": "URN",
    "data_catalog": "urn:nbn:fi:att:data-catalog-ida",
    "metadata_owner": {
        "user": "test_user_a",
        "organization": "Test Organization A"
    },
    "access_rights": {
        "access_type": {
            "url": "http://uri.suomi.fi/codelist/fairdata/access_type/code/open"
        },
       "license": [
			{
				"url": "http://uri.suomi.fi/codelist/fairdata/license/code/CC0-1.0"
			}
		]
    },
    "actors": [
        {
            "roles": [
                "creator", "publisher"
            ],
            "person": {
                "name": "Test User A"
            },
            "organization": {
                "url": "http://uri.suomi.fi/codelist/fairdata/organization/code/09206320"
            }
        }
    ],
    "description": {
        "en": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    },
    "title": {
        "en": "Test Dataset"
    },
    "state": "published"
}

DATASET_TEMPLATE_V1 = {
    "data_catalog": "urn:nbn:fi:att:data-catalog-ida",
    "metadata_provider_user": "test_user_a",
    "metadata_provider_org": "test_organization_a",
    "research_dataset": {
        "access_rights": {
            "access_type": {
                "identifier": "http://uri.suomi.fi/codelist/fairdata/access_type/code/open"
            }
        },
        "creator": [
            {
                "@type": "Person",
                "member_of": {
                    "@type": "Organization",
                    "name": {
                        "en": "Test Organization A"
                    }
                },
                "name": "Test User A"
            }
        ],
        "description": {
            "en": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        },
        "title": {
            "en": "Test Dataset"
        }
    }
}

DATASET_TITLES = [
    { "en": "Lake Chl-a products from Finland (MERIS, FRESHMON)" },
    { "fi": "MERIVEDEN LÄMPÖTILA POHJALLA (VELMU)" },
    { "sv": "Svenska ortnamn i Finland" },
    { "en": "The Finnish Subcorpus of Topling - Paths in Second Language Acquisition" },
    { "en": "SMEAR data preservation 2019" },
    { "en": "Finnish Opinions on Security Policy and National Defence 2001: Autumn" }
]


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
        'IDA_API':       server_configuration.IDA_API,
        'FILE_API':      server_configuration.FILE_API,
        'SHARE_API':     server_configuration.SHARE_API,
        'GROUP_API':     server_configuration.GROUP_API,
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
        'METAX_API':              server_configuration.METAX_API,
        'METAX_PASS':             server_configuration.METAX_PASS,
        'IDA_MIGRATION':          service_constants.IDA_MIGRATION,
        'IDA_MIGRATION_TS':       service_constants.IDA_MIGRATION_TS,
        'START':                  generate_timestamp()
    }

    if hasattr(server_configuration, 'DOWNLOAD_SERVICE_ROOT'):
        config['DOWNLOAD_SERVICE_ROOT'] = server_configuration.DOWNLOAD_SERVICE_ROOT

    if hasattr(server_configuration, 'METAX_USER'):
        config['METAX_USER'] = server_configuration.METAX_USER

    if hasattr(server_configuration, 'METAX_RPC'):
        config['METAX_RPC'] = server_configuration.METAX_RPC

    if '/rest/' in server_configuration.METAX_API:
        config['METAX_API_VERSION'] = 1
    else:
        config['METAX_API_VERSION'] = 3

    if hasattr(server_configuration, 'TEST_PAS_CONTRACT_ID'):
        config['TEST_PAS_CONTRACT_ID'] = server_configuration.TEST_PAS_CONTRACT_ID

    try:
        config['RABBIT_PROTOCOL'] = server_configuration.RABBIT_PROTOCOL
    except:
        config['RABBIT_PROTOCOL'] = 'http'

    try:
        config['NO_FLUSH_AFTER_TESTS'] = server_configuration.NO_FLUSH_AFTER_TESTS
    except:
        config['NO_FLUSH_AFTER_TESTS'] = 'false'

    try:
        config['SEND_TEST_EMAILS'] = server_configuration.SEND_TEST_EMAILS
    except:
        config['SEND_TEST_EMAILS'] = 'false'

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


def generate_timestamp():
    """
    Get current time as normalized ISO 8601 UTC timestamp string
    """
    time.sleep(1) # ensure a unique timestamp, as timestamps have single-second resolution
    timestamp = normalize_timestamp(datetime.utcnow().replace(microsecond=0))
    time.sleep(1) # ensure all subsequent actions happen after the newly generated timestamp 
    return timestamp


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


def subtract_days_from_timestamp(timestamp, days):
    start_datetime = dateutil.parser.isoparse(timestamp)
    start_ts = start_datetime.replace(tzinfo=timezone.utc).timestamp()
    start_offset_ts = start_ts - (days * 86400) # 86400 seconds in a day
    return normalize_timestamp(datetime.utcfromtimestamp(start_offset_ts))


def make_ida_offline(self):
    print("(putting IDA service into offline mode)")
    ida_admin_auth = (self.config['NC_ADMIN_USER'], self.config['NC_ADMIN_PASS'])
    offline_sentinel_file = "%s/control/OFFLINE" % self.config["STORAGE_OC_DATA_ROOT"]
    if os.path.exists(offline_sentinel_file):
        print("(service already in offline mode)")
        return True
    url = "%s/offline" % self.config['IDA_API']
    response = requests.post(url, auth=ida_admin_auth, verify=False)
    if response.status_code == 200:
        return True
    return False


def make_ida_online(self):
    print("(putting IDA service into online mode)")
    ida_admin_auth = (self.config['NC_ADMIN_USER'], self.config['NC_ADMIN_PASS'])
    offline_sentinel_file = "%s/control/OFFLINE" % self.config["STORAGE_OC_DATA_ROOT"]
    if not os.path.exists(offline_sentinel_file):
        print("(service already in online mode)")
        return True
    url = "%s/offline" % self.config['IDA_API']
    response = requests.delete(url, auth=ida_admin_auth, verify=False)
    if response.status_code == 200:
        return True
    return False


def wait_for_pending_actions(self, project, user):
    print("(waiting for pending actions to fully complete)")
    print(".", end='', flush=True)
    response = requests.get("%s/actions?project=%s&status=pending" % (self.config["IDA_API"], project), auth=user, verify=False)
    self.assertEqual(response.status_code, 200)
    actions = response.json()
    max_time = time.time() + self.timeout
    while len(actions) > 0 and time.time() < max_time:
        print(".", end='', flush=True)
        time.sleep(1)
        response = requests.get("%s/actions?project=%s&status=pending" % (self.config["IDA_API"], project), auth=user, verify=False)
        self.assertEqual(response.status_code, 200)
        actions = response.json()
    print("")
    self.assertEqual(len(actions), 0, "Timed out waiting for pending actions to fully complete")


def check_for_failed_actions(self, project, user, should_be_failed = False):
    print("(verifying no failed actions)")
    response = requests.get("%s/actions?project=%s&status=failed" % (self.config["IDA_API"], project), auth=user, verify=False)
    self.assertEqual(response.status_code, 200)
    actions = response.json()
    if should_be_failed:
        assert(len(actions) > 0)
    else:
        assert(len(actions) == 0)
    return actions


def build_dataset_files(self, action_files):
    dataset_files = []
    for action_file in action_files:
        dataset_file = {
            "title": action_file['pathname'],
            "identifier": action_file['pid'],
            "description": "test data file",
            "use_category": { "identifier": "http://uri.suomi.fi/codelist/fairdata/use_category/code/source" }
        }
        dataset_files.append(dataset_file)
    return dataset_files


def flush_datasets(self):
    print ("Flushing test datasets from METAX...")
    dataset_pids = get_dataset_pids(self)
    for pid in dataset_pids:
        print ("   %s" % pid)
        if self.config["METAX_API_VERSION"] >= 3:
            requests.delete("%s/datasets/%s" % (self.config['METAX_API'], pid), headers=self.metax_headers)
        else:
            requests.delete("%s/datasets/%s" % (self.config['METAX_API'], pid), auth=self.metax_user)


def get_dataset_pids(self):
    pids = []
    test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
    data = { "project": "test_project_a", "pathname": "/testdata" }
    response = requests.post("%s/datasets" % self.config["IDA_API"], data=data, auth=test_user_a, verify=False)
    if response.status_code == 200:
        datasets = response.json()
        for dataset in datasets:
            pids.append(dataset['pid'])
    return pids


def get_frozen_file_pids(self, project, user):
    """
    Retrieve exhaustive list of PIDs of all frozen files currently stored in IDA which are associated with project
    """

    frozen_file_pids = []

    response = requests.get("%s/frozen_file_pids/%s" % (self.config["IDA_API"], project), auth=user, verify=False)

    if response.status_code == 200:

        frozen_file_pids = response.json()

        if not isinstance(frozen_file_pids, list):
            frozen_file_pids = [frozen_file_pids]

    return sorted(frozen_file_pids)


def get_metax_file_pids(self, project):
    """
    Retrieve exhaustive list of PIDs of all frozen files known to Metax which are associated with project
    """

    metax_file_pids = []

    if self.config['METAX_API_VERSION'] >= 3:
        headers = { "Authorization": "Token %s" % self.config['METAX_PASS'] }
        url = "%s/files?csc_project=%s&storage_service=ida&limit=9999" % (self.config["METAX_API"], project)
    else:
        headers = { "Authorization": make_ba_http_header(self.config['METAX_USER'], self.config['METAX_PASS']) }
        url = "%s/files?fields=identifier&file_storage=urn:nbn:fi:att:file-storage-ida&ordering=id&project_identifier=%s&limit=9999" % (self.config["METAX_API"], project)

    #print("HEADER: %s URL %s" % (json.dumps(headers), url)) # TEMP DEBUG

    response = requests.get(url, headers=headers, verify=False)

    if response.status_code == 200:
        file_data = response.json()
        for record in file_data['results']:
            if self.config['METAX_API_VERSION'] >= 3:
                metax_file_pids.append(record['storage_identifier'])
            else:
                metax_file_pids.append(record['identifier'])

    return sorted(metax_file_pids)


def make_ba_http_header(username, password):
    return 'Basic %s' % b64encode(bytes('%s:%s' % (username, password), 'utf-8')).decode('utf-8')


def array_difference(arr1, arr2):
    """
    Returns a tuple of two arrays:
    - The first array contains strings in arr1 that are not in arr2.
    - The second array contains strings in arr2 that are not in arr1.
    
    Parameters:
    arr1 (list of str): The first array of strings.
    arr2 (list of str): The second array of strings.
    
    Returns:
    tuple: A tuple containing two lists.
    """
    set1 = set(arr1)
    set2 = set(arr2)
    
    in_first_not_second = sorted(list(set1 - set2))
    in_second_not_first = sorted(list(set2 - set1))
    
    return (in_first_not_second, in_second_not_first)


def audit_project(self, project, status, after = None, area = None, timestamps = True, checksums = True, before = None):
    """
    Audit the specified project, verify that the audit report file was created with the specified
    status, and load and return the audit report as a JSON object, with the audit report pathname
    defined in the returned object for later timestamp repair if/as needed.

    A full audit with no restrictions and including timestamps and checksums is done by default.
    """

    parameters = ""

    if after is None and before is None and area is None and timestamps and checksums:
        parameters = " --full"

    else:

        if after:
            parameters = "%s --changed-after %s" % (parameters, after)

        if before:
            parameters = "%s --changed-before %s" % (parameters, before)

        if area:
            parameters = "%s --%s" % (parameters, area)
            area = " %s" % area

        if timestamps:
            parameters = "%s --timestamps" % parameters

        if checksums:
            parameters = "%s --checksums" % parameters

    if self.config.get('SEND_TEST_EMAILS') == 'true':
        parameters = "%s --report" % parameters

    print ("(auditing project %s%s)" % (project, parameters))

    cmd = "sudo -u %s DEBUG=false %s/utils/admin/audit-project %s %s" % (
        self.config["HTTPD_USER"],
        self.config["ROOT"],
        project,
        parameters
    )

    # print(cmd) # TEMP HACK

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
    except subprocess.CalledProcessError as error:
        self.fail(error.output.decode(sys.stdout.encoding))

    self.assertNotEqual(output, None, output)
    self.assertNotEqual(output, "", output)
    self.assertTrue(("Audit results saved to file " in output), output)

    start = output.index("Audit results saved to file ")
    report_pathname = output[start + 28:]
    report_pathname = report_pathname.split('\n', 1)[0]

    print("Verify audit report exists and has the correct status")
    self.assertTrue(report_pathname.endswith(".%s.json" % status), report_pathname)
    path = Path(report_pathname)
    self.assertTrue(path.exists(), path)
    self.assertTrue(path.is_file(), path)

    print("(loading audit report %s)" % report_pathname)
    try:
        report_data = json.load(open(report_pathname))
    except subprocess.CalledProcessError as error:
        self.fail(error.output.decode(sys.stdout.encoding))
    self.assertEqual(report_data.get("project"), project)

    report_data["reportPathname"] = report_pathname

    return report_data


def remove_report(self, pathname):
    try:
        os.remove(pathname)
    except:
        pass
