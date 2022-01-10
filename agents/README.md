<!--
This file is part of the IDA research data storage service

Copyright (C) 2018 Ministry of Education and Culture, Finland

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

@author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
@license  GNU Affero General Public License, version 3
@link     https://research.csc.fi/
-->

This is the root directory for all event-driven agents which
perform core IDA service operations in response to events initiated
by users or by other components or processes of the service.

In the IDA RabbitMQ context, the terms "agent" and "consumer" are synonymous.

Agents are implemented as RabbitMQ listener agents which respond to `freeze`,
`unfreeze`, `delete`, and repair messages published by the IDA service.

The metadata agent responds to all action messages, and ensures
that the file specific metadata maintained in METAX is kept up-to-date,
generating PIDs, checksums (SHA-256), and aggregating all relevant metadata
accordingly. In practice, `unfreeze` and `delete` events are treated the same
(files are simply marked as deleted in METAX). Once done, for `freeze` and
`repair` actions, the metadata agent publishes a replication message to the
designated replication agent RabbitMQ exchange. For other actions, the
metadata agent marks the action as completed.

The replication agent responds only to `freeze` and `repair` action messages. It
copies all files associated with a given action, from the frozen area of the
project to the configured replication location, employing checksum validation
on each copied file. However, if the execution environment is 'TEST', or if
the action is a repair action, and the file both already exists in the replication
location and the file size of both the frozen file and replicated file are the
same, the file is skipped.

# Agent installation

Assuming IDA has been installed to /var/ida.

Before proceeding, ensure the rabbitmq management plugin is installed, and the
config file is in place in /var/ida/config/config.sh and contains valid parameters
for whatever environment you are running in. The utility script
rabbitmq_create_users in /var/ida/utils should be executed to set the admin user
password, so that later the rabbitmq initialization script can access the management
plugin API. The commands below should optimally be included in some generic installation script
of IDA.

```
# setup a python virtual env and install required packages
cd /var/ida/utils
./initialize_agents_venv

# enable rabbitmq management plugin, initialize and configure rabbitmq users, exchanges, and queues
cd /var/ida/utils
./initialize_rabbitmq

# setup rabbitmq agent services
cd /usr/lib/systemd/system
ln -s /var/ida/agents/services/rabbitmq-metadata-agent.service rabbitmq-metadata-agent.service
ln -s /var/ida/agents/services/rabbitmq-replication-agent.service rabbitmq-replication-agent.service
systemctl daemon-reload
systemctl start rabbitmq-metadata-agent
systemctl start rabbitmq-replication-agent

```

For development, the agents can be executed separately:

```
python -m agents.metadata.metadata_agent
```

...or both at once (taking turns processing their queues):

```
python -m agents.run_all
```

## Testing

### Unit tests

To execute all unit tests, in directory /var/ida execute:

(remember to source /srv/venv-agents/bin/activate)

```
python -W ignore -m unittest discover tests.agents
```

The test suite creates its own rabbitmq vhost, exchanges and users. During the tests, messages are
published to rabbitmq, and the agents processes messages from a real rabbitmq queue.

Both the IDA web API, and Metax web API, are mocked. The pre-generated test data
used during the tests are stored in tests/agents/testdata/testdata.py, which is what the mocked IDA
api uses as its "database".

In test environments, the replication location does not have to be mounted; it is treated as a
normal directory, and will be created when necessary.

### Behavioral tests

Behavioral testing of the postprocessing agents is part of the wider Nextcloud tests
in various test files in tests/.

# Settings

The general, global settings in config/config.sh are also used by the agents.
Additionally, there are some settings in agents/settings.py, most importantly
the locations of the config.sh and constants.sh need to be defined. For the
rest of the options available in settings.py, see the file itself.

Details of the created rabbitmq vhost, exchanges, and queues are specified in the rabbitmq utils file
agents/utils/rabbitmq.py.

