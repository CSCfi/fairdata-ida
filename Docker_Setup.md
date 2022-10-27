
# IDA Development Environment setup instructions

These instructions specify how to setup a containerized development environment for [Fairdata IDA](https://gitlab.ci.csc.fi/fairdata/fairdata-ida/). This environment will include running instances of the following services and utilities and can be used for their
development and testing:

 * IDA / Nextcloud
 * IDA command line tools
 * IDA healthcheck service
 * IDA admin portal
 * Fairdata Download Service


## 1 Preparations

### 1.1 Install Docker if not done already

Before starting, you need to have Docker installed. See instructions for Mac and Linux here: https://docs.docker.com/get-docker/

For Mac, the recommended version is Docker Desktop `4.3.0`

### 1.2 Configure DNS

Ensure that ida.fd-dev.csc.fi resolves correctly to IP address 0.0.0.0. This can be achieved by adding the following
entry to your `/etc/hosts` file (Linux/Mac):

```
0.0.0.0 ida.fd-dev.csc.fi download.fd-dev.csc.fi
```

### 1.3 Clone the necessary IDA and Fairdata git repositories locally

Clone the IDA git repositories into your local development folder on your machine.

```
mkdir ~/dev
cd ~/dev
```

Option 1: Internal users
```
git clone https://gitlab.ci.csc.fi/fairdata/fairdata-ida.git
git clone https://gitlab.ci.csc.fi/fairdata/ida-command-line-tools.git
git clone https://gitlab.ci.csc.fi/fairdata/ida-service-internals.git
git clone https://gitlab.ci.csc.fi/fairdata/fairdata-ida-healthcheck.git
git clone https://gitlab.ci.csc.fi/fairdata/fairdata-download-service.git
git clone https://gitlab.ci.csc.fi/fairdata/fairdata-secrets.git
```

Option 2: External users
```
git clone https://ci.fd-staging.csc.fi/fairdata/fairdata-ida.git
git clone https://ci.fd-staging.csc.fi/fairdata/ida-command-line-tools.git
git clone https://ci.fd-staging.csc.fi/fairdata/ida-service-internals.git
git clone https://ci.fd-staging.csc.fi/fairdata/fairdata-ida-healthcheck.git
git clone https://ci.fd-staging.csc.fi/fairdata/fairdata-download-service.git
git clone https://ci.fd-staging.csc.fi/fairdata/fairdata-secrets.git
```

If you do not have access to the encrypted configuration files in `fairdata-secrets`, see that repository's `README.md` file for how to gain access.

### 1.4 Start Docker

Make sure your local Docker instance or engine is running.

If you are using Mac and Docker desktop, make sure you have started Docker desktop.

## 2. Set up fairdata-secrets (config) repository

Decrypt and unpack the configuration files in the fairdata-secrets repository:

```
cd ~/dev/fairdata-secrets
git fetch
git checkout master
git pull
./reveal_configs.sh
```

Answer 'Y' to all prompts.

## 3 Pull and build the docker images

Ensure you are in the master branch of the fairdata-ida cloned repository and that it is fully up-to-date, and permissions are open:
```
cd ~/dev/fairdata-ida
git fetch
git checkout master
git pull
chmod -R g+rwX,o+rX .
```

Pull the following supporting images:
```
docker pull postgres:12
docker pull rabbitmq:management
docker pull redis:latest
```

Build the IDA image locally:
```
docker build --no-cache . -f Dockerfile -t fairdata-ida-nextcloud
```

## 4. Initialize the docker swarm and deploy required configurations

### 4.1 Initialize docker swarm

A `docker swarm` must be running in order to proceed with

```
docker swarm init
```

### 4.2. Deploy required configurations from fairdata-secrets

Once `fairdata-secrets` is cloned, configurations can be deployed with stacks included in Fairdata-Secrets repository by running the following commands at the `fairdata-secrets` repository root.

```
cd ~/dev/fairdata-secrets
chmod -R g+rwX,o+rX .
docker stack deploy -c ida/docker-compose.dev.yml fairdata-conf
docker stack deploy -c tls/docker-compose.dev.yml fairdata-conf
docker stack deploy -c fairdata-test-accounts/docker-compose.dev.yml fairdata-conf
docker stack deploy -c download/docker-compose.idadev.yml fairdata-conf
```

## 5. Deploy the IDA dev stack

Create the IDA stack for Docker Swarm by running the following command at the `fairdata-ida` repository root:

### 5.1 Deployment command

Ensure you are in the IDA repository, permissions are open, and deploy:
```
cd ~/dev/fairdata-ida
chmod -R g+rwX,o+rX .
docker stack deploy --with-registry-auth --resolve-image always -c docker-compose.yml fairdata-dev
```

### 5.2 Inspection of stack status

```
docker service ls
```

According to the above command, when all services are listed as `MODE` = "replicated" and the value of all `REPLICAS` is "1/1", the stack is deployed. 

At this point you can proceed.

## 6. Initialize IDA nextcloud

The Nextcloud application can be initialized using a utility script included in ida repository. Run the following command at the `fairdata-ida` repository root:

```
./docker_init_dev.sh
```

## 7. Login to https://ida.fd-dev.csc.fi

You should now be able to login to `https://ida.fd-dev.csc.fi`, either with local login on the left side of the home page as `$NC_ADMIN_USER` with password `$NC_ADMIN_PASS` or as `test_user` with pasword `$TEST_USER_PASS`, as defined in `/var/ida/config/config.sh`, or if you optionally generated the Fairdata test accounts (see below) you should be able to log in with SSO login using any of the Fairdata test accounts and credentials in `fairdata-secrets/fairdata-test-accounts/config/credentials.json`

## 8. Run automated tests

To verify that all components of the IDA service are fully functional, run the automated tests.

### 8.1 Core IDA automated tests

The automated tests for the core IDA service and postprocessing agents can be run with the following command:

```
docker exec -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) /var/ida/tests/run-tests
```

### 8.2 IDA command line tools automated tests

The automated tests for the IDA command line tools can be run with the following command:

```
docker exec -w /var/ida-tools -it $(docker ps -q -f name=ida-nextcloud) /var/ida-tools/tests/run-tests
```

### 8.3 IDA healthcheck service automated tests

The automated tests for the IDA healthcheck service can be run with the following command:

```
docker exec -w /opt/fairdata/ida-healthcheck -it $(docker ps -q -f name=ida-nextcloud) /opt/fairdata/ida-healthcheck/tests/run-tests
```

### 8.4 IDA statdb and project activity reporting automated tests

The automated tests for the IDA statdb and project activity reporting can be run with the following command:

```
docker exec -w /opt/fairdata/ida-report -it $(docker ps -q -f name=ida-nextcloud) /opt/fairdata/ida-report/tests/run-tests
```

### 8.5 Fairdata download service automated tests

The automated tests for the Fairdata download service can be run with the following command:

```
docker exec -w /opt/fairdata/fairdata-download-service -it $(docker ps -q -f name=ida-nextcloud) /opt/fairdata/fairdata-download-service/dev_config/utils/run-tests
```

### 8.6 IDA admin portal manual tests

The IDA admin portal can be manually tested using your local browser at https://ida.fd-dev.csc.fi:8888

## 9. Initialize Fairdata test accounts

If needed, initialize the Fairdata test accounts, to be used with SSO login by CSC account, by running the following command:

```
docker exec -it $(docker ps -q -f name=ida-nextcloud) python3 /var/fairdata-test-accounts/initialize-ida-accounts 
```

# After setup

## Redeploying the development environment after pulling and/or building new images, or if environment malfunctioning

The development environment should be redeployed cleanly after pulling or building any new images.

This may also need to be done if after stopping and restarting docker, the environment behaves strangely. Normally, when
restarting docker after shutting it down properly the swarm should resume execution without issues. However sometimes things
go amiss an the environment needs to be redepoloyed cleanly.

First shut down and discard all running containers and remove all existing volumes, then reinitialize the swarm, initialize
secrets, and redeploy the stack:

```
docker swarm leave --force
docker volume rm $(docker volume ls -q)
docker swarm init
cd ~/dev/fairdata-secrets
chmod -R g+rwX,o+rX .
docker stack deploy -c ida/docker-compose.dev.yml fairdata-conf
docker stack deploy -c tls/docker-compose.dev.yml fairdata-conf
docker stack deploy -c fairdata-test-accounts/docker-compose.dev.yml fairdata-conf
docker stack deploy -c download/docker-compose.idadev.yml fairdata-conf
cd ~/dev/fairdata-ida
chmod -R g+rwX,o+rX .
docker stack deploy --with-registry-auth --resolve-image always -c docker-compose.yml fairdata-dev
```

Repeatedly check with `docker service ls` until all containers are running. Then initialize the IDA container:

```
./docker_init_dev.sh
```

## Removing the docker development environment

To remove the docker development environment entirely from your machine, either for good or before 
rebuilding the environment fully cleanly, do the following:

Warning: this will delete all images from your docker environment, not only those which are part of the IDA development environment. If you have other images you don't want to delete, then you will need to delete each IDA development docker image manually.

```
# Shut down the swarm, force stopping all running containers
docker swarm leave --force

# Remove all images
docker rmi -f `docker images -qa`

# Remove all volumes
docker volume rm $(docker volume ls -q)

# Purge cache
docker system prune -a -f
```

Note: there is a utility script `docker_purge_all` in the root of the fairdata-ida repository which executes the above four steps.

## Rebuilding the development environment cleanly

Remove the docker environment components as detailed immediately above, then follow steps 3 through 7 above to re-deploy and configure the development environment.
