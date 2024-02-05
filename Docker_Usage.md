

# Utilities and development with Docker

This documentation describes how to run utility scripts, inspect logs, and do other tasks with a Dockerized version of IDA.

# 1 Nextcloud

The instance of the IDA service running in the docker container can be accessed in your local browser at https://ida.fd-dev.csc.fi

The instance of the IDA admin portal can be accessed at https://ida.fd-dev.csc.fi:8888

## 1.1 How to enter the NextCloud Docker container

```
# Enter container
docker exec -it $(docker ps -q -f name=ida-nextcloud) sudo su -l root -s /bin/bash
```

### 1.1.1 Restarting apache 

If changes are made to the apache configuration from within a running container, apache can be restarted with

```
/etc/init.d/apache2 reload
```

### 1.1.2 Inspect logs

Logs are available at:
```
/mnt/storage_vol01/log/
```

### 1.1.3 Available utility scripts

Below are listed scripts that can be run with a basic Docker setup of IDA. These scripts should be run inside the NextCloud Docker container.

#### List active projects

```
cd /var/ida/utils/admin
./list-active-projects
```

#### Batch initialize files

```
cd /var/ida/tests/utils

# 5,000 files
./initialize-max-files test_project_a

# 1,000,000 files
./initialize-one-million-files test_project_a
```

#### Batch operations on generated files
```
cd /var/ida/tests/utils

# 5,000 files
./execute-batch-action-max-files test_project_a freeze
./execute-batch-action-max-files test_project_a unfreeze
./execute-batch-action-max-files test_project_a delete

# 1,000,000 files
./execute-batch-action-max-files test_project_a freeze
./execute-batch-action-max-files test_project_a unfreeze
./execute-batch-action-max-files test_project_a delete
```

#### General batch freeze

Typical usage of this script requires a project with many uploaded or generated files (files can be initialized with the `/var/ida/tests/utils/initialize_max_files` script)

```
cd /var/ida/utils/admin

# Generic usage
./execute-batch-action {{ project }} {{ path }}

# Example usage
./execute-batch-action test_project_a freeze /testdata/MaxFiles/5000_files/500_files_1/100_files_1
```

# 2 Postprocessing

## 2.1 Restarting the postprocessing agents

Identify the process numbers of the running agents with the following command:

```
docker exec -it $(docker ps -q -f name=ida-nextcloud) ps auxw | grep agents
```

Then kill one or either of the running agents as needed where `N` is the process number of the running agent to be stopped:

```
docker exec -it $(docker ps -q -f name=ida-nextcloud) sudo kill -9 N
```

Then restart one or both of the agents:

```
docker exec -u www-data --detach -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) python -m agents.metadata.metadata_agent
docker exec -u www-data --detach -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) python -m agents.replication.replication_agent
```

## 2.2 Inspect the postprocessing logs

Inside each of the IDA container, the postprocessing agent log is available as follows:
```
cat /mnt/storage_vol01/log/agents-ida-test.log
```

# 3 RabbitMQ

## 3.1 RabbitMQ container

```
docker exec -it $(docker ps -q -f name=fairdata-dev_ida-rabbitmq) sh

# Check status with rabbitmqctl, such as:
rabbitmqctl list_users --vhost ida-vhost
rabbitmqctl list_exchanges --vhost ida-vhost
```

## 3.2 RabbitMQ web console

The RabbitMQ web console is available at `0.0.0.0:15672`. You can login with the following default values:

```
username = admin
password = test
```

# 4 Automated tests

Run all automated tests:

```
docker exec -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) /var/ida/tests/run-tests
docker exec -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) /var/ida-tools/tests/run-tests
docker exec -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) /opt/fairdata/ida-healthcheck/tests/run-tests
docker exec -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) /usr/local/fd/fairdata-download/tests/run-tests
```

Run a specific IDA test module (see /var/ida/utils/run-tests for module list), e.g.:

```
docker exec -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) /var/ida/tests/run-tests tests.auditing
```
