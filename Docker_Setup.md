
# IDA Development Environment setup instructions

These instructions specify how to setup a containerized development environment for [Fairdata IDA](https://gitlab.ci.csc.fi/fairdata/fairdata-ida/).

## 1 Preparations

### 1.1 Install Docker if not done already

Before starting, you need to have Docker installed. See instructions for Mac and Linux here: https://docs.docker.com/get-docker/

For Mac, the recommended version is Docker Desktop `4.3.0`

### 1.2 Configure DNS

Ensure that ida.fd-dev.csc.fi resolves correctly to IP address 0.0.0.0. This can be achieved by adding the following
entry to your `/etc/hosts` file (Linux/Mac):

```
0.0.0.0 ida.fd-dev.csc.fi
```

### 1.3 Set up IDA git repository

Git clone the fairdata-ida repository into your local development folder on your machine

Option 1: Internal users
```
git clone ssh://git@gitlab.ci.csc.fi/fairdata/fairdata-ida.git
```

Option 2: External users
```
git clone ssh://git@ci.fd-staging.csc.fi:10022/fairdata/fairdata-ida.git
```

### 1.4 Start Docker

Make sure your local Docker instance or engine is running.

If you are using Mac and Docker desktop, make sure you have started Docker desktop.

## 2. Set up fairdata-secrets (config) repository

Clone the fairdata-secrets repository. This repository can be placed next to the `fairdata-ida` repository, for instance (i.e. next to each other, in the same folder).

Option 1: Internal users
```
git clone https://gitlab.ci.csc.fi/fairdata/fairdata-secrets
```

Option 2: External users
```
git clone https://ci.fd-staging.csc.fi/fairdata/fairdata-secrets
```

If you do not have access to the encrypted configuration files in `fairdata-secrets`, see that repository's `README.md` file for how to gain access.

## 3 Pull and build the docker images

Ensure you are in the master branch of the fairdata-ida cloned repository and that it is fully up-to-date, and permissions are open:
```
cd fairdata-ida
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

Ensure you are in the staging branch and it is fully up-to-date, and you are using the latest secrets:
```
cd fairdata-secrets
git fetch
git checkout staging
git pull
./reveal_configs.sh
chmod -R g+rwX,o+rX .
docker stack deploy -c ida/docker-compose.dev.yml fairdata-conf
docker stack deploy -c tls/docker-compose.dev.yml fairdata-conf
docker stack deploy -c fairdata-test-accounts/docker-compose.dev.yml fairdata-conf
```

## 5. Deploy the IDA dev stack

Create the IDA stack for Docker Swarm by running the following command at the `fairdata-ida` repository root:

### 5.1 Deployment command

Ensure you are back in the IDA repository and deploy:
```
cd fairdata-ida
docker stack deploy --with-registry-auth --resolve-image always -c docker-compose.yml fairdata-dev
```

### 5.2 Inspection of stack status

```
docker service ls
```

According to the above command, when all services are listed as `MODE` = "replicated" and the value of all `REPLICAS` is "1/1", the stack is deployed. If you go to `https://ida.fd-dev.csc.fi`, you should now see:

```
Error
It looks like you are trying to reinstall your Nextcloud...
```

At this point you can proceed.

## 6. Initialize IDA nextcloud

Finally, the Nextcloud application can be initialized using a utility script included in ida repository. Run the following command at the `fairdata-ida` repository root:

```
./docker_init_dev.sh
```

Note: if you have restarted your workstation and are seeing issues with NextCloud when visiting `https://ida.fd-dev.csc.fi`, you may need to rerun this script.

## 7. Login to https://ida.fd-dev.csc.fi

You should now be able to login to `https://ida.fd-dev.csc.fi`, either with local login on the left side of the home page as `admin` with password `admin` or as `test_user` with pasword `test`, or if you optionally generated the Fairdata test accounts (see below) with SSO login, using any of the Fairdata test accounts and credentials in `fairdata-secrets/fairdata-test-accounts/config/credentials.json`

## 8. Run automated tests

To verify that the IDA service is fully functional, run the following command:

```
docker exec -w /var/ida -it $(docker ps -q -f name=ida-nextcloud) /var/ida/tests/run-tests
```

## 9. Initialize Fairdata test accounts

If needed, initialize the Fairdata test accounts by running the following command:

```
docker exec -u root -it $(docker ps -q -f name=ida-nextcloud) /var/ida/venv/bin/python /var/fairdata-test-accounts/initialize-ida-accounts 
```

# After setup

## Redeploying the development environment after pulling or building new images

Redeploy
```
docker stack deploy --with-registry-auth --resolve-image always -c docker-compose.yml fairdata-dev
```

Run the init_dev.sh script
```
./docker_init_dev.sh
```

## Removing the docker development environment

To remove the docker development environment entirely from your machine, do the following:

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
