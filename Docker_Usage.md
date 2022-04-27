

# Utilities and development with Docker

This documentation describes how to run utility scripts, inspect logs, and do other tasks with a Dockerized version of IDA.

# 1 Nextcloud

## 1.1 How to enter the NextCloud Docker container

```
# Enter container
docker exec -it $(docker ps -q -f name=ida-nextcloud) sudo su -l www-data -s /bin/bash
```

### 1.1.1 Inspect logs

Logs are available at:
```
/mnt/storage_vol01/log/
```

### 1.1.2 Available utility scripts

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

## 2.1 Postprocessing agent containers
```
docker exec -it $(docker ps -q -f name=fairdata-dev_ida-metadata) sh

docker exec -it $(docker ps -q -f name=fairdata-dev_ida-replication) sh
```

## 2.2 Inspect postprocessing logs

Inside each of the postprocessing containers, the RabbitMQ log is available:
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
