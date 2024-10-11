# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2024 Ministry of Education and Culture, Finland
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
#

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


class TestAuditing(unittest.TestCase):


    @classmethod
    def setUpClass(cls):
        print("=== tests/auditing/test_cache_orphans")


    def setUp(self):

        # load service configuration variables
        self.config = load_configuration()

        self.config['START'] = generate_timestamp()
        print("START: %s" % self.config['START'])

        # keep track of success, for reference in tearDown
        self.success = False

        # timeout when waiting for actions to complete
        self.timeout = 10800 # 3 hours

        print("(initializing)")

        if self.config['SEND_TEST_EMAILS'] == 'true':
            print("(sending test emails)")
        else:
            print("(not sending test emails)")

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        self.config['INITIALIZED'] = generate_timestamp()
        print("INITIALIZED: %s" % self.config['INITIALIZED'])


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':
            print("(cleaning)")
            cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts --flush %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
            result = os.system(cmd)
            self.assertEqual(result, 0)

            # delete all test project related audit reports, so they don't build up
            cmd = "rm -f %s/audits/*/*/*_test_project_[a-e].*" % self.config["LOG_ROOT"]
            result = os.system(cmd)
            self.assertEqual(result, 0)


    def remove_report(self, pathname):
        try:
            os.remove(pathname)
        except:
            pass


    def audit_project(self, project, status, since = None, area = None, timestamps = True, checksums = True):
        """
        Audit the specified project, verify that the audit report file was created with the specified
        status, and load and return the audit report as a JSON object, with the audit report pathname
        defined in the returned object for later timestamp repair if/as needed.

        A full audit with no restrictions and including timestamps and checksums is done by default.
        """

        parameters = ""

        if since is None and area is None and timestamps and checksums:
            parameters = " --full"

        else:

            if since:
                parameters = "%s --changed-since %s" % (parameters, since)

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

        cmd = "sudo -u %s DEBUG=false AUDIT_START_OFFSET=0 %s/utils/admin/audit-project %s %s" % (self.config["HTTPD_USER"], self.config["ROOT"], project, parameters)

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


    def test_cache_orphans(self):

        pso_user_a = ("PSO_test_project_a", self.config["PROJECT_USER_PASS"])
        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])

        frozen_area_root_a = "%s/PSO_test_project_a/files/test_project_a" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_a = "%s/PSO_test_project_a/files/test_project_a%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        # --------------------------------------------------------------------------------
        # open database connection

        dblib = psycopg2

        if self.config['DBTYPE'] == 'mysql':
            dblib = pymysql

        conn = dblib.connect(database=self.config["DBNAME"],
                             user=self.config["DBUSER"],
                             password=self.config["DBPASSWORD"],
                             host=self.config["DBHOST"],
                             port=self.config["DBPORT"])

        cur = conn.cursor()

        # --------------------------------------------------------------------------------
        # --------------------------------------------------------------------------------
        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project A")

        print("(creating orphan file cache records for project A)")
        cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-cache-orphans test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        # --------------------------------------------------------------------------------

        print("--- Auditing project A and checking results")

        report_data = self.audit_project("test_project_a", "ERR")
        report_pathname_a = report_data["reportPathname"]
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 113)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 123)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 0)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 10)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 14)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 3)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEqual(len(nodes), report_data['invalidNodeCount'])

        # Verify invalid node error messages for each orphan node...

        orphan_pathnames = [
            "staging/orphans/foo", 
            "staging/orphans/foo/bar", 
            "staging/orphans/foo/test1.dat", 
            "staging/orphans/foo/test2.dat", 
            "staging/orphans/foo/bar/test3.dat", 
            "staging/orphans/foo/bar/test4.dat", 
            "staging/orphans/foo/bar/test5.dat", 
            "frozen/orphans/bas", 
            "frozen/orphans/bas/test6.dat", 
            "frozen/orphans/bas/test7.dat"
        ] 

        print("Verify correct error report of orphan Nextcloud node records")

        for pathname in orphan_pathnames:
            node = nodes.get(pathname)
            self.assertIsNotNone(node)
            errors = node.get("errors")
            self.assertIsNotNone(errors)
            self.assertTrue("Node does not exist in filesystem" in errors)

        # --------------------------------------------------------------------------------

        print("--- Repairing project A")

        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_a)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        self.remove_report(report_pathname_a)

        # --------------------------------------------------------------------------------

        print("--- Re-auditing project A and checking results")

        report_data = self.audit_project("test_project_a", "OK")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 113)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 113)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 0)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 0)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 0)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 0)

        print("Verify correct oldest and newest dates")
        self.assertIsNone(report_data.get("oldest"))
        self.assertIsNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
