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
import urllib
import subprocess
import unittest
import psycopg2
import pymysql
import time
import os
import sys
import shutil
import json
from pathlib import Path
from tests.common.utils import load_configuration
from datetime import datetime

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

class TestDatasets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("=== tests/datasets/test_datasets")

    def setUp(self):

        # load service configuration variables
        self.config = load_configuration()

        # keep track of success, for reference in tearDown
        self.success = False

        # timeout when waiting for actions to complete
        self.timeout = 10800 # 3 hours

        self.assertEqual(self.config["METAX_AVAILABLE"], 1)

        print("(initializing)")

        self.flushDatasets()

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        cmd = "sudo -u %s %s/tests/utils/initialize-max-files test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':

            print("(cleaning)")

            self.flushDatasets()

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
            response = requests.delete("%s/datasets/%s" % (self.config['METAX_API_ROOT_URL'], pid), auth=metax_user, verify=False)


    def getDatasetPids(self):
        pids = []
        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
        data = { "project": "test_project_a", "pathname": "/testdata" }
        response = requests.post("%s/datasets" % self.config["IDA_API_ROOT_URL"], data=data, auth=test_user_a, verify=False)
        if response.status_code == 200:
            datasets = response.json()
            for dataset in datasets:
                pids.append(dataset['pid'])
        return pids


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
        self.assertEqual(len(actions), 0, "Timed out waiting for pending actions to fully complete")


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


    def test_datasets(self):

        """
        Overview:

        1. The test projects and user accounts will be created and initialized as usual.

        2. Project A will have three folders frozen, and the tests will wait until all postprocessing
           has completed such that all metadata is recorded in Metax.

        3. Three datasets will be created in Metax, each with files included from each frozen folder.
        
        4. Metax will be queried with various sets of input file PIDs to verify that the correct
           set of dataset PIDs are returned.
        """

        admin_user = (self.config["NC_ADMIN_USER"], self.config["NC_ADMIN_PASS"])
        pso_user_a = (self.config["PROJECT_USER_PREFIX"] + "test_project_a", self.config["PROJECT_USER_PASS"])
        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
        metax_user = (self.config["METAX_API_USER"], self.config["METAX_API_PASS"])

        # --------------------------------------------------------------------------------

        headers = { 'X-SIMULATE-AGENTS': 'true' }

        print("Freezing folder /testdata/2017-08/Experiment_1")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Retrieve frozen file details for all files associated with freeze action of folder /2017-08/Experiment_1")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        experiment_1_files = response.json()
        self.assertEqual(len(experiment_1_files), 13)

        print("Freezing folder /testdata/2017-08/Experiment_2")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_2"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Retrieve frozen file details for all files associated with freeze action of folder /2017-08/Experiment_2")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        experiment_2_files = response.json()
        self.assertEqual(len(experiment_2_files), 13)

        print("Freezing folder /testdata/2017-10/Experiment_3")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-10/Experiment_3"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])
        action_pid = action_data["pid"]

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Retrieve frozen file details for all files associated with freeze action of folder /2017-10/Experiment_3")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        experiment_3_files = response.json()
        self.assertEqual(len(experiment_3_files), 13)

        print("Freezing folder /testdata/2017-10/Experiment_4")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-10/Experiment_4"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])
        action_pid = action_data["pid"]

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Retrieve frozen file details for all files associated with freeze action of folder /2017-10/Experiment_4")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        experiment_4_files = response.json()
        self.assertEqual(len(experiment_4_files), 12)

        frozen_area_root = "%s/PSO_test_project_a/files/test_project_a" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root = "%s/PSO_test_project_a/files/test_project_a%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])
        cmd_base="sudo -u %s SIMULATE_AGENTS=true %s/utils/admin/execute-batch-action" % (self.config["HTTPD_USER"], self.config["ROOT"])

        print("Batch freezing a folder with more than max allowed files")
        cmd = "%s test_project_a freeze /testdata/MaxFiles >/dev/null" % (cmd_base)
        result = os.system(cmd)
        self.assertEqual(result, 0)

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Verify data was physically moved from staging to frozen area")
        self.assertFalse(os.path.exists("%s/testdata/MaxFiles/%s_files/500_files_1/100_files_1/10_files_1/test_file_1.dat" % (staging_area_root, self.config["MAX_FILE_COUNT"])))
        self.assertFalse(os.path.exists("%s/testdata/MaxFiles" % (staging_area_root)))
        self.assertTrue(os.path.exists("%s/testdata/MaxFiles/%s_files/500_files_1/100_files_1/10_files_1/test_file_1.dat" % (frozen_area_root, self.config["MAX_FILE_COUNT"])))

        print("Attempt to query IDA for datasets intersecting scope which exceeds max file count")
        data = { "project": "test_project_a", "pathname": "/testdata" }
        response = requests.post("%s/datasets" % self.config["IDA_API_ROOT_URL"], data=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['message'], "Maximum allowed file count for a single action was exceeded.")

        print("Creating Dataset 1 containing all files in scope /testdata/2017-08/Experiment_1")
        dataset_data = DATASET_TEMPLATE
        dataset_data['research_dataset']['title'] = DATASET_TITLES[0]
        dataset_data['research_dataset']['files'] = self.build_dataset_files(experiment_1_files)
        response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], json=dataset_data, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))
        dataset_1 = response.json()
        dataset_1_pid = dataset_1['identifier']
        dataset_1_urn = dataset_1['research_dataset']['preferred_identifier']

        print("Creating Dataset 2 containing all files in scope /testdata/2017-08/Experiment_2")
        dataset_data = DATASET_TEMPLATE
        dataset_data['research_dataset']['title'] = DATASET_TITLES[1]
        dataset_data['research_dataset']['files'] = self.build_dataset_files(experiment_2_files)
        response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], json=dataset_data, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))
        dataset_2 = response.json()
        dataset_2_pid = dataset_2['identifier']
        dataset_2_urn = dataset_2['research_dataset']['preferred_identifier']

        print("Creating Dataset 3 containing all files in scope /testdata/2017-10/Experiment_3")
        dataset_data = DATASET_TEMPLATE
        dataset_data['research_dataset']['title'] = DATASET_TITLES[2]
        dataset_data['research_dataset']['files'] = self.build_dataset_files(experiment_3_files)
        response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], json=dataset_data, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))
        dataset_3 = response.json()
        dataset_3_pid = dataset_3['identifier']
        dataset_3_urn = dataset_3['research_dataset']['preferred_identifier']

        print("Query Metax with selected files from Dataset 1")
        files = [ experiment_1_files[1]['pid'], experiment_1_files[7]['pid'], experiment_1_files[11]['pid'] ] 
        response = requests.post("%s/files/datasets" % self.config['METAX_API_ROOT_URL'], json=files, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        datasets = response.json()
        self.assertEqual(len(datasets), 1)
        self.assertTrue(dataset_1_pid in datasets or dataset_1_urn in datasets)

        print("Query Metax with selected files from Dataset 2")
        files = [ experiment_2_files[2]['pid'], experiment_2_files[8]['pid'], experiment_2_files[12]['pid'] ] 
        response = requests.post("%s/files/datasets" % self.config['METAX_API_ROOT_URL'], json=files, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        datasets = response.json()
        self.assertEqual(len(datasets), 1)
        self.assertTrue(dataset_2_pid in datasets or dataset_2_urn in datasets)

        print("Query Metax with selected files from Dataset 3")
        files = [ experiment_3_files[0]['pid'], experiment_3_files[6]['pid'], experiment_3_files[10]['pid'] ] 
        response = requests.post("%s/files/datasets" % self.config['METAX_API_ROOT_URL'], json=files, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        datasets = response.json()
        self.assertEqual(len(datasets), 1)
        self.assertTrue(dataset_3_pid in datasets or dataset_3_urn in datasets)

        print("Query Metax with selected files from Datasets 1 and 2")
        files = [ experiment_1_files[1]['pid'], experiment_2_files[8]['pid'] ] 
        response = requests.post("%s/files/datasets" % self.config['METAX_API_ROOT_URL'], json=files, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        datasets = response.json()
        self.assertEqual(len(datasets), 2)
        self.assertTrue(dataset_1_pid in datasets or dataset_1_urn in datasets)
        self.assertTrue(dataset_2_pid in datasets or dataset_2_urn in datasets)

        print("Query Metax with selected files from Datasets 2 and 3")
        files = [ experiment_2_files[2]['pid'], experiment_3_files[0]['pid'] ] 
        response = requests.post("%s/files/datasets" % self.config['METAX_API_ROOT_URL'], json=files, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        datasets = response.json()
        self.assertEqual(len(datasets), 2)
        self.assertTrue(dataset_2_pid in datasets or dataset_2_urn in datasets)
        self.assertTrue(dataset_3_pid in datasets or dataset_3_urn in datasets)

        print("Query Metax with selected files from Datasets 1 and 3")
        files = [ experiment_1_files[1]['pid'], experiment_3_files[0]['pid'] ] 
        response = requests.post("%s/files/datasets" % self.config['METAX_API_ROOT_URL'], json=files, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        datasets = response.json()
        self.assertEqual(len(datasets), 2)
        self.assertTrue(dataset_1_pid in datasets or dataset_1_urn in datasets)
        self.assertTrue(dataset_3_pid in datasets or dataset_3_urn in datasets)

        print("Query Metax with selected files from Datasets 1, 2 and 3")
        files = [ experiment_1_files[1]['pid'], experiment_2_files[8]['pid'], experiment_3_files[10]['pid'] ] 
        response = requests.post("%s/files/datasets" % self.config['METAX_API_ROOT_URL'], json=files, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        datasets = response.json()
        self.assertEqual(len(datasets), 3)
        self.assertTrue(dataset_1_pid in datasets or dataset_1_urn in datasets)
        self.assertTrue(dataset_2_pid in datasets or dataset_2_urn in datasets)
        self.assertTrue(dataset_3_pid in datasets or dataset_3_urn in datasets)

        print("Query Metax with no files from Datasets 1, 2, or 3")
        files = [ experiment_4_files[3]['pid'], experiment_4_files[4]['pid'], experiment_4_files[5]['pid'] ] 
        response = requests.post("%s/files/datasets" % self.config['METAX_API_ROOT_URL'], json=files, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        datasets = response.json()
        self.assertEqual(len(datasets), 0)

        print("Creating submitted PAS Dataset 4 containing all files in scope /testdata/2017-10/Experiment_4")
        dataset_data = DATASET_TEMPLATE
        dataset_data['research_dataset']['title'] = DATASET_TITLES[3]
        dataset_data['research_dataset']['files'] = self.build_dataset_files(experiment_4_files)
        dataset_data['preservation_state'] = 10
        response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], json=dataset_data, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))
        dataset_4 = response.json()
        dataset_4_pid = dataset_4['identifier']
        dataset_4_urn = dataset_4['research_dataset']['preferred_identifier']

        print("Creating pending PAS Dataset 5 containing all files in scope /testdata/2017-10/Experiment_4")
        dataset_data = DATASET_TEMPLATE
        dataset_data['research_dataset']['title'] = DATASET_TITLES[4]
        dataset_data['research_dataset']['files'] = self.build_dataset_files(experiment_4_files)
        dataset_data['preservation_state'] = 10
        dataset_data['preservation_dataset_origin_version'] = {
            "deprecated": False,
            "id": 54321,
            "identifier": "e4b9bdae-f7ba-48ad-b3c0-222bf0eac8a0",
            "preferred_identifier": "urn:nbn:fi:att:f8c3b322-8a52-424a-b27e-d2a2a48d4b35"
        }
        response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], json=dataset_data, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))
        dataset_5 = response.json()
        dataset_5_pid = dataset_5['identifier']
        dataset_5_urn = dataset_5['research_dataset']['preferred_identifier']

        print("Creating completed PAS Dataset 6 containing all files in scope /testdata/2017-10/Experiment_4")
        dataset_data = DATASET_TEMPLATE
        dataset_data['research_dataset']['title'] = DATASET_TITLES[5]
        dataset_data['research_dataset']['files'] = self.build_dataset_files(experiment_4_files)
        dataset_data['preservation_state'] = 120
        dataset_data['preservation_dataset_origin_version'] = {
            "deprecated": False,
            "id": 65432,
            "identifier": "a4b9bdae-f7ba-48ad-b3c0-222bf0eac8a0",
            "preferred_identifier": "urn:nbn:fi:att:a8c3b322-8a52-424a-b27e-d2a2a48d4b35"
        }
        response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], json=dataset_data, auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))
        dataset_6 = response.json()
        dataset_6_pid = dataset_6['identifier']
        dataset_6_urn = dataset_6['research_dataset']['preferred_identifier']

        print("Query IDA for datasets intersecting scope /testdata/2017-08/Experiment_1")
        data = { "project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1" }
        response = requests.post("%s/datasets" % self.config["IDA_API_ROOT_URL"], data=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        datasets = response.json()
        self.assertEqual(len(datasets), 1)
        self.assertTrue(datasets[0]['pid'] == dataset_1_pid)

        print("Query IDA for datasets intersecting scope /testdata/2017-08")
        data = { "project": "test_project_a", "pathname": "/testdata/2017-08" }
        response = requests.post("%s/datasets" % self.config["IDA_API_ROOT_URL"], data=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        datasets = response.json()
        self.assertEqual(len(datasets), 2)
        for dataset in datasets:
            self.assertTrue(dataset['pid'] in [ dataset_1_pid, dataset_2_pid ])

        print("Query IDA for datasets intersecting scope /testdata/2017-10/Experiment_3")
        data = { "project": "test_project_a", "pathname": "/testdata/2017-10/Experiment_3" }
        response = requests.post("%s/datasets" % self.config["IDA_API_ROOT_URL"], data=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        datasets = response.json()
        self.assertEqual(len(datasets), 1)
        self.assertTrue(datasets[0]['pid'] == dataset_3_pid)

        print("Query IDA for datasets intersecting scope /testdata/2017-10")
        data = { "project": "test_project_a", "pathname": "/testdata/2017-10" }
        response = requests.post("%s/datasets" % self.config["IDA_API_ROOT_URL"], data=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        datasets = response.json()
        self.assertEqual(len(datasets), 4)
        for dataset in datasets:
            self.assertTrue(dataset['pid'] in [ dataset_3_pid, dataset_4_pid, dataset_5_pid, dataset_6_pid ])
            if dataset['pid'] == dataset_3_pid:
                self.assertTrue(dataset['pas'] == False)
            elif dataset['pid'] == dataset_4_pid:
                self.assertTrue(dataset['pas'] == True)
            elif dataset['pid'] == dataset_5_pid:
                self.assertTrue(dataset['pas'] == True)
            elif dataset['pid'] == dataset_6_pid:
                self.assertTrue(dataset['pas'] == False)

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
