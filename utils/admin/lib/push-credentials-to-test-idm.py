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
# This script pushes user credentials to the test IdM service per the specified
# credentials file.
#
# --------------------------------------------------------------------------------
#
# IdM integration must be defined in the IDA config.sh file with the variables:
#
#     TEST_IDM_PROXY_USER_PASSWORD="***"
#     TEST_IDM_CLIENT_PASSWORD="***"
#     TEST_IDM_SHARED_SECRET="***"
#
#--------------------------------------------------------------------------------

import importlib.util
import sys
import os
import json
import hashlib
import base64
import requests
from Crypto.Cipher import AES


def main():

    try:

        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % os.getenv('ROOT'))

        #config.DEBUG = "true" # TEMP HACK

        config.INPUT_FILE = sys.argv[1]

        if config.DEBUG == 'true':
            sys.stdout.write("ROOT:       %s\n" % config.ROOT)
            sys.stdout.write("INPUT_FILE: %s\n" % config.INPUT_FILE)

        # Test IdM integration settings

        test_idm_oauth_endpoint = "https://idtestapps.csc.fi:8543/osp/a/idm/auth/oauth2/token"
        test_idm_workflow_endpoint = "https://idtestapps.csc.fi:8543/IDMProv/rest/access/requests/permissions/v2"
        test_idm_proxy_user = "cn=fairdata,ou=users,o=local"
        test_idm_client = "fairdata"
        test_idm_proxy_user_password = config.TEST_IDM_PROXY_USER_PASSWORD
        test_idm_client_password = config.TEST_IDM_CLIENT_PASSWORD
        test_idm_shared_secret = config.TEST_IDM_SHARED_SECRET

        # Setup for password encryption using IdM shared secret

        bs = 16
        pad = lambda s: s + (bs - len(s) % bs) * chr(bs - len(s) % bs)
        digest = hashlib.sha256(test_idm_shared_secret.encode('utf-8')).hexdigest()
        cipher = AES.new(bytes.fromhex(digest), AES.MODE_ECB)
        encrypt_password = lambda p: base64.b64encode(cipher.encrypt(pad(p).encode())).decode('utf-8')

        # Load credentials from input file

        credentials = load_credentials(config.INPUT_FILE)

        # Construct value array

        # [
        #     "<USERNAME1>|<BASE64-ENCODED-SYMMETRICALLY-ENCRYPTED-PASSWORD-FOR-USERNAME1>",
        #     "<USERNAME2>|<BASE64-ENCODED-SYMMETRICALLY-ENCRYPTED-PASSWORD-FOR-USERNAME2>",
        #     ...
        # ]

        values = []

        for username, password in credentials.items():
            values.append("%s|%s" % ( username, encrypt_password(password)))

        # Construct payload
        
        payload = {
            "reqPermissions": [
                {
                    "id": "cn=FD-Set-Demo-Account-Passwords_v0_1,cn=RequestDefs,cn=AppConfig,cn=User Application Driver,cn=driverset1,o=system",
                    "entityType": "PRD"
                }
            ],
            "data": [
                {
                    "key": "payloads",
                    "value": values
                }
            ]
        }

        # Push payload to IdM 

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

        if config.DEBUG == 'true':
            sys.stdout.write("workflow request url: %s\n" % test_idm_workflow_endpoint)
            sys.stdout.write("workflow request headers:\n%s\n" % json.dumps(headers, indent=4))
            sys.stdout.write("workflow request payload:\n%s\n" % json.dumps(payload, indent=4))

        response = requests.post(test_idm_workflow_endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            raise Exception("Workflow initiation failed: %s %s %s" % (response.status_code, response.reason, response.text))

        data = response.json()

        # Hopefully this structure will be consistent
        workflow = data['OperationNodes'][0]['succeeded'][0]['requestId']

        sys.stdout.write("workflow: %s\n" % workflow)

    except BaseException as e:
        sys.stderr.write("Error: %s\n" % e)
        exit(1)


def load_credentials(pathname):
    """
    Load and return as a dict credentials from the specified input file
    """
    credentials = {}
    with open(pathname) as input_file:
        for line in input_file:
            tokens = line.strip().split()
            if len(tokens) == 2:
                credentials[tokens[0]] = tokens[1]
    return credentials


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
