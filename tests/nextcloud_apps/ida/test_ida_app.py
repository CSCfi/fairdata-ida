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


class TestIdaApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("=== tests/nextcloud_apps/ida/test_ida_app")

    def setUp(self):
        # load service configuration variables
        self.config = load_configuration()

        # keep track of success, for reference in tearDown
        self.success = False

        # timeout when waiting for actions to complete
        self.timeout = 10800 # 3 hours

        print("(initializing)")

        # ensure we start with a fresh setup of projects, user accounts, and data

        cmd = "sudo -u %s %s/tests/utils/initialize_test_accounts" % (self.config["HTTPD_USER"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEquals(result, 0)

        cmd = "sudo -u %s %s/tests/utils/initialize_max_files test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEquals(result, 0)

        cmd = "sudo -u %s %s/tests/utils/initialize_max_files test_project_b" % (self.config["HTTPD_USER"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEquals(result, 0)


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success:
            print("(cleaning)")
            cmd = "sudo -u %s %s/tests/utils/initialize_test_accounts flush" % (self.config["HTTPD_USER"], self.config["ROOT"])
            os.system(cmd)


    def waitForPendingActions(self, project, user):
        print("(waiting for pending actions to fully complete)")
        print(".", end='', flush=True)
        response = requests.get("%s/actions?project=%s&status=pending" % (self.config["IDA_API_ROOT_URL"], project), auth=user, verify=False)
        self.assertEqual(response.status_code, 200)
        actions = response.json()
        max_time = time.time() + self.timeout
        while len(actions) > 0 and time.time() < max_time:
            print(".", end='', flush=True)
            time.sleep(1)
            response = requests.get("%s/actions?project=%s&status=pending" % (self.config["IDA_API_ROOT_URL"], project), auth=user, verify=False)
            self.assertEqual(response.status_code, 200)
            actions = response.json()
        print("")
        self.assertEqual(len(actions), 0, "Timed out waiting for pending actions to fully complete")


    def checkForFailedActions(self, project, user):
        print("(verifying no failed actions)")
        response = requests.get("%s/actions?project=%s&status=failed" % (self.config["IDA_API_ROOT_URL"], project), auth=user, verify=False)
        self.assertEqual(response.status_code, 200)
        actions = response.json()
        assert(len(actions) == 0)


    def test_ida_app(self):

        admin_user = (self.config["NC_ADMIN_USER"], self.config["NC_ADMIN_PASS"])
        pso_user_a = (self.config["PROJECT_USER_PREFIX"] + "test_project_a", self.config["PROJECT_USER_PASS"])
        pso_user_b = (self.config["PROJECT_USER_PREFIX"] + "test_project_b", self.config["PROJECT_USER_PASS"])
        pso_user_c = (self.config["PROJECT_USER_PREFIX"] + "test_project_c", self.config["PROJECT_USER_PASS"])
        pso_user_d = (self.config["PROJECT_USER_PREFIX"] + "test_project_d", self.config["PROJECT_USER_PASS"])
        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
        test_user_b = ("test_user_b", self.config["TEST_USER_PASS"])
        test_user_c = ("test_user_c", self.config["TEST_USER_PASS"])
        test_user_d = ("test_user_d", self.config["TEST_USER_PASS"])
        test_user_x = ("test_user_x", self.config["TEST_USER_PASS"])

        frozen_area_root = "%s/PSO_test_project_a/files/test_project_a" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root = "%s/PSO_test_project_a/files/test_project_a%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        print("--- Freeze Actions")

        print("Freeze a single file")
        data = {"project": "test_project_a", "pathname": "/2017-08/Experiment_1/test01.dat"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        # TODO: check that all mandatory fields are defined with valid values for action

        print("Verify file was physically moved from staging to frozen area")
        self.assertFalse(os.path.exists("%s/2017-08/Experiment_1/test01.dat" % (staging_area_root)))
        self.assertTrue(os.path.exists("%s/2017-08/Experiment_1/test01.dat" % (frozen_area_root)))

        print("Retrieve details of all frozen files associated with previous action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), 1)
        file_data = file_set_data[0]
        file_pid = file_data["pid"]
        self.assertEqual(file_data["project"], data["project"])
        self.assertEqual(file_data["action"], action_data["pid"])

        # TODO: check that all mandatory fields are defined with valid values for frozen file

        print("Retrieve frozen file details by pathname")
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API_ROOT_URL"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["pathname"], data["pathname"])
        self.assertEqual(file_data["pid"], file_pid)
        self.assertEqual(file_data["size"], 446)

        print("Retrieve frozen file details by PID")
        response = requests.get("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data_2 = response.json()
        self.assertEqual(file_data_2["pid"], file_data["pid"])
        self.assertEqual(file_data_2["project"], file_data["project"])
        self.assertEqual(file_data_2["pathname"], file_data["pathname"])
        self.assertEqual(file_data["size"], 446)

        print("Freeze a folder")
        data["pathname"] = "/2017-08/Experiment_1"
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        action_pid = action_data["pid"]
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        # TODO: ensure folder was physically moved from staging area to frozen area

        print("Retrieve details of all frozen files associated with previous action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), 12)
        # file count for this freeze folder action should never change, even if files are unfrozen/deleted
        # (store this action PID and verify after all unfreeze and delete actions that count has not changed)
        original_freeze_folder_action_pid = action_pid
        original_freeze_folder_action_file_count = 12

        print("Retrieve file details from hidden frozen file")
        data = {"project": "test_project_a", "pathname": "/2017-08/Experiment_1/.hidden_file"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API_ROOT_URL"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_x_data = response.json()
        self.assertEqual(file_x_data.get('size', None), 446)

        print("Attempt to freeze an empty folder")
        data["pathname"] = "/empty_folder"
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data["message"], "The specified folder contains no files which can be frozen.")

        # --------------------------------------------------------------------------------

        print("--- Unfreeze Actions")

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Unfreeze single frozen file")
        data["pathname"] = "/2017-08/Experiment_1/baseline/test01.dat"
        response = requests.post("%s/unfreeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "unfreeze")
        self.assertEqual(action_data["pathname"], data["pathname"])

        # TODO: check that all mandatory fields are defined with valid values for action

        print("Verify file was physically moved from frozen to staging area")
        self.assertFalse(os.path.exists("%s/2017-08/Experiment_1/baseline/test01.dat" % (frozen_area_root)))
        self.assertTrue(os.path.exists("%s/2017-08/Experiment_1/baseline/test01.dat" % (staging_area_root)))

        print("Retrieve details of all frozen files associated with previous action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), 1)
        file_data = file_set_data[0]
        self.assertEqual(file_data["project"], data["project"])
        self.assertEqual(file_data["action"], action_data["pid"])

        # TODO: check that all mandatory fields are defined with valid values for unfrozen file (e.g. removed, etc.)

        print("Unfreeze a folder")
        data["pathname"] = "/2017-08/Experiment_1/baseline"
        response = requests.post("%s/unfreeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "unfreeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        # TODO: ensure folder was physically moved from frozen area to staging area

        print("Retrieve details of all unfrozen files associated with previous action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), 5)

        print("Attempt to retrieve details of all unfrozen files associated with previous action as user without rights to project")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Attempt to retrieve details of all unfrozen files associated with a non-existent action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], "NO_SUCH_PID"), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Attempt to unfreeze an empty folder")
        data["pathname"] = "/empty_folder"
        response = requests.post("%s/unfreeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data["message"], "The specified folder contains no files which can be unfrozen.")

        # --------------------------------------------------------------------------------

        print("--- Delete Actions")

        print("Delete single frozen file")
        data["pathname"] = "/2017-08/Experiment_1/test02.dat"
        response = requests.post("%s/delete" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "delete")
        self.assertEqual(action_data["pathname"], data["pathname"])

        # TODO: check that all mandatory fields are defined with valid values for action

        print("Verify file was physically removed from frozen area")
        self.assertFalse(os.path.exists("%s/2017-08/Experiment_1/test02.dat" % (frozen_area_root)))

        print("Retrieve details of all deleted files associated with previous action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), 1)
        file_data = file_set_data[0]
        self.assertEqual(file_data["project"], data["project"])
        self.assertEqual(file_data["action"], action_data["pid"])
        self.assertIsNotNone(file_data.get("removed", None))

        # TODO: check that all mandatory fields are defined with valid values for unfrozen file

        print("Delete a frozen folder")
        data["pathname"] = "/2017-08/Experiment_1"
        response = requests.post("%s/delete" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "delete")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        print("Verify folder was physically removed from frozen area")
        self.assertFalse(os.path.exists("%s/2017-08/Experiment_1" % (frozen_area_root)))

        print("Retrieve details of all deleted files associated with previous action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), 6)

        print("Verify file count has not changed for original freeze folder action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], original_freeze_folder_action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), original_freeze_folder_action_file_count)

        print("Delete an empty folder and verify action is completed")
        data["pathname"] = "/empty_folder"
        response = requests.post("%s/delete" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "delete")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])
        self.assertIsNotNone(action_data.get("completed", None))

        # --------------------------------------------------------------------------------

        print("--- Maximum File Limitations")

        print("Attempt to freeze a folder with more than max allowed files")
        data["pathname"] = "/MaxFiles"
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 400)

        # TODO: Verify after failed freeze request that files are still in staging and no pending action exists

        print("Freeze a folder with max allowed files")
        data["pathname"] = "/MaxFiles/%s_files" % (self.config["MAX_FILE_COUNT"])
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Freeze one additional file to folder with max allowed files")
        data["pathname"] = "/MaxFiles/test_file.dat"
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        action_data = response.json()
        action_pid = action_data["pid"]
        self.assertEqual(response.status_code, 200)

        print("Attempt to unfreeze a frozen folder with more than max allowed files")
        data["pathname"] = "/MaxFiles"
        response = requests.post("%s/unfreeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 400)

        print("Attempt to delete a frozen folder with more than max allowed files")
        data["pathname"] = "/MaxFiles"
        response = requests.post("%s/delete" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 400)

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Unfreeze a folder with max allowed files")
        data["pathname"] = "/MaxFiles/%s_files" % (self.config["MAX_FILE_COUNT"])
        response = requests.post("%s/unfreeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.text)

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Freeze a folder with max allowed files")
        data["pathname"] = "/MaxFiles/%s_files" % (self.config["MAX_FILE_COUNT"])
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Delete a folder with max allowed files")
        data["pathname"] = "/MaxFiles/%s_files" % (self.config["MAX_FILE_COUNT"])
        response = requests.post("%s/delete" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        # --------------------------------------------------------------------------------

        print("--- Action Record Operations")

        print("Retrieve set of completed actions")
        data = {"projects": "test_project_a", "status": "completed"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 12)
        action_data = action_set_data[0]
        action_pid = action_data["pid"]
        self.assertIsNotNone(action_data.get("completed", None))

        print("Update action as pending, clearing completed timestamp")
        data = {"completed": "null"}
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["pid"], action_pid)
        self.assertIsNone(action_data.get("completed", None))

        print("Retrieve set of pending actions")
        data = {"projects": "test_project_a", "status": "pending"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 1)
        action_data = action_set_data[0]
        self.assertEqual(action_data["pid"], action_pid)
        self.assertIsNone(action_data.get("completed", None))

        print("Update action as incomplete, clearing storage timestamp")
        data = {"storage": "null"}
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["pid"], action_pid)
        self.assertIsNone(action_data.get("storage", None))
        self.assertIsNone(action_data.get("completed", None))

        print("Retrieve set of incomplete actions")
        data = {"projects": "test_project_a", "status": "incomplete"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 1)
        action_data = action_set_data[0]
        self.assertEqual(action_data["pid"], action_pid)
        self.assertIsNone(action_data.get("storage", None))
        self.assertIsNone(action_data.get("completed", None))

        print("Update action as failed with error message")
        data = {"error": "test error message", "failed": "2000-01-01T00:00:00Z", "completed": "null"}
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["pid"], action_pid)
        self.assertEqual(action_data["error"], data["error"])
        self.assertEqual(action_data["failed"], data["failed"])
        self.assertIsNone(action_data.get("storage", None))
        self.assertIsNone(action_data.get("completed", None))

        print("Retrieve set of failed actions")
        data = {"projects": "test_project_a", "status": "failed"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 1)
        action_data = action_set_data[0]
        self.assertEqual(action_data["pid"], action_pid)
        self.assertIsNotNone(action_data.get("error", None))
        self.assertIsNotNone(action_data.get("failed", None))
        self.assertIsNone(action_data.get("storage", None))
        self.assertIsNone(action_data.get("completed", None))

        print("Clear failed action")
        response = requests.post("%s/clear/%s" % (self.config["IDA_API_ROOT_URL"], action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["pid"], action_pid)
        self.assertIsNotNone(action_data.get("cleared", None))

        print("Attempt to retrieve set of actions for project user has no rights to")
        data = {"projects": "test_project_c"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 0)

        # TODO: consider which tests may be missing...

        # --------------------------------------------------------------------------------

        print("--- File Record Operations")

        print("Freeze a single file")
        data = {"project": "test_project_a", "pathname": "/License.txt"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Retrieve frozen file details by pathname")
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API_ROOT_URL"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        file_pid = file_data["pid"]
        file_node = file_data["node"]

        print("Retrieve frozen file details by PID")
        response = requests.get("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data_2 = response.json()
        self.assertEqual(file_data_2["id"], file_data["id"])

        print("Retrieve frozen file details by Nextcloud node ID")
        response = requests.get("%s/files/byNextcloudNodeId/%d" % (self.config["IDA_API_ROOT_URL"], file_node), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data_2 = response.json()
        self.assertEqual(file_data_2["id"], file_data["id"])

        print("Attempt to retrieve details of file user has no rights to")
        response = requests.get("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Update checksum as plain checksum value")
        data = {"checksum": "thisisaplainchecksumvalue"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["pid"], file_pid)
        self.assertEqual(file_data["checksum"], "sha256:thisisaplainchecksumvalue")

        print("Update checksum as sha256: checksum URI")
        data = {"checksum": "sha256:thisisachecksumuri"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["pid"], file_pid)
        self.assertEqual(file_data["checksum"], "sha256:thisisachecksumuri")

        print("Update size")
        data = {"size": 1234}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["pid"], file_pid)
        self.assertEqual(file_data["size"], data["size"])

        print("Update metadata timestamp")
        data = {"metadata": "2000-01-01T00:00:00Z"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["pid"], file_pid)
        self.assertEqual(file_data["metadata"], data["metadata"])

        print("Clear removed timestamp")
        data = {"removed": "null"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["pid"], file_pid)
        self.assertIsNone(file_data.get("removed", None))

        print("Set removed timestamp")
        data = {"removed": "2000-01-01T00:00:00Z"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["pid"], file_pid)
        self.assertEqual(file_data["removed"], data["removed"])

        print("Attempt to retrieve removed file details by pathname")
        data = {"project": "test_project_a", "pathname": "/License.txt"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API_ROOT_URL"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Attempt to retrieve removed file details by PID")
        response = requests.get("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Attempt to retrieve removed file details by Nextcloud node ID")
        response = requests.get("%s/files/byNextcloudNodeId/%d" % (self.config["IDA_API_ROOT_URL"], file_node), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 404)

        # TODO: consider which tests may be missing...

        # --------------------------------------------------------------------------------

        print("--- Invalid Timestamps")

        # All of the preceding tests cover expected behavior with valid timestamps used. The
        # following tests ensure that requests with invalid timestamps are rejected.

        print("Attempt to set invalid timestamp: date only, no time")
        data = {"removed": "2017-11-12"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 400)

        print("Attempt to set invalid timestamp: invalid time separator syntax")
        data = {"removed": "2017-11-12 15:48:15Z"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 400)

        print("Attempt to set invalid timestamp: invalid timezone")
        data = {"removed": "2017-11-12T15:48+0000"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 400)

        print("Attempt to set invalid timestamp: invalid format")
        data = {"removed": "Tue, Dec 12, 2017 10:03 UTC"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API_ROOT_URL"], file_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 400)

        # TODO: consider which tests may be missing...

        # --------------------------------------------------------------------------------

        print("--- Failed Actions")

        # Strategy: freeze a file, waiting for action to complete. Clear all postprocessing
        # related timestamps, i.e. all following the Pids timestamp, and mark the action as
        # failed. Then retry the failed freeze action, which will result in all postprocesing
        # steps being redone (even though unnecesary)

        print("Freeze a single file")
        data = {"project": "test_project_a", "pathname": "/2017-08/Experiment_2/test01.dat"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        action_pid = action_data["pid"]
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Update action as failed, clearing postprocessing timestamps")
        data = {
            "error":       "test error message",
            "failed":      "2000-01-01T00:00:00Z",
            "checksums":   "null",
            "metadata":    "null",
            "replication": "null",
            "completed":   "null"
        }
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["pid"], action_pid)
        self.assertEqual(action_data["error"], data["error"])
        self.assertEqual(action_data["failed"], data["failed"])
        self.assertIsNone(action_data.get("checksums", None))
        self.assertIsNone(action_data.get("metadata", None))
        self.assertIsNone(action_data.get("replication", None))
        self.assertIsNone(action_data.get("completed", None))

        print("Retrieve set of failed actions")
        data = {"projects": "test_project_a", "status": "failed"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 1)
        action_data = action_set_data[0]
        self.assertEqual(action_data["pid"], action_pid)
        self.assertIsNotNone(action_data.get("error", None))
        self.assertIsNotNone(action_data.get("failed", None))
        self.assertIsNone(action_data.get("checksums", None))
        self.assertIsNone(action_data.get("metadata", None))
        self.assertIsNone(action_data.get("replication", None))
        self.assertIsNone(action_data.get("completed", None))
        self.assertIsNone(action_data.get("retry", None))
        self.assertIsNone(action_data.get("retrying", None))

        print("Retry failed action")
        response = requests.post("%s/retry/%s" % (self.config["IDA_API_ROOT_URL"], action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["pid"], action_pid)
        self.assertIsNone(action_data.get("retrying", None))
        self.assertIsNotNone(action_data.get("retry", None))
        self.assertIsNotNone(action_data.get("cleared", None))
        self.assertIsNotNone(action_data.get("error", None))
        self.assertIsNotNone(action_data.get("failed", None))
        retry_action_pid = action_data["retry"]

        print("Retrieve retry action")
        response = requests.get("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], retry_action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["pid"], retry_action_pid)
        self.assertEqual(action_data.get("retrying", None), action_pid)
        self.assertIsNone(action_data.get("retry", None))
        self.assertIsNone(action_data.get("cleared", None))
        action_pid = retry_action_pid

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("Verify set of failed actions is empty")
        data = {"project": "test_project_a", "status": "failed"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 0)

        print("Update retry action as failed")
        data = {"error": "test error message", "failed": "2000-01-01T00:00:00Z"}
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_pid), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["pid"], action_pid)
        self.assertEqual(action_data["error"], data["error"])
        self.assertEqual(action_data["failed"], data["failed"])

        print("Retrieve set of failed actions")
        data = {"projects": "test_project_a", "status": "failed"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 1)
        action_data = action_set_data[0]
        self.assertEqual(action_data["pid"], action_pid)

        print("Clear all failed actions for project")
        data = {"projects": "test_project_a", "status": "failed"}
        response = requests.post("%s/clearall" % (self.config["IDA_API_ROOT_URL"]), json=data, auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify set of failed actions is empty")
        data = {"project": "test_project_a", "status": "failed"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 0)

        # TODO: consider which tests may be missing...

        # --------------------------------------------------------------------------------

        print("--- Access Control")

        # All of the preceding tests cover expected behavior with the credentials used. The
        # following tests ensure that requests with inappropriate credentials are rejected.

        print("Attempt to freeze file as admin user")
        data = {"project": "test_project_c", "pathname": "/2017-08/Experiment_2/test01.dat"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 401)

        print("Attempt to retrieve file details from project to which user does not belong")
        data = {"project": "test_project_a", "pathname": "/2017-08/Experiment_1/test05.dat"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 401)

        print("Attempt to freeze file in project to which user does not belong")
        data = {"project": "test_project_c", "pathname": "/2017-08/Experiment_1/test05.dat"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 401)

        # TODO: add tests attempting to update file and action records as normal user, when must be PSO user

        # TODO: add tests for housekeeping operations as normal user, when must be admin or PSO user

        # TODO: add tests for housekeeping operations as PSO user, when must be admin

        # TODO: consider which tests may be missing...

        # --------------------------------------------------------------------------------
        
        # TODO: add tests attempting to copy files or folders to or within the frozen area (not fully covered by CLI tests)

        # TODO: add tests for copying files or folders from the frozen area to the staging area (not fully covered by CLI tests)

        # TODO: add tests for checking required parameters

        # TODO: add tests for pathnames containing special characters

        # --------------------------------------------------------------------------------

        print("--- Project Locking")

        print("Verify that project is unlocked")
        # GET /app/ida/api/lock/test_project_c as test_user_c should fail with 404 Not found
        response = requests.get("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Attempt to lock project as regular user")
        # POST /app/ida/api/lock/test_project_c as test_user_c should fail with 401 Unauthorized
        response = requests.post("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 401)

        print("Lock project")
        # POST /app/ida/api/lock/test_project_c as pso_user_c should succeed with 200 OK
        response = requests.post("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that project is locked")
        # GET /app/ida/api/lock/test_project_c as test_user_c should succeed with 200 OK
        response = requests.get("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Attempt to lock already locked project")
        # POST /app/ida/api/lock/test_project_c as pso_user_c should fail with 409 Conflict due
        # to already locked project
        response = requests.post("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        print("Attempt to freeze file while project is locked")
        # POST /app/ida/api/freeze?project=test_project_c&pathname=/2017-08/Experiment_1/test01.dat
        # should fail with 409 Conflict due to locked project
        data = {"project": "test_project_c", "pathname": "/2017-08/Experiment_1/test01.dat"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        print("Attempt to unlock project as regular user")
        # DELETE /app/ida/api/lock/test_project_c as test_user_c should fail with 401 Unauthorized
        response = requests.delete("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 401)

        print("Unlock project")
        # DELETE /app/ida/api/lock/test_project_c as pso_user_c should succeed with 200 OK
        response = requests.delete("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that project is unlocked")
        # GET /app/ida/api/lock/test_project_c as test_user_c should fail with 404 Not found
        response = requests.get("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Unlock already unlocked project")
        # DELETE /app/ida/api/lock/test_project_c as pso_user_c should still succeed with 200 OK
        response = requests.delete("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Freeze a file in an unlocked project")
        # POST /app/ida/api/freeze?project=test_project_c&pathname=/2017-08/Experiment_1/test01.dat
        # should succeed with 200 OK as project is not locked
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("--- Service Locking")

        print("Verify that service is unlocked")
        # GET /app/ida/api/lock/all as test_user_c should fail with 404 Not found
        response = requests.get("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Attempt to lock service as regular user")
        # POST /app/ida/api/lock/all as test_user_c should fail with 401 Unauthorized
        response = requests.post("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 401)

        print("Attempt to lock service as project share owner")
        # POST /app/ida/api/lock/all as pso_user_c should fail with 401 Unauthorized
        response = requests.post("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 401)

        print("Lock service")
        # POST /app/ida/api/lock/all as admin_user should succeed with 200 OK
        response = requests.post("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that service is locked as regular user")
        # GET /app/ida/api/lock/all as test_user_c should succeed with 200 OK
        response = requests.get("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that service is locked as project share owner")
        # GET /app/ida/api/lock/all as pso_user_c should succeed with 200 OK
        response = requests.get("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that service is locked as admin user")
        # GET /app/ida/api/lock/all as admin_user should succeed with 200 OK
        response = requests.get("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Attempt to lock project while service is locked")
        # POST /app/ida/api/lock/test_project_c as pso_user_c should fail with 409 Conflict as
        # can't lock a project when service is locked
        response = requests.post("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        print("Lock already locked service")
        # POST /app/ida/api/lock/all as admin_user should still succeed with 200 OK
        response = requests.post("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Attempt to freeze file while service is locked")
        # POST /app/ida/api/freeze?project=test_project_c&pathname=/2017-08/Experiment_1/test02.dat
        # should fail with 409 Conflict due to locked project
        data["pathname"] = "/2017-08/Experiment_1/test02.dat"
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        print("Verify all scope checks fail while service is locked")
        # All of the following requests as test_user_c should fail with 409 Conflict as service is locked:
        data["pathname"] = "/"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)
        data["pathname"] = "/2017-08"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)
        data["pathname"] = "/2017-08/Experiment_1"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)
        data["pathname"] = "/2017-08/Experiment_1/test01.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)
        data["pathname"] = "/2017-08/Contact.txt"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)
        data["pathname"] = "/X/Y/Z"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        print("Attempt to unlock service as regular user")
        # DELETE /app/ida/api/lock/all as test_user_c should fail with 401 Unauthorized
        response = requests.delete("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 401)

        print("Attempt to unlock service as project share owner")
        # DELETE /app/ida/api/lock/all as PSO_test_project_c should fail with 401 Unauthorized
        response = requests.delete("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 401)

        print("Unlock service")
        # DELETE /app/ida/api/lock/all as admin_user should succeed with 200 OK
        response = requests.delete("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that service is unlocked")
        # GET /app/ida/api/lock/all as test_user_c should fail with 404 Not found
        response = requests.get("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Unlock already unlocked service")
        # DELETE /app/ida/api/lock/all as admin_user should still succeed with 200 OK
        response = requests.delete("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Freeze file in unlocked service")
        # POST /app/ida/api/freeze?project=test_project_c&pathname=/2017-08/Experiment_1/test02.dat as
        # test_user_c should succeed with 200 OK as service is not locked
        data["pathname"] = "/2017-08/Experiment_1/test02.dat"
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json() # For use in subsequent action collision tests below

        print("Lock project in unlocked service")
        # POST /app/ida/api/lock/test_project_c as pso_user_c should succeed with 200 OK
        response = requests.post("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Lock service even though project is locked")
        # POST /app/ida/api/lock/all as admin_user should succeed with 200 OK
        response = requests.post("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Unlock project even though service is locked")
        # DELETE /app/ida/api/lock/test_project_c as pso_user_c should succeed with 200 OK as it
        # should be allowed to unlock a project even when the service is locked
        response = requests.delete("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Unlock service")
        # DELETE /app/ida/api/lock/all as admin_user should succeed with 200 OK
        response = requests.delete("%s/lock/all" % self.config["IDA_API_ROOT_URL"], auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("--- Action Collisions")

        print("Simulate pending action")
        # Simulate pending freeze action by removing all step timestamps from preceeding action following storage timestamp
        # (frozen pending action pathname = "/2017-08/Experiment_1/test02.dat")
        data = {"checksums": "null", "metadata": "null", "replication": "null", "completed": "null"}
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), json=data, auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Create new file in staging with same pathname as file in scope of pending action")
        # pathname = "/2017-08/Experiment_1/test02.dat"
        cmd = "touch %s/PSO_test_project_c/files/test_project_c+/2017-08/Experiment_1/test02.dat" % (self.config["STORAGE_OC_DATA_ROOT"])
        os.system(cmd)
        cmd = "sudo -u %s %s/nextcloud/occ files:scan PSO_test_project_c 2>&1 >/dev/null" % (self.config["HTTPD_USER"], self.config["ROOT"])
        os.system(cmd)

        print("Attempt to freeze folder which intersects with file associated with pending action")
        # POST /app/ida/api/unfreeze?project=test_project_c&pathname=/2017-08/Experiment_1 as test_user_c
        # should fail with 409 Conflict due to collision with the previous pending action
        data = {"project": "test_project_c", "pathname": "/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)
        # TODO: check for actual error message indicating cause of conflict

        print("Freeze file which does not intersect with pending action")
        # POST /app/ida/api/freeze?project=test_project_c&pathname=/2017-10/Experiment_3/test01.dat
        # should succeed with 200 OK
        data["pathname"] = "/2017-10/Experiment_3/test01.dat"
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify that project is unlocked")
        # GET /app/ida/api/lock/test_project_c as test_user_c should fail with 404 Not found
        response = requests.get("%s/lock/test_project_c" % self.config["IDA_API_ROOT_URL"], auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 404)

        print("Complete simulated pending action")
        # Update simulated action to be fully completed with all timestamps defined
        data = {"completed": "2000-01-01T00:00:00Z"}
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), json=data, auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Attempt to freeze folder which intersects with file already in frozen area")
        # POST /app/ida/api/unfreeze?project=test_project_c&pathname=/2017-08/Experiment_1 as test_user_c
        # should fail with 409 Conflict due to collision with existing file in frozen area
        data = {"project": "test_project_c", "pathname": "/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)
        # TODO: check for actual error message indicating cause of conflict

        print("Remove new file in staging with same pathname as file in scope of pending action")
        # pathname = "/2017-08/Experiment_1/test02.dat"
        cmd = "rm %s/PSO_test_project_c/files/test_project_c+/2017-08/Experiment_1/test02.dat" % (self.config["STORAGE_OC_DATA_ROOT"])
        os.system(cmd)
        cmd = "sudo -u %s %s/nextcloud/occ files:scan PSO_test_project_c 2>&1 >/dev/null" % (self.config["HTTPD_USER"], self.config["ROOT"])
        os.system(cmd)

        print("Freeze folder which no longer intersects with pending action or existing file in frozen area")
        # POST /app/ida/api/unfreeze?project=test_project_c&pathname=/2017-08/Experiment_1 as
        # test_user_c should succeed with 200 OK
        data = {"project": "test_project_c", "pathname": "/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        # TODO: consider which tests may be missing...

        print("--- Scope Collisions")

        print("Freeze folder which does not intersect with pending action or existing file in frozen area")
        # POST /app/ida/api/freeze?project=test_project_c&pathname=/2017-11/Experiment_6 should succeed with 200 OK
        data = {"project": "test_project_c", "pathname": "/2017-11/Experiment_6"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json() # For use in subsequent action collision tests below

        self.waitForPendingActions("test_project_c", test_user_c)
        self.checkForFailedActions("test_project_c", test_user_c)

        print("Simulate incomplete action")
        # Simulate incomplete freeze action by removing all step timestamps from preceeding action following pids timestamp
        # (frozen pending action pathname = "/2017-11/Experiment_6")
        data = {"storage": "null", "checksums": "null", "metadata": "null", "replication": "null", "completed": "null"}
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), json=data, auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify disallowed scopes are rejected")
        # All of the following as test_user_c should fail with 409 Conflict:
        data = {"project": "test_project_c"}

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/
        data["pathname"] = "/"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11
        data["pathname"] = "/2017-11"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11/Experiment_6
        data["pathname"] = "/2017-11/Experiment_6"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11/Experiment_6/test9999.dat
        data["pathname"] = "/2017-11/Experiment_6/test9999.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11/Experiment_6/baseline/testXYZ.dat
        data["pathname"] = "/2017-11/Experiment_6/baseline/testXYZ.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11/Experiment_6/.hidden_file.dat
        data["pathname"] = "/2017-11/Experiment_6/.hidden_file.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        print("Verify allowed scopes are OK")
        # All of the following as test_user_c should succeed with 200 OK:

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/XYZ
        data["pathname"] = "/XYZ"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2018-08
        data["pathname"] = "/2017-08"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2018-08/test05.dat
        data["pathname"] = "/2017-08/test05.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-10/Experiment_5
        data["pathname"] = "/2017-10/Experiment_5"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/Contact.txt
        data["pathname"] = "/Contact.txt"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-10/Experiment_2/baseline/test03.dat
        data["pathname"] = "/2017-10/Experiment_2/baseline/test03.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        print("Verify root scope blocks all other scopes")

        # Record incomplete freeze action as completed
        data = {"completed": "2000-01-01T00:00:00Z"}
        response = requests.post("%s/actions/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), json=data, auth=pso_user_c, verify=False)
        self.assertEqual(response.status_code, 200)

        # Verify no incomplete actions
        data = {"project": "test_project_c", "status": "incomplete"}
        response = requests.get("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)
        action_set_data = response.json()
        self.assertEqual(len(action_set_data), 0)

        # Simulate repair action with scope "/" and ensure every possible other scope is blocked
        data = {"action": "repair", "project": "test_project_c", "pathname": "/"}
        response = requests.post("%s/actions" % self.config["IDA_API_ROOT_URL"], json=data, auth=admin_user, verify=False)
        self.assertEqual(response.status_code, 200)

        # All of the following as test_user_c should fail with 409 Conflict:
        data = {"project": "test_project_c"}

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/
        data["pathname"] = "/"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11
        data["pathname"] = "/2017-11"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11/Experiment_6
        data["pathname"] = "/2017-11/Experiment_6"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11/Experiment_6/test9999.dat
        data["pathname"] = "/2017-11/Experiment_6/test9999.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11/Experiment_6/baseline/testXYZ.dat
        data["pathname"] = "/2017-11/Experiment_6/baseline/testXYZ.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-11/Experiment_6/.hidden_file.dat
        data["pathname"] = "/2017-11/Experiment_6/.hidden_file.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/XYZ
        data["pathname"] = "/XYZ"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2018-08
        data["pathname"] = "/2017-08"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2018-08/test05.dat
        data["pathname"] = "/2017-08/test05.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-10/Experiment_5
        data["pathname"] = "/2017-10/Experiment_5"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/Contact.txt
        data["pathname"] = "/Contact.txt"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # POST /app/ida/api/checkScope?project=test_project_c&pathname=/2017-10/Experiment_2/baseline/test03.dat
        data["pathname"] = "/2017-10/Experiment_2/baseline/test03.dat"
        response = requests.post("%s/checkScope" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 409)

        # TODO: consider which tests may be missing...

        # --------------------------------------------------------------------------------

        print("--- Repair Actions")

        print("Freeze a folder")
        data = {"project": "test_project_d", "pathname": "/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        action_pid = action_data["pid"]
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_d", test_user_d)
        self.checkForFailedActions("test_project_d", test_user_d)

        print("Retrieve details of all frozen files associated with freeze action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        # File count for this freeze folder action should always be the same, based on the static test data initialized
        self.assertEqual(len(file_set_data), 13)
        file_data = file_set_data[0]
        self.assertIsNotNone(file_data.get("frozen", None))
        self.assertIsNone(file_data.get("cleared", None))
        # Save key values for later checks
        original_action_pid = action_data["pid"]
        original_action_file_count = 13
        original_first_file_record_id = file_data["id"]
        original_first_file_pid = file_data["pid"]
        original_first_file_pathname = file_data["pathname"]

        print("Retrieve file details from hidden frozen file")
        data = {"project": "test_project_d", "pathname": "/2017-08/Experiment_1/.hidden_file"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API_ROOT_URL"], data["project"]), json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        file_x_data = response.json()
        self.assertEqual(file_x_data.get('size', None), 446)

        print("Repair project...")
        response = requests.post("%s/repair" % self.config["IDA_API_ROOT_URL"], auth=pso_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        action_pid = action_data["pid"]
        self.assertEqual(action_data["action"], "repair")
        self.assertEqual(action_data["pathname"], "/")

        self.waitForPendingActions("test_project_d", test_user_d)
        self.checkForFailedActions("test_project_d", test_user_d)

        print("Retrieve details of all frozen files associated with repair action")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_d, verify=False)
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
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], original_action_pid), auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), original_action_file_count)
        file_data = file_set_data[0]
        self.assertEqual(file_data["id"], original_first_file_record_id)
        # Original frozen file record should be both frozen and also now cleared
        self.assertIsNotNone(file_data.get("frozen", None))
        self.assertIsNotNone(file_data.get("cleared", None))

        print("Retrieve file details from hidden frozen file")
        data = {"project": "test_project_d", "pathname": "/2017-08/Experiment_1/.hidden_file"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API_ROOT_URL"], data["project"]), json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        file_x_data = response.json()
        self.assertEqual(file_x_data.get('size', None), 446)

        # NOTE tests for postprocessing results of repair action are handled in /tests/agents/test_agents.py

        # --------------------------------------------------------------------------------

        print("--- Batch Actions")

        frozen_area_root = "%s/PSO_test_project_b/files/test_project_b" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root = "%s/PSO_test_project_b/files/test_project_b%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])
        cmd_base="sudo -u %s %s/utils/admin/execute-batch-action" % (self.config["HTTPD_USER"], self.config["ROOT"])

        print("Attempt to freeze a folder with more than max allowed files")
        data = {"project": "test_project_b", "pathname": "/MaxFiles"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_b, verify=False)
        self.assertEqual(response.status_code, 400)

        print("Batch freeze a folder with more than max allowed files")
        cmd = "%s test_project_b freeze /MaxFiles >/dev/null" % (cmd_base)
        result = os.system(cmd)
        self.assertEqual(result, 0)

        self.waitForPendingActions("test_project_b", test_user_b)
        self.checkForFailedActions("test_project_b", test_user_b)

        print("Verify data was physically moved from staging to frozen area")
        self.assertFalse(os.path.exists("%s/MaxFiles/%s_files/500_files_1/100_files_1/10_files_1/test_file_1.dat" % (staging_area_root, self.config["MAX_FILE_COUNT"])))
        self.assertFalse(os.path.exists("%s/MaxFiles" % (staging_area_root)))
        self.assertTrue(os.path.exists("%s/MaxFiles/%s_files/500_files_1/100_files_1/10_files_1/test_file_1.dat" % (frozen_area_root, self.config["MAX_FILE_COUNT"])))

        print("Batch unfreeze a folder with more than max allowed files")
        cmd = "%s test_project_b unfreeze /MaxFiles >/dev/null" % (cmd_base)
        result = os.system(cmd)
        self.assertEqual(result, 0)

        self.waitForPendingActions("test_project_b", test_user_b)
        self.checkForFailedActions("test_project_b", test_user_b)

        print("Verify data was physically moved from frozen to staging area")
        self.assertFalse(os.path.exists("%s/MaxFiles/%s_files/500_files_1/100_files_1/10_files_1/test_file_1.dat" % (frozen_area_root, self.config["MAX_FILE_COUNT"])))
        self.assertFalse(os.path.exists("%s/MaxFiles" % (frozen_area_root)))
        self.assertTrue(os.path.exists("%s/MaxFiles/%s_files/500_files_1/100_files_1/10_files_1/test_file_1.dat" % (staging_area_root, self.config["MAX_FILE_COUNT"])))

        print("Batch freeze a folder with more than max allowed files")
        cmd = "%s test_project_b freeze /MaxFiles >/dev/null" % (cmd_base)
        result = os.system(cmd)
        self.assertEqual(result, 0)

        self.waitForPendingActions("test_project_b", test_user_b)
        self.checkForFailedActions("test_project_b", test_user_b)

        print("Batch delete a folder with more than max allowed files")
        cmd = "%s test_project_b delete /MaxFiles >/dev/null" % (cmd_base)
        result = os.system(cmd)
        self.assertEqual(result, 0)

        self.waitForPendingActions("test_project_b", test_user_b)
        self.checkForFailedActions("test_project_b", test_user_b)

        print("Verify data was physically removed from frozen area")
        self.assertFalse(os.path.exists("%s/MaxFiles" % (frozen_area_root)))

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
