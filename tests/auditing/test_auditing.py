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

class TestAuditing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("=== tests/auditing/test_auditing")

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


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success:
            print("(cleaning)")
            cmd = "sudo -u %s %s/tests/utils/initialize_test_accounts flush" % (self.config["HTTPD_USER"], self.config["ROOT"])
            result = os.system(cmd)
            self.assertEquals(result, 0)

            # delete all test project related audit reports, so they don't build up
            cmd = "rm -f %s/audits/*_test_project_[a-e].*" % self.config["LOG_ROOT"]
            result = os.system(cmd)
            self.assertEquals(result, 0)

            if self.config["METAX_AVAILABLE"] != 1:
                print('')
                print("***********************************")
                print("*** METAX AUDITING NOT TESTED!! ***")
                print("***********************************")
                print('')


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


    def auditProject(self, project, suffix):
        """
        Audit the specified project, verify that the audit report log was created with
        the specified suffix, and load and return the audit report as a JSON object.
        """

        print ("(auditing project %s)" % project)
        cmd = "sudo -u %s %s/utils/admin/audit-project %s | \
               grep '\"start\":' | head -1 | \
               sed -e 's/^[^\"]*\"start\": *\"//' | \
               sed -e 's/\".*$//'" % (self.config["HTTPD_USER"], self.config["ROOT"], project)
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertNotEqual(start, None, start)
        self.assertNotEqual(start, "", start)

        print("Verify audit report exists and has the correct suffix")
        report_pathname = "%s/audits/%s_%s.%s" % (self.config["LOG_ROOT"], start, project, suffix)
        path = Path(report_pathname)
        self.assertTrue(path.exists(), report_pathname)
        self.assertTrue(path.is_file(), report_pathname)

        print("(loading audit report)")
        try:
            report_data = json.load(open(report_pathname))
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertEquals(report_data.get("project", None), project)
        self.assertEquals(report_data.get("start", None), start)

        return report_data


    def repairProject(self, project):
        """
        Repair the specified project.
        """

        print ("(repairing project %s)" % project)

        print("Verify repair was successful")
        report_pathname = "%s/audits/%s_%s.%s" % (self.config["LOG_ROOT"], start, project, suffix)
        path = Path(report_pathname)
        self.assertTrue(path.exists(), report_pathname)
        self.assertTrue(path.is_file(), report_pathname)

        print("(loading audit report)")
        try:
            report_data = json.load(open(report_pathname))
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))
        self.assertEquals(report_data.get("project", None), project)
        self.assertEquals(report_data.get("start", None), start)

        return report_data



    def test_auditing(self):

        """
        Overview:

        1. The test projects and user accounts will be created and initialized as usual.

        2. The following actions and modifications will be made to specific test projects:

        a. Project A will have a folder frozen, and will have files both added and deleted from both
           the frozen space and staging area in the filesystem only, such that the staging area also
           contains more files on disk than the frozen area, covering errors where Nextcloud and the
           filesystem disagree on the existence of files and folders, and the number of nodes.

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

        e. Project E will have no modifications of any kind, and therefore should not have any log
           entries, and the audit will be expected to find no errors of any kind..

        3. The script list-active-projects will be run and the script output verified to include the
           three projects A, B, C, and D but not E.
            
        4. The script audit-project will be run on all of the projects A, B, C, D, and E and the
           audit report logs checked for correctness, that they exist and have the correct suffix,
           and that all expected errors are reported correctly and no other errors are reported.
           
        Note: no testing of the emailing functionality will be done, only the correctness of the 
        auditing process and reported results.
        """

        admin_user = (self.config["NC_ADMIN_USER"], self.config["NC_ADMIN_PASS"])

        pso_user_a = (self.config["PROJECT_USER_PREFIX"] + "test_project_a", self.config["PROJECT_USER_PASS"])
        pso_user_b = (self.config["PROJECT_USER_PREFIX"] + "test_project_b", self.config["PROJECT_USER_PASS"])
        pso_user_c = (self.config["PROJECT_USER_PREFIX"] + "test_project_c", self.config["PROJECT_USER_PASS"])
        pso_user_d = (self.config["PROJECT_USER_PREFIX"] + "test_project_d", self.config["PROJECT_USER_PASS"])
        pso_user_e = (self.config["PROJECT_USER_PREFIX"] + "test_project_e", self.config["PROJECT_USER_PASS"])

        test_user_a = ("test_user_a", self.config["TEST_USER_PASS"])
        test_user_b = ("test_user_b", self.config["TEST_USER_PASS"])
        test_user_c = ("test_user_c", self.config["TEST_USER_PASS"])
        test_user_d = ("test_user_d", self.config["TEST_USER_PASS"])
        test_user_e = ("test_user_e", self.config["TEST_USER_PASS"])
        test_user_x = ("test_user_x", self.config["TEST_USER_PASS"])

        metax_user = (self.config["METAX_API_USER"], self.config["METAX_API_PASS"])

        frozen_area_root_a = "%s/PSO_test_project_a/files/test_project_a" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_a = "%s/PSO_test_project_a/files/test_project_a%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        frozen_area_root_b = "%s/PSO_test_project_b/files/test_project_b" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_b = "%s/PSO_test_project_b/files/test_project_b%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        frozen_area_root_c = "%s/PSO_test_project_c/files/test_project_c" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_c = "%s/PSO_test_project_c/files/test_project_c%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        frozen_area_root_d = "%s/PSO_test_project_d/files/test_project_d" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_d = "%s/PSO_test_project_d/files/test_project_d%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        frozen_area_root_e = "%s/PSO_test_project_e/files/test_project_e" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_e = "%s/PSO_test_project_e/files/test_project_e%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        # If Metax is available, disable simulation of agents, no matter what might be defined in configuration
        if self.config["METAX_AVAILABLE"] == 1:
            headers = { 'X-SIMULATE-AGENTS': 'false' }
        else:
            headers = { 'X-SIMULATE-AGENTS': 'true' }

        # --------------------------------------------------------------------------------

        # Get current time, for SINCE, before making explicit modifications to test projects
        self.config["SINCE"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # Ensure that all modification timestamps are at least one second later than SINCE 
        time.sleep(1)

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

        print("(freezing folder /2017-08/Experiment_1/baseline in project A)")
        data = {"project": "test_project_a", "pathname": "/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], headers=headers, json=data, auth=test_user_a, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("(deleting folder /2017-08/Experiment_1/baseline from frozen area of filesystem)")
        pathname = "%s/2017-08/Experiment_1/baseline" % frozen_area_root_a
        path = Path(pathname)
        try:
            shutil.rmtree(pathname)
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())

        print("(deleting folder /2017-08/Experiment_3/baseline from staging area of filesystem)")
        pathname = "%s/2017-10/Experiment_3/baseline" % staging_area_root_a
        path = Path(pathname)
        try:
            shutil.rmtree(pathname)
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())

        print("(creating zero sized ghost file /2017-08/Experiment_1/baseline/test01.dat in staging area of filesystem)")
        # Create subfolder /2017-08/Experiment_1/baseline in staging area
        pathname = "%s/2017-08/Experiment_1/baseline" % staging_area_root_a
        path = Path(pathname)
        try:
            path.mkdir()
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to create folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())
        # Create zero sized ghost file in staging area of frozen file /2017-08/Experiment_1/baseline/test01.dat
        pathname = "%s/2017-08/Experiment_1/baseline/test01.dat" % staging_area_root_a
        path = Path(pathname)
        try:
            shutil.copyfile("/dev/null", pathname)
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to create empty file %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())
        self.assertEquals(0, path.stat().st_size)

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project B")

        print("(freezing folder /2017-08/Experiment_1/baseline in project B)")
        data = {"project": "test_project_b", "pathname": "/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], headers=headers, json=data, auth=test_user_b, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_b", test_user_b)
        self.checkForFailedActions("test_project_b", test_user_b)

        # retrieve PSO storage id for test_project_b
        cur.execute("SELECT numeric_id from %sstorages WHERE id = 'home::%stest_project_b' LIMIT 1"
                    % (self.config["DBTABLEPREFIX"], self.config["PROJECT_USER_PREFIX"]))
        rows = cur.fetchall()
        if len(rows) != 1:
            self.fail("Failed to retrieve storage id for test_project_b")
        storage_id_b = rows[0][0]

        print("(changing size of Nextcloud file node /2017-08/Experiment_1/baseline/test01.dat in frozen area)")
        pathname = "files/test_project_b/2017-08/Experiment_1/baseline/test01.dat"
        cur.execute("UPDATE %sfilecache SET size = %d WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], 123, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node size")

        print("(changing modified timestamp of Nextcloud file node /2010-10/Experiment_3/baseline/test03.dat in staging area)")
        # 1500000000 = "2017-07-14T02:40:00Z"
        pathname = "files/test_project_b%s/2017-10/Experiment_3/baseline/test03.dat" % self.config["STAGING_FOLDER_SUFFIX"]
        cur.execute("UPDATE %sfilecache SET mtime = %d WHERE storage = %d AND path = '%s'"
                    % (self.config["DBTABLEPREFIX"], 1500000000, storage_id_b, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update Nextcloud file node modification timestamp")

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project C")

        print("(freezing folder /2017-08/Experiment_1/baseline in project C)")
        data = {"project": "test_project_c", "pathname": "/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], headers=headers, json=data, auth=test_user_c, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_c", test_user_c)
        self.checkForFailedActions("test_project_c", test_user_c)

        print("(replacing file /2017-08/Experiment_1/baseline/test01.dat from frozen area of filesystem with same-named folder)")
        # Delete file /2017-08/Experiment_1/baseline/test01.dat from frozen area
        pathname = "%s/2017-08/Experiment_1/baseline/test01.dat" % frozen_area_root_c
        path = Path(pathname)
        try:
            os.remove(pathname)
        except Exception as error:
            self.fail("Failed to delete file %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())
        # Create folder /2017-08/Experiment_1/baseline/test01.dat in frozen area
        try:
            path.mkdir()
        except Exception as error:
            self.fail("Failed to create folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())

        print("(replacing file /2017-10/Experiment_3/baseline/test03.dat from staging area of filesystem with same-named folder)")
        # Delete file /2017-10/Experiment_3/baseline/test03.dat from staging area
        pathname = "%s/2017-10/Experiment_3/baseline/test03.dat" % staging_area_root_c
        path = Path(pathname)
        try:
            os.remove(pathname)
        except Exception as error:
            self.fail("Failed to delete file %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())
        # Create folder /2017-10/Experiment_3/baseline/test03.dat in staging area
        try:
            path.mkdir()
        except Exception as error:
            self.fail("Failed to create folder %s: %s" % (pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())

        print("(replacing folder /empty_folder from staging area of filesystem with same-named file)")
        # Delete folder /empty_folder from staging area
        pathname = "%s/empty_folder" % staging_area_root_c
        path = Path(pathname)
        try:
            shutil.rmtree(pathname)
        except Exception as error:
            self.fail("Failed to delete folder %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())
        # Copy file /License.txt in staging area as file /empty_folder in staging area
        pathname2 = "%s/License.txt" % staging_area_root_c
        try:
            shutil.copyfile(pathname2, pathname)
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to copy file %s as file %s: %s" % (pathname2, pathname, str(error)))
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())

        # --------------------------------------------------------------------------------

        print("--- Modifying state of test project D")

        print("(freezing folder /2017-08/Experiment_1/baseline in project D)")
        data = {"project": "test_project_d", "pathname": "/2017-08/Experiment_1/baseline"}
        response = requests.post("%s/freeze" % self.config["IDA_API_ROOT_URL"], headers=headers, json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "freeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_d", test_user_d)
        self.checkForFailedActions("test_project_d", test_user_d)

        print("(unfreezing file /2017-08/Experiment_1/baseline/test01.dat only in IDA, simulating postprocessing agents)")
        data = {"project": "test_project_d", "pathname": "/2017-08/Experiment_1/baseline/test01.dat"}
        headers_d = { 'X-SIMULATE-AGENTS': 'true' }
        response = requests.post("%s/unfreeze" % self.config["IDA_API_ROOT_URL"], headers=headers_d, json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        action_data = response.json()
        self.assertEqual(action_data["action"], "unfreeze")
        self.assertEqual(action_data["project"], data["project"])
        self.assertEqual(action_data["pathname"], data["pathname"])

        self.waitForPendingActions("test_project_d", test_user_d)
        self.checkForFailedActions("test_project_d", test_user_d)

        print("(deleting file /2017-08/Experiment_1/baseline/test02.dat from Metax)")
        data = {"project": "test_project_d", "pathname": "/2017-08/Experiment_1/baseline/test02.dat"}
        response = requests.get("%s/files/byProjectPathname/%s" % (self.config["IDA_API_ROOT_URL"], data["project"]), json=data, auth=test_user_d, verify=False)
        self.assertEqual(response.status_code, 200)
        file_data = response.json()
        pid = file_data["pid"]
        response = requests.delete("%s/files/%s" % (self.config["METAX_API_ROOT_URL"], pid), auth=metax_user, verify=False)
        self.assertEqual(response.status_code, 200)

        print("(changing size of file /2017-08/Experiment_1/baseline/test03.dat in IDA db)")
        pathname = "/2017-08/Experiment_1/baseline/test03.dat"
        cur.execute("UPDATE %sida_frozen_file SET size = %d WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], 123, pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file size")

        print("(changing checksum of file /2017-08/Experiment_1/baseline/test03.dat in IDA db)")
        pathname = "/2017-08/Experiment_1/baseline/test03.dat"
        cur.execute("UPDATE %sida_frozen_file SET checksum = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], "a0b0c0", pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file checksum")

        print("(changing pid of file /2017-08/Experiment_1/baseline/test03.dat in IDA db)")
        pathname = "/2017-08/Experiment_1/baseline/test03.dat"
        cur.execute("UPDATE %sida_frozen_file SET pid = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], "abc123", pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file pid")

        print("(changing frozen timestamp of file /2017-08/Experiment_1/baseline/test03.dat in IDA db)")
        pathname = "/2017-08/Experiment_1/baseline/test03.dat"
        cur.execute("UPDATE %sida_frozen_file SET frozen = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], '2017-01-01T00:00:00Z', pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file frozen timestamp")

        print("(changing modification timestamp of file /2017-08/Experiment_1/baseline/test03.dat in IDA db)")
        pathname = "/2017-08/Experiment_1/baseline/test03.dat"
        cur.execute("UPDATE %sida_frozen_file SET modified = '%s' WHERE project = 'test_project_d' AND pathname = '%s'"
                    % (self.config["DBTABLEPREFIX"], '2017-01-01T00:00:00Z', pathname))
        conn.commit()
        self.assertEqual(cur.rowcount, 1, "Failed to update IDA file modification timestamp")

        print("(deleting file /2017-08/Experiment_1/baseline/test04.dat from replication)")
        pathname = "%s/projects/test_project_d/2017-08/Experiment_1/baseline/test04.dat" % self.config['DATA_REPLICATION_ROOT']
        try:
            os.remove(pathname)
        except Exception as error:
            self.fail("Failed to delete file %s: %s" % (pathname, str(error)))
        path = Path(pathname)
        self.assertFalse(path.exists())

        print("(changing size of file /2017-08/Experiment_1/baseline/test05.dat in replication)")
        pathname = "%s/projects/test_project_d/2017-08/Experiment_1/baseline/test05.dat" % self.config['DATA_REPLICATION_ROOT']
        try:
            shutil.copyfile("/dev/null", pathname)
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to change size of file %s: %s" % (pathname, str(error)))
        path = Path(pathname)
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())

        print("(swapping file for folder in replication)")

        # Delete file /2017-08/Experiment_1/baseline/zero_size_file from replication
        pathname = "%s/projects/test_project_d/2017-08/Experiment_1/baseline/zero_size_file" % self.config['DATA_REPLICATION_ROOT']
        path = Path(pathname)
        try:
            os.remove(pathname)
        except Exception as error:
            self.fail("Failed to delete file %s: %s" % (pathname, str(error)))
        self.assertFalse(path.exists())

        # Create folder /2017-08/Experiment_1/baseline/zero_size_file in replication
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

        # --------------------------------------------------------------------------------

        print("--- Checking detection of active projects")

        print("(retrieving list of active projects)")
        cmd = "sudo -u %s %s/utils/admin/list-active-projects %s" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["SINCE"])
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
        
        # --------------------------------------------------------------------------------

        print("--- Auditing project A and checking results")

        report_data = self.auditProject("test_project_a", "err")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 94)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 106)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 6)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 16)
        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEquals(len(nodes), report_data['invalidNodeCount'])

        # Verify select invalid node error messages for each type of error...

        print("Verify correct error report of Nextcloud folder missing from filesystem")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)
        node = nodes.get("staging/2017-10/Experiment_3/baseline", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)

        print("Verify correct error report of Nextcloud file missing from filesystem")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/test01.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)
        node = nodes.get("staging/2017-10/Experiment_3/baseline/test03.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in filesystem" in errors)

        print("Verify correct error report of filesystem file missing from Nextcloud")
        node = nodes.get("staging/2017-08/Experiment_1/baseline/test01.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in Nextcloud" in errors)

        # --------------------------------------------------------------------------------

        print("--- Auditing project B and checking results")

        report_data = self.auditProject("test_project_b", "err")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 106)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 106)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 6)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 2)
        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEquals(len(nodes), report_data['invalidNodeCount'])

        # Verify both invalid node error messages...

        print("Verify correct error report of Nextcloud file size conflict with filesystem")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/test01.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node size different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud", None)
        self.assertIsNotNone(nextcloud)
        self.assertEquals(nextcloud.get("type", None), "file")
        self.assertEquals(nextcloud.get("size", None), 123)

        print("Verify correct error report of Nextcloud modification timestamp conflict with filesystem")
        node = nodes.get("staging/2017-10/Experiment_3/baseline/test03.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node modification timestamp different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud", None)
        self.assertIsNotNone(nextcloud)
        self.assertEquals(nextcloud.get("type", None), "file")
        self.assertEquals(nextcloud.get("modified", None), "2017-07-14T02:40:00Z")

        # --------------------------------------------------------------------------------

        print("--- Auditing project C and checking results")

        report_data = self.auditProject("test_project_c", "err")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 106)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 106)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 6)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 6)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 3)
        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEquals(len(nodes), report_data['invalidNodeCount'])

        # Verify all three invalid node error messages...

        print("Verify correct error report of Nextcloud file type conflict with filesystem folder")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/test01.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud", None)
        self.assertIsNotNone(nextcloud)
        self.assertEquals(nextcloud.get("type", None), "file")
        filesystem = node.get("filesystem", None)
        self.assertIsNotNone(filesystem)
        self.assertEquals(filesystem.get("type", None), "folder")

        node = nodes.get("staging/2017-10/Experiment_3/baseline/test03.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud", None)
        self.assertIsNotNone(nextcloud)
        self.assertEquals(nextcloud.get("type", None), "file")
        filesystem = node.get("filesystem", None)
        self.assertIsNotNone(filesystem)
        self.assertEquals(filesystem.get("type", None), "folder")

        print("Verify correct error report of Nextcloud folder type conflict with filesystem file")
        node = nodes.get("staging/empty_folder", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for filesystem and Nextcloud" in errors)
        nextcloud = node.get("nextcloud", None)
        self.assertIsNotNone(nextcloud)
        self.assertEquals(nextcloud.get("type", None), "folder")
        filesystem = node.get("filesystem", None)
        self.assertIsNotNone(filesystem)
        self.assertEquals(filesystem.get("type", None), "file")

        # --------------------------------------------------------------------------------

        print("--- Auditing project D and checking results")
        
        report_data = self.auditProject("test_project_d", "err")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 107)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 107)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 5)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 5)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 6)
        try:
            nodes = report_data["invalidNodes"]
        except Exception as error:
            self.fail(str(error))
        self.assertEquals(len(nodes), report_data['invalidNodeCount'])

        # Verify all invalid node error messages...

        print("Verify correct error report of frozen file known to Metax but missing from IDA")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/test01.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in IDA" in errors)

        # Delete file from Metax
        print("Verify correct error report of frozen file known to IDA but missing from Metax")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/test02.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in Metax" in errors)

        # Change size of frozen file in IDA db
        # Change checksum of frozen file in IDA db
        # Change pid of frozen file in IDA db
        # Change frozen timestamp of frozen file in IDA db
        # Change modification timestamp of frozen file in IDA db

        print("Verify correct error report of IDA file size conflict with Metax")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/test03.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
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
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/test04.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node does not exist in replication" in errors)

        print("Verify correct error report of IDA file size conflict with replication")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/test05.dat", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node size different for IDA and replication" in errors)

        print("Verify correct error report of IDA file type conflict with replication")
        node = nodes.get("frozen/2017-08/Experiment_1/baseline/zero_size_file", None)
        self.assertIsNotNone(node)
        errors = node.get("errors", None)
        self.assertIsNotNone(errors)
        self.assertTrue("Node type different for IDA and replication" in errors)

        # --------------------------------------------------------------------------------

        print("--- Auditing project E and checking results")
        
        report_data = self.auditProject("test_project_e", "ok")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 104)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 104)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 0)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 0)

        # --------------------------------------------------------------------------------

        # TODO: Uncomment once project repair bugs are resolved per CSCIDA-691

        """
        print("--- Repairing projects A, B, C, and D for re-auditing")
        
        print("(repairing project A)")
        cmd = "sudo -u %s %s/utils/admin/repair-project test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.waitForPendingActions("test_project_a", test_user_a)
        self.checkForFailedActions("test_project_a", test_user_a)

        print("(repairing project B)")
        cmd = "sudo -u %s %s/utils/admin/repair-project test_project_b" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.waitForPendingActions("test_project_b", test_user_b)
        self.checkForFailedActions("test_project_b", test_user_b)

        print("(repairing project C)")
        cmd = "sudo -u %s %s/utils/admin/repair-project test_project_c" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.waitForPendingActions("test_project_c", test_user_c)
        self.checkForFailedActions("test_project_c", test_user_c)

        print("(repairing project D)")
        cmd = "sudo -u %s %s/utils/admin/repair-project test_project_d" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            start = subprocess.check_output(cmd, shell=True).decode(sys.stdout.encoding).strip()
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))

        self.waitForPendingActions("test_project_d", test_user_d)
        self.checkForFailedActions("test_project_d", test_user_d)

        print("--- Re-auditing project A and checking results")
        
        report_data = self.auditProject("test_project_a", "ok")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 104)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 104)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 0)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 0)

        print("--- Re-auditing project B and checking results")
        
        report_data = self.auditProject("test_project_b", "ok")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 104)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 104)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 0)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 0)

        print("--- Re-auditing project C and checking results")
        
        report_data = self.auditProject("test_project_c", "ok")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 104)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 104)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 0)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 0)

        print("--- Re-auditing project D and checking results")
        
        report_data = self.auditProject("test_project_d", "ok")

        print("Verify correct number of reported filesystem nodes")
        self.assertEquals(report_data.get("filesystemNodeCount", None), 104)

        print("Verify correct number of reported Nextcloud nodes")
        self.assertEquals(report_data.get("nextcloudNodeCount", None), 104)

        print("Verify correct number of reported IDA nodes")
        self.assertEquals(report_data.get("idaNodeCount", None), 0)

        print("Verify correct number of reported Metax nodes")
        self.assertEquals(report_data.get("metaxNodeCount", None), 0)

        print("Verify correct number of reported invalid nodes")
        self.assertEquals(report_data.get("invalidNodeCount", None), 0)
        """

        # --------------------------------------------------------------------------------
        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
