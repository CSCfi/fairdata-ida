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
from shutil import rmtree
import errno
import os

from agents.utils import rabbitmq
from agents.utils.utils import get_settings, construct_file_path


SETTINGS = get_settings()


def init_rabbitmq():
    rabbitmq.init_rabbitmq()

def teardown_rabbitmq():
    rabbitmq.teardown_rabbitmq()

def create_test_file(uida_conf_vars, test_file_data):
    file_path = construct_file_path(uida_conf_vars, test_file_data)
    dir_path, file_name = os.path.split(file_path)
    try:
        os.makedirs(dir_path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    with open(file_path, 'w+') as f:
        f.write('filename is %s' % file_name)

def delete_test_directory(dir_path):
    try:
        rmtree(dir_path)
    except FileNotFoundError:
        # can happen when executed in init
        pass
