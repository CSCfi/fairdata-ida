# IDA Development Environment setup instructions

These instructions specify how to setup a containerized development environment for [Fairdata IDA](https://gitlab.ci.csc.fi/fairdata/fairdata-ida/).

# 1 Preparations

## 1.1 Install Docker if not done already

Before starting, you need to have Docker installed. See instructions for Mac and Linux here: https://docs.docker.com/get-docker/

For Mac, the recommended version is Docker Desktop `4.3.0`

## 1.2 Configure DNS

Ensure that ida.fd-dev.csc.fi resolves correctly to IP address 0.0.0.0. This can be achieved by adding the following
entry to your `/etc/hosts` file (Linux/Mac):

```
0.0.0.0 ida.fd-dev.csc.fi
```

## 1.3 Set up repository and branch

Git clone the fairdata-ida repository into your local development folder on your machine

Option 1
```
git clone ssh://git@gitlab.ci.csc.fi/fairdata/fairdata-ida.git
```

Option 2
```
git clone ssh://git@ci.fd-staging.csc.fi:10022/fairdata/fairdata-ida.git
```

Checkout the `ida-docker-2` branch (This step will be deprecated once `ida-docker-2` is merged to the main development branch).

```
cd fairdata-ida
git checkout ida-docker-2
```

## 1.4 Start Docker

Make sure your local Docker instance or engine is running.

If you are using Mac and Docker desktop, make sure you have started Docker desktop.

## 1.5 Optional: access to Artifactory for externals

If you are accessing Artifactory as an external, see:
```
https://ci.fd-staging.csc.fi/fairdata/fairdata-docker/-/blob/staging/proxy_access/external_access_to_artifactory_gitlab.md#docker-client-configuration-mac
```

# 2 Prepare Docker images

# 2.1 Pull the images

Option 1:
```
docker pull fairdata-docker.artifactory.ci.csc.fi/postgres:9
docker pull fairdata-docker.artifactory.ci.csc.fi/rabbitmq:management
docker pull fairdata-docker.artifactory.ci.csc.fi/redis:latest
docker pull fairdata-docker.artifactory.ci.csc.fi/nginx:latest
```

Option 2:
```
docker pull postgres:9
docker pull rabbitmq:management
docker pull redis:latest
docker pull nginx:latest
```

# 2.2 Pull or build IDA images

Option 1: If you are accessing the images as an external, also do a pull on the IDA-specific images
```
docker pull fairdata-docker.artifactory.ci.csc.fi/fairdata-ida-replication:latest
docker pull fairdata-docker.artifactory.ci.csc.fi/fairdata-ida-metadata:latest
docker pull fairdata-docker.artifactory.ci.csc.fi/fairdata-ida-nextcloud:latest
```

Option 2: Otherwise, run the following command in the `fairdata-ida` repository root.
```
docker build . -f Dockerfile -t fairdata-docker.artifactory.ci.csc.fi/fairdata-ida-nextcloud
docker build . -f Dockerfile.replication -t fairdata-docker.artifactory.ci.csc.fi/fairdata-ida-replication
docker build . -f Dockerfile.metadata -t fairdata-docker.artifactory.ci.csc.fi/fairdata-ida-metadata
```

# 3. Initialize docker swarm

A `docker swarm` must be running in order to proceed with

```
docker swarm init
```

# 4. fairdata-secrets

## 4.1. Set up fairdata-secrets (config) repository

Clone the fairdata-secrets repository. This repository can be placed next to the `fairdata-ida` repository, for instance (i.e. next to each other, in the same folder).

Option 1:
```
git clone https://gitlab.ci.csc.fi/fairdata/fairdata-secrets
```

Option 2:
```
git clone https://ci.fd-staging.csc.fi/fairdata/fairdata-secrets
```

If you do not have access to the encrypted configuration files in `fairdata-secrets`, see that repository's `README.md` file for how to gain access.

## 4.2. Deploy required configurations from fairdata-secrets

Once `fairdata-secrets` is cloned, configurations can be deployed with stacks included in Fairdata-Secrets repository by running the following commands at
the `fairdata-secrets` repository root.

```
cd fairdata-secrets
./reveal_configs.sh
docker stack deploy -c ida/docker-compose.dev.yml fairdata-conf
docker stack deploy -c tls/docker-compose.dev.yml fairdata-conf
```

# 5. Deploy the IDA dev stack

Create the IDA stack for Docker Swarm by running the following command at the `fairdata-ida` repository root:

```
cd fairdata-ida
docker stack deploy --with-registry-auth --resolve-image always -c docker-compose.yml fairdata-dev
```

If you go to `ida.fd-dev.csc.fi`, you should now see:

```
Error
It looks like you are trying to reinstall your Nextcloud...
```

# 6. Initialize IDA nextcloud

Finally, the Nextcloud application can be initialized using a utility script included in ida repository. Run the following command at
the `fairdata-ida` repository root:

```
./init_dev.sh
```

Note: if you have restarted your workstation and are seeing issues with NextCloud when visiting `ida.fd-dev.csc.fi`, you may need to rerun this script.

# 7. Login to https://ida.fd-dev.csc.fi

You should now be able to login to `https://ida.fd-dev.csc.fi` using the test account(s), for instance:
```
test_user_a
test
```
