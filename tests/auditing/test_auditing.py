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
#
# Overview:
#
# 1. Test projects and user accounts will be created and initialized as usual, and
#    a timestamp INITIALIZED will be created after initialization.
#
# 2. The following actions and modifications will be made to specific test projects,
#    and a second timestamp MODIFIED will be created after modifications:
#
# a. Project A will have a folder frozen, and will have files both added and deleted
#    from both the frozen space and staging area in the filesystem only, covering
#    errors where Nextcloud and the filesystem disagree on the existence of files
#    and folders, and the number of nodes.
#
# b. Project B will have a folder frozen, and will have files both changed in size
#    and touched with new modification timestamps in the filesystem, covering errors
#    where Nextcloud and the filesystem disagree about size and modification
#    timestamps of files.
#
# c. Project C will have a folder frozen, and will have files replaced by folders
#    and folders replaced by files in both the frozen and staging areas of the
#    filesystem, preserving the same exact pathnames, covering errors where
#    Nextcloud and the filesystem disagree about the type of nodes.
#
# d. Project D will have a folder frozen, and will have changes to files in IDA,
#    Metax, and replication, removing a file from IDA, removing a file from Metax,
#    removing a file from replication, and changing file details for a file in IDA
#    such that it disagrees with both Metax and replication.
#
# e. Project E will have no modifications of any kind, and therefore should not
#    have any errors reported of any kind.
#
# 3. Active project listings will be tested with the following variations:
#
# a. An active project listing will be generated with the START timestamp and the
#    script output to include all projects A, B, C, D and E.
#
# b. An active project listing will be generated with the INITIALIZED timestamp and
#    the script output verified to include the projects A, B, C, and D but not E.
#
# c. An active project listing will be generated with the MODIFIED timestamp and
#    the script output verified to include none of the projects A, B, C, D or E.
#
# 4. All projects A, B, C, D, and E will be audited with the following variations
#    and results checked for correctness, that the report files exist and have the
#    correct status, that all expected errors are reported correctly, and no other
#    errors are reported, and that project E has no errors reported for any
#    variation.
#
# a. Projects will be audited with the --full parameter and no restrictions
#    (exhaustive audit).
#
# b. Projects will be audited with --staging --timestamps --checksums parameters,
#    limiting checks to files in the staging area.
#
# c. Projects will be audited with --frozen --timestamps --checksums parameters,
#    limiting checks to files in the frozen area.
#
# d. Projects will be audited with --changed-since START --timestamps --checksums
#    parameters, limiting checks to files uploaded or frozen since the START
#    timestamp, and their ancestor folders.
#
# e. Projects will be audited with --changed-since INITIALIZED --timestamps
#    --checksums parameters, limiting checks to files uploaded or frozen since
#    the INITIALIZED timestamp, and their ancestor folders.
#
# f. Projects will be audited with --changed-since MODIFIED --timestamps
#    --checksums parameters, limiting checks to files uploaded or frozen since
#    the MODIFIED timestamp, and their ancestor folders, verifying no errors
#    reported for any projects.
#
# 5. Projects A, B, C, and D will be fully repaired and then audited with
#    the --full parameter and no restrictions (exhaustive audit), and results
#    checked to ensure correct node counts and verifying no errors reported for
#    any projects.
#
# 6. Checksum checks as part of the freezing process will be tested as follows:
# 
# a. Project A will be modified by changing the cache checksums of three files
#    in staging, freezing the directory containing the files, and verifying that
#    the freeze action fails and the three checksum mismatches are reported.
#
# b. Project A will then be audited with the --full parameter and the expected
#    errors verified.
# 
# c. Project A will then be repaired and audited with the --full parameter to
#    ensure that the checksums are restored based on the files on disk, and that
#    the project state is as if the failed freeze action had
#    completed successfully.
#
# 6. Checksum and timestamp option checks will be tested as follows:
# 
# a. Project B will be modified by changing the cache checksums of three frozen
#    files, in the cache, IDA, and Metax respectively, and the cache checksum of
#    one file in staging.
#    
# b. Project B will be further modified by changing the modified timestamp of
#    three different frozen files, in the cache, IDA, and Metax respectively, and the
#    cache modified timestamp of one different file in staging.
#    
# c. Project B will then be audited with no parameters (no checksum nor
#    timestamp checks) to verify that no errors are reported.
# 
# d. Project B will then be audited with the --checksums parameters (no timestamp
#    checks) to verify that all expected checksum errors are reported but no
#    timestamp errors are reported.
# 
# e. Project B will then be audited with the --timestamps parameters (no checksum
#    checks) to verify that all expected timestamp errors are reported but no
#    checksum errors are reported.
# 
# f. Project B will then be audited with the --full parameter (both checksum
#    and timestamp checks) to verify that all expected checksum and timestamp
#    errors are reported.
# 
# g. Project B will then be repaired and audited with the --full parameter to
#    ensure that no errors are reported.
#
# Note: no testing of the emailing functionality will be done, only the
# correctness of the auditing process and reported results.
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