When executing tests, the variables from config/config.sh are used, but some variables
are overrided using tests/agents/config/config.sh to use a different rabbitmq vhost etc.

## Enabling/disabling metax dependency

Setting the METAX_AVAILABLE option in config/config.sh to 0 indicates that actions
should be marked as completed without connecting to Metax, effectively allowing
IDA to function without depending on Metax being there.

In practice, if METAX_AVAILABLE is 0:
* `freeze` actions are marked as completed once checksums have been saved to nodes in IDA.
  i.e., file metadata is not published to Metax.
* `unfreeze` and `delete` actions are marked completed immediately, without informing Metax.

For normal operation, value of METAX_AVAILABLE should be 1.

# RabbitMQ exchanges, queues, retry mechanics

When freezing/unfreezing/deleting files in IDA, an action (a message) of specific
type is published to a specific rabbitmq exchange. The agents are listening on
queues bound to that exchange, picking a single message from a specific queue,
process it, and either:
* mark the processed sub-action(s) as completed, and ack the message (removing it from message circulation)
* upon failure, republish the message to a delayed queue for retry at a later date
* or mark the action as failed and ack the message for no further autonomous retries.

For failures, there are a couple of error-types that will be automatically retried indefinetly:

* HTTP requests which fail due to connection errors (host not responding etc)
* Replication location is not mounted

The exchanges used are:

exchange | type | comment
----|------|-------
actions | fanout | The initial `freeze`, `unfreeze`, or `delete` message is published here only.
replication | fanout | Once metadata publication has been successfully processed, a message is published here.
actions-failed | direct | When an action fails even once, all subsequent message handling occurs here.
batch-actions | fanout | For batch actions, the initial `freeze`, `unfreeze`, or `delete` message is published here only.
batch-replication | fanout | For batch actions, once metadata publication has been successfully processed, a message is published here.
batch-actions-failed | direct | For batch actions, when an action fails even once, all subsequent message handling occurs here.

The various queues used are:

