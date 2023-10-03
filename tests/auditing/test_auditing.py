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
from datetime import datetime
from tests.common.utils import load_configuration, generate_timestamp


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

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts" % (self.config["HTTPD_USER"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        time.sleep(1)
        self.config['INITIALIZED'] = generate_timestamp()
        print("INITIALIZED: %s" % self.config['INITIALIZED'])
        time.sleep(1)


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success:
            print("(cleaning)")
            cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts --flush" % (self.config["HTTPD_USER"], self.config["ROOT"])
            result = os.system(cmd)
            self.assertEqual(result, 0)

            # delete all test project related audit reports, so they don't build up
            cmd = "rm -f %s/audits/*_test_project_[a-e].*" % self.config["LOG_ROOT"]
            result = os.system(cmd)
            self.assertEqual(result, 0)

            if self.config["METAX_AVAILABLE"] != 1:
                print('')
                print("***********************************")
                print("*** METAX AUDITING NOT TESTED!! ***")
                print("***********************************")
                print('')


    def wait_for_pending_actions(self, project, user):
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


    def check_for_failed_actions(self, project, user):
        print("(verifying no failed actions)")
        response = requests.get("%s/actions?project=%s&status=failed" % (self.config["IDA_API_ROOT_URL"], project), auth=user, verify=False)
        self.assertEqual(response.status_code, 200)
        actions = response.json()
        assert(len(actions) == 0)


    def remove_report(self, pathname):
        try:
            os.remove(pathname)
        except:
            pass


    def audit_project(self, project, status, since = None, area = None, check_timestamps = True):
        """
        Audit the specified project, verify that the audit report file was created with
        the specified status, and load and return the audit report as a JSON object, with
        the audit report pathname defined in the returned object for later timestamp
        repair if/as needed.
        """

        parameters = ""

        if since:
            parameters = "%s --changed-since %s" % (parameters, since)

        if area:
            parameters = "%s --%s" % (parameters, area)
            area = " %s" % area

        if check_timestamps:
            parameters = "%s --timestamps" % parameters

        #parameters = "%s --report" % parameters # TEMP DEBUG

        print ("(auditing project %s%s)" % (project, parameters))

        cmd = "sudo -u %s %s/utils/admin/audit-project %s %s" % (self.config["HTTPD_USER"], self.config["ROOT"], project, parameters)

        try:
            output = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
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

        """
        Overview:

        1. Test projects and user accounts will be created and initialized as usual, and a
           timestamp INITIALIZED will be created after initialization.

        2. The following actions and modifications will be made to specific test projects, and
           a second timestamp MODIFIED will be created after modifications:

        a. Project A will have a folder frozen, and will have files both added and deleted from both
           the frozen space and staging area in the filesystem only, covering errors where Nextcloud and
           the filesystem disagree on the existence of files and folders, and the number of nodes.

        b. Project B will have a folder frozen, and will have files both changed in size and touched
           with new modification timestamps in the filesystem, covering errors where Nextcloud and the
           filesystem disagree about size and modification timestamps of files.

        c. Project C will have a folder frozen, and will have files replaced by folders and folders
           replaced by files in both the frozen and staging areas of the filesystem, preserving the
           same exact pathnames, covering errors where Nextcloud and the filesystem disagree about
           the type of nodes.

        d. Project D will have a folder frozen, and will have changes to files in IDA, Metax, and
           replication, removing a file from IDA, removing a file from Metax, removing a file
           from replication, and changing file details for a file in IDA such that it disagrees
           with both Metax and replication.

        e. Project E will have no modifications of any kind, and therefore should not have any errors
           reported of any kind.

        3. Active project listings will be tested with the following variations:

        a. An active project listing will be generated with the START timestamp and the script output
           to include all projects A, B, C, D and E.

        b. An active project listing will be generated with the INITIALIZED timestamp and the script output
           verified to include the projects A, B, C, and D but not E.

        c. An active project listing will be generated with the MODIFIED timestamp and the script output
           verified to include none of the projects A, B, C, D or E.

        4. All projects A, B, C, D, and E will be audited with the following variations and results
           checked for correctness, that the report files exist and have the correct status, that all
           expected errors are reported correctly, and no other errors are reported, and that project E
           has no errors reported for any variation.
        
        a. Projects will be audited with the --timestamps parameter and no restrictions (exhaustive audit).

        b. Projects will be audited with --staging --timestamps parameters, limiting checks to files
           in the staging area.

        c. Projects will be audited with --frozen --timestamps parameters, limiting checks to files
           in the frozen area.

        d. Projects will be audited with --changed-since START --timestamps, limiting checks to files
           uploaded or frozen since the START timestamp, and their ancestor folders.

        e. Projects will be audited with --changed-since INITIALIZED --timestamps, limiting checks to files
           uploaded or frozen since the INITIALIZED timestamp, and their ancestor folders.

        f. Projects will be audited with --changed-since MODIFIED --timestamps, limiting checks to files
           uploaded or frozen since the MODIFIED timestamp, and their ancestor folders, verifying no errors
           reported for any projects.

        5. Projects A, B, C, and D will be fully repaired and then re-audited with the --timestamps parameter
           and no restrictions (exhaustive audit), and results checked to ensure correct node counts and verifying
           no errors reported for any projects.

        Note: no testing of the emailing functionality will be done, only the correctness of the
        auditing process and reported results.
        """

        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
        test_user_b = ("test_user_b", self.config["TEST_USER_PASS"])
        test_user_c = ("test_user_c", self.config["TEST_USER_PASS"])
        test_user_d = ("test_user_d", self.config["TEST_USER_PASS"])

        metax_user = (self.config["METAX_API_USER"], self.config["METAX_API_PASS"])

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

        print("--- Modifying state of test project A")

        print("(freezing folder /testdata/2017-08/Experiment_1/baseline in project A)")
        data = {"project": "test_project_a", "pathname": "/testdata/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], headers=headers, json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.wait_for_pending_actions("test_project_a", test_user_a)
        self.check_for_failed_actions("test_project_a", test_user_a)

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

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project B")

        print("(freezing folder /testdata/2017-08/Experiment_1/baseline in project B)")
        data = {"project": "test_project_b", "pathname": "/testdata/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], headers=headers, json=data, auth=test_user_b, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.wait_for_pending_actions("test_project_b", test_user_b)
        self.check_for_failed_actions("test_project_b", test_user_b)

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
        # 1500000000 = "2017-07-14T02:40:00Z"
        pathname = "files/test_project_b/testdata/2017-08/Experiment_1/baseline/test04.dat"
        cur.execute("UPDATE %sfilecache SET mtime = %d WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], 1500000000, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node modification timestamp")

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project C")

        print("(freezing folder /testdata/2017-08/Experiment_1/baseline in project C)")
        data = {"project": "test_project_c", "pathname": "/testdata/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], headers=headers, json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.wait_for_pending_actions("test_project_c", test_user_c)
        self.check_for_failed_actions("test_project_c", test_user_c)

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

        # After repair the node type in Nextcloud will be changed to folder, since that is what is on disk
        print("(replacing file /testdata/2017-10/Experiment_3/baseline/test03.dat from staging area of filesystem with same-named folder)")
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

        # After repair the node type in Nextcloud will be changed to folder, since that is what is on disk
        print("(replacing folder /testdata/empty_folder from staging area of filesystem with same-named file)")
        # Delete folder /testdata/empty_folder from staging area
        pathname = "%s/testdata/empty_folder" % staging_area_root_c
        path = Path(pathname)
        try:
            shutil.rmtree(pathname)
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())
        # Copy file /testdata/License.txt in staging area as file /testdata/empty_folder in staging area
        pathname2 = "%s/testdata/License.txt" % staging_area_root_c
        try:
            shutil.copyfile(pathname2, pathname)
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to copy file %s as file %s: %s" % (pathname2, pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project D")

        print("(freezing folder /testdata/2017-08/Experiment_1/baseline in project D)")
        data = {"project": "test_project_d", "pathname": "/testdata/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], headers=headers, json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.wait_for_pending_actions("test_project_d", test_user_d)
        self.check_for_failed_actions("test_project_d", test_user_d)

        # After repair there will be one additional node (folder) due to the existence of the 'baseline' directory
        # in both frozen area and staging compared to before freezing the 'baseline' folder and unfreezing test01.dat
        print("(unfreezing file /testdata/2017-08/Experiment_1/baseline/test01.dat only in IDA, simulating postprocessing agents)")
        data = {"project": "test_project_d", "pathname": "/testdata/2017-08/Experiment_1/baseline/test01.dat"}
        headers_d = { 'X-SIMULATE-AGENTS': 'true' }
        response = requests.post("%s/unfreeze" % self.config["IDA_API_ROOT_URL"], headers=headers_d, json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "unfreeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.wait_for_pending_actions("test_project_d", test_user_d)
        self.check_for_failed_actions("test_project_d", test_user_d)

        print("(deleting file /testdata/2017-08/Experiment_1/baseline/test02.dat from Metax)")
        data = {"project": "test_project_d", "pathname": "/testdata/2017-08/Experiment_1/baseline/test02.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API_ROOT_URL"], data["project"]), json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        pid = file_data["pid"]
        if self.config["METAX_API_VERSION"] >= 3:
            data = [{ "storage_service": "ida", "storage_identifier": pid }]
            # TODO: add bearer token header when supported
            response = requests.post("%s/files/delete-many" % self.config["METAX_API_ROOT_URL"], json=data, verify=False)
        else:
            response = requests.delete("%s/files/%s" % (self.config["METAX_API_ROOT_URL"], pid), auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200)

        pathname = "/testdata/2017-08/Experiment_1/baseline/test03.dat"

        print("(retrieving pid of file %s in IDA db)")
        cur.execute("SELECT pid FROM %sida_frozen_file WHERE project = 'test_project_d' AND pathname = '%s'" % (self.config["DBTABLEPREFIX"], pathname))
        rows = cur.fetchall()
        if len(rows) != 1:
            self.fail("Failed to retrieve pid for frozen file")
        # The following are used below to restore the original frozen file pid after temporarily changing it before auditing tests
        original_frozen_file_pid = rows[0][0]
        original_frozen_file_pathname = pathname

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
        original_frozen_file_pathname = pathname # used below to restore original pid
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

        # --------------------------------------------------------------------------------

        # Ensure auditing tests start at least one second after file modifications
        # (sometimes on very fast hardware, the auditing begins in less than one
        # second after the modifications to the projects, resulting in those final
        # file and folder modifications from being excluded from the audit due
        # to the START timestamp cutoff)

        time.sleep(1)
        self.config['MODIFIED'] = generate_timestamp()
        print("MODIFIED: %s" % self.config['MODIFIED'])
        time.sleep(1)

        # --------------------------------------------------------------------------------

        print("--- Checking detection of active projects")

        print("(retrieving list of active projects since initialization)")
        cmd = "sudo -u %s %s/utils/admin/list-active-projects %s" % (
            self.config["HTTPD_USER"],
            self.config["ROOT"],
            self.config["START"]
        )
        try:
            output = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding)
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
        cmd = "sudo -u %s %s/utils/admin/list-active-projects %s" % (
            self.config["HTTPD_USER"],
            self.config["ROOT"],
            self.config["INITIALIZED"]
        )
        try:
            output = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding)
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
        cmd = "sudo -u %s %s/utils/admin/list-active-projects %s" % (
            self.config["HTTPD_USER"],
            self.config["ROOT"],
            self.config["MODIFIED"]
        )
        try:
            output = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding)
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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 97)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 109)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 93)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 98)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 4)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 11)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 95)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 109)

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

        report_pathname_b = report_data["reportPathname"]

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 109)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 109)

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

        print("Verify correct error report of Nextcloud modification timestamp conflict with filesystem")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test04.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node modification timestamp different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud")
        self.assertIsNotNone(nextcloud)
        self.assertEqual(nextcloud.get("type"), "file")
        self.assertEqual(nextcloud.get("modified"), "2017-07-14T02:40:00Z")

        print("--- Auditing staging area of project B and checking results")

        report_data = self.audit_project("test_project_b", "OK", area="staging")

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 98)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 98)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 11)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 11)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 109)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 109)

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

        report_pathname_c = report_data["reportPathname"]

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 109)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 109)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 3)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 5)

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

        # Verify all three invalid node error messages...

        print("Verify correct error report of Nextcloud file type conflict with filesystem folder")
        node = nodes.get("frozen/testdata/2017-08/Experiment_1/baseline/test01.dat")
        self.assertIsNotNone(node)
        errors = node.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud")
        self.assertIsNotNone(nextcloud)
        self.assertEqual(nextcloud.get("type"), "file")
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
        filesystem = node.get("filesystem")
        self.assertIsNotNone(filesystem)
        self.assertEqual(filesystem.get("type"), "folder")

        print("Verify correct error report of Nextcloud folder type conflict with filesystem file")
        node = nodes.get("staging/testdata/empty_folder")
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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 98)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 98)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 0)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 2)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 2)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 1)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify all reported invalid nodes are in staging area")
        self.assertFalse(any(map(lambda key: key.startswith('frozen/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing frozen area of project C and checking results")

        report_data = self.audit_project("test_project_c", "ERR", area="frozen")

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 11)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 11)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 109)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 109)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 6)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 3)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 5)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 3)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project C after initialization and checking results")

        report_data = self.audit_project("test_project_c", "ERR", since=self.config['INITIALIZED'])

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

        report_pathname_d = report_data["reportPathname"]

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 110)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 110)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 5)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 6)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 17)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 16)

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

        print("Verify correct error report of IDA file checksum conflict with Metax")
        self.assertTrue("Node checksum different for IDA and Metax" in errors)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 100)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 100)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 10)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 10)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 5)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 6)

        print("Verify correct number of reported node errors")
        self.assertEqual(report_data.get("errorNodeCount"), 17)

        print("Verify correct number of reported errors")
        self.assertEqual(report_data.get("errorCount"), 16)

        print("Verify correct oldest and newest dates")
        self.assertIsNotNone(report_data.get("oldest"))
        self.assertIsNotNone(report_data.get("newest"))

        print("Verify all reported invalid nodes are in frozen area")
        self.assertFalse(any(map(lambda key: key.startswith('staging/'), report_data['invalidNodes'].keys())))

        self.remove_report(report_data['reportPathname'])

        print("--- Auditing changes in project D after start of tests and checking results")

        report_data = self.audit_project("test_project_d", "ERR", since=self.config['START'])

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 110)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 110)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 107)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 107)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 105)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 105)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 2)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 2)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 107)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 107)

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

        print("(repairing project A)")
        cmd = "sudo -u %s %s/utils/admin/repair-project test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.wait_for_pending_actions("test_project_a", test_user_a)
        self.check_for_failed_actions("test_project_a", test_user_a)

        cmd = "sudo -u %s %s/utils/admin/repair-timestamps %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_a)
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        print("(repairing project B)")
        cmd = "sudo -u %s %s/utils/admin/repair-project test_project_b" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.wait_for_pending_actions("test_project_b", test_user_b)
        self.check_for_failed_actions("test_project_b", test_user_b)

        cmd = "sudo -u %s %s/utils/admin/repair-timestamps %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_b)
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        print("(repairing project C)")
        cmd = "sudo -u %s %s/utils/admin/repair-project test_project_c" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.wait_for_pending_actions("test_project_c", test_user_c)
        self.check_for_failed_actions("test_project_c", test_user_c)

        cmd = "sudo -u %s %s/utils/admin/repair-timestamps %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_c)
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        print("(repairing project D)")

        # The repair process doesn't resolve a mismatch of node types (file vs folder) in replication,
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
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())

        # The repair process doesn't properly resolve a frozen file pid mismatch between IDA and Metax, even
        # though the audit process will report the issue if it ever occurs in reality (which it likely never
        # will), so to ensure the repair process and post repair auditing succeed for these tests, we will
        # repair the pid mismatch that was created for the auditing tests prior to proceeding...

        cur.execute("UPDATE %sida_frozen_file SET pid = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], original_frozen_file_pid, original_frozen_file_pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file pid")

        cmd = "sudo -u %s %s/utils/admin/repair-project test_project_d" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.wait_for_pending_actions("test_project_d", test_user_d)
        self.check_for_failed_actions("test_project_d", test_user_d)

        cmd = "sudo -u %s %s/utils/admin/repair-timestamps %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_d)
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.remove_report(report_pathname_a)
        self.remove_report(report_pathname_b)
        self.remove_report(report_pathname_c)
        self.remove_report(report_pathname_d)

        print("--- Re-auditing project A and checking results")

        report_data = self.audit_project("test_project_a", "OK")

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 97)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 97)

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

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 109)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 109)

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

        report_data = self.audit_project("test_project_c", "OK")

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 109)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 109)

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

        self.remove_report(report_data['reportPathname'])

        print("--- Re-auditing project D and checking results")

        # Because we change the pid and timestamps of one file prior to the previous
        # repair, we still will get that file reported with timestamp discrepancies
        # because the timestamp repair would be unable to fix the timstamps in IDA
        # and Metax due to the wrong pid. So we need to actually expect one invalid
        # node in the next audit, then repair timestamps based on the new audit error
        # report and thereafter should get no errors reported for project D.

        report_data = self.audit_project("test_project_d", "ERR")

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 110)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 110)

        print("Verify correct number of reported IDA frozen files")
        self.assertEqual(report_data.get("frozenFileCount"), 5)

        print("Verify correct number of reported Metax files")
        self.assertEqual(report_data.get("metaxFileCount"), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEqual(report_data.get("invalidNodeCount"), 1)

        report_pathname_d = report_data["reportPathname"]

        cmd = "sudo -u %s %s/utils/admin/repair-timestamps %s" % (self.config["HTTPD_USER"], self.config["ROOT"], report_pathname_d)
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.remove_report(report_pathname_d)

        report_data = self.audit_project("test_project_d", "OK")

        print("Verify correct number of reported filesystem nodes")
        self.assertEqual(report_data.get("filesystemNodeCount"), 110)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEqual(report_data.get("nextcloudNodeCount"), 110)

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

        self.remove_report(report_data['reportPathname'])

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