class TestAuditing(unittest.TestCase):


    @classmethod
    def setUpClass(cls):
        print("=== tests/auditing/test_auditing")


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

        # If Metax v3 or later, define authentication header
        if self.config["METAX_API_VERSION"] >= 3:
            self.metax_headers = { 'Authorization': 'Token %s' % self.config["METAX_PASS"] }
        else:
            self.metax_user = (self.config["METAX_USER"], self.config["METAX_PASS"])

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts" % (self.config["HTTPD_USER"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        # ensure all cache checksums have been generated for test_project_a (if OK, assume OK for all test projects)
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/list-missing-checksums test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
            self.assertEqual(len(output), 0)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.config['INITIALIZED'] = generate_timestamp()
        print("INITIALIZED: %s" % self.config['INITIALIZED'])


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':
            print("(cleaning)")
            cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts --flush" % (self.config["HTTPD_USER"], self.config["ROOT"])
            result = os.system(cmd)
            self.assertEqual(result, 0)

            # delete all test project related audit reports, so they don't build up
            cmd = "rm -f %s/audits/*/*/*_test_project_[a-e].*" % self.config["LOG_ROOT"]
            result = os.system(cmd)
            self.assertEqual(result, 0)

            if self.config["METAX_AVAILABLE"] != 1:
                print('')
                print("***********************************")
                print("*** METAX AUDITING NOT TESTED!! ***")
                print("***********************************")
                print('')


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

        #parameters = "%s --report" % parameters

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


    def test_auditing(self):

        invalid_timestamp = "2023-01-01T00:00:00Z"
        invalid_timestamp_seconds = 1672531200
        invalid_checksum = "a1b2c3d4e5"
        invalid_checksum_uri = "sha256:%s" % invalid_checksum

        pso_user_a = ("PSO_test_project_a", self.config["PROJECT_USER_PASS"])
        pso_user_b = ("PSO_test_project_b", self.config["PROJECT_USER_PASS"])

        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
        test_user_b = ("test_user_b", self.config["TEST_USER_PASS"])
        test_user_c = ("test_user_c", self.config["TEST_USER_PASS"])
        test_user_d = ("test_user_d", self.config["TEST_USER_PASS"])
        test_user_e = ("test_user_e", self.config["TEST_USER_PASS"])

        frozen_area_root_a = "%s/PSO_test_project_a/files/test_project_a" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_a = "%s/PSO_test_project_a/files/test_project_a%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        frozen_area_root_c = "%s/PSO_test_project_c/files/test_project_c" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_c = "%s/PSO_test_project_c/files/test_project_c%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        # If Metax is available, disable simulation of agents, no matter what might be defined in configuration
        if self.config["METAX_AVAILABLE"] == 1:
            headers = { 'X-SIMULATE-AGENTS': 'false' }
        else:
            headers = { 'X-SIMULATE-AGENTS': 'true' }

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

        print("(retrieving frozen file PID lists for project A from IDA and Metax before modifications)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_a', test_user_a)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_a')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 0)
        self.assertEqual(len(metax_file_pids_1), 0)

        print("(freezing folder /testdata/2017-08/Experiment_1/baseline)")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=headers, json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        print("(retrieving frozen file PID lists for project A from IDA and Metax after freezing)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_a', test_user_a)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_a')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 6)
        self.assertEqual(len(metax_file_pids_2), 6)

        print("(comparing PID lists for project A in IDA and Metax after freezing)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2v1 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2v1 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 0)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 6)
        self.assertEqual(len(metax_file_pid_diff_1v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v1), 6)

        # After repair there will be one additional node (folder) due to the existence of the 'baseline' directory
        # in both frozen area and staging compared to before freezing the 'baseline' folder and unfreezing test01.dat
        print("(unfreezing file /testdata/2017-08/Experiment_1/baseline/test01.dat only in IDA, simulating postprocessing agents)")
        data = {"project": "test_project_d", "pathname": "/testdata/2017-08/Experiment_1/baseline/test01.dat"}
        print("(deleting folder /testdata/2017-08/Experiment_1/baseline from frozen area of filesystem)")
        pathname = "%s/testdata/2017-08/Experiment_1/baseline" % frozen_area_root_a
        path = Path(pathname)
        try:
            shutil.rmtree(pathname)
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())

        print("(deleting folder /testdata/2017-08/Experiment_3/baseline from staging area of filesystem)")
        pathname = "%s/testdata/2017-10/Experiment_3/baseline" % staging_area_root_a
        path = Path(pathname)
        try:
            shutil.rmtree(pathname)
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())

        print("(creating zero sized ghost file /testdata/2017-08/Experiment_1/baseline/test01.dat in staging area of filesystem)")
        # Create subfolder /2017-08/Experiment_1/baseline in staging area
        pathname = "%s/testdata/2017-08/Experiment_1/baseline" % staging_area_root_a
        path = Path(pathname)
        try:
            path.mkdir()
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to create folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())
        # Create zero sized ghost file in staging area of frozen file /2017-08/Experiment_1/baseline/test01.dat
        pathname = "%s/testdata/2017-08/Experiment_1/baseline/test01.dat" % staging_area_root_a
        path = Path(pathname)
        try:
            shutil.copyfile("/dev/null", pathname)
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to create empty file %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())
        self.assertEqual(0, path.stat().st_size)

        print("(retrieving frozen file PID lists for project A from IDA and Metax after modifications)")
        frozen_file_pids_3 = get_frozen_file_pids(self, 'test_project_a', test_user_a)
        metax_file_pids_3 = get_metax_file_pids(self, 'test_project_a')
        #print("IDA frozen file PIDs 3: %s" % json.dumps(frozen_file_pids_3))
        #print("IDA frozen file PID count 3: %d" % len(frozen_file_pids_3))
        #print("Metax frozen file PIDs 3: %s" % json.dumps(metax_file_pids_3))
        #print("Metax frozen file PID count 3: %d" % len(metax_file_pids_3))
        self.assertEqual(len(frozen_file_pids_3), 6)
        self.assertEqual(len(metax_file_pids_3), 6)

        print("(comparing PID lists for project A in IDA and Metax after modifications)")
        frozen_file_pid_diff_2v3, frozen_file_pid_diff_3v2 = array_difference(frozen_file_pids_2, frozen_file_pids_3)
        metax_file_pid_diff_2v3, metax_file_pid_diff_3v2 = array_difference(metax_file_pids_2, metax_file_pids_3)
        #print("IDA frozen file diff 2v3: %s" % json.dumps(frozen_file_pid_diff_2v3))
        #print("IDA frozen file diff 3v2: %s" % json.dumps(frozen_file_pid_diff_3v2))
        #print("Metax frozen file diff 2v3: %s" % json.dumps(metax_file_pid_diff_2v3))
        #print("Metax frozen file diff 3v2: %s" % json.dumps(metax_file_pid_diff_3v2))
        self.assertEqual(len(frozen_file_pid_diff_2v3), 0)
        self.assertEqual(len(frozen_file_pid_diff_3v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v3), 0)
        self.assertEqual(len(metax_file_pid_diff_3v2), 0)

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project B")

        print("(retrieving frozen file PID lists for project B from IDA and Metax before modifications)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_b', test_user_b)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_b')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 0)
        self.assertEqual(len(metax_file_pids_1), 0)

        print("(freezing folder /testdata/2017-08/Experiment_1/baseline)")
        data = {"project": "test_project_b", "pathname": "/testdata/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=headers, json=data, auth=test_user_b, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_b", test_user_b)
        check_for_failed_actions(self, "test_project_b", test_user_b)

        print("(retrieving frozen file PID lists for project B from IDA and Metax after freezing)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_b', test_user_b)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_b')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 6)
        self.assertEqual(len(metax_file_pids_2), 6)

        print("(comparing PID lists for project B in IDA and Metax after freezing)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2v1 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2v1 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 0)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 6)
        self.assertEqual(len(metax_file_pid_diff_1v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v1), 6)

        # retrieve PSO storage id for test_project_b
        cur.execute("SELECT numeric_id from %sstorages WHERE id = 'home::%stest_project_b' LIMIT 1"
                    % (self.config["DBTABLEPREFIX"], self.config["PROJECT_USER_PREFIX"]))
        rows = cur.fetchall()
        if len(rows) != 1:
            self.fail("Failed to retrieve storage id for test_project_b")
        storage_id_b = rows[0][0]

        print("(changing size of Nextcloud file node /testdata/2017-08/Experiment_1/baseline/test01.dat in frozen area)")
        pathname = "files/test_project_b/testdata/2017-08/Experiment_1/baseline/test01.dat"
        cur.execute("UPDATE %sfilecache SET size = %d WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], 123, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node size")

        print("(changing modified timestamp of Nextcloud file node /testdata/2017-08/Experiment_1/baseline/test04.dat in frozen area)")
        pathname = "files/test_project_b/testdata/2017-08/Experiment_1/baseline/test04.dat"
        cur.execute("UPDATE %sfilecache SET mtime = %d WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], invalid_timestamp_seconds, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node modification timestamp")

        print("(retrieving frozen file PID lists for project B from IDA and Metax after modifications)")
        frozen_file_pids_3 = get_frozen_file_pids(self, 'test_project_b', test_user_b)
        metax_file_pids_3 = get_metax_file_pids(self, 'test_project_b')
        #print("IDA frozen file PIDs 3: %s" % json.dumps(frozen_file_pids_3))
        #print("IDA frozen file PID count 3: %d" % len(frozen_file_pids_3))
        #print("Metax frozen file PIDs 3: %s" % json.dumps(metax_file_pids_3))
        #print("Metax frozen file PID count 3: %d" % len(metax_file_pids_3))
        self.assertEqual(len(frozen_file_pids_3), 6)
        self.assertEqual(len(metax_file_pids_3), 6)

        print("(comparing PID lists for project B in IDA and Metax after modifications)")
        frozen_file_pid_diff_2v3, frozen_file_pid_diff_3v2 = array_difference(frozen_file_pids_2, frozen_file_pids_3)
        metax_file_pid_diff_2v3, metax_file_pid_diff_3v2 = array_difference(metax_file_pids_2, metax_file_pids_3)
        #print("IDA frozen file diff 2v3: %s" % json.dumps(frozen_file_pid_diff_2v3))
        #print("IDA frozen file diff 3v2: %s" % json.dumps(frozen_file_pid_diff_3v2))
        #print("Metax frozen file diff 2v3: %s" % json.dumps(metax_file_pid_diff_2v3))
        #print("Metax frozen file diff 3v2: %s" % json.dumps(metax_file_pid_diff_3v2))
        self.assertEqual(len(frozen_file_pid_diff_2v3), 0)
        self.assertEqual(len(frozen_file_pid_diff_3v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v3), 0)
        self.assertEqual(len(metax_file_pid_diff_3v2), 0)

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project C")

        print("(retrieving frozen file PID lists for project C from IDA and Metax before modifications)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_c', test_user_c)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_c')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 0)
        self.assertEqual(len(metax_file_pids_1), 0)

        print("(freezing folder /testdata/2017-08/Experiment_1/baseline)")
        data = {"project": "test_project_c", "pathname": "/testdata/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=headers, json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_c", test_user_c)
        check_for_failed_actions(self, "test_project_c", test_user_c)

        print("(retrieving frozen file PID lists for project C from IDA and Metax after freezing)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_c', test_user_c)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_c')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 6)
        self.assertEqual(len(metax_file_pids_2), 6)

        print("(comparing PID lists for project C in IDA and Metax after freezing)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2v1 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2v1 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 0)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 6)
        self.assertEqual(len(metax_file_pid_diff_1v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v1), 6)

        # After repair the frozen file record in IDA and Metax will be purged as it no longer
        # corresponds to a frozen file on disk, and the node type in Nextcloud will be changed
        # to folder, since that is what is on disk. The IDA and Metax node counts in the audit
        # report will be reduced to 5
        print("(replacing file /testdata/2017-08/Experiment_1/baseline/test01.dat from frozen area of filesystem with same-named folder)")
        # Delete file /testdata/2017-08/Experiment_1/baseline/test01.dat from frozen area
        pathname = "%s/testdata/2017-08/Experiment_1/baseline/test01.dat" % frozen_area_root_c
        path = Path(pathname)
        try:
            os.remove(pathname)
        except Exception as error:
            self.fail("Failed to delete file %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())
        # Create folder /testdata/2017-08/Experiment_1/baseline/test01.dat in frozen area
        try:
            path.mkdir()
        except Exception as error:
            self.fail("Failed to create folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())

        print("(replacing file /testdata/2017-10/Experiment_3/baseline/test03.dat from staging area of filesystem with same-named folder)")
        # After repair the node type in Nextcloud will be changed to folder, since that is what is on disk
        # Delete file /testdata/2017-10/Experiment_3/baseline/test03.dat from staging area
        pathname = "%s/testdata/2017-10/Experiment_3/baseline/test03.dat" % staging_area_root_c
        path = Path(pathname)
        try:
            os.remove(pathname)
        except Exception as error:
            self.fail("Failed to delete file %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())
        # Create folder /testdata/2017-10/Experiment_3/baseline/test03.dat in staging area
        try:
            path.mkdir()
        except Exception as error:
            self.fail("Failed to create folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())

        print("(replacing folder /testdata/empty_folder_s from staging area of filesystem with same-named file)")
        # After repair the node type in Nextcloud will be changed to file, since that is what is on disk
        # Delete folder /testdata/empty_folder_s and its subfolders from staging area
        pathname = "%s/testdata/empty_folder_s" % staging_area_root_c
        path = Path(pathname)
        try:
            shutil.rmtree(pathname)
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())
        # Copy file /testdata/License.txt in staging area as file /testdata/empty_folder_s in staging area
        pathname2 = "%s/testdata/License.txt" % staging_area_root_c
        try:
            shutil.copyfile(pathname2, pathname)
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to copy file %s as file %s: %s" % (pathname2, pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())

        print("(retrieving frozen file PID lists for project C from IDA and Metax after modifications)")
        frozen_file_pids_3 = get_frozen_file_pids(self, 'test_project_c', test_user_c)
        metax_file_pids_3 = get_metax_file_pids(self, 'test_project_c')
        #print("IDA frozen file PIDs 3: %s" % json.dumps(frozen_file_pids_3))
        #print("IDA frozen file PID count 3: %d" % len(frozen_file_pids_3))
        #print("Metax frozen file PIDs 3: %s" % json.dumps(metax_file_pids_3))
        #print("Metax frozen file PID count 3: %d" % len(metax_file_pids_3))
        self.assertEqual(len(frozen_file_pids_3), 6)
        self.assertEqual(len(metax_file_pids_3), 6)

        print("(comparing PID lists for project C in IDA and Metax after modifications)")
        frozen_file_pid_diff_2v3, frozen_file_pid_diff_3v2 = array_difference(frozen_file_pids_2, frozen_file_pids_3)
        metax_file_pid_diff_2v3, metax_file_pid_diff_3v2 = array_difference(metax_file_pids_2, metax_file_pids_3)
        #print("IDA frozen file diff 2v3: %s" % json.dumps(frozen_file_pid_diff_2v3))
        #print("IDA frozen file diff 3v2: %s" % json.dumps(frozen_file_pid_diff_3v2))
        #print("Metax frozen file diff 2v3: %s" % json.dumps(metax_file_pid_diff_2v3))
        #print("Metax frozen file diff 3v2: %s" % json.dumps(metax_file_pid_diff_3v2))
        self.assertEqual(len(frozen_file_pid_diff_2v3), 0)
        self.assertEqual(len(frozen_file_pid_diff_3v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v3), 0)
        self.assertEqual(len(metax_file_pid_diff_3v2), 0)

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project D")

        print("(retrieving frozen file PID lists for project D from IDA and Metax before modifications)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_d', test_user_d)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_d')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 0)
        self.assertEqual(len(metax_file_pids_1), 0)

        print("(freezing folder /testdata/2017-08/Experiment_1/baseline)")
        data = {"project": "test_project_d", "pathname": "/testdata/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=headers, json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_d", test_user_d)
        check_for_failed_actions(self, "test_project_d", test_user_d)

        print("(retrieving frozen file PID lists for project D from IDA and Metax after freezing)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_d', test_user_d)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_d')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 6)
        self.assertEqual(len(metax_file_pids_2), 6)

        print("(comparing PID lists for project D in IDA and Metax after freezing)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2v1 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2v1 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 0)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 6)
        self.assertEqual(len(metax_file_pid_diff_1v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v1), 6)

        # After repair there will be one additional node (folder) due to the existence of the 'baseline' directory
        # in both frozen area and staging compared to before freezing the 'baseline' folder and unfreezing test01.dat
        print("(unfreezing file /testdata/2017-08/Experiment_1/baseline/test01.dat only in IDA, simulating postprocessing agents)")
        data = {"project": "test_project_d", "pathname": "/testdata/2017-08/Experiment_1/baseline/test01.dat"}
        headers_d = { 'X-SIMULATE-AGENTS': 'true' }
        response = requests.post("%s/unfreeze" % self.config["IDA_API"], headers=headers_d, json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "unfreeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_d", test_user_d)
        check_for_failed_actions(self, "test_project_d", test_user_d)

        print("(deleting file /testdata/2017-08/Experiment_1/baseline/test02.dat from Metax)")
        data = {"project": "test_project_d", "pathname": "/testdata/2017-08/Experiment_1/baseline/test02.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        pid = file_data["pid"]
        if self.config["METAX_API_VERSION"] >= 3:
            data = [{ "storage_service": "ida", "storage_identifier": pid }]
            response = requests.post("%s/files/delete-many" % self.config["METAX_API"], json=data, headers=self.metax_headers)
        else:
            response = requests.delete("%s/files/%s" % (self.config["METAX_API"], pid), auth=self.metax_user)
        self.assertEqual(response.status_code, 200)

        pathname = "/testdata/2017-08/Experiment_1/baseline/test03.dat"

        print("(retrieving pid of file %s in IDA db)")
        cur.execute("SELECT pid FROM %sida_frozen_file WHERE project = 'test_project_d' AND pathname = '%s'" % (self.config["DBTABLEPREFIX"], pathname))
        rows = cur.fetchall()
        if len(rows) != 1:
            self.fail("Failed to retrieve pid for frozen file")
        # The following are used below to restore the original frozen file pid after temporarily changing it before auditing tests
        original_frozen_file_pid = rows[0][0]
        original_frozen_file_pathname = pathname # used below to restore original pid

        print("(changing size of file %s in IDA db)" % pathname)
        cur.execute("UPDATE %sida_frozen_file SET size = %d WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], 123, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file size")

        print("(changing checksum of file %s in IDA db)" % pathname)
        cur.execute("UPDATE %sida_frozen_file SET checksum = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], "a0b0c0", pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file checksum")

        print("(changing frozen timestamp of file %s in IDA db)" % pathname)
        cur.execute("UPDATE %sida_frozen_file SET frozen = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], '2017-01-01T00:00:00Z', pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file frozen timestamp")

        print("(changing modification timestamp of file %s in IDA db)" % pathname)
        cur.execute("UPDATE %sida_frozen_file SET modified = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], '2017-01-01T00:00:00Z', pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file modification timestamp")

        print("(changing pid of file %s in IDA db)" % pathname)
        cur.execute("UPDATE %sida_frozen_file SET pid = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], "abc123", pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file pid")

        print("(deleting file /testdata/2017-08/Experiment_1/baseline/test04.dat from replication)")
        pathname = "%s/projects/test_project_d/testdata/2017-08/Experiment_1/baseline/test04.dat" % self.config['DATA_REPLICATION_ROOT']
        try:
            os.remove(pathname)
        except Exception as error:
            self.fail("Failed to delete file %s: %s" % (pathname, str(error)))
        path = Path(pathname)
        self.assertFalse(path.exists())

        print("(changing size of file /testdata/2017-08/Experiment_1/baseline/test05.dat in replication)")
        pathname = "%s/projects/test_project_d/testdata/2017-08/Experiment_1/baseline/test05.dat" % self.config['DATA_REPLICATION_ROOT']
        try:
            shutil.copyfile("/dev/null", pathname)
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to change size of file %s: %s" % (pathname, str(error)))
        path = Path(pathname)
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())

        print("(swapping file for folder in replication)")

        # Delete file /testdata/2017-08/Experiment_1/baseline/zero_size_file from replication
        pathname = "%s/projects/test_project_d/testdata/2017-08/Experiment_1/baseline/zero_size_file" % self.config['DATA_REPLICATION_ROOT']
        path = Path(pathname)
        try:
            os.remove(pathname)
        except Exception as error:
            self.fail("Failed to delete file %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())

        # Create folder /testdata/2017-08/Experiment_1/baseline/zero_size_file in replication
        try:
            path.mkdir()
        except Exception as error:
            self.fail("Failed to create folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())

        self.config['MODIFIED'] = generate_timestamp()
        print("MODIFIED: %s" % self.config['MODIFIED'])

        print("(retrieving frozen file PID lists for project D from IDA and Metax after modifications)")
        frozen_file_pids_3 = get_frozen_file_pids(self, 'test_project_d', test_user_d)
        metax_file_pids_3 = get_metax_file_pids(self, 'test_project_d')
        #print("IDA frozen file PIDs 3: %s" % json.dumps(frozen_file_pids_3))
        #print("IDA frozen file PID count 3: %d" % len(frozen_file_pids_3))
        #print("Metax frozen file PIDs 3: %s" % json.dumps(metax_file_pids_3))
        #print("Metax frozen file PID count 3: %d" % len(metax_file_pids_3))
        self.assertEqual(len(frozen_file_pids_3), 5)
        self.assertEqual(len(metax_file_pids_3), 5)

        print("(comparing PID lists for project D in IDA and Metax after modifications)")
        frozen_file_pid_diff_2v3, frozen_file_pid_diff_3v2 = array_difference(frozen_file_pids_2, frozen_file_pids_3)
        metax_file_pid_diff_2v3, metax_file_pid_diff_3v2 = array_difference(metax_file_pids_2, metax_file_pids_3)
        #print("IDA frozen file diff 2v3: %s" % json.dumps(frozen_file_pid_diff_2v3))
        #print("IDA frozen file diff 3v2: %s" % json.dumps(frozen_file_pid_diff_3v2))
        #print("Metax frozen file diff 2v3: %s" % json.dumps(metax_file_pid_diff_2v3))
        #print("Metax frozen file diff 3v2: %s" % json.dumps(metax_file_pid_diff_3v2))
        self.assertEqual(len(frozen_file_pid_diff_2v3), 2)
        self.assertEqual(len(frozen_file_pid_diff_3v2), 1)
        self.assertEqual(len(metax_file_pid_diff_2v3), 1)
        self.assertEqual(len(metax_file_pid_diff_3v2), 0)

        # --------------------------------------------------------------------------------

        print("--- Checking detection of active projects")

        print("(retrieving list of active projects since initialization)")
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/list-active-projects %s" % (
            self.config["HTTPD_USER"],
            self.config["ROOT"],
            self.config["START"]
        )
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        print("Verify active projects list includes project A")
        self.assertIn("test_project_a", output)

        print("Verify active projects list includes project B")
        self.assertIn("test_project_b", output)

        print("Verify active projects list includes project C")
        self.assertIn("test_project_c", output)

        print("Verify active projects list includes project D")
        self.assertIn("test_project_d", output)

        print("Verify active projects list includes project E")
        self.assertIn("test_project_e", output)

        print("(retrieving list of active projects since initialization)")
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/list-active-projects %s" % (
            self.config["HTTPD_USER"],
            self.config["ROOT"],
            self.config["INITIALIZED"]
        )
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        print("Verify active projects list includes project A")
        self.assertIn("test_project_a", output)

        print("Verify active projects list includes project B")
        self.assertIn("test_project_b", output)

        print("Verify active projects list includes project C")
        self.assertIn("test_project_c", output)

        print("Verify active projects list includes project D")
        self.assertIn("test_project_d", output)

        print("Verify active projects list does not include project E")
        self.assertNotIn("test_project_e", output)

        print("(retrieving list of active projects since modifications)")
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/list-active-projects %s" % (
            self.config["HTTPD_USER"],
            self.config["ROOT"],
            self.config["MODIFIED"]
        )
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding)
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        print("Verify active projects list does not include project A")
        self.assertNotIn("test_project_a", output)

        print("Verify active projects list does not include project B")
        self.assertNotIn("test_project_b", output)

        print("Verify active projects list does not include project C")
        self.assertNotIn("test_project_c", output)

        print("Verify active projects list does not include project D")
        self.assertNotIn("test_project_d", output)

        print("Verify active projects list does not include project E")
        self.assertNotIn("test_project_e", output)

        # --------------------------------------------------------------------------------

        print("--- Auditing project A and checking results")

        report_data = self.audit_project("test_project_a", "ERR")
        report_pathname_a = report_data["reportPathname"]
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 103)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 115)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 16)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 16)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 2)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEqual(len(nodes), report_data['invalidNodeCount'])

        # Verify select invalid node error messages for each type of error...

        print("Verify correct error report of Nextcloud folder missing from filesystem")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)
        node = nodes.get("staging/testdata/2017-10/Experiment_3/baseline")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)

        print("Verify correct error report of Nextcloud file missing from filesystem")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test01.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)
        node = nodes.get("staging/testdata/2017-10/Experiment_3/baseline/test03.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)

        print("Verify correct error report of filesystem file missing from Nextcloud")
        node = nodes.get("staging/testdata/2017-08/Experiment_1/baseline/test01.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in Nextcloud" in errors)

        print("--- Auditing staging area of project A and checking results")

        report_data = self.audit_project("test_project_a", "ERR", area="staging")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertFalse(report_data.get('auditFrozen'), True)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 96)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 101)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 0)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 9)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 9)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 2)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify all reported invalid nodes are in staging area")
        self.assertFalse(any(map(lambda key: key.startswith('frozen/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing frozen area of project A and checking results")

        report_data = self.audit_project("test_project_a", "ERR", area="frozen")
        self.assertFalse(report_data.get('auditStaging'), True)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 7)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 14)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 7)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 7)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 1)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify all reported invalid nodes are in frozen area")
        self.assertFalse(any(map(lambda key: key.startswith('staging/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project A after start of tests and checking results")

        report_data = self.audit_project("test_project_a", "ERR", since=self.config['START'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['START'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 101)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 115)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 14)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 14)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 1)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project A after initialization and checking results")

        report_data = self.audit_project("test_project_a", "ERR", since=self.config['INITIALIZED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['INITIALIZED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 6)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 13)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 7)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 7)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 1)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project A after modifications and checking results")

        report_data = self.audit_project("test_project_a", "OK", since=self.config['MODIFIED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['MODIFIED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 0)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 0)

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

        print("--- Auditing project B and checking results")

        report_data = self.audit_project("test_project_b", "ERR")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        report_pathname_b = report_data["reportPathname"]

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 115)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 115)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 2)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 6)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 6)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEqual(len(nodes), report_data['invalidNodeCount'])

        # Verify both invalid node error messages...

        print("Verify correct error report of Nextcloud file size conflict with filesystem")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test01.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node size different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud")
        self.assertIsNotNone(nextcloud)
        self.assertEqual(nextcloud.get("type"), "file")
        self.assertEqual(nextcloud.get("size"), 123)
        self.assertIsNotNone(nextcloud.get("uploaded"))

        print("Verify correct error report of Nextcloud modification timestamp conflict with filesystem")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test04.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node modification timestamp different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud")
        self.assertIsNotNone(nextcloud)
        self.assertEqual(nextcloud.get("type"), "file")
        self.assertEqual(nextcloud.get("modified"), invalid_timestamp)
        self.assertIsNotNone(nextcloud.get("uploaded"))

        print("--- Auditing staging area of project B and checking results")

        report_data = self.audit_project("test_project_b", "OK", area="staging")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertFalse(report_data.get('auditFrozen'), True)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 101)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 101)

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

        print("--- Auditing frozen area of project B and checking results")

        report_data = self.audit_project("test_project_b", "ERR", area="frozen")
        self.assertFalse(report_data.get('auditStaging'), True)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 14)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 14)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 2)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 6)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 6)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify all reported invalid nodes are in frozen area")
        self.assertFalse(any(map(lambda key: key.startswith('staging/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project B after start of tests and checking results")

        report_data = self.audit_project("test_project_b", "ERR", since=self.config['START'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['START'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 115)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 115)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 2)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 6)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 6)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project B after initialization and checking results")

        report_data = self.audit_project("test_project_b", "ERR", since=self.config['INITIALIZED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['INITIALIZED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 13)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 13)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 2)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 6)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 6)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project B after modifications and checking results")

        report_data = self.audit_project("test_project_b", "OK", since=self.config['MODIFIED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['MODIFIED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 0)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 0)

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

        print("--- Auditing project C and checking results")

        report_data = self.audit_project("test_project_c", "ERR")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        report_pathname_c = report_data["reportPathname"]

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 112)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 115)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 6)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 8)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 4)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEqual(len(nodes), report_data['invalidNodeCount'])

        # Verify all invalid node error messages...

        print("Verify correct error report of Nextcloud file type conflict with filesystem folder")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test01.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud")
        self.assertIsNotNone(nextcloud)
        self.assertEqual(nextcloud.get("type"), "file")
        self.assertIsNotNone(nextcloud.get("uploaded"))
        filesystem = node.get("filesystem")
        self.assertIsNotNone(filesystem)
        self.assertEqual(filesystem.get("type"), "folder")

        node = nodes.get("staging/testdata/2017-10/Experiment_3/baseline/test03.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud")
        self.assertIsNotNone(nextcloud)
        self.assertEqual(nextcloud.get("type"), "file")
        self.assertIsNotNone(nextcloud.get("uploaded"))
        filesystem = node.get("filesystem")
        self.assertIsNotNone(filesystem)
        self.assertEqual(filesystem.get("type"), "folder")

        print("Verify correct error report of Nextcloud folder type conflict with filesystem file")
        node = nodes.get("staging/testdata/empty_folder_s")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud")
        self.assertIsNotNone(nextcloud)
        self.assertEqual(nextcloud.get("type"), "folder")
        filesystem = node.get("filesystem")
        self.assertIsNotNone(filesystem)
        self.assertEqual(filesystem.get("type"), "file")

        print("--- Auditing staging area of project C and checking results")

        report_data = self.audit_project("test_project_c", "ERR", area="staging")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertFalse(report_data.get('auditFrozen'), True)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 98)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 101)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 0)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 5)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 5)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 2)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify all reported invalid nodes are in staging area")
        self.assertFalse(any(map(lambda key: key.startswith('frozen/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing frozen area of project C and checking results")

        report_data = self.audit_project("test_project_c", "ERR", area="frozen")
        self.assertFalse(report_data.get('auditStaging'), True)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 14)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 14)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 1)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 3)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 3)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify all reported invalid nodes are in frozen area")
        self.assertFalse(any(map(lambda key: key.startswith('staging/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project C after start of tests and checking results")

        report_data = self.audit_project("test_project_c", "ERR", since=self.config['START'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['START'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 112)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 115)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 6)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 8)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 4)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project C after initialization and checking results")

        report_data = self.audit_project("test_project_c", "ERR", since=self.config['INITIALIZED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['INITIALIZED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 13)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 13)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 1)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 3)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 3)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project C after modifications and checking results")

        report_data = self.audit_project("test_project_c", "OK", since=self.config['MODIFIED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['MODIFIED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 0)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 0)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 0)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 0)

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

        print("--- Auditing project D and checking results")

        report_data = self.audit_project("test_project_d", "ERR")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        report_pathname_d = report_data["reportPathname"]

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 116)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 116)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 5)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 6)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 19)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 18)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEqual(len(nodes), report_data['invalidNodeCount'])

        # Verify all invalid node error messages...

        print("Verify correct error report of frozen file known to Metax but missing from IDA")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test01.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in IDA" in errors)
        self.assertTrue("Node does not exist in Nextcloud" in errors)
        self.assertTrue("Node does not exist in filesystem" in errors)

        print("Verify correct error report of frozen file known to IDA but missing from Metax")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test02.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in Metax" in errors)

        print("Verify correct error report of IDA file size conflict with Metax")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test03.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node size different for IDA and Metax" in errors)

        print("Verify correct error report of IDA file checksum conflict with both filesystem and Metax")
        self.assertTrue("Node checksum different for IDA and Metax" in errors)
        self.assertTrue("Node checksum different for Nextcloud and IDA" in errors)
        self.assertTrue("Node checksum different for filesystem and IDA" in errors)

        print("Verify correct error report of IDA file pid conflict with Metax")
        self.assertTrue("Node pid different for IDA and Metax" in errors)

        print("Verify correct error report of IDA file frozen timestamp conflict with Metax")
        self.assertTrue("Node frozen timestamp different for IDA and Metax" in errors)

        print("Verify correct error report of IDA file modification timestamp conflict with Metax")
        self.assertTrue("Node modification timestamp different for IDA and Metax" in errors)

        print("Verify correct error report of IDA file missing from replication")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test04.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in replication" in errors)

        print("Verify correct error report of IDA file size conflict with replication")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test05.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node size different for replication and IDA" in errors)

        print("Verify correct error report of IDA file type conflict with replication")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/zero_size_file")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for replication and IDA" in errors)

        print("--- Auditing staging area of project D and checking results")

        report_data = self.audit_project("test_project_d", "OK", area="staging")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertFalse(report_data.get('auditFrozen'), True)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 103)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 103)

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

        print("Verify all reported invalid nodes are in staging area")
        self.assertFalse(any(map(lambda key: key.startswith('frozen/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing frozen area of project D and checking results")

        report_data = self.audit_project("test_project_d", "ERR", area="frozen")
        self.assertFalse(report_data.get('auditStaging'), True)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 13)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 13)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 5)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 6)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 19)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 18)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify all reported invalid nodes are in frozen area")
        self.assertFalse(any(map(lambda key: key.startswith('staging/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project D after start of tests and checking results")

        report_data = self.audit_project("test_project_d", "ERR", since=self.config['START'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['START'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 116)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 116)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 4)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 6)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 8)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 7)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project D after initialization and checking results")

        report_data = self.audit_project("test_project_d", "ERR", since=self.config['INITIALIZED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['INITIALIZED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 13)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 13)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 4)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 6)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 8)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 7)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project D after modifications and checking results")

        report_data = self.audit_project("test_project_d", "OK", since=self.config['MODIFIED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['MODIFIED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 0)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 0)

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

        print("--- Auditing project E and checking results")

        report_data = self.audit_project("test_project_e", "OK")
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

        print("--- Auditing staging area of project E and checking results")

        report_data = self.audit_project("test_project_e", "OK", area="staging")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertFalse(report_data.get('auditFrozen'), True)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 108)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 108)

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

        print("--- Auditing frozen area of project E and checking results")

        report_data = self.audit_project("test_project_e", "OK", area="frozen")
        self.assertFalse(report_data.get('auditStaging'), True)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 5)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 5)

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

        print("--- Auditing changes in project E after start of tests and checking results")

        report_data = self.audit_project("test_project_e", "OK", since=self.config['START'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['START'])

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

        print("--- Auditing changes in project E after initialization and checking results")

        report_data = self.audit_project("test_project_e", "OK", since=self.config['INITIALIZED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['INITIALIZED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 0)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 0)

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

        print("--- Auditing changes in project E after modifications and checking results")

        report_data = self.audit_project("test_project_e", "OK", since=self.config['MODIFIED'])
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('changedSince'), self.config['MODIFIED'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 0)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 0)

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

        print("--- Repairing projects A, B, C, and D for re-auditing")

        print("(retrieving frozen file PID lists for project A from IDA and Metax before repair)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_a', test_user_a)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_a')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 6)
        self.assertEqual(len(metax_file_pids_1), 6)

        print("(repairing project A)")
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_a)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        print("(retrieving frozen file PID lists for project A from IDA and Metax after repair)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_a', test_user_a)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_a')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 0)
        self.assertEqual(len(metax_file_pids_2), 0)

        print("(comparing PID lists for project A in IDA and Metax after repair)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2v1 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2v1 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 6)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 0)
        self.assertEqual(len(metax_file_pid_diff_1v2), 6)
        self.assertEqual(len(metax_file_pid_diff_2v1), 0)

        print("(retrieving frozen file PID lists for project B from IDA and Metax before repair)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_b', test_user_b)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_b')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 6)
        self.assertEqual(len(metax_file_pids_1), 6)

        print("(repairing project B)")
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_b)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_b", test_user_b)
        check_for_failed_actions(self, "test_project_b", test_user_b)

        print("(retrieving frozen file PID lists for project B from IDA and Metax after repair)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_b', test_user_b)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_b')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 6)
        self.assertEqual(len(metax_file_pids_2), 6)

        print("(comparing PID lists for project B in IDA and Metax after repair)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2v1 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2v1 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 0)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 0)
        self.assertEqual(len(metax_file_pid_diff_1v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v1), 0)

        print("(retrieving frozen file PID lists for project C from IDA and Metax before repair)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_c', test_user_c)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_c')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 6)
        self.assertEqual(len(metax_file_pids_1), 6)

        print("(repairing project C)")
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_c)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_c", test_user_c)
        check_for_failed_actions(self, "test_project_c", test_user_c)

        print("(retrieving frozen file PID lists for project C from IDA and Metax after repair)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_c', test_user_c)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_c')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 5)
        self.assertEqual(len(metax_file_pids_2), 5)

        print("(comparing PID lists for project C in IDA and Metax after repair)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2v1 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2v1 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 1)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 0)
        self.assertEqual(len(metax_file_pid_diff_1v2), 1)
        self.assertEqual(len(metax_file_pid_diff_2v1), 0)

        print("(retrieving frozen file PID lists for project D from IDA and Metax before repair)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_d', test_user_d)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_d')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 5)
        self.assertEqual(len(metax_file_pids_1), 5)

        print("(repairing project D)")

        # NOTE: The repair process doesn't resolve a mismatch of node types (file vs folder) in replication,
        # even though the audit process will report the issue if it ever occurs in reality (which it
        # likely never will), so to ensure the repair process and post-repair auditing succeed for these
        # tests, we will first restore the file which was replaced with a same named folder, via which
        # the tests introduced the conflicting node type error to be detected by the auditing process...

        pathname = "%s/projects/test_project_d/testdata/2017-08/Experiment_1/baseline/zero_size_file" % self.config['DATA_REPLICATION_ROOT']
        path = Path(pathname)
        try:
            shutil.rmtree(pathname)
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())
        cmd = "sudo -u %s touch %s" % (self.config["HTTPD_USER"], pathname)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())

        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_d)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_d", test_user_d)
        check_for_failed_actions(self, "test_project_d", test_user_d)

        print("(retrieving frozen file PID lists for project D from IDA and Metax after repair)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_d', test_user_d)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_d')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 5)
        self.assertEqual(len(metax_file_pids_2), 5)

        print("(comparing PID lists for project D in IDA and Metax after repair)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2 = array_difference(frozen_file_pids_1, frozen_file_pids_1)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 0)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 0)
        self.assertEqual(len(metax_file_pid_diff_1v2), 2)
        self.assertEqual(len(metax_file_pid_diff_2v1), 0)

        self.remove_report(report_pathname_a)
        self.remove_report(report_pathname_b)
        self.remove_report(report_pathname_c)
        self.remove_report(report_pathname_d)

        # --------------------------------------------------------------------------------
        # --------------------------------------------------------------------------------
        # --------------------------------------------------------------------------------

        print("--- Re-auditing project A and checking results")

        report_data = self.audit_project("test_project_a", "OK")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 103)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 103)

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

        print("--- Re-auditing project B and checking results")

        report_data = self.audit_project("test_project_b", "OK")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 115)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 115)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

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

        print("--- Re-auditing project C and checking results")

        # NOTE: The repair process will fail to fully repair three empty folders which
        # no longer exist in the filesystem in staging but are defined in the Nextcloud
        # cache. This is because we deleted them from the filesystem and changed their
        # ancestor folder to a file with the same pathname. However, the occ files:scan
        # tool is unable to detect this odd form of corruption and update the cache
        # fully. It will update the cache record for the folder that was changed to a file,
        # but the records for the descendant folders removed from the filesystem and now
        # with no ancestor folder, i.e. orphaned, remain as residue in the cache records.
        # We will simply ignore these remaining errors. If any such corruption occurs in
        # reality, it will need to be fixed manually.

        report_data = self.audit_project("test_project_c", "ERR")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 112)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 115)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 5)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 3)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 3)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 1)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify exact error and node pathnames to be ignored")
        self.assertTrue('Node does not exist in filesystem' in report_data['errors'])
        self.assertEqual(report_data["errors"]["Node does not exist in filesystem"]["folders"]["staging"]["node_count"], 3)
        self.assertEqual(report_data["invalidNodes"]["staging/testdata/empty_folder_s/a"]["errors"][0], "Node does not exist in filesystem")
        self.assertEqual(report_data["invalidNodes"]["staging/testdata/empty_folder_s/a"]["nextcloud"]["type"], "folder")
        self.assertEqual(report_data["invalidNodes"]["staging/testdata/empty_folder_s/a/b"]["errors"][0], "Node does not exist in filesystem")
        self.assertEqual(report_data["invalidNodes"]["staging/testdata/empty_folder_s/a/b"]["nextcloud"]["type"], "folder")
        self.assertEqual(report_data["invalidNodes"]["staging/testdata/empty_folder_s/a/b/c"]["errors"][0], "Node does not exist in filesystem")
        self.assertEqual(report_data["invalidNodes"]["staging/testdata/empty_folder_s/a/b/c"]["nextcloud"]["type"], "folder")

        self.remove_report(report_data['reportPathname'])

        print("--- Re-auditing project D and checking results")

        report_data = self.audit_project("test_project_d", "OK")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 116)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 116)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 5)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 0)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 0)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 0)

        print("Verify correct oldest and newest dates")
        self.assertIsNone(report_data.get("oldest"))
        self.assertIsNone(report_data.get("newest"))

        report_pathname_d = report_data["reportPathname"]

        print("--- Running repair on project D again when there are no issues, to ensure no unintended changes when repair not needed")

        print("(retrieving frozen file PID lists for project D from IDA and Metax before repair)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_d', test_user_d)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_d')

        print("(repairing project D)")
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project test_project_d" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_d", test_user_d)
        check_for_failed_actions(self, "test_project_d", test_user_d)

        print("(retrieving frozen file PID lists for project D from IDA and Metax after repair)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_d', test_user_d)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_d')

        print("(comparing before and after PID lists for project D in IDA and Metax)")
        frozen_file_pid_diff_1, frozen_file_pid_diff_2 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1, metax_file_pid_diff_2 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("IDA frozen file diff 1: %s" % json.dumps(frozen_file_pid_diff_1))
        #print("IDA frozen file diff 2: %s" % json.dumps(frozen_file_pid_diff_2))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        #print("Metax frozen file diff 1: %s" % json.dumps(metax_file_pid_diff_1))
        #print("Metax frozen file diff 2: %s" % json.dumps(metax_file_pid_diff_2))
        self.assertEqual(len(frozen_file_pids_1), len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_2), len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_1), len(frozen_file_pids_2))
        self.assertEqual(len(metax_file_pids_1), len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pid_diff_1), 0)
        self.assertEqual(len(metax_file_pid_diff_1), 0)
        self.assertEqual(len(frozen_file_pid_diff_2), 0)
        self.assertEqual(len(metax_file_pid_diff_2), 0)

        print("--- Re-auditing project D and checking results")

        report_data = self.audit_project("test_project_d", "OK")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 116)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 116)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 5)
        self.assertEqual(report_data.get("frozenFileCount"), len(frozen_file_pids_1))
        self.assertEqual(report_data.get("frozenFileCount"), len(frozen_file_pids_2))

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)
        self.assertEqual(report_data.get("metaxFileCount"), len(metax_file_pids_1))
        self.assertEqual(report_data.get("metaxFileCount"), len(metax_file_pids_2))

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

        print("--- Modifying state of test project A for checksum validation during freezing")

        print("(changing cache checksums of three files in staging in folder /testdata/2017-08/Experiment_2/baseline)")
        data = { "pathname": "staging/testdata/2017-08/Experiment_2/baseline/test01.dat", "checksum": invalid_checksum_uri }
        response = requests.post("%s/repairCacheChecksum" % self.config["IDA_API"], headers=headers, json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['project'], 'test_project_a')
        self.assertEqual(response_data['pathname'], 'staging/testdata/2017-08/Experiment_2/baseline/test01.dat')
        self.assertEqual(response_data['checksum'], invalid_checksum_uri)
        self.assertIsNotNone(response_data['nodeId'])
        data = { "pathname": "staging/testdata/2017-08/Experiment_2/baseline/test02.dat", "checksum": invalid_checksum_uri }
        response = requests.post("%s/repairCacheChecksum" % self.config["IDA_API"], headers=headers, json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['project'], 'test_project_a')
        self.assertEqual(response_data['pathname'], 'staging/testdata/2017-08/Experiment_2/baseline/test02.dat')
        self.assertEqual(response_data['checksum'], invalid_checksum_uri)
        self.assertIsNotNone(response_data['nodeId'])
        data = { "pathname": "staging/testdata/2017-08/Experiment_2/baseline/test03.dat", "checksum": invalid_checksum_uri }
        response = requests.post("%s/repairCacheChecksum" % self.config["IDA_API"], headers=headers, json=data, auth=pso_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['project'], 'test_project_a')
        self.assertEqual(response_data['pathname'], 'staging/testdata/2017-08/Experiment_2/baseline/test03.dat')
        self.assertEqual(response_data['checksum'], invalid_checksum_uri)
        self.assertIsNotNone(response_data['nodeId'])

        print("(freezing folder /testdata/2017-08/Experiment_2/baseline)")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_2/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=headers, json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_a", test_user_a)

        print("--- Verifying freeze action failed due to checksum mismatch")

        actions = check_for_failed_actions(self, "test_project_a", test_user_a, should_be_failed = True)
        assert(len(actions) == 1)
        action = actions[0]
        self.assertEqual(action.get('action'), 'freeze')
        self.assertEqual(action.get('project'), 'test_project_a')
        self.assertEqual(action.get('user'), 'test_user_a')
        self.assertEqual(action.get('pathname'), '/testdata/2017-08/Experiment_2/baseline')
        self.assertIsNotNone(action.get('failed'))
        self.assertIsNotNone(action.get('error'))
        self.assertTrue(action['error'].startswith('Files on disk do not match their Nextcloud cache checksums (total: 3):'))

        print("--- Verifying modified state of Project A")

        print("(retrieving inventory for Project A)")
        response = requests.get("%s/inventory/test_project_a?testing=true" % self.config["IDA_API"], auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        inventory = response.json()
        frozen = inventory.get('frozen')
        self.assertIsNotNone(frozen)
        for pathname in [ "/testdata/2017-08/Experiment_2/baseline/test01.dat",
                          "/testdata/2017-08/Experiment_2/baseline/test02.dat",
                          "/testdata/2017-08/Experiment_2/baseline/test03.dat" ]:
            file = frozen.get(pathname)
            self.assertIsNotNone(file)
            self.assertIsNotNone(file.get('frozen'))
            checksum = file.get('checksum')
            self.assertIsNotNone(checksum)
            self.assertEqual(checksum, invalid_checksum_uri)
            self.assertEqual(checksum, invalid_checksum_uri, "%s %s != %s" % (pathname, checksum, invalid_checksum_uri))

        print("--- Auditing project A and verifying checksum errors reported")

        report_data = self.audit_project("test_project_a", "ERR")
        report_pathname = report_data["reportPathname"]
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))
        self.assertEqual(report_data.get('invalidNodeCount'), 6)
        self.assertEqual(report_data.get('errorNodeCount'), 15)
        self.assertEqual(report_data.get('errorCount'), 3)
        errors = list(report_data['errors'].keys())
        self.assertEqual(len(errors), 3)
        self.assertTrue('Node checksum different for filesystem and Nextcloud' in errors)
        self.assertTrue('Node checksum missing for IDA' in errors)
        self.assertTrue('Node does not exist in Metax' in errors)

        print("--- Repairing project A")

        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_a", test_user_a)
        check_for_failed_actions(self, "test_project_a", test_user_a)

        print("--- Auditing project A and verifying no errors are reported")

        report_data = self.audit_project("test_project_a", "OK")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))

        print("--- Verifying repaired state of Project A")

        print("(retrieving inventory for Project A)")
        response = requests.get("%s/inventory/test_project_a?testing=true" % self.config["IDA_API"], auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        inventory = response.json()
        frozen = inventory.get('frozen')
        self.assertIsNotNone(frozen)
        for pathname in [ "/testdata/2017-08/Experiment_2/baseline/test01.dat",
                          "/testdata/2017-08/Experiment_2/baseline/test02.dat",
                          "/testdata/2017-08/Experiment_2/baseline/test03.dat",
                          "/testdata/2017-08/Experiment_2/baseline/test04.dat",
                          "/testdata/2017-08/Experiment_2/baseline/test05.dat",
                          "/testdata/2017-08/Experiment_2/baseline/zero_size_file" ]:
            file = frozen.get(pathname)
            self.assertIsNotNone(file)
            self.assertIsNotNone(file.get('frozen'))
            checksum = file.get('checksum')
            self.assertIsNotNone(checksum)
            self.assertNotEqual(checksum, invalid_checksum_uri, pathname)
            cacheChecksum = file.get('cacheChecksum')
            self.assertIsNotNone(cacheChecksum)
            self.assertNotEqual(cacheChecksum, invalid_checksum_uri, pathname)

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project B for checksum and timestamp option checks")

        print("(freezing folder /testdata/2017-08/Experiment_2/baseline)")
        data = {"project": "test_project_b", "pathname": "/testdata/2017-08/Experiment_2/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=headers, json=data, auth=test_user_b, verify=False)
        self.assertEqual(response.status_code, 200)

        wait_for_pending_actions(self, "test_project_b", test_user_b)
        check_for_failed_actions(self, "test_project_b", test_user_b)

        # retrieve PSO storage id for test_project_b
        cur.execute("SELECT numeric_id from %sstorages WHERE id = 'home::%stest_project_b' LIMIT 1"
                    % (self.config["DBTABLEPREFIX"], self.config["PROJECT_USER_PREFIX"]))
        rows = cur.fetchall()
        if len(rows) != 1:
            self.fail("Failed to retrieve storage id for test_project_b")
        storage_id_b = rows[0][0]

        print("(changing checksum in Nextcloud of frozen file /testdata/2017-08/Experiment_2/baseline/test01.dat)")
        pathname = "files/test_project_b/testdata/2017-08/Experiment_2/baseline/test01.dat"
        cur.execute("UPDATE %sfilecache SET checksum = '%s' WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], invalid_checksum_uri, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node modification timestamp")

        print("(changing checksum in IDA of frozen file /testdata/2017-08/Experiment_2/baseline/test02.dat)")
        pathname = "/testdata/2017-08/Experiment_2/baseline/test02.dat"
        cur.execute("UPDATE %sida_frozen_file SET checksum = '%s' WHERE project = 'test_project_b' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], invalid_checksum, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file checksum")

        print("(changing checksum in Metax of frozen file /testdata/2017-08/Experiment_2/baseline/test03.dat)")
        data = {"project": "test_project_b", "pathname": "/testdata/2017-08/Experiment_2/baseline/test03.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API"], data["project"]), json=data, auth=test_user_b, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        pid = file_data["pid"]
        if self.config["METAX_API_VERSION"] >= 3:
            data = [{ "storage_service": "ida", "storage_identifier": pid, "checksum": invalid_checksum_uri }]
            response = requests.post("%s/files/patch-many" % self.config["METAX_API"], headers=self.metax_headers, json=data)
        else:
            data = { "checksum": { "algorithm": "SHA-256", "value": invalid_checksum, "checked": self.config['START'] } }
            response = requests.patch("%s/files/%s" % (self.config["METAX_API"], pid), auth=self.metax_user, json=data)
        self.assertEqual(response.status_code, 200)

        print("(changing checksum in Nextcloud of staging file /testdata/2017-08/Experiment_2/test04.dat)")
        pathname = "files/test_project_b+/testdata/2017-08/Experiment_2/test04.dat"
        cur.execute("UPDATE %sfilecache SET checksum = '%s' WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], invalid_checksum_uri, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node modification timestamp")

        print("(changing modified timestamp in Nextcloud of frozen file /testdata/2017-08/Experiment_2/baseline/test01.dat)")
        pathname = "files/test_project_b/testdata/2017-08/Experiment_2/baseline/test01.dat"
        cur.execute("UPDATE %sfilecache SET mtime = %d WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], invalid_timestamp_seconds, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node modification timestamp")

        print("(changing modified timestamp in IDA of frozen file /testdata/2017-08/Experiment_2/baseline/test02.dat)")
        pathname = "/testdata/2017-08/Experiment_2/baseline/test02.dat"
        cur.execute("UPDATE %sida_frozen_file SET modified = '%s' WHERE project = 'test_project_b' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], invalid_timestamp, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file modification timestamp")

        print("(changing modified timestamp in Metax of frozen file /testdata/2017-08/Experiment_2/baseline/test03.dat)")
        if self.config["METAX_API_VERSION"] >= 3:
            data = [{ "storage_service": "ida", "storage_identifier": pid, "modified": invalid_timestamp }]
            response = requests.post("%s/files/patch-many" % self.config["METAX_API"], headers=self.metax_headers, json=data)
        else:
            data = { "file_modified": invalid_timestamp }
            response = requests.patch("%s/files/%s" % (self.config["METAX_API"], pid), auth=self.metax_user, json=data)
        self.assertEqual(response.status_code, 200)

        print("(changing modified timestamp in Nextcloud of staging file /testdata/2017-08/Experiment_2/test04.dat)")
        pathname = "files/test_project_b+/testdata/2017-08/Experiment_2/test04.dat"
        cur.execute("UPDATE %sfilecache SET mtime = %d WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], invalid_timestamp_seconds, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node modification timestamp")

        print("--- Verifying modified state of Project B")

        print("(retrieving inventory for Project B from IDA)")
        response = requests.get("%s/inventory/test_project_b?testing=true" % self.config["IDA_API"], auth=test_user_b, verify=False)
        self.assertEqual(response.status_code, 200)
        inventory = response.json()
        frozen = inventory.get('frozen')
        staging = inventory.get('staging')
        self.assertIsNotNone(frozen)
        self.assertIsNotNone(staging)

        pathname = "/testdata/2017-08/Experiment_2/baseline/test01.dat"
        file = frozen.get(pathname)
        self.assertIsNotNone(file)
        self.assertIsNotNone(file.get('frozen'))
        checksum = file.get('checksum')
        self.assertIsNotNone(checksum)
        self.assertNotEqual(checksum, invalid_checksum_uri)
        cacheChecksum = file.get('cacheChecksum')
        self.assertIsNotNone(cacheChecksum)
        self.assertEqual(cacheChecksum, invalid_checksum_uri)
        modified = file.get('modified')
        self.assertIsNotNone(modified)
        self.assertNotEqual(modified, invalid_timestamp)
        cacheModified = file.get('cacheModified')
        self.assertIsNotNone(cacheModified)
        self.assertEqual(cacheModified, invalid_timestamp)

        pathname = "/testdata/2017-08/Experiment_2/baseline/test02.dat"
        file = frozen.get(pathname)
        self.assertIsNotNone(file)
        self.assertIsNotNone(file.get('frozen'))
        checksum = file.get('checksum')
        self.assertIsNotNone(checksum)
        self.assertEqual(checksum, invalid_checksum_uri)
        cacheChecksum = file.get('cacheChecksum')
        self.assertIsNotNone(cacheChecksum)
        self.assertNotEqual(cacheChecksum, invalid_checksum_uri)
        modified = file.get('modified')
        self.assertIsNotNone(modified)
        self.assertEqual(modified, invalid_timestamp)
        cacheModified = file.get('cacheModified')
        self.assertIsNotNone(cacheModified)
        self.assertNotEqual(cacheModified, invalid_timestamp)

        pathname = "/testdata/2017-08/Experiment_2/baseline/test03.dat"
        file = frozen.get(pathname)
        self.assertIsNotNone(file)
        self.assertIsNotNone(file.get('frozen'))
        checksum = file.get('checksum')
        self.assertIsNotNone(checksum)
        self.assertNotEqual(checksum, invalid_checksum_uri)
        cacheChecksum = file.get('cacheChecksum')
        self.assertIsNotNone(cacheChecksum)
        self.assertNotEqual(cacheChecksum, invalid_checksum_uri)
        modified = file.get('modified')
        self.assertIsNotNone(modified)
        self.assertNotEqual(modified, invalid_timestamp)
        cacheModified = file.get('cacheModified')
        self.assertIsNotNone(cacheModified)
        self.assertNotEqual(cacheModified, invalid_timestamp)

        pathname = "/testdata/2017-08/Experiment_2/test04.dat"
        file = staging.get(pathname)
        self.assertIsNotNone(file)
        self.assertIsNone(file.get('frozen'))
        checksum = file.get('checksum')
        self.assertIsNotNone(checksum)
        self.assertEqual(checksum, invalid_checksum_uri)
        cacheChecksum = file.get('cacheChecksum')
        self.assertIsNone(cacheChecksum)
        modified = file.get('modified')
        self.assertIsNotNone(modified)
        self.assertEqual(modified, invalid_timestamp)
        cacheModified = file.get('cacheModified')
        self.assertIsNone(cacheModified)

        print("(retrieving files for Project B from Metax)")

        if self.config["METAX_API_VERSION"] >= 3:
            url = "%s/files?storage_service=ida&storage_identifier=%s" % (self.config["METAX_API"], pid)
            response = requests.get(url, headers=self.metax_headers)
        else:
            response = requests.get("%s/files/%s" % (self.config["METAX_API"], pid), auth=self.metax_user)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data)
        if self.config["METAX_API_VERSION"] >= 3:
            self.assertEqual(data.get('count'), 1)
            results = data.get('results')
            self.assertIsNotNone(results)
            file = results[0]
            self.assertIsNotNone(file)
            self.assertEqual(file['checksum'], invalid_checksum_uri)
            self.assertEqual(normalize_timestamp(file['modified']), invalid_timestamp)
        else:
            self.assertEqual(data['checksum']['value'], invalid_checksum, json.dumps(file))
            self.assertEqual(normalize_timestamp(data['file_modified']), invalid_timestamp, json.dumps(file))

        print("--- Auditing project B with neither checksum nor timestamp options and verifying no errors reported")

        report_data = self.audit_project("test_project_b", "OK", checksums = False, timestamps = False)
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertFalse(report_data.get('auditChecksums'), True)
        self.assertFalse(report_data.get('auditTimestamps'), True)
        self.assertEqual(report_data.get('invalidNodeCount'), 0)
        self.assertEqual(report_data.get('errorNodeCount'), 0)
        self.assertEqual(report_data.get('errorCount'), 0)
        self.assertIsNone(report_data.get('changedSince'))

        print("--- Auditing project B with --checksums parameter and verifying only checksum errors are reported")

        report_data = self.audit_project("test_project_b", "ERR", checksums = True, timestamps = False)
        report_pathname = report_data["reportPathname"]
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertFalse(report_data.get('auditTimestamps'), True)
        self.assertIsNone(report_data.get('changedSince'))
        self.assertEqual(report_data.get('invalidNodeCount'), 4)
        self.assertEqual(report_data.get('errorNodeCount'), 10)
        self.assertEqual(report_data.get('errorCount'), 6)
        errors = list(report_data['errors'].keys())
        self.assertEqual(len(errors), 6)
        self.assertTrue('Node checksum different for IDA and Metax' in errors)
        self.assertTrue('Node checksum different for Nextcloud and IDA' in errors)
        self.assertTrue('Node checksum different for Nextcloud and Metax' in errors)
        self.assertTrue('Node checksum different for filesystem and IDA' in errors)
        self.assertTrue('Node checksum different for filesystem and Metax' in errors)
        self.assertTrue('Node checksum different for filesystem and Nextcloud' in errors)

        print("--- Auditing project B with --timestamp parameter and verifying only timestamp errors are reported")

        report_data = self.audit_project("test_project_b", "ERR", checksums = False, timestamps = True)
        report_pathname = report_data["reportPathname"]
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertFalse(report_data.get('auditChecksums'), True)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))
        self.assertEqual(report_data.get('invalidNodeCount'), 4)
        self.assertEqual(report_data.get('errorNodeCount'), 10)
        self.assertEqual(report_data.get('errorCount'), 6)
        errors = list(report_data['errors'].keys())
        self.assertEqual(len(errors), 6)
        self.assertTrue('Node modification timestamp different for IDA and Metax' in errors)
        self.assertTrue('Node modification timestamp different for Nextcloud and IDA' in errors)
        self.assertTrue('Node modification timestamp different for Nextcloud and Metax' in errors)
        self.assertTrue('Node modification timestamp different for filesystem and IDA' in errors)
        self.assertTrue('Node modification timestamp different for filesystem and Metax' in errors)
        self.assertTrue('Node modification timestamp different for filesystem and Nextcloud' in errors)

        print("--- Auditing project B with --full parameter and verifying both checksum and timestamp errors are reported")

        report_data = self.audit_project("test_project_b", "ERR")
        report_pathname = report_data["reportPathname"]
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertIsNone(report_data.get('changedSince'))
        self.assertEqual(report_data.get('invalidNodeCount'), 4)
        self.assertEqual(report_data.get('errorNodeCount'), 20)
        self.assertEqual(report_data.get('errorCount'), 12)
        errors = list(report_data['errors'].keys())
        self.assertEqual(len(errors), 12)
        self.assertTrue('Node checksum different for IDA and Metax' in errors)
        self.assertTrue('Node checksum different for Nextcloud and IDA' in errors)
        self.assertTrue('Node checksum different for Nextcloud and Metax' in errors)
        self.assertTrue('Node checksum different for filesystem and IDA' in errors)
        self.assertTrue('Node checksum different for filesystem and Metax' in errors)
        self.assertTrue('Node checksum different for filesystem and Nextcloud' in errors)
        self.assertTrue('Node modification timestamp different for IDA and Metax' in errors)
        self.assertTrue('Node modification timestamp different for Nextcloud and IDA' in errors)
        self.assertTrue('Node modification timestamp different for Nextcloud and Metax' in errors)
        self.assertTrue('Node modification timestamp different for filesystem and IDA' in errors)
        self.assertTrue('Node modification timestamp different for filesystem and Metax' in errors)
        self.assertTrue('Node modification timestamp different for filesystem and Nextcloud' in errors)

        print("--- Repairing project B")

        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_b", test_user_b)
        check_for_failed_actions(self, "test_project_b", test_user_b)

        print("--- Auditing project with --full parameter and verifying no errors are reported")

        report_data = self.audit_project("test_project_b", "OK")
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)
        self.assertEqual(report_data.get('invalidNodeCount'), 0)
        self.assertEqual(report_data.get('errorNodeCount'), 0)
        self.assertEqual(report_data.get('errorCount'), 0)
        self.assertIsNone(report_data.get('changedSince'))

        print("--- Verifying repaired state of Project B")

        print("(retrieving inventory for Project B)")
        response = requests.get("%s/inventory/test_project_b?testing=true" % self.config["IDA_API"], auth=test_user_b, verify=False)
        self.assertEqual(response.status_code, 200)
        inventory = response.json()
        frozen = inventory.get('frozen')
        staging = inventory.get('staging')
        self.assertIsNotNone(frozen)
        self.assertIsNotNone(staging)
        for pathname in [ "/testdata/2017-08/Experiment_2/baseline/test01.dat",
                          "/testdata/2017-08/Experiment_2/baseline/test02.dat",
                          "/testdata/2017-08/Experiment_2/baseline/test03.dat" ]:
            file = frozen.get(pathname)
            self.assertIsNotNone(file)
            self.assertIsNotNone(file.get('frozen'))
            checksum = file.get('checksum')
            self.assertIsNotNone(checksum)
            self.assertNotEqual(checksum, invalid_checksum_uri, pathname)
            self.assertNotEqual(checksum, invalid_checksum, pathname)
            modified = file.get('modified')
            self.assertIsNotNone(modified)
            self.assertNotEqual(modified, invalid_timestamp, pathname)
        pathname = "/testdata/2017-08/Experiment_2/test04.dat"
        file = staging.get(pathname)
        self.assertIsNotNone(file)
        self.assertIsNone(file.get('frozen'))
        checksum = file.get('checksum')
        self.assertIsNotNone(checksum)
        self.assertNotEqual(checksum, invalid_checksum_uri)
        self.assertNotEqual(checksum, invalid_checksum)
        modified = file.get('modified')
        self.assertIsNotNone(modified)
        self.assertNotEqual(modified, invalid_timestamp)

        if self.config["METAX_API_VERSION"] >= 3:
            response = requests.get("%s/files?storage_service=ida&storage_identifier=%s" % (self.config["METAX_API"], pid), headers=self.metax_headers)
        else:
            response = requests.get("%s/files/%s" % (self.config["METAX_API"], pid), auth=self.metax_user)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data)
        if self.config["METAX_API_VERSION"] >= 3:
            self.assertEqual(data.get('count'), 1)
            results = data.get('results')
            self.assertIsNotNone(results)
            file = results[0]
            self.assertIsNotNone(file)
            self.assertNotEqual(file['checksum'], invalid_checksum_uri)
            self.assertNotEqual(normalize_timestamp(file['modified']), invalid_timestamp)
        else:
            self.assertNotEqual(data['checksum']['value'], invalid_checksum)
            self.assertNotEqual(normalize_timestamp(data['file_modified']), invalid_timestamp)

        # --------------------------------------------------------------------------------
        # --------------------------------------------------------------------------------
        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project E (pass 1 repair with no audit report)")

        print("(retrieving frozen file PID lists for project E from IDA and Metax before modifications)")
        frozen_file_pids_1 = get_frozen_file_pids(self, 'test_project_e', test_user_e)
        metax_file_pids_1 = get_metax_file_pids(self, 'test_project_e')
        #print("IDA frozen file PIDs 1: %s" % json.dumps(frozen_file_pids_1))
        #print("IDA frozen file PID count 1: %d" % len(frozen_file_pids_1))
        #print("Metax frozen file PIDs 1: %s" % json.dumps(metax_file_pids_1))
        #print("Metax frozen file PID count 1: %d" % len(metax_file_pids_1))
        self.assertEqual(len(frozen_file_pids_1), 0)
        self.assertEqual(len(metax_file_pids_1), 0)

        print("(freezing folder /testdata)")
        data = {"project": "test_project_e", "pathname": "/testdata"}
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=headers, json=data, auth=test_user_e, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_e", test_user_e)
        check_for_failed_actions(self, "test_project_e", test_user_e)

        print("(retrieving frozen file PID lists for project E from IDA and Metax after freezing)")
        frozen_file_pids_2 = get_frozen_file_pids(self, 'test_project_e', test_user_e)
        metax_file_pids_2 = get_metax_file_pids(self, 'test_project_e')
        #print("IDA frozen file PIDs 2: %s" % json.dumps(frozen_file_pids_2))
        #print("IDA frozen file PID count 2: %d" % len(frozen_file_pids_2))
        #print("Metax frozen file PIDs 2: %s" % json.dumps(metax_file_pids_2))
        #print("Metax frozen file PID count 2: %d" % len(metax_file_pids_2))
        self.assertEqual(len(frozen_file_pids_2), 83)
        self.assertEqual(len(metax_file_pids_2), 83)

        print("(comparing PID lists for project E in IDA and Metax after freezing)")
        frozen_file_pid_diff_1v2, frozen_file_pid_diff_2v1 = array_difference(frozen_file_pids_1, frozen_file_pids_2)
        metax_file_pid_diff_1v2, metax_file_pid_diff_2v1 = array_difference(metax_file_pids_1, metax_file_pids_2)
        #print("IDA frozen file diff 1v2: %s" % json.dumps(frozen_file_pid_diff_1v2))
        #print("IDA frozen file diff 2v1: %s" % json.dumps(frozen_file_pid_diff_2v1))
        #print("Metax frozen file diff 1v2: %s" % json.dumps(metax_file_pid_diff_1v2))
        #print("Metax frozen file diff 2v1: %s" % json.dumps(metax_file_pid_diff_2v1))
        self.assertEqual(len(frozen_file_pid_diff_1v2), 0)
        self.assertEqual(len(frozen_file_pid_diff_2v1), 83)
        self.assertEqual(len(metax_file_pid_diff_1v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v1), 83)

        print("(unfreezing frozen folder /testdata/2017-08 only in IDA, simulating postprocessing agents)")
        data = {"project": "test_project_e", "pathname": "/testdata/2017-08"}
        headers_e = { 'X-SIMULATE-AGENTS': 'true' }
        response = requests.post("%s/unfreeze" % self.config["IDA_API"], headers=headers_e, json=data, auth=test_user_e, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "unfreeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_e", test_user_e)
        check_for_failed_actions(self, "test_project_e", test_user_e)

        print("(retrieving frozen file PID lists for project E from IDA and Metax after unfreezing)")
        frozen_file_pids_3 = get_frozen_file_pids(self, 'test_project_e', test_user_e)
        metax_file_pids_3 = get_metax_file_pids(self, 'test_project_e')
        #print("IDA frozen file PIDs 3: %s" % json.dumps(frozen_file_pids_3))
        #print("IDA frozen file PID count 3: %d" % len(frozen_file_pids_3))
        #print("Metax frozen file PIDs 3: %s" % json.dumps(metax_file_pids_3))
        #print("Metax frozen file PID count 3: %d" % len(metax_file_pids_3))
        self.assertEqual(len(frozen_file_pids_3), 56)
        self.assertEqual(len(metax_file_pids_3), 83)

        print("(comparing PID lists for project E in IDA and Metax after unfreezing)")
        frozen_file_pid_diff_2v3, frozen_file_pid_diff_3v2 = array_difference(frozen_file_pids_2, frozen_file_pids_3)
        metax_file_pid_diff_2v3, metax_file_pid_diff_3v2 = array_difference(metax_file_pids_2, metax_file_pids_3)
        #print("IDA frozen file diff 2v3: %s" % json.dumps(frozen_file_pid_diff_2v3))
        #print("IDA frozen file diff 3v2: %s" % json.dumps(frozen_file_pid_diff_3v2))
        #print("Metax frozen file diff 2v3: %s" % json.dumps(metax_file_pid_diff_2v3))
        #print("Metax frozen file diff 3v2: %s" % json.dumps(metax_file_pid_diff_3v2))
        self.assertEqual(len(frozen_file_pid_diff_2v3), 27)
        self.assertEqual(len(frozen_file_pid_diff_3v2), 0)
        self.assertEqual(len(metax_file_pid_diff_2v3), 0)
        self.assertEqual(len(metax_file_pid_diff_3v2), 0)

        print("--- Repairing project E (with no audit error report provided)")

        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project test_project_e" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_e", test_user_e)
        check_for_failed_actions(self, "test_project_e", test_user_e)

        print("(retrieving frozen file PID lists for project E from IDA and Metax after repair)")
        frozen_file_pids_4 = get_frozen_file_pids(self, 'test_project_e', test_user_e)
        metax_file_pids_4 = get_metax_file_pids(self, 'test_project_e')
        #print("IDA frozen file PIDs 4: %s" % json.dumps(frozen_file_pids_4))
        #print("IDA frozen file PID count 4: %d" % len(frozen_file_pids_4))
        #print("Metax frozen file PIDs 4: %s" % json.dumps(metax_file_pids_4))
        #print("Metax frozen file PID count 4: %d" % len(metax_file_pids_4))
        self.assertEqual(len(frozen_file_pids_4), 56)
        self.assertEqual(len(metax_file_pids_4), 56)

        print("(comparing PID lists for project E in IDA and Metax after repair)")
        frozen_file_pid_diff_3v4, frozen_file_pid_diff_4v3 = array_difference(frozen_file_pids_3, frozen_file_pids_4)
        metax_file_pid_diff_3v4, metax_file_pid_diff_4v3 = array_difference(metax_file_pids_3, metax_file_pids_4)
        #print("IDA frozen file diff 3v4: %s" % json.dumps(frozen_file_pid_diff_3v4))
        #print("IDA frozen file diff 4v3: %s" % json.dumps(frozen_file_pid_diff_4v3))
        #print("Metax frozen file diff 3v4: %s" % json.dumps(metax_file_pid_diff_3v4))
        #print("Metax frozen file diff 4v3: %s" % json.dumps(metax_file_pid_diff_4v3))
        self.assertEqual(len(frozen_file_pid_diff_3v4), 0)
        self.assertEqual(len(frozen_file_pid_diff_4v3), 0)
        self.assertEqual(len(metax_file_pid_diff_3v4), 27)
        self.assertEqual(len(metax_file_pid_diff_4v3), 0)

        print("--- Auditing project E and checking results")
        self.audit_project("test_project_e", "OK")

        print("(refreezing folder /testdata/2017-08)")
        data = {"project": "test_project_e", "pathname": "/testdata/2017-08"}
        headers_e = { 'X-SIMULATE-AGENTS': 'false' }
        response = requests.post("%s/freeze" % self.config["IDA_API"], headers=headers_e, json=data, auth=test_user_e, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_e", test_user_e)
        check_for_failed_actions(self, "test_project_e", test_user_e)

        print("(retrieving frozen file PID lists for project E from IDA and Metax after refreezing)")
        frozen_file_pids_5 = get_frozen_file_pids(self, 'test_project_e', test_user_e)
        metax_file_pids_5 = get_metax_file_pids(self, 'test_project_e')
        #print("IDA frozen file PIDs 5: %s" % json.dumps(frozen_file_pids_5))
        #print("IDA frozen file PID count 5: %d" % len(frozen_file_pids_5))
        #print("Metax frozen file PIDs 5: %s" % json.dumps(metax_file_pids_5))
        #print("Metax frozen file PID count 5: %d" % len(metax_file_pids_5))
        self.assertEqual(len(frozen_file_pids_5), 83)
        self.assertEqual(len(metax_file_pids_5), 83)

        print("--- Auditing project E and checking results")
        self.audit_project("test_project_e", "OK")

        print("--- Modifying state of test project E (pass 2 repair with audit error report)")

        print("(unfreezing frozen folder /testdata/2017-08 only in IDA, simulating postprocessing agents)")
        data = {"project": "test_project_e", "pathname": "/testdata/2017-08"}
        headers_e = { 'X-SIMULATE-AGENTS': 'true' }
        response = requests.post("%s/unfreeze" % self.config["IDA_API"], headers=headers_e, json=data, auth=test_user_e, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "unfreeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        wait_for_pending_actions(self, "test_project_e", test_user_e)
        check_for_failed_actions(self, "test_project_e", test_user_e)

        print("(retrieving frozen file PID lists for project E from IDA and Metax after unfreezing)")
        frozen_file_pids_6 = get_frozen_file_pids(self, 'test_project_e', test_user_e)
        metax_file_pids_6 = get_metax_file_pids(self, 'test_project_e')
        #print("IDA frozen file PIDs 6: %s" % json.dumps(frozen_file_pids_6))
        #print("IDA frozen file PID count 6: %d" % len(frozen_file_pids_6))
        #print("Metax frozen file PIDs 6: %s" % json.dumps(metax_file_pids_6))
        #print("Metax frozen file PID count 6: %d" % len(metax_file_pids_6))
        self.assertEqual(len(frozen_file_pids_6), 56)
        self.assertEqual(len(metax_file_pids_6), 83)

        print("(comparing PID lists for project E in IDA and Metax after unfreezing)")
        frozen_file_pid_diff_5v6, frozen_file_pid_diff_6v5 = array_difference(frozen_file_pids_5, frozen_file_pids_6)
        metax_file_pid_diff_5v6, metax_file_pid_diff_6v5 = array_difference(metax_file_pids_5, metax_file_pids_6)
        #print("IDA frozen file diff 5v6: %s" % json.dumps(frozen_file_pid_diff_5v6))
        #print("IDA frozen file diff 6v5: %s" % json.dumps(frozen_file_pid_diff_6v5))
        #print("Metax frozen file diff 5v6: %s" % json.dumps(metax_file_pid_diff_5v6))
        #print("Metax frozen file diff 6v5: %s" % json.dumps(metax_file_pid_diff_6v5))
        self.assertEqual(len(frozen_file_pid_diff_5v6), 27)
        self.assertEqual(len(frozen_file_pid_diff_6v5), 0)
        self.assertEqual(len(metax_file_pid_diff_5v6), 0)
        self.assertEqual(len(metax_file_pid_diff_6v5), 0)

        print("--- Auditing project E and checking results")
        report_data = self.audit_project("test_project_e", "ERR")
        report_pathname_e = report_data["reportPathname"]
        self.assertTrue(report_data.get('auditStaging'), False)
        self.assertTrue(report_data.get('auditFrozen'), False)
        self.assertTrue(report_data.get('auditChecksums'), False)
        self.assertTrue(report_data.get('auditTimestamps'), False)

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 113)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 113)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 56)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 83)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 27)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 81)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 3)

        print("Verify correct reported errors")
        self.assertEqual(report_data['errors']['Node does not exist in filesystem']['files']['frozen']['node_count'], 27)
        self.assertEqual(report_data['errors']['Node does not exist in Nextcloud']['files']['frozen']['node_count'], 27)
        self.assertEqual(report_data['errors']['Node does not exist in IDA']['files']['frozen']['node_count'], 27)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEqual(len(nodes), report_data['invalidNodeCount'])

        print("Verify correct error reports of select file in Metax missing from filesystem, Nextcloud, and IDA")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/test01.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)
        self.assertTrue("Node does not exist in Nextcloud" in errors)
        self.assertTrue("Node does not exist in IDA" in errors)

        print("--- Repairing project E (with audit error report provided)")

        cmd = "sudo -u %s DEBUG=false %s/utils/admin/repair-project %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_e)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        wait_for_pending_actions(self, "test_project_e", test_user_e)
        check_for_failed_actions(self, "test_project_e", test_user_e)

        print("(retrieving frozen file PID lists for project E from IDA and Metax after repair)")
        frozen_file_pids_4 = get_frozen_file_pids(self, 'test_project_e', test_user_e)
        metax_file_pids_4 = get_metax_file_pids(self, 'test_project_e')
        #print("IDA frozen file PIDs 4: %s" % json.dumps(frozen_file_pids_4))
        #print("IDA frozen file PID count 4: %d" % len(frozen_file_pids_4))
        #print("Metax frozen file PIDs 4: %s" % json.dumps(metax_file_pids_4))
        #print("Metax frozen file PID count 4: %d" % len(metax_file_pids_4))
        self.assertEqual(len(frozen_file_pids_4), 56)
        self.assertEqual(len(metax_file_pids_4), 56)

        print("(comparing PID lists for project E in IDA and Metax after repair)")
        frozen_file_pid_diff_3v4, frozen_file_pid_diff_4v3 = array_difference(frozen_file_pids_3, frozen_file_pids_4)
        metax_file_pid_diff_3v4, metax_file_pid_diff_4v3 = array_difference(metax_file_pids_3, metax_file_pids_4)
        #print("IDA frozen file diff 3v4: %s" % json.dumps(frozen_file_pid_diff_3v4))
        #print("IDA frozen file diff 4v3: %s" % json.dumps(frozen_file_pid_diff_4v3))
        #print("Metax frozen file diff 3v4: %s" % json.dumps(metax_file_pid_diff_3v4))
        #print("Metax frozen file diff 4v3: %s" % json.dumps(metax_file_pid_diff_4v3))
        self.assertEqual(len(frozen_file_pid_diff_3v4), 0)
        self.assertEqual(len(frozen_file_pid_diff_4v3), 0)
        self.assertEqual(len(metax_file_pid_diff_3v4), 27)
        self.assertEqual(len(metax_file_pid_diff_4v3), 0)

        print("--- Auditing project E and checking results")
        self.audit_project("test_project_e", "OK")

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