exchange | queue | consumers (agents) | on fail, republish to | delayed | delayed republish to
---------|-------|-----------|------------------|-----------------------|---------------------
actions | metadata | metadata | (checksums&#124;metadata)-failed-waiting | |
replication | replication | replication | replication-failed-waiting | |
actions-failed | checksums-failed-waiting | | | x | metadata-failed
actions-failed | metadata-failed-waiting | | | x | metadata-failed
actions-failed | replication-failed-waiting | | | x | replication-failed
actions-failed | metadata-failed | metadata | (checksums&#124;metadata)-failed-waiting | |
actions-failed | replication-failed | replication | replication-failed-waiting | |
batch-actions | batch-metadata | metadata | batch-(checksums&#124;metadata)-failed-waiting | |
batch-replication | batch-replication | replication | batch-replication-failed-waiting | |
batch-actions-failed | batch-checksums-failed-waiting | | | x | batch-metadata-failed
batch-actions-failed | batch-metadata-failed-waiting | | | x | batch-metadata-failed
batch-actions-failed | batch-replication-failed-waiting | | | x | batch-replication-failed
batch-actions-failed | batch-metadata-failed | metadata | batch-(checksums&#124;metadata)-failed-waiting | |
batch-actions-failed | batch-replication-failed | replication | batch-replication-failed-waiting | |

The retry-mechanics are implemented using the so called 'dead-letter-exchanges', nicely described [here](https://stackoverflow.com/a/17014585/1201945),
which require a few extra queues and configuration.

## Message lifecycle

A short description of the lifecycle of a message through these exchanges and queues:

When an action is initially published, it is published to the `actions` (standard action) or the `batch-actions` (batch action) exchange, from where the action flows to either the `metadata` or the `batch-metadata` queue, for first processing attempt. If the processing is successful, checksum- and metadata sub-actions are marked completed, and a new message is published to the `replication` or the `batch-replication` exchange. The initial message is acked by the common `metadata` consumer/agent, and removed from circulation. The common `replication` consumer/agent consumes the new message from the `replication` or the `batch-replication` queue, and begins its work. Once done, it marks the sub-action as completed, acks the message, removing it from criculation.

### Message lifecycle during errors

Depending on if a message is a standard message or a batch message, different lifecycles will be used. Standard messages use the standard queues and batch messages uses the batch queues. All batch queues are prefixed with `batch-`. Standard queues have no prefix. Otherwise the lifecycles are identical.

If the processing fails, say in metadata publication phase, the message is republished to the queue `metadata-failed-waiting`/`batch-metadata-failed-waiting`. These queues have no consumers/agents. The message will sit for a period of time (specified in `settings.py`, `retry_policy` -> `metadata` -> `retry_interval`). The message is then automatically republished to the queue `metadata-failed`/`batch-metadata-failed`. These queues have an attached consumer/agent (the `metadata` agent). From these queues, a retry attempt will be executed. 

A success in the retry will remove the message from circulation, while a failure will increment the retry count in the message, and republish again to the queue `metadata-failed-waiting`/`batch-metadata-failed-waiting`) - unless `max_retries` is exceeded, in which case the message is marked as failed instead, and removed from circulation.

In other words, when a message is first published, it enters the `actions`/`batch-actions` exchange. If processing fails even once, for the rest of its life the message exists only in the `actions-failed`/`batch-actions-failed` exchange and its several queues.

If the message processing never succeeded, and was marked as failed, a manual republish of the message should target the `actions`/`batch-actions` exchange, so that it may begin the complete cycle again.

### Potential improvements

Since the volume of messages circulating in the exchanges is most probably not going to be a performance issue,
the current retry mechanism using the dead-letter-exchanges could be made more sophisticated by simply creating
more delayed queues, with varying delays. As an example, for metadata publication: Create three waiting queues,
first queue has a republish delay of 1 minute, the second would have 6 hours, third could have 3 days.

# Agent processing logic

When an agent is started, the agent will try to retrieve a single message from its
designated main queue, and process it. After a message is processed from the main queue, the corresponding queue
for failed messages is checked, and if the failed-queue contains messages, it will be continuously processed until
empty, to ensure that newer messages don't continuously block and delay the processing of possibly long overdue failed
messages, which would otherwise be ripe for retry.

For simplicity, the agents should be executed in their own processes, to ensure that one agent is not continuously
blocking and delaying the other agent's work. Multiple agents may be started on a single machine, or on multiple servers,
they should not interfere with each other.

# Agent monitoring

When an agent is in the middle of processing some action, the agent creates a monitoring file in directory
RABBIT_MONITORING_DIR (see config/config.sh), which tells how long an agent has been processing a message.
The monitoring files can be utilized by external monitoring services by checking the last-modified date of
the file, to raise alerts when some agent has been working for longer than expected.

The monitoring filename consists of the agent hostname, agent type, and process id. The files contain
additional information, such as action id of current action being processed. The agents clean up old
monitoring files when processing of an action has concluded, and when an agent is terminated, or restarted 
(in case there was a crash, and the agent had no chance to clean up after itself).

A monitoring script intended for use by Nagios can be found in monitoring/.

To clear an alert from a file, "touch" the file update the last-modified timestamp.

# Connection between FreezingController and RabbitMQ exchanges

```
                                                                      RabbitMQ exchanges
API call            FreezingController    registerAction call		      actions		batch-actions
--------            ------------------    -------------------         -------   -------------
/api/freeze         freezeFiles()         registerAction('freeze')	  x		      x
/api/unfreeze       unfreezeFiles()       registerAction('unfreeze')	x		      x
/api/delete         deleteFiles()         registerAction('delete')	  x		      x
'/api/retry/{pid}   retryAction()         registerAction()            x         x
/api/bootstrap      bootStrapProject()    registerAction($action)		  -		      x
/api/repair         repairProject()       registerAction('repair')	  -		      x
```
