#!/bin/bash
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

# Note: This script assumes that it is being executed at the root of the fairdata-ida
# repository and that the fairdata-secrets repository is cloned as a sibling directory
# of the fairdata-ida repository. If not, the pathname below should be edited accordingly.

FAIRDATA_SECRETS="../fairdata-secrets"

echo "Cleaning up any previous installation configurations..."
if [ -d ./config ]
then
    rm -fr ./config
fi

if [ -d ./nextcloud/config ]
then
    rm -fr ./nextcloud/config
fi

if [ -d ./venv ]
then
    rm -fr ./venv
fi

echo "IDA NextCloud container: Installing config.sh..."
docker exec -it $(docker ps -q -f name=ida-nextcloud) mkdir /var/ida/config > /dev/null
docker cp $FAIRDATA_SECRETS/ida/config/config.dev.sh $(docker ps -q -f name=ida-nextcloud):/var/ida/config/config.sh > /dev/null
docker exec -it $(docker ps -q -f name=ida-nextcloud) chown -R www-data:www-data /var/ida/config > /dev/null

echo "IDA NextCloud container: Installing Nextcloud..."
docker exec -it $(docker ps -q -f name=ida-nextcloud) mkdir /var/ida/nextcloud/config > /dev/null
docker exec -it $(docker ps -q -f name=ida-nextcloud) chown www-data:www-data /var/ida/nextcloud/config > /dev/null
docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) cp /var/ida/nextcloud/.htaccess /tmp/.htaccess > /dev/null
docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ maintenance:install --database "pgsql" --database-name "nextcloud" --database-host "ida-db" --database-user "nextcloud" --database-pass "nextcloud" --admin-user "admin" --admin-pass "admin" --data-dir "/mnt/storage_vol01/ida" #> /dev/null
docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) mv /tmp/.htaccess /var/ida/nextcloud/.htaccess > /dev/null

echo "IDA NextCloud container: Installing Nextcloud config.php..."
docker cp $FAIRDATA_SECRETS/ida/config/config.dev.php $(docker ps -q -f name=ida-nextcloud):/var/ida/nextcloud/config/config.php > /dev/null
docker exec -it $(docker ps -q -f name=ida-nextcloud) chown -R www-data:www-data /var/ida/nextcloud/config > /dev/null

echo "IDA NextCloud container: Enabling essential Nextcloud apps..."
docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ app:enable files_sharing > /dev/null
docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ app:enable admin_audit > /dev/null
docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ app:enable ida > /dev/null
docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ app:enable idafirstrunwizard > /dev/null

echo "IDA NetxCloud container: Disabling unused Nextcloud apps..."
docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) /var/ida/utils/disable_nextcloud_apps > /dev/null

echo "Database container: Adding optimization indices to database..."
docker cp ./utils/create_db_indices.pgsql $(docker ps -q -f name=ida-db):/tmp/create_db_indices.pgsql > /dev/null
docker exec -u www-data -it $(docker ps -q -f name=ida-db) psql -f /tmp/create_db_indices.pgsql nextcloud > /dev/null

echo "Metadata & replication containers: Initializing rabbitmq and restarting containers..."
docker exec -it $(docker ps -q -f name=ida-metadata) python -m agents.utils.rabbitmq > /dev/null
METADATA=$(docker ps -q -f name=ida-metadata)
REPLICATION=$(docker ps -q -f name=ida-replication)
docker kill $METADATA $REPLICATION > /dev/null
docker rm $METADATA $REPLICATION > /dev/null

echo "IDA NextCloud container: Initializing Python3 virtual environment..."
docker cp requirements.txt $(docker ps -q -f name=ida-nextcloud):/var/ida/requirements.txt > /dev/null
docker exec -it $(docker ps -q -f name=ida-nextcloud) /var/ida/utils/initialize_venv > /dev/null

echo "IDA NextCloud container: Fixing file ownership and permissions..."
docker exec -it $(docker ps -q -f name=ida-nextcloud) /var/ida/utils/fix-permissions > /dev/null
docker exec -it $(docker ps -q -f name=ida-nextcloud) chown 33:33 /mnt/storage_vol01/ida_replication > /dev/null
