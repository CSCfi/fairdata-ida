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
# Note regarding sequence of tests: this test case contains only a single test
# method, which utilizes the test projects, user accounts, and project data
# initialized during setup, such that the sequential actions in the single
# test method create side effects which subsequent actions and assertions may
# depend on. The state of the test accounts and data must be taken into account
# whenever adding tests at any particular point in that execution sequence.
# --------------------------------------------------------------------------------

import requests
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
from tests.common.utils import *


class TestOldData(unittest.TestCase):


    @classmethod
    def setUpClass(cls):
        print("=== tests/auditing/test_olddata")


    def setUp(self):

        # load service configuration variables
        self.config = load_configuration()

        # keep track of success, for reference in tearDown
        self.success = False

        # timeout when waiting for actions to complete
        self.timeout = 10800 # 3 hours

        print("(initializing)")

        self.assertEqual(self.config["METAX_AVAILABLE"], 1)

        # If Metax v3 or later, define authentication header
        if self.config["METAX_API_VERSION"] >= 3:
            self.metax_headers = { 'Authorization': 'Token %s' % self.config["METAX_API_PASS"] }
        else:
            self.metax_user = (self.config["METAX_API_USER"], self.config["METAX_API_PASS"])

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts %s/tests/utils/double-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':
            print("(cleaning)")
            cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts --flush" % (self.config["HTTPD_USER"], self.config["ROOT"])
            result = os.system(cmd)
            self.assertEqual(result, 0)

            # delete all test project related old data reports, so they don't build up
            cmd = "rm -f %s/old_data/*/*/*_test_project_[a-e].json" % self.config["LOG_ROOT"]
            result = os.system(cmd)
            self.assertEqual(result, 0)


    def audit_old_data(self, project):

        print ("(auditing old data for project %s)" % project)

        cmd = "sudo -u %s DEBUG=false %s/utils/admin/audit-old-data %s 0 --json-output" % (self.config["HTTPD_USER"], self.config["ROOT"], project)

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.assertNotEqual(output, None, output)
        self.assertNotEqual(output, "", output)

        summary_data = json.loads(output)

        self.assertIsNotNone(summary_data.get('reportPathname'))
        self.assertIsNotNone(summary_data.get('project'))
        self.assertIsNotNone(summary_data.get('maxDataAgeInDays'))
        self.assertIsNotNone(summary_data.get('totalBytes'))
        self.assertIsNotNone(summary_data.get('totalFiles'))
        self.assertIsNotNone(summary_data.get('totalFrozenBytes'))
        self.assertIsNotNone(summary_data.get('totalFrozenFiles'))
        self.assertIsNotNone(summary_data.get('totalStagingBytes'))
        self.assertIsNotNone(summary_data.get('totalStagingFiles'))
        self.assertIsNone(summary_data.get('frozenFiles'))
        self.assertIsNone(summary_data.get('stagingFiles'))

        report_pathname = summary_data['reportPathname']

        print("Verify old data report exists")
        self.assertTrue(report_pathname.endswith(".json"), report_pathname)
        path = Path(report_pathname)
        self.assertTrue(path.exists(), path)
        self.assertTrue(path.is_file(), path)

        print("(loading old data report %s)" % report_pathname)
        try:
            report_data = json.load(open(report_pathname))
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertEqual(report_data.get("project"), project)

        return report_data


    def audit_all_old_data(self, projects):

        print ("(auditing old data for all projects: %s)" % projects)

        cmd = "sudo -u %s PROJECTS=\"%s\" DEBUG=false %s/utils/admin/audit-all-old-data 0 --json-output" % (self.config["HTTPD_USER"], projects, self.config["ROOT"])

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.assertNotEqual(output, None, output)
        self.assertNotEqual(output, "", output)

        summary_data = json.loads(output)

        self.assertIsNotNone(summary_data.get('reportPathname'))
        self.assertIsNotNone(summary_data.get('projectCount'))
        self.assertIsNotNone(summary_data.get('maxDataAgeInDays'))
        self.assertIsNotNone(summary_data.get('totalBytes'))
        self.assertIsNotNone(summary_data.get('totalFiles'))
        self.assertIsNotNone(summary_data.get('totalFrozenBytes'))
        self.assertIsNotNone(summary_data.get('totalFrozenFiles'))
        self.assertIsNotNone(summary_data.get('totalStagingBytes'))
        self.assertIsNotNone(summary_data.get('totalStagingFiles'))
        self.assertIsNone(summary_data.get('projects'))

        report_pathname = summary_data['reportPathname']

        print("Verify old data report exists")
        self.assertTrue(report_pathname.endswith(".json"), report_pathname)
        path = Path(report_pathname)
        self.assertTrue(path.exists(), path)
        self.assertTrue(path.is_file(), path)

        print("(loading old data report %s)" % report_pathname)
        try:
            report_data = json.load(open(report_pathname))
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        return report_data


    def test_olddata(self):

        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])

        print("(freezing folder /testdata/2017-08/Experiment_1)")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        print("Retrieve frozen file details for all files associated with freeze action of folder /2017-08/Experiment_1")
        response = requests.get("%s/files/action/%s" % (self.config["IDA_API_ROOT_URL"], action_data["pid"]), auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200, response.content.decode(sys.stdout.encoding))
        experiment_1_files = response.json()
        self.assertEqual(len(experiment_1_files), 13)

        print("(freezing folder /testdata/2017-08/Experiment_2)")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_2"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        print("Creating Dataset containing all files in scope /testdata/2017-08/Experiment_1")
        if self.config["METAX_API_VERSION"] >= 3:
            dataset_data = DATASET_TEMPLATE_V3
            dataset_data['title'] = DATASET_TITLES[0]
            dataset_data['fileset'] = {
                "storage_service": "ida",
                "csc_project": "test_project_a",
                "directory_actions": [
                    {
                        "action": "add",
                        "pathname": "/testdata/2017-08/Experiment_1/"
                    }
                ]
            }
            response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], headers=self.metax_headers, json=dataset_data)
        else:
            dataset_data = DATASET_TEMPLATE_V1
            dataset_data['research_dataset']['title'] = DATASET_TITLES[0]
            dataset_data['research_dataset']['files'] = build_dataset_files(self, experiment_1_files)
            response = requests.post("%s/datasets" % self.config['METAX_API_ROOT_URL'], json=dataset_data, auth=self.metax_user)
        self.assertEqual(response.status_code, 201, response.content.decode(sys.stdout.encoding))

        print("--- Auditing old data in project A and checking results")

        report_data = self.audit_old_data("test_project_a")
        report_pathname = report_data["reportPathname"]

        self.assertEqual(report_data.get('project'), 'test_project_a')
        self.assertEqual(report_data.get('maxDataAgeInDays'), 0)
        self.assertEqual(report_data.get('totalBytes'), 119247)
        self.assertEqual(report_data.get('totalFiles'), 70)
        self.assertEqual(report_data.get('totalFrozenBytes'), 23040)
        self.assertEqual(report_data.get('totalFrozenFiles'), 13)
        self.assertEqual(report_data.get('totalStagingBytes'), 96207)
        self.assertEqual(report_data.get('totalStagingFiles'), 57)
        frozenFiles = report_data.get('frozenFiles')
        self.assertIsNotNone(frozenFiles)
        self.assertEqual(len(frozenFiles), 13)
        self.assertIsNone(frozenFiles.get('/testdata/2017-08/Experiment_1/test01.dat'))
        self.assertIsNotNone(frozenFiles.get('/testdata/2017-08/Experiment_2/test01.dat'))
        stagingFiles = report_data.get('stagingFiles')
        self.assertIsNotNone(stagingFiles)
        self.assertEqual(len(stagingFiles), 57)
        self.assertIsNone(stagingFiles.get('/testdata/2017-08/Experiment_1/test01.dat'))
        self.assertIsNone(stagingFiles.get('/testdata/2017-08/Experiment_2/test01.dat'))
        self.assertIsNotNone(stagingFiles.get('/testdata/2017-10/Experiment_3/test01.dat'))
        self.assertIsNotNone(stagingFiles.get('/testdata/2017-10/Experiment_4/test01.dat'))
        self.assertIsNotNone(stagingFiles.get('/testdata/2017-10/Experiment_5/test01.dat'))
        self.assertIsNotNone(stagingFiles.get('/testdata/2017-11/Experiment_6/test01.dat'))
        self.assertIsNotNone(stagingFiles.get('/testdata/2017-11/Experiment_7/baseline/.hidden_file'))
        self.assertIsNotNone(stagingFiles.get('/testdata/Contact.txt'))
        self.assertIsNotNone(stagingFiles.get('/testdata/License.txt'))

        print("--- Auditing old data for all projects and checking results")

        report_data = self.audit_all_old_data("test_project_a test_project_b")
        report_pathname = report_data["reportPathname"]

        print("--- Checking JSON report details")

        self.assertEqual(report_data.get('projectCount'), 2)
        self.assertEqual(report_data.get('maxDataAgeInDays'), 0)
        self.assertEqual(report_data.get('totalBytes'), 261534)
        self.assertEqual(report_data.get('totalFiles'), 153)
        self.assertEqual(report_data.get('totalFrozenBytes'), 23040)
        self.assertEqual(report_data.get('totalFrozenFiles'), 13)
        self.assertEqual(report_data.get('totalStagingBytes'), 238494)
        self.assertEqual(report_data.get('totalStagingFiles'), 140)
        projects = report_data.get('projects')
        self.assertIsNotNone(projects)
        self.assertEqual(len(projects), 2)
        project_data = projects[0]
        self.assertEqual(project_data.get('project'), 'test_project_a')
        self.assertEqual(project_data.get('totalBytes'), 119247)
        self.assertEqual(project_data.get('totalFiles'), 70)
        self.assertEqual(project_data.get('totalFrozenBytes'), 23040)
        self.assertEqual(project_data.get('totalFrozenFiles'), 13)
        self.assertEqual(project_data.get('totalStagingBytes'), 96207)
        self.assertEqual(project_data.get('totalStagingFiles'), 57)
        self.assertIsNone(project_data.get('maxDataAgeInDays'))
        self.assertIsNone(project_data.get('frozenFiles'))
        self.assertIsNone(project_data.get('stagingFiles'))
        project_data = projects[1]
        self.assertEqual(project_data.get('project'), 'test_project_b')
        self.assertEqual(project_data.get('totalBytes'), 142287)
        self.assertEqual(project_data.get('totalFiles'), 83)
        self.assertEqual(project_data.get('totalFrozenBytes'), 0)
        self.assertEqual(project_data.get('totalFrozenFiles'), 0)
        self.assertEqual(project_data.get('totalStagingBytes'), 142287)
        self.assertEqual(project_data.get('totalStagingFiles'), 83)
        self.assertIsNone(project_data.get('maxDataAgeInDays'))
        self.assertIsNone(project_data.get('frozenFiles'))
        self.assertIsNone(project_data.get('stagingFiles'))

        print("--- Checking CSV report details")

        report_pathname = "%s.csv" % report_pathname[:-5]
        path = Path(report_pathname)
        self.assertTrue(path.exists(), path)
        self.assertTrue(path.is_file(), path)
        with open(report_pathname, 'r') as file:
            lines = file.readlines()
            number_of_lines = len(lines)
        self.assertEqual(number_of_lines, 4)
        self.assertEqual(lines[0].rstrip('\n'), 'PROJECT,BYTES,FILES,FROZEN BYTES,FROZEN FILES,STAGING BYTES,STAGING FILES')
        self.assertEqual(lines[1].rstrip('\n'), 'ALL,261534,153,23040,13,238494,140')
        self.assertEqual(lines[2].rstrip('\n'), 'test_project_b,142287,83,0,0,142287,83')
        self.assertEqual(lines[3].rstrip('\n'), 'test_project_a,119247,70,23040,13,96207,57')

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
