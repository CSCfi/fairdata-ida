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

import requests
import unittest
import os
import sys
import shutil
from pathlib import Path
from tests.common.utils import *


class TestChecksums(unittest.TestCase):


    @classmethod
    def setUpClass(cls):
        print("=== tests/checksums/test_checksums")


    def setUp(self):

        # load service configuration variables
        self.config = load_configuration()

        # keep track of success, for reference in tearDown
        self.success = False

        # timeout when waiting for actions to complete
        self.timeout = 600

        print("(initializing)")

        # ensure we start with a fresh setup of projects, user accounts, and data
        cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        # ensure all cache checksums have been generated for test_project_a (if OK, assume OK for all test projects)
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/list-missing-checksums test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
            self.assertEqual(len(output), 0, output[:2000])
        except subprocess.CalledProcessError as error:
            self.fail(error.output.decode(sys.stdout.encoding))


    def tearDown(self):
        # flush all test projects, user accounts, and data, but only if all tests passed,
        # else leave projects and data as-is so test project state can be inspected

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':

            print("(cleaning)")

            cmd = "sudo -u %s DEBUG=false %s/tests/utils/initialize-test-accounts --flush %s/tests/utils/single-project.config" % (self.config["HTTPD_USER"], self.config["ROOT"], self.config["ROOT"])
            result = os.system(cmd)
            self.assertEqual(result, 0)

        self.assertTrue(self.success)


    def test_checksums(self):

        admin_user = (self.config['NC_ADMIN_USER'], self.config['NC_ADMIN_PASS'])
        test_user_a = ('test_user_a', self.config['TEST_USER_PASS'])
        pso_user_a = ('PSO_test_project_a', self.config['PROJECT_USER_PASS'])

        frozen_area_root_a = "%s/PSO_test_project_a/files/test_project_a" % (self.config["STORAGE_OC_DATA_ROOT"])
        staging_area_root_a = "%s/PSO_test_project_a/files/test_project_a%s" % (self.config["STORAGE_OC_DATA_ROOT"], self.config["STAGING_FOLDER_SUFFIX"])

        # --------------------------------------------------------------------------------

        # Add new file to test project A, which won't have checksum (copy to staging and run occ files:scan).
        pathname = "%s/testdata/newfile.dat" % staging_area_root_a
        try:
            with open(pathname, 'w') as file:
                file.write("TEST")
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to create test file %s: %s" % (pathname, str(error)))
        path = Path(pathname)
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())
        original_size = path.stat().st_size
        self.assertEqual(original_size, 4)

        cmd = "sudo -u %s DEBUG=false %s/nextcloud/occ files:scan PSO_test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        result = os.system(cmd)
        self.assertEqual(result, 0)

        # Run list-missing-checksums to ensure file has no checksum and it is listed in output.
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/list-missing-checksums test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        self.assertTrue("/testdata/newfile.dat" in output, output)

        # Change file on disk so that it doesn't match Nextcloud cache size.
        try:
            with open(pathname, 'w') as file:
                file.write("TEST123")
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to modify test file %s: %s" % (pathname, str(error)))
        path = Path(pathname)
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())
        updated_size = path.stat().st_size
        self.assertEqual(updated_size, 7)

        # Run generate-missing-checksums and ensure warning is output for file regarding size mismatch.
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/generate-missing-checksums test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        warning = "Warning: Recorded size 4 does not match size on disk 7 for test_project_a /test_project_a+/testdata/newfile.dat (skipped)"
        self.assertTrue(warning in output, output)

        # Fix file on disk so it matches recorded file size.
        try:
            with open(pathname, 'w') as file:
                file.write("TEST")
            shutil.chown(pathname, user=self.config["HTTPD_USER"], group=self.config["HTTPD_USER"])
        except Exception as error:
            self.fail("Failed to create test file %s: %s" % (pathname, str(error)))
        path = Path(pathname)
        self.assertTrue(path.exists())
        self.assertTrue(path.is_file())
        fixed_size = path.stat().st_size
        self.assertEqual(fixed_size, 4)

        # Run generate-missing-checksums and ensure no warning is output.
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/generate-missing-checksums test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        status = " recorded in cache for test_project_a /test_project_a+/testdata/newfile.dat"
        self.assertFalse("Warning:" in output, output)
        self.assertTrue(status in output, output)

        # Run list-missing-checksums to ensure no files listed.
        cmd = "sudo -u %s DEBUG=false %s/utils/admin/list-missing-checksums test_project_a" % (self.config["HTTPD_USER"], self.config["ROOT"])
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(sys.stdout.encoding).strip()
        self.assertFalse("/testdata/newfile.dat" in output, output)

        # If all tests passed, record success, in which case tearDown will be done

        self.success = True

        # --------------------------------------------------------------------------------
        # TODO: consider which tests may be missing...
