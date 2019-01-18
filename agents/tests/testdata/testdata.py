#--------------------------------------------------------------------------------
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
#--------------------------------------------------------------------------------

"""
This file contains test data used in automated tests. Objects below
are used when mocking requests to the ida api at /ida/api/

Data gathered from real requests to the api on a dev server, plus some custom stuff.
"""

ida = {

    #
    # actions /ida/api/actions/pid
    #

    'actions': [
        # custom freeze action with only one associated node, 0 sub-actions completed
        {
            "id": 1,
            "action": "freeze",
            "checksums": "",
            "metadata": "",
            "replication": "",
            "initiated": "2017-10-26T07:48:45Z",
            "node": 2500,
            "pathname": "/Custom_Experiment",
            "pid": "pidactionwithonenodeonly",
            "pids": "2017-10-26T07:48:46Z",
            "project": "Project_X",
            "storage": "2017-10-25T07:48:45Z",
            "user": "TestUser"
        },
        # a freeze action that has many nodes. from actual ida api request. 0 sub-actions completed
        {
            "id": 2,
            "action": "freeze",
            "checksums": "",
            "metadata": "",
            "replication": "",
            "initiated": "2017-10-25T07:48:45Z",
            "node": 2339,
            "pathname": "/Experiment_2",
            "pid": "59f041dd30c2b572563900a2339",
            "pids": "2017-10-25T07:48:46Z",
            "project": "Project_B",
            "storage": "2017-10-25T07:48:45Z",
            "user": "user_B"
        },
        # custom freeze action with only one associated node. checksums sub-action already completed
        {
            "id": 3,
            "action": "freeze",
            "checksums": "2017-10-26T07:48:50Z",
            "metadata": "",
            "replication": "",
            "initiated": "2017-10-26T07:48:45Z",
            "node": 2501,
            "pathname": "/Custom_Experiment",
            "pid": "pidactionwithchecksumscompleted",
            "pids": "2017-10-26T07:48:46Z",
            "project": "Project_X",
            "storage": "2017-10-25T07:48:45Z",
            "user": "TestUser"
        },
        # custom freeze action with only one associated node. replication sub-action already completed
        {
            "id": 4,
            "action": "freeze",
            "checksums": "",
            "metadata": "",
            "replication": "2017-10-26T07:48:50Z",
            "initiated": "2017-10-26T07:48:45Z",
            "node": 2502,
            "pathname": "/Custom_Experiment",
            "pid": "pidactionwithreplicationcompleted",
            "pids": "2017-10-26T07:48:46Z",
            "project": "Project_X",
            "storage": "2017-10-25T07:48:45Z",
            "user": "TestUser"
        },
        # custom unfreeze action with only one associated node
        {
            "id": 5,
            "action": "unfreeze",
            "checksums": "",
            "metadata": "",
            "initiated": "2017-10-26T07:48:45Z",
            "node": 2503,
            "pathname": "/Custom_Experiment",
            "pid": "pidunfreezingaction",
            "pids": "",
            "project": "Project_X",
            "storage": "",
            "user": "TestUser"
        },
        # freeze action with three associated nodes. metada sub-action already completed.
        {
            "id": 6,
            "action": "freeze",
            "checksums": "2017-10-26T08:48:45Z",
            "metadata": "2017-10-26T09:48:45Z",
            "replicated": "",
            "initiated": "2017-10-26T07:48:45Z",
            "node": 2504,
            "pathname": "/Custom_Experiment",
            "pid": "pidreplicationaction",
            "pids": "2017-10-26T07:48:46Z",
            "project": "Project_X",
            "storage": "",
            "user": "TestUser"
        }

    ],

    #
    # nodes associated with an action /ida/api/nodes/action/pid
    #

    'nodes': [
        {
            "action": "pidactionwithonenodeonly",
            "frozen": "2017-10-26T07:48:45Z",
            "id": 19,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Custom_Experiment/test01.dat",
            "pid": "pidveryuniquefilepidhere",
            "project": "Project_X",
            "size": 3728,
            "type": "file"
        },
        {
            "action": "pidactionwithchecksumscompleted",
            "frozen": "2017-10-26T07:48:45Z",
            "id": 20,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Custom_Experiment/test01.dat",
            "pid": "pidveryuniquefilepidherealso",
            "checksum": "has_checksum_already_generated",
            "project": "Project_X",
            "size": 3728,
            "type": "file"
        },
        {
            "action": "pidactionwithreplicationcompleted",
            "frozen": "2017-10-26T07:48:45Z",
            "id": 21,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Custom_Experiment/test01.dat",
            "pid": "pidveryuniquefilepidhereagain",
            "project": "Project_X",
            "size": 3728,
            "type": "file"
        },
        {
            "action": "pidunfreezingaction",
            "frozen": "2017-10-26T07:48:45Z",
            "id": 22,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Custom_Experiment/test01.dat",
            "pid": "pidveryuniquefilepidherewhat",
            "project": "Project_X",
            "size": 3728,
            "type": "file"
        },
        {
            "action": "59f041dd30c2b572563900a2339",
            "frozen": "2017-10-25T07:48:45Z",
            "id": 13,
            "modified": "2017-10-16T12:45:09Z",
            "pathname": "/Experiment_2",
            "pid": "59f041dda2e53579057900d2339",
            "project": "Project_B",
            "type": "folder"
        },
        {
            "action": "59f041dd30c2b572563900a2339",
            "frozen": "2017-10-25T07:48:45Z",
            "id": 14,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Experiment_2/test01.dat",
            "pid": "59f041ddb37b7105065601f2342",
            "project": "Project_B",
            "size": 446,
            "type": "file"
        },
        {
            "action": "59f041dd30c2b572563900a2339",
            "frozen": "2017-10-25T07:48:45Z",
            "id": 15,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Experiment_2/test02.dat",
            "pid": "59f041ddc36fd974782529f2343",
            "project": "Project_B",
            "size": 1531,
            "type": "file"
        },
        {
            "action": "59f041dd30c2b572563900a2339",
            "frozen": "2017-10-25T07:48:45Z",
            "id": 16,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Experiment_2/test03.dat",
            "pid": "59f041ddd3ed0740421277f2344",
            "project": "Project_B",
            "size": 2263,
            "type": "file"
        },
        {
            "action": "59f041dd30c2b572563900a2339",
            "frozen": "2017-10-25T07:48:45Z",
            "id": 17,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Experiment_2/test04.dat",
            "pid": "59f041dde3f81314898983f2341",
            "project": "Project_B",
            "size": 3329,
            "type": "file"
        },
        {
            "action": "59f041dd30c2b572563900a2339",
            "frozen": "2017-10-25T07:48:45Z",
            "id": 18,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Experiment_2/test05.dat",
            "pid": "59f041ddf3d5d594705199f2345",
            "project": "Project_B",
            "size": 3728,
            "type": "file"
        },
        {
            "action": "pidreplicationaction",
            "frozen": "2017-10-26T07:48:45Z",
            "id": 23,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Custom_Experiment/test01.dat",
            "checksum": "c20a6d5b03450bbc65fd5cd043e1bc8d7842815efd4e431a06a7a7b641fc30ed",
            "pid": "filereplication1",
            "project": "Project_X",
            "size": 3728,
            "type": "file"
        },
        {
            "action": "pidreplicationaction",
            "frozen": "2017-10-26T07:48:45Z",
            "id": 24,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Custom_Experiment/test02.dat",
            "checksum": "607ff9b9d60bedb47f448d585cc34453b60bb454c167797d569021a4e36448b3",
            "pid": "filereplication2",
            "project": "Project_X",
            "size": 3728,
            "type": "file"
        },
        {
            "action": "pidreplicationaction",
            "frozen": "2017-10-26T07:48:45Z",
            "id": 25,
            "modified": "2017-10-16T12:45:08Z",
            "pathname": "/Custom_Experiment/test03.dat",
            "checksum": "5cee01b4ccf026a865630fca290e22dd1ccbffdad5563bbdcb61a4f0ac4cad16",
            "pid": "filereplication3",
            "project": "Project_X",
            "size": 3728,
            # already replicated ! ! !
            "replicated": "2017-10-26T09:48:45Z",
            "type": "file"
        },
    ]
}
