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

from time import sleep

import gevent

from agents.metadata.metadata_agent import MetadataAgent
from agents.replication.replication_agent import ReplicationAgent
from agents.utils.utils import get_settings, get_logger


settings = get_settings()

def sleeper():
    while True:
        sleep(settings['main_loop_delay'])
        gevent.sleep(0)


if __name__ == '__main__':
    """
    Runs one agent's main loop once, and yields execution to another agent (once added).
    Repeat.
    """

    logger = get_logger('agent.run_all.py')
    logger.info('---- running all rabbitmq agents ---')

    MdA = MetadataAgent()
    MdA.gevent = gevent
    RA = ReplicationAgent()
    RA.gevent = gevent

    try:
        gevent.joinall([
            gevent.spawn(MdA.start),
            gevent.spawn(RA.start),
            gevent.spawn(sleeper),
        ])
    except KeyboardInterrupt:
        logger.info('---- rabbitmq agents stopped ---')
