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
import shutil
from tests.common.utils import *


class TestAgents(unittest.TestCase):


    @classmethod
    def setUpClass(cls):
        print("=== tests/agents/test_agents")


    def setUp(self):
        # load service configuration variables
        self.config = load_configuration()

        # keep track of success, for reference in tearDown
        self.success = False

        # timeout when waiting for actions to complete
        self.timeout = 10800 # 3 hours

        print("(initializing)")

        # ensure we start with a fresh setup of projects, user accounts, and data

        cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        # print("Verify agents are running")
        # TODO Check for running agents


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':
            print("(cleaning)")
            cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts --flush %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
            os.system(cmd)
            if self.config["METAX_AVAILABLE"] != 1:
                print('')
                print("**************************************")
                print("*** METAX INTEGRATION NOT TESTED!! ***")
                print("**************************************")
                print('')

        self.assertTrue(self.success)


    def test_agents(self):

        admin_user = (self.config["NC_ADMIN_USER"], self.config["NC_ADMIN_PASS"])
        pso_user_a = (self.config["PROJECT_USER_PREFIX"] + "test_project_a", self.config["PROJECT_USER_PASS"])
        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])

        frozen_area_root = "%s/PSO_test_project_a/files/test_project_a" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root = "%s/PSO_test_project_a/files/test_project_a%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        # If Metax is available, disable simulation of agents, no matter what might be defined in configuration
        if self.config["METAX_AVAILABLE"] == 1:
            ida_headers = { 'X-SIMULATE-AGENTS': 'false' }
        else:
            ida_headers = { 'X-SIMULATE-AGENTS': 'true' }

        # If Metax v3 or later, define authentication header
        if self.config["METAX_API_VERSION"] >= 3:
            metax_headers = { "Authorization": "Token %s" % self.config["METAX_PASS"] }
        else:
            metax_user = (self.config["METAX_USER"], self.config["METAX_PASS"])

        print("--- Freeze Action Postprocessing")

        print("Freeze a folder")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=ida_headers, json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        action_pid = action_data["pid"]
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        print("Verify folder was physically moved from frozen to staging area")
        self.assertFalse(os.path.exists("%s/testdata/2017-08/Experiment_1" % (staging_area_root)))
        self.assertTrue(os.path.exists("%s/testdata/2017-08/Experiment_1" % (frozen_area_root)))

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        print("Retrieve completed freeze action details")
        response = requests.get("%s/actions/%s" % (self.config["IDA_API"], action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertIsNotNone(action_data.get("metadata", None))
        self.assertIsNotNone(action_data.get("replication", None))
        self.assertIsNotNone(action_data.get("completed", None))

        print("Retrieve frozen file details")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API"], action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertTrue(len(file_set_data) > 0)
        file_data = file_set_data[0]
        self.assertEqual(file_data["action"], action_pid)
        self.assertIsNotNone(file_data.get("checksum", None))
        self.assertIsNotNone(file_data.get("frozen", None))
        self.assertIsNone(file_data.get("removed", None))
        self.assertIsNone(file_data.get("cleared", None))
        self.assertTrue(os.path.exists("%s/projects/test_project_a/%s" % (self.config["DATA_REPLICATION_ROOT"], file_data['pathname'])))
        file_pid = file_data["pid"]

        if self.config["METAX_AVAILABLE"] == 1:
            print("Verify frozen file details accessible from METAX")
            if self.config["METAX_API_VERSION"] >= 3:
                url = "%s/files?storage_service=ida&storage_identifier=%s&pagination=false" % (self.config["METAX_API"], file_pid)
                response = requests.get(url, headers=metax_headers)
            else:
                response = requests.get("%s/files/%s" % (self.config["METAX_API"], file_pid), auth=metax_user)
            self.assertEqual(response.status_code, 200)
            if self.config["METAX_API_VERSION"] >= 3:
                metax_file_data = response.json()[0]
                self.assertEqual(file_data["pid"], metax_file_data["storage_identifier"])
                self.assertEqual(file_data["project"], metax_file_data["csc_project"])
                self.assertEqual(file_data["pathname"], metax_file_data["pathname"])
                self.assertEqual(file_data["checksum"], metax_file_data["checksum"])
                self.assertEqual(file_data["size"], metax_file_data["size"])
                self.assertEqual(metax_file_data["storage_service"], "ida")
                self.assertIsNotNone(metax_file_data.get("frozen", None))
                self.assertIsNotNone(metax_file_data.get("modified", None))
                self.assertEqual(metax_file_data["user"], "test_user_a")
                self.assertFalse(metax_file_data.get("removed"), False)
            else:
                metax_file_data = response.json()
                self.assertEqual(file_data["pid"], metax_file_data["identifier"])
                self.assertEqual(file_data["project"], metax_file_data["project_identifier"])
                self.assertEqual(file_data["pathname"], metax_file_data["file_path"])
                self.assertEqual(file_data["checksum"], 'sha256:%s' % metax_file_data["checksum"]["value"])
                self.assertEqual(file_data["size"], metax_file_data["byte_size"])
                self.assertIsNotNone(metax_file_data.get("file_frozen", None))
                self.assertIsNotNone(metax_file_data.get("file_modified", None))
                self.assertEqual(metax_file_data["service_created"], "ida")
                self.assertFalse(metax_file_data.get("removed"), False)

        # --------------------------------------------------------------------------------

        print("--- Unfreeze Action Postprocessing")

        print("Unfreeze single frozen file")
        data["pathname"] = "/testdata/2017-08/Experiment_1/test01.dat"
        response = requests.post("%s/unfreeze" % self.config["IDA_API"], headers=ida_headers, json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        action_pid = action_data["pid"]
        self.assertEqual(action_data["action"], "unfreeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        print("Verify file was physically moved from frozen to staging area")
        self.assertFalse(os.path.exists("%s/testdata/2017-08/Experiment_1/test01.dat" % (frozen_area_root)))
        self.assertTrue(os.path.exists("%s/testdata/2017-08/Experiment_1/test01.dat" % (staging_area_root)))

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        print("Retrieve completed unfreeze action details")
        response = requests.get("%s/actions/%s" % (self.config["IDA_API"], action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertIsNotNone(action_data.get("metadata", None))
        self.assertIsNotNone(action_data.get("completed", None))

        print("Retrieve unfrozen file details")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API"], action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertTrue(len(file_set_data) > 0)
        file_data = file_set_data[0]
        self.assertEqual(file_data["action"], action_pid)
        self.assertIsNotNone(file_data.get("removed", None))
        self.assertIsNone(file_data.get("cleared", None))
        file_pid = file_data["pid"]

        if self.config["METAX_AVAILABLE"] == 1:
            print("Verify unfrozen file marked as removed in METAX")
            if self.config["METAX_API_VERSION"] >= 3:
                response = requests.get("%s/files?storage_service=ida&storage_identifier=%s&pagination=false" % (self.config["METAX_API"], file_pid), headers=metax_headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()), 0)
            else:
                response = requests.get("%s/files/%s" % (self.config["METAX_API"], file_pid), auth=metax_user)
                self.assertEqual(response.status_code, 404)

        # --------------------------------------------------------------------------------

        print("--- Delete Action Postprocessing")

        print("Delete single frozen file")
        data["pathname"] = "/testdata/2017-08/Experiment_1/test02.dat"
        response = requests.post("%s/delete" % self.config["IDA_API"], headers=ida_headers, json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        action_pid = action_data["pid"]
        self.assertEqual(action_data["action"], "delete")
        self.assertEqual(action_data["pathname"], data["pathname"])

        print("Verify file was physically removed from frozen area")
        self.assertFalse(os.path.exists("%s/testdata/2017-08/Experiment_1/test02.dat" % (frozen_area_root)))

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        print("Retrieve completed delete action details")
        response = requests.get("%s/actions/%s" % (self.config["IDA_API"], action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertIsNotNone(action_data.get("metadata", None))
        self.assertIsNotNone(action_data.get("completed", None))

        print("Retrieve deleted file details")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API"], action_pid), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertTrue(len(file_set_data) > 0)
        file_data = file_set_data[0]
        self.assertEqual(file_data["action"], action_pid)
        self.assertIsNotNone(file_data.get("removed", None))
        self.assertIsNone(action_data.get("cleared", None))
        file_pid = file_data["pid"]

        if self.config["METAX_AVAILABLE"] == 1:
            print("Verify deleted file marked as removed in METAX")
            if self.config["METAX_API_VERSION"] >= 3:
                response = requests.get("%s/files?storage_service=ida&storage_identifier=%s&pagination=false" % (self.config["METAX_API"], file_pid), headers=metax_headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()), 0)
            else:
                response = requests.get("%s/files/%s" % (self.config["METAX_API"], file_pid), auth=metax_user)
                self.assertEqual(response.status_code, 404)

        # --------------------------------------------------------------------------------

        print("--- Repair Action Postprocessing")

        # TODO Include more files in repair actions, more than 10 files total and 2-3 min new and deleted files...

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        if self.config["METAX_AVAILABLE"] == 1:
            if self.config["METAX_API_VERSION"] >= 3:
                url = "%s/files?csc_project=test_project_a&storage_service=ida&limit=100" % self.config["METAX_API"]
                response = requests.get(url, headers=metax_headers)
            else:
                url = "%s/files?fields=identifier&storage_service=urn:nbn:fi:att:file-storage-ida&ordering=id&project_identifier=test_project_a&limit=100" % self.config["METAX_API"]
                response = requests.get(url, auth=metax_user)
            self.assertEqual(response.status_code, 200)
            file_data = response.json()
            self.assertEqual(file_data["count"], 11)

        print("Retrieve file details from already frozen file 1")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/baseline/test01.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_1_data = response.json()

        print("Update frozen file 1 record to remove replicated timestamp")
        data = {"replicated": "null"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API"], file_1_data["pid"]), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertIsNone(file_data.get("replicated", None))

        print("Retrieve file details from already frozen file 2")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/baseline/test02.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_2_data = response.json()

        print("Update frozen file 2 record to set both size and checksum to null in IDA")
        data = {"size": "null", "checksum": "null"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API"], file_2_data["pid"]), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_2_data = response.json()
        # Undefined file size should result in default value of 0
        self.assertEqual(file_2_data.get("size", None), 0)
        self.assertIsNone(file_2_data.get("checksum", None))

        print("Retrieve file details from already frozen file 3")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/baseline/test03.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_3_data = response.json()

        print("Update frozen file 3 record to set size to 999 and checksum to 'sha256:abcdef' in IDA")
        data = {"size": 999, "checksum": "sha256:abcdef"}
        response = requests.post("%s/files/%s" % (self.config["IDA_API"], file_3_data["pid"]), json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_3_data = response.json()
        self.assertEqual(file_3_data["size"], 999)
        self.assertEqual(file_3_data["checksum"], "sha256:abcdef")

        if self.config["METAX_AVAILABLE"] == 1:

            print("Update frozen file 3 record to set size to 999 and checksum to equivalent of 'sha256:abcdef' in METAX")
            if self.config["METAX_API_VERSION"] >= 3:
                data = [{
                    #"project": "test_project_a",
                    "storage_service": "ida",
                    "storage_identifier": file_3_data["pid"],
                    "size": 999,
                    "checksum": "sha256:abcdef"
                }]
                response = requests.post("%s/files/patch-many" % self.config["METAX_API"], headers=metax_headers, json=data)
            else:
                data = {"byte_size": 999, "checksum": { "algorithm": "SHA-256", "value": "abcdef"} }
                response = requests.patch("%s/files/%s" % (self.config["METAX_API"], file_3_data["pid"]), json=data, auth=metax_user)
            self.assertEqual(response.status_code, 200)
            #print(str(response.content))
            if self.config["METAX_API_VERSION"] >= 3:
                metax_file_data = response.json()["success"][0]["object"]
                self.assertEqual(metax_file_data["size"], 999)
                self.assertEqual(metax_file_data["checksum"], "sha256:abcdef")
            else:
                metax_file_data = response.json()
                self.assertEqual(metax_file_data["byte_size"], 999)
                self.assertEqual(metax_file_data["checksum"]["algorithm"], "SHA-256")
                self.assertEqual(metax_file_data["checksum"]["value"], "abcdef")

            if self.config["METAX_API_VERSION"] < 3:
                print("Update frozen file 3 record to simulate legacy metadata stored in METAX")
                data = { "file_characteristics_extension": { "foo": "bar" } }
                response = requests.patch("%s/files/%s" % (self.config["METAX_API"], file_3_data["pid"]), json=data, auth=metax_user)
                self.assertEqual(response.status_code, 200)
                metax_file_data = response.json()
                self.assertEqual(metax_file_data["file_characteristics_extension"]["foo"], "bar")

        print("Physically delete replication of file 3")
        pathname = "%s/projects/test_project_a/testdata/2017-08/Experiment_1/baseline/test03.dat" % (self.config["DATA_REPLICATION_ROOT"])
        result = os.remove(pathname)
        self.assertFalse(os.path.exists(pathname))

        print("Retrieve file details from already frozen file 4")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/test04.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_4_data = response.json()

        print("Physically delete previously frozen file 4 from frozen area")
        pathname = "%s/testdata/2017-08/Experiment_1/test04.dat" % (frozen_area_root)
        result = os.remove(pathname)
        self.assertFalse(os.path.exists(pathname))

        print("Retrieve file details from already frozen file 5")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/test05.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_5_data = response.json()
        self.assertEqual(file_5_data.get('size', None), 3728)

        print("Physically modify replication of file 5")
        pathname = "%s/projects/test_project_a/testdata/2017-08/Experiment_1/test05.dat" % (self.config["DATA_REPLICATION_ROOT"])
        self.assertTrue(os.path.exists(pathname))
        self.assertEqual(os.path.getsize(pathname), 3728)
        cmd = "sudo -u %s /bin/echo x >> %s" % (self.config["HTTPD_USER"], pathname)
        result = os.system(cmd)
        self.assertEqual(result, 0)
        self.assertEqual(os.path.getsize(pathname), 3730)

        print("Physically move folder from staging to frozen area")
        result = shutil.move("%s/testdata/2017-08/Experiment_2" % (staging_area_root), "%s/testdata/2017-08/Experiment_2" % (frozen_area_root))
        self.assertEqual(result, "%s/testdata/2017-08/Experiment_2" % (frozen_area_root))

        print("Update Nextcloud file database")
        cmd = "sudo -u %s %s/nextcloud/occ files:scan PSO_test_project_a" % (self.config['HTTPD_USER'], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        print("Repair project")
        response = requests.post("%s/repair?project=test_project_a" % (self.config["IDA_API"]), headers=ida_headers, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        response = requests.get("%s/files/action/%s" % (self.config["IDA_API"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_set_data = response.json()
        self.assertEqual(len(file_set_data), 23)

        print("Verify file details from post-repair frozen file 1 are repaired in IDA")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/baseline/test01.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["size"], 446)
        self.assertEqual(file_data["checksum"], "sha256:56293a80e0394d252e995f2debccea8223e4b5b2b150bee212729b3b39ac4d46")
        self.assertEqual(file_1_data['pid'], file_data['pid'])
        self.assertEqual(file_1_data['pathname'], file_data['pathname'])
        self.assertEqual(file_1_data['frozen'], file_data['frozen'])
        self.assertEqual(file_1_data['frozen'], file_data['replicated'])

        print("Verify file details from post-repair frozen file 2 are repaired in IDA")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/baseline/test02.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["size"], 1531)
        self.assertEqual(file_data["checksum"], "sha256:c5a8e40a8afaebf3d8429266a6f54ef52eff14dcd22cb64a59a06e4d724eebb9")
        self.assertEqual(file_2_data['replicated'], file_data['replicated'])

        print("Verify file details from post-repair frozen file 3 are repaired in IDA")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/baseline/test03.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["size"], 2263)
        self.assertEqual(file_data["checksum"], "sha256:8950fc9b4292a82cfd1b5e6bbaec578ed00ac9a9c27bf891130f198fef2f0168")
        pathname = "%s/projects/test_project_a/testdata/2017-08/Experiment_1/baseline/test03.dat" % (self.config["DATA_REPLICATION_ROOT"])
        self.assertTrue(os.path.exists(pathname))
        self.assertNotEqual(file_3_data['replicated'], file_data['replicated'])

        if self.config["METAX_AVAILABLE"] == 1:

            print("Verify file details from post-repair frozen file 3 are repaired in METAX")
            if self.config["METAX_API_VERSION"] >= 3:
                response = requests.get("%s/files?storage_service=ida&storage_identifier=%s&pagination=false" % (self.config["METAX_API"], file_data["pid"]), headers=metax_headers)
            else:
                response = requests.get("%s/files/%s" % (self.config["METAX_API"], file_data["pid"]), auth=metax_user)
            self.assertEqual(response.status_code, 200)
            if self.config["METAX_API_VERSION"] >= 3:
                metax_file_data = response.json()[0]
                self.assertEqual(metax_file_data["size"], 2263)
                self.assertEqual(metax_file_data["checksum"], "sha256:8950fc9b4292a82cfd1b5e6bbaec578ed00ac9a9c27bf891130f198fef2f0168")
            else:
                metax_file_data = response.json()
                self.assertEqual(metax_file_data["byte_size"], 2263)
                self.assertEqual(metax_file_data["checksum"]["algorithm"], "SHA-256")
                self.assertEqual(metax_file_data["checksum"]["value"], "8950fc9b4292a82cfd1b5e6bbaec578ed00ac9a9c27bf891130f198fef2f0168")

            if self.config["METAX_API_VERSION"] < 3:
                print("Verify simulated legacy metadata of post-repair frozen file 3 remains in METAX")
                self.assertEqual(metax_file_data["file_characteristics_extension"]["foo"], "bar")

        print("Verify file details from post-repair file manually moved to frozen space are defined in IDA")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_2/baseline/test01.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_data["size"], 446)
        self.assertEqual(file_data["checksum"], "sha256:56293a80e0394d252e995f2debccea8223e4b5b2b150bee212729b3b39ac4d46")
        pathname = "%s/projects/test_project_a/testdata/2017-08/Experiment_2/baseline/test01.dat" % (self.config["DATA_REPLICATION_ROOT"])
        self.assertTrue(os.path.exists(pathname))

        print("Attempt to retrieve file details from post-repair file manually removed from frozen space")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/test04.dat"}
        response = requests.get("%s/files/byProjectPathname/%s?includeInactive=true" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertIsNotNone(file_data.get("cleared", None))

        if self.config["METAX_AVAILABLE"] == 1:

            print("Verify correct number of frozen files active in METAX")
            if self.config["METAX_API_VERSION"] >= 3:
                url = "%s/files?csc_project=test_project_a&storage_service=ida&limit=100" % self.config["METAX_API"]
                response = requests.get(url, headers=metax_headers)
            else:
                response = requests.get(url, auth=metax_user)
            self.assertEqual(response.status_code, 200)
            file_data = response.json()
            self.assertEqual(file_data["count"], 23)

            print("Verify manually removed frozen file marked as removed in METAX")
            if self.config["METAX_API_VERSION"] >= 3:
                response = requests.get("%s/files?storage_service=ida&storage_identifier=%s&pagination=false" % (self.config["METAX_API"], file_4_data["pid"]), headers=metax_headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()), 0)
            else:
                response = requests.get("%s/files/%s" % (self.config["METAX_API"], file_4_data["pid"]), auth=metax_user)
                self.assertEqual(response.status_code, 404)

        print("Verify file details from already frozen file 5 remain unchanged")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/test05.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        self.assertEqual(file_5_data['pathname'], file_data['pathname'])
        self.assertEqual(file_5_data['size'], file_data['size'])
        self.assertEqual(file_5_data['checksum'], file_data['checksum'])
        self.assertEqual(file_5_data['frozen'], file_data['frozen'])

        print("Verify replication of frozen file 5 was repaired")
        pathname = "%s/projects/test_project_a/testdata/2017-08/Experiment_1/test05.dat" % (self.config["DATA_REPLICATION_ROOT"])
        self.assertTrue(os.path.exists(pathname))
        self.assertEqual(os.path.getsize(pathname), 3728)

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
