#--------------------------------------------------------------------------------
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
#
# This script queries the IdM for the status of a credentials update workflow
#
# --------------------------------------------------------------------------------
#
# IdM integration must be defined in the IDA config.sh file with the variables:
#
#     TEST_IDM_PROXY_USER_PASSWORD="***"
#     TEST_IDM_CLIENT_PASSWORD="***"
#
#--------------------------------------------------------------------------------

import importlib.util
import sys
import os
import json
import requests
from Crypto.Cipher import AES


def main():

    try:

        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % os.getenv('ROOT'))

        #config.DEBUG = "true" # TEMP HACK

        config.WORKFLOW_ID = sys.argv[1]

        if config.DEBUG == 'true':
            sys.stdout.write("ROOT:        %s\n" % config.ROOT)
            sys.stdout.write("WORKFLOW_ID: %s\n" % config.WORKFLOW_ID)

        # Test IdM integration settings

        test_idm_oauth_endpoint = "https://idtestapps.csc.fi:8543/osp/a/idm/auth/oauth2/token"
        test_idm_workflow_endpoint = "https://idtestapps.csc.fi:8543/IDMProv/rest/access/requests/history/item"
        test_idm_proxy_user = "cn=fairdata,ou=users,o=local"
        test_idm_client = "fairdata"
        test_idm_proxy_user_password = config.TEST_IDM_PROXY_USER_PASSWORD
        test_idm_client_password = config.TEST_IDM_CLIENT_PASSWORD

        # Query IdM 

        headers = { 
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "password",
            "username": test_idm_proxy_user,
            "password": test_idm_proxy_user_password,
            "client_id": test_idm_client,
            "client_secret": test_idm_client_password
        }

        if config.DEBUG == 'true':
            sys.stdout.write("token request url: %s\n" % test_idm_oauth_endpoint)
            sys.stdout.write("token request headers:\n%s\n" % json.dumps(headers, indent=4))
            sys.stdout.write("token request payload:\n%s\n" % json.dumps(data, indent=4))

        response = requests.post(test_idm_oauth_endpoint, headers=headers, data=data)

        if response.status_code != 200:
            raise Exception("Access token retrieval failed: %s %s %s" % (response.status_code, response.reason, response.text))

        data = response.json()
        access_token = data.get('access_token', None)

        headers = {
            "Accept": "application/json",
            "Content-type": "application/json",
            "Authorization": "Bearer %s" % access_token
        }

        data = {
            "id": config.WORKFLOW_ID,
            "entityType": "PRD"
        }

        if config.DEBUG == 'true':
            sys.stdout.write("workflow request url: %s\n" % test_idm_workflow_endpoint)
            sys.stdout.write("workflow request headers:\n%s\n" % json.dumps(headers, indent=4))
            sys.stdout.write("workflow request payload:\n%s\n" % json.dumps(data, indent=4))

        response = requests.post(test_idm_workflow_endpoint, headers=headers, json=data)

        if response.status_code != 200:
            raise Exception("Workflow retrieval failed: %s %s %s" % (response.status_code, response.reason, response.text))

        data = response.json()

        #{
        #    "id":"5ee0f5d47dca4d57b525f3126efbcfc1",
        #    "name":"Data Deletion Report v0.6",
        #    "entityType":"prd",
        #    "requestState":4,
        #    "processState":2,
        #    "requester":"cn=dataretention,ou=users,o=local",
        #    "recipient":"cn=dataretention,ou=users,o=local",
        #    "recipientName":" dataretention proxy (dataretention, )",
        #    "recipientType":"user",
        #    "requestDate":1645181530250,
        #    "confirmationNumber":"20220218-20",
        #    "retractable":False,
        #    "comments":[
        #        {
        #            "user":"cn=dataretention,ou=users,o=local",
        #            "comment":"{Enter comment here}",
        #            "date":1645181530302,
        #            "activity":"csc.out",
        #            "commentDn":"cn=dataretention,ou=users,o=local",
        #            "commentFullName":" dataretention proxy (dataretention, )"
        #        }
        #    ],
        #    "requesterName":" dataretention proxy (dataretention, )",
        #    "requesterType":"user"
        #}

        # requestState 0 = Running (workflow is running)
        # requestState 1 = Denied (workflow finished with denied status)
        # requestState 2 = Approved (workflow finished with approved status)
        # requestState 3 = Cancelled (when workflow is 'retracted')
        # requestState 4 = When workflow crashes (Don't know label for this one)
        # requestState 5 = (Don't know this one; Not many rows in database with this status)
        # 
        # processState 0 = Running (workflow is running)
        # processState 2 = Terminated (when workflow crashed or workflow is 'retracted' by admin)
        # processState 3 = Completed (Workflow has completed running)
        # 
        # When workflow has crashed:
        # requestState': 4, 'processState': 2
        # 
        # When workflow has finished successfully: 
        # requestState': 2, 'processState': 3

        process_state = data.get('processState', 99)

        if (process_state == 0):
            status = 'running'
        elif (process_state == 3):
            status = 'completed'
        else:
            status = 'failed'

        sys.stdout.write("workflow: %s status: %s\n" % (config.WORKFLOW_ID, status))

    except BaseException as e:
        sys.stderr.write("Error: %s\n" % e)
        exit(1)


def load_configuration(pathname):
    """
    Load and return as a dict variables from the main IDA configuration file
    """
    module_name = "config.variables"
    try:
        # python versions >= 3.5
        module_spec = importlib.util.spec_from_file_location(module_name, pathname)
        config = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(config)
    except AttributeError:
        # python versions < 3.5
        from importlib.machinery import SourceFileLoader
        config = SourceFileLoader(module_name, pathname).load_module()
    return config


if __name__ == "__main__":
    main()
