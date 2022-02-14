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

import responses
import unittest
import subprocess
import os
import sys
from tests.common.utils import load_configuration


class TestIdaUser(unittest.TestCase):


    @classmethod
    def setUpClass(cls):
        print("=== tests/admin/test_ida_user")


    def setUp(self):
        self.config = load_configuration()
        self.project_name = "test_project_a"
        self.ida_project = "sudo -u %s %s/admin/ida_project" % (self.config["HTTPD_USER"], self.config["ROOT"])
        self.ida_user = "sudo -u %s %s/admin/ida_user" % (self.config["HTTPD_USER"], self.config["ROOT"])
        self.offlineSentinelFile = "%s/control/OFFLINE" % self.config.get('STORAGE_OC_DATA_ROOT', '/mnt/storage_vol01/ida')

        # clear any residual accounts, if they exist from a prior run
        self.success = True
        noflush = self.config.get('NO_FLUSH_AFTER_TESTS', 'false')
        self.config['NO_FLUSH_AFTER_TESTS'] = 'false'
        self.tearDown()
        self.success = False
        self.config['NO_FLUSH_AFTER_TESTS'] = noflush

        print("(initializing)")

        # create project if it doesn't already exist
        cmd = "%s ADD %s 1 2>&1" % (self.ida_project, self.project_name)
        subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)

        # set quota to 1G, success tells us the project exists as required
        cmd = "%s MODIFY %s 1 2>&1" % (self.ida_project, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        if OUT != 0:
            raise Exception("Failed to set up test project")


    def tearDown(self):
        # clear all test accounts, ignoring any errors if they do not exist

        if self.success and self.config.get('NO_FLUSH_AFTER_TESTS', 'false') == 'false':

            print("(cleaning)")
    
            if (os.path.exists(self.offlineSentinelFile)) :
                os.remove(self.offlineSentinelFile)

            cmd = "sudo -u %s %s/tests/utils/initialize-test-accounts flush" % (self.config["HTTPD_USER"], self.config["ROOT"])
            os.system(cmd)

        self.assertTrue(self.success)


    def test_ida_user(self):

        print("Create new user")
        cmd = "%s ADD user_1_%s %s 2>&1" % (self.ida_user, self.project_name, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "User already exists")

        print("Attempt to create existing user")
        cmd = "%s ADD user_1_%s %s 2>&1" % (self.ida_user, self.project_name, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 1, "User does not exist")

        print("Disable active user")
        cmd = "%s DISABLE user_1_%s 2>&1" % (self.ida_user, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "Seems like user does not exist")

        print("Enable disabled user")
        cmd = "%s ENABLE user_1_%s 2>&1" % (self.ida_user, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "User does not exist")

        print("Attempt to disable non-existent user")
        cmd = "%s DISABLE user_X_%s 2>&1" % (self.ida_user, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 1, "User exists")

        print("Remove user from a project")
        cmd = "%s REMOVE user_1_%s %s 2>&1" % (self.ida_user, self.project_name, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "User does not exist")

        print("Add existing user to a project")
        cmd = "%s JOIN user_1_%s %s 2>&1" % (self.ida_user, self.project_name, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "User does not exist")

        print("Delete user")
        cmd = "%s DELETE user_1_%s 2>&1" % (self.ida_user, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "User does not exist")

        print("Attempt to delete non-existent user")
        cmd = "%s DELETE user_X_%s 2>&1" % (self.ida_user, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 1, "User exists")

        print("Delete project share owner")
        cmd = "%s DELETE PSO_%s 2>&1" % (self.ida_user, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "User does not exist")

        print("Attempt to create new user while service in OFFLINE mode")
        with open(self.offlineSentinelFile, 'a') as sentinelFile:
            sentinelFile.write("TEST")
            sentinelFile.close()
        cmd = "%s ADD user_2_%s %s 2>&1" % (self.ida_user, self.project_name, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 1, "Sentinel file ignored")
        os.remove(self.offlineSentinelFile)

        self.success = True

        # TODO: add addition tests involving non-existent users and projects, verifying failure of request
