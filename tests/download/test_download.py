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
# Note regarding sequence of tests: this test case contains only a single test
# method, which utilizes the test projects, user accounts, and project data
# initialized during setup, such that the sequential actions in the single
# test method create side effects which subsequent actions and assertions may
# depend on. The state of the test accounts and data must be taken into account
# whenever adding tests at any particular point in that execution sequence.
# --------------------------------------------------------------------------------

import requests
import unittest
import time
import os
import sys
import socket
from tests.common.utils import load_configuration

DATASET_TEMPLATE = {
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
    },
    "preservation_state": 0
}

DATASET_TITLES = [
    { "en": "Lake Chl-a products from Finland (MERIS, FRESHMON)" },
    { "fi": "MERIVEDEN LÄMPÖTILA POHJALLA (VELMU)" },
    { "sv": "Svenska ortnamn i Finland" },
    { "en": "The Finnish Subcorpus of Topling - Paths in Second Language Acquisition" },
    { "en": "SMEAR data preservation 2019" },
    { "en": "Finnish Opinions on Security Policy and National Defence 2001: Autumn" }
]

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r

class TestDownload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("=== tests/datasets/test_download")

    def setUp(self):

        # load service configuration variables
        self.config = load_configuration()

        self.config['DOWNLOAD_SERVICE_ROOT'] = self.config.get('DOWNLOAD_SERVICE_ROOT', "/opt/fairdata/fairdata-download-service")

        if 'TRUSTED_SERVICE_TOKEN' in os.environ:
            self.trusted_service_token = os.environ['TRUSTED_SERVICE_TOKEN']
        else:
            print("WARNING: No trusted service token found in environment! Using default (which may fail)")
            self.trusted_service_token = 'test42'

        self.token_auth = BearerAuth(self.trusted_service_token)

        # keep track of success, for reference in tearDown
        self.success = False

        # timeout when waiting for actions to complete
        self.timeout = 10800 # 3 hours

        self.assertEqual(self.config["METAX_AVAILABLE"], 1)

        print("(initializing)")

        offline_sentinel_file = "%s/control/OFFLINE" % self.config["STORAGE_OC_DATA_ROOT"]
        if os.path.exists(offline_sentinel_file):
            os.remove(offline_sentinel_file)
            self.assertFalse(os.path.exists(offline_sentinel_file))

        self.flushDatasets()
        self.flushDownloads()

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':

            print("(cleaning)")

            self.flushDatasets()
            self.flushDownloads()

            cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts --flush %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
            result = os.system(cmd)
            self.assertEqual(result, 0)

        self.assertTrue(self.success)


    def flushDatasets(self):
        print ("Flushing test datasets from METAX...")
        dataset_pids = self.getDatasetPids()
        metax_user = (self.config["METAX_API_USER"], self.config["METAX_API_PASS"])
        for pid in dataset_pids:
            print ("   %s" % pid)
            requests.delete("%s/datasets/%s" % (self.config['METAX_API_ROOT_URL'], pid), auth=metax_user, verify=False)


    def flushDownloads(self):
        print ("Flushing test download packages and records from Download Service...")
        dl_root = self.config['DOWNLOAD_SERVICE_ROOT']
        if dl_root:
            cmd = "%s/dev_config/utils/flush-all" % dl_root
            result = os.system(cmd)
            self.assertEqual(result, 0)
        else:
            self.fail("Could not locate the download service root directory")


    def getDatasetPids(self):
        pids = []
        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
        data = { "project": "test_project_a", "pathname": "/testdata" }
        response = requests.post("%s/datasets" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        if response.status_code == 200:
            datasets = response.json()
            for dataset in datasets:
                pids.append(dataset['pid'])
        return pids


    def waitForPendingRequests(self, dataset_pid):
        print("(waiting for requested packages to be generated)")
        max_time = time.time() + self.timeout
        pending = True
        looped = False
        while pending and time.time() < max_time:
            response = requests.get("https://localhost:4431/requests?dataset=%s" % dataset_pid, auth=self.token_auth, verify=False)
            self.assertTrue(response.status_code in [ 200, 404 ], response.content.decode(sys.stdout.encoding))
            if response.status_code == 200:
                response_json = response.json()
                status = response_json.get('status')
                pending = status != None and status not in [ 'SUCCESS', 'FAILED' ]
                if not pending:
                    partial = response_json.get('partial', [])
                    for req in partial:
                        if not pending:
                            pending = req.get('status') not in [ 'SUCCESS', 'FAILED' ] 
                if pending:
                    looped = True
                    print(".", end='', flush=True)
                    time.sleep(1)
            else: # 404
                pending = False
        if looped:
            print("")
        self.assertTrue(time.time() < max_time, "Timed out waiting for requested packages to be generated")


    def waitForPendingActions(self, project, user):
        print("(waiting for pending actions to fully complete)")
        print(".", end='', flush=True)
        response = requests.get("%s/actions?project=%s&status=pending" % (self.config["IDA_API_ROOT_URL"], project), auth=user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        actions = response.json()
        max_time = time.time() + self.timeout
        while len(actions) > 0 and time.time() < max_time:
            print(".", end='', flush=True)
            time.sleep(1)
            response = requests.get("%s/actions?project=%s&status=pending" % (self.config["IDA_API_ROOT_URL"], project), auth=user, verify=False)
            self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
            actions = response.json()
        print("")
        self.assertTrue(time.time() < max_time, "Timed out waiting for pending actions to fully complete")


    def checkForFailedActions(self, project, user):
        print("(verifying no failed actions)")
        response = requests.get("%s/actions?project=%s&status=failed" % (self.config["IDA_API_ROOT_URL"], project), auth=user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        actions = response.json()
        assert(len(actions) == 0)


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


    def test_download(self):

        """
        Overview:

        1. The test project and user account will be created and initialized as usual.

        2. Project A will have one folder frozen, and the tests will wait until all postprocessing
           has completed such that all metadata is recorded in Metax.

        3. A dataset will be created in Metax, with files included from the frozen folder.
        
        4. The download service will be tested based on the defined dataset, requesting generation of
           multiple packages, both for full and partial dataset, listings of pending and available
           package generation, retrieval of authorization tokens, and download of individual files.
        """

        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
        metax_user = (self.config["METAX_API_USER"], self.config["METAX_API_PASS"])

        # --------------------------------------------------------------------------------

        print("Freezing folder")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Retrieving frozen file details for all files associated with freeze action of folder")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        experiment_1_files = response.json()
        self.assertEqual(len(experiment_1_files), 13)

        print("Creating dataset containing all files in scope of frozen folder")
        dataset_data = DATASET_TEMPLATE
        dataset_data['research_dataset']['title'] = DATASET_TITLES[0]
        dataset_data['research_dataset']['files'] = self.build_dataset_files(experiment_1_files)
        response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], json=dataset_data, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))
        dataset = response.json()
        dataset_pid = dataset.get('identifier')
        self.assertIsNotNone(dataset_pid)

        # --------------------------------------------------------------------------------
  
        print("Verify that no active package generation requests exist for dataset")
        response = requests.get("https://localhost:4431/requests?dataset=%s" % dataset_pid, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 404, response.content.decode(sys.stdout.encoding))

        print("Authorize individual dataset file download") 
        file = experiment_1_files[0]
        filename = file.get('pathname')
        self.assertIsNotNone(filename)
        data = { "dataset": dataset_pid, "file": filename }
        response = requests.post("https://localhost:4431/authorize", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        token = response.json().get('token')
        self.assertIsNotNone(token)

        print("Download individual dataset file using authorization token") 
        response = requests.get("https://localhost:4431/download?token=%s" % token, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))

        print("Attempt to download individual dataset file using authorization token a second time") 
        response = requests.get("https://localhost:4431/download?token=%s" % token, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 401, response.content.decode(sys.stdout.encoding))

        print("Request generation of complete dataset package")
        data = { "dataset": dataset_pid }
        response = requests.post("https://localhost:4431/requests", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        self.assertIsNotNone(response_json)
        self.assertEqual(response_json.get('dataset'), dataset_pid, response.content.decode(sys.stdout.encoding))

        self.waitForPendingRequests(dataset_pid)

        print("Verifying generation of complete dataset package")
        response = requests.get("https://localhost:4431/requests?dataset=%s" % dataset_pid, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        self.assertEqual(response_json.get('status'), 'SUCCESS')
        package = response_json.get('package')
        self.assertIsNotNone(package)

        print("Authorize complete dataset package download") 
        data = { "dataset": dataset_pid, "package": package }
        response = requests.post("https://localhost:4431/authorize", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        token = response.json().get('token')
        self.assertIsNotNone(token)

        print("Download complete dataset package using authorization token") 
        response = requests.get("https://localhost:4431/download?token=%s" % token, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Request generation of a partial dataset package")
        data = { "dataset": dataset_pid, "scope": [ "/testdata/2017-08/Experiment_1/baseline", "/testdata/2017-08/Experiment_1/test01.dat" ] }
        response = requests.post("https://localhost:4431/requests", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        self.assertIsNotNone(response_json)
        self.assertEqual(response_json.get('dataset'), dataset_pid, response.content.decode(sys.stdout.encoding))

        self.waitForPendingRequests(dataset_pid)

        print("Verifying generation of partial dataset package")
        response = requests.get("https://localhost:4431/requests?dataset=%s" % dataset_pid, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        partial = response_json.get('partial')
        self.assertIsNotNone(partial)
        self.assertEqual(len(partial), 1)
        self.assertEqual(partial[0].get('status'), 'SUCCESS')
        scope = partial[0].get('scope')
        self.assertIsNotNone(scope)
        self.assertEqual(len(scope), 2)
        self.assertTrue("/testdata/2017-08/Experiment_1/baseline" in scope)
        self.assertTrue("/testdata/2017-08/Experiment_1/test01.dat" in scope)
        package = partial[0].get('package')
        self.assertIsNotNone(package)

        print("Authorize partial dataset package download") 
        data = { "dataset": dataset_pid, "package": package }
        response = requests.post("https://localhost:4431/authorize", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        token = response.json().get('token')
        self.assertIsNotNone(token)

        print("Download partial dataset package using authorization token") 
        response = requests.get("https://localhost:4431/download?token=%s" % token, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Putting IDA service into offline mode")
        offline_sentinel_file = "%s/control/OFFLINE" % self.config["STORAGE_OC_DATA_ROOT"]
        cmd = "sudo -u %s touch %s" % (self.config["HTTPD_USER"], offline_sentinel_file)
        result = os.system(cmd)
        self.assertEqual(result, 0)
        self.assertTrue(os.path.exists(offline_sentinel_file))

        print("Authorize individual dataset file download") 
        data = { "dataset": dataset_pid, "file": filename }
        response = requests.post("https://localhost:4431/authorize", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        token = response.json().get('token')
        self.assertIsNotNone(token)

        print("Attempt to download individual dataset file while IDA service is offline") 
        response = requests.get("https://localhost:4431/download?token=%s" % token, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 503, response.content.decode(sys.stdout.encoding))

        print("Authorize existing dataset package download") 
        data = { "dataset": dataset_pid, "package": package }
        response = requests.post("https://localhost:4431/authorize", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        token = response.json().get('token')
        self.assertIsNotNone(token)

        print("Download existing dataset package while IDA service is offline") 
        response = requests.get("https://localhost:4431/download?token=%s" % token, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200)

        self.flushDownloads()

        print("Request generation of complete dataset package")
        data = { "dataset": dataset_pid }
        response = requests.post("https://localhost:4431/requests", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        self.assertIsNotNone(response_json)
        self.assertEqual(response_json.get('dataset'), dataset_pid, response.content.decode(sys.stdout.encoding))

        print("Verify that package generation request is pending")
        response = requests.get("https://localhost:4431/requests?dataset=%s" % dataset_pid, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        self.assertTrue(response_json.get('status') in ['RETRY', 'PENDING'], response.content.decode(sys.stdout.encoding))

        print("Subscribe to notification of generation of dataset package")
        data = { "dataset": dataset_pid, "subscriptionData": "abcdef", "notifyURL": "https://%s:4431/mock_notify" % socket.gethostname() }
        notification_file = "%s/data/download-cache/mock_notifications/abcdef" % self.config['DOWNLOAD_SERVICE_ROOT']
        response = requests.post("https://localhost:4431/subscribe", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        self.assertIsNotNone(response_json)
        self.assertEqual(response_json.get('dataset'), dataset_pid, response.content.decode(sys.stdout.encoding))

        print("(sleeping...)")
        time.sleep(5)

        print("Verify that package generation request is still pending")
        response = requests.get("https://localhost:4431/requests?dataset=%s" % dataset_pid, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        self.assertTrue(response_json.get('status') in ['RETRY', 'PENDING'], response.content.decode(sys.stdout.encoding))

        print("Returning IDA service to online mode")
        os.remove(offline_sentinel_file)
        self.assertFalse(os.path.exists(offline_sentinel_file))

        self.waitForPendingRequests(dataset_pid)

        print("Verifying generation of complete dataset package")
        response = requests.get("https://localhost:4431/requests?dataset=%s" % dataset_pid, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        response_json = response.json()
        self.assertEqual(response_json.get('status'), 'SUCCESS')

        print("Verifying subscribed notification of completed dataset package generation was received")
        self.assertTrue(os.path.exists(notification_file))

        print("Authorize complete dataset package download") 
        package = response_json.get('package')
        data = { "dataset": dataset_pid, "package": package }
        response = requests.post("https://localhost:4431/authorize", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        token = response.json().get('token')
        self.assertIsNotNone(token)

        print("Download complete dataset package using authorization token") 
        response = requests.get("https://localhost:4431/download?token=%s" % token, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Authorize individual dataset file download") 
        data = { "dataset": dataset_pid, "file": filename }
        response = requests.post("https://localhost:4431/authorize", json=data, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        token = response.json().get('token')
        self.assertIsNotNone(token)

        print("Download individual dataset file using authorization token") 
        response = requests.get("https://localhost:4431/download?token=%s" % token, auth=self.token_auth, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
