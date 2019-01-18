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


class TestIdaProject(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("=== tests/admin/test_ida_project")

    def setUp(self):
        self.config = load_configuration()
        self.project_name = "test_project_a"
        self.ida_project = "sudo -u %s %s/admin/ida_project" % (self.config['HTTPD_USER'], self.config['ROOT'])
        self.ida_user = "sudo -u %s %s/admin/ida_user" % (self.config['HTTPD_USER'], self.config['ROOT'])

        # clear any residual accounts, if they exist from a prior run
        self.tearDown()

        print("(initializing)")

        # (nothing needs to be done for initialization...)

    def tearDown(self):
        # clear all test accounts, ignoring any errors if they do not exist

        print("(cleaning)")

        cmd = "%s DISABLE %s 1 2>&1" % (self.ida_project, self.project_name)
        subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)

        cmd = "%s DELETE PSO_%s 2>&1" % (self.ida_user, self.project_name)
        subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)

    def test_ida_project(self):
        print("Create new project")
        cmd = "%s ADD %s 1 2>&1" % (self.ida_project, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "Project already exists")

        print("Attempt to create existing project")
        cmd = "%s ADD %s 1 2>&1" % (self.ida_project, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 1, "No existing project")

        print("Modify project quota")
        cmd = "%s MODIFY %s 2 2>&1" % (self.ida_project, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "Cannot modify quota")

        print("Attempt to modify project quota with invalid non-number")
        cmd = "%s MODIFY %s 2e6 2>&1" % (self.ida_project, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 1, "Input is a valid number")

        print("Disable project")
        cmd = "%s DISABLE %s 2>&1" % (self.ida_project, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 0, "Cannot disable project")

        print("Attempt to disable non-existent project")
        cmd = "%s DISABLE %s 2>&1" % (self.ida_project, self.project_name)
        OUT = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(OUT, 1, "User exists")
