# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2019 Ministry of Education and Culture, Finland
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
import time
import os
from tests.common.utils import load_configuration


class TestRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("=== tests/nextcloud_apps/ida/test_repair")

    def setUp(self):
        # load service configuration variables
        self.config = load_configuration()

        # keep track of success, for reference in tearDown
        self.success = False

        print("(initializing)")

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s %s/tests/utils/initialize_test_accounts" % (self.config["HTTPD_USER"], self.config["ROOT"])
        os.system(cmd)
        cmd = "sudo -u %s %s/tests/utils/initialize_max_files test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        os.system(cmd)

    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success:
            print("(cleaning)")
            cmd = "sudo -u %s %s/tests/utils/initialize_test_accounts flush" % (self.config["HTTPD_USER"], self.config["ROOT"])
            os.system(cmd)

    def test_repair(self):

        # Note: the project names, user account names, and password for all PSO and user accounts
        # of test projects is hard coded in the initialization script, and the password for PSO
        # and user accounts is always "test".

        admin_user = (self.config["NC_ADMIN_USER"], self.config["NC_ADMIN_PASS"])
        pso_user_a = (self.config["PROJECT_USER_PREFIX"] + "test_project_a", "test")
        test_user_a = ("test_user_a", "test")

        print("--- Repair Actions")

        print("Freeze a folder")
        data = {"project": "test_project_a", "pathname": "/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        # Wait until previous action is complete, checking once per second, with timeout of 1 minute...
        print("(waiting for previous action to fully complete) ", end='')
        max_time = time.time() + 60
        while action_data.get("completed", None) == None and time.time() < max_time:
            time.sleep(1)
            response = requests.get("%s/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
            self.assertEqual(response.status_code, 200)
            action_data = response.json()
            print(".", end='')
        print("")
        self.assertIsNotNone(action_data.get("completed", None))

        print("Retrieve details of all frozen files associated with freeze action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        # File count for this freeze folder action should always be the same, based on the static test data initialized
        self.assertEqual(len(file_set_data), 11)
        file_data = file_set_data[0]
        self.assertIsNotNone(file_data.get("frozen", None))
        self.assertIsNone(file_data.get("cleared", None))
        # Save key values for later checks
        original_action_pid = action_data["pid"]
        original_action_file_count = 11
        original_first_file_record_id = file_data["id"]
        original_first_file_pid = file_data["pid"]
        original_first_file_pathname = file_data["pathname"]

        print("Repair project...")
        response = requests.post("%s/repair" % self.config["IDA_API_ROOT_URL"], auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "repair")
        self.assertEqual(action_data["pathname"], "/")

        # Wait until previous action is complete, checking once per second, with timeout of 1 minute...
        print("(waiting for previous action to fully complete) ", end='')
        max_time = time.time() + 60
        while action_data.get("completed", None) == None and time.time() < max_time:
            time.sleep(1)
            response = requests.get("%s/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
            self.assertEqual(response.status_code, 200)
            action_data = response.json()
            print(".", end='')
        print("")
        self.assertIsNotNone(action_data.get("completed", None))

        print("Retrieve details of all frozen files associated with repair action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        # Total count of frozen files should remain the same
        self.assertEqual(len(file_set_data), original_action_file_count)
        file_data = file_set_data[0]
        # First frozen file record should be clone of original and have different record id
        self.assertNotEqual(file_data["id"], original_first_file_record_id)
        # PID and pathname should not have changed for cloned file record
        self.assertEqual(file_data["pid"], original_first_file_pid)
        self.assertEqual(file_data["pathname"], original_first_file_pathname)
        # New cloned file record should be frozen but not cleared
        self.assertIsNotNone(file_data.get("frozen", None))
        self.assertIsNone(file_data.get("cleared", None))

        print("Retrieve details of all frozen files associated with original freeze action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], original_action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), original_action_file_count)
        file_data = file_set_data[0]
        self.assertEqual(file_data["id"], original_first_file_record_id)
        # Original frozen file record should be both frozen and also now cleared
        self.assertIsNotNone(file_data.get("frozen", None))
        self.assertIsNotNone(file_data.get("cleared", None))

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

