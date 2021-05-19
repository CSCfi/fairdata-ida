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

install_shell_config() {
  echo "1. IDA NextCloud container: Installing config.sh..."
  docker cp ../fairdata-secrets/ida/config/config.dev.sh $(docker ps -q -f name=ida-nextcloud):/var/ida-config/config.sh > /dev/null
  docker exec -it $(docker ps -q -f name=ida-nextcloud) chown www-data:www-data /var/ida-config/config.sh > /dev/null
}

install_nextcloud() {
  echo "2. IDA NextCloud container: Installing Nextcloud..."
  docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) cp /var/ida/nextcloud/.htaccess /tmp/.htaccess # > /dev/null
  docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ maintenance:install --database "pgsql" --database-name "nextcloud" --database-host "ida-db" --database-user "nextcloud" --database-pass "nextcloud" --admin-user "admin" --admin-pass "admin" --data-dir "/mnt/storage_vol01/ida" > /dev/null
  docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) mv /tmp/.htaccess /var/ida/nextcloud/.htaccess # > /dev/null
}

install_php_config() {
  echo "3. IDA NextCloud container: Installing config.php..."
  docker cp ../fairdata-secrets/ida/config/config.dev.php $(docker ps -q -f name=ida-nextcloud):/var/ida-config/config.php > /dev/null
  docker exec -it $(docker ps -q -f name=ida-nextcloud) chown www-data:www-data /var/ida-config/config.php > /dev/null
}

fix_permissions() {
  echo "4. IDA NextCloud container: Fixing file permissions..."
  docker exec -it $(docker ps -q -f name=ida-nextcloud) /var/ida/utils/fix-permissions > /dev/null
  docker exec -it $(docker ps -q -f name=ida-nextcloud) chown 33:33 /mnt/storage_vol01/ida_replication > /dev/null
}

enable_nextcloud_apps() {
  echo "5. IDA NextCloud container: Enabling Nextcloud apps..."
  docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ app:enable ida > /dev/null
  docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ app:enable idafirstrunwizard > /dev/null
  docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) php /var/ida/nextcloud/occ app:enable admin_audit > /dev/null
}

index_database() {
  echo "6. Database container: Indexing database..."
  docker cp ./utils/create_db_indices.pgsql $(docker ps -q -f name=ida-db):/tmp/create_db_indices.pgsql > /dev/null
  docker exec -u www-data -it $(docker ps -q -f name=ida-db) psql -f /tmp/create_db_indices.pgsql nextcloud > /dev/null
}

initialize_rabbitmq() {
  echo "7. Metadata & replication containers: Initializing rabbitmq and restarting containers..."
  docker exec -it $(docker ps -q -f name=ida-metadata) python -m agents.utils.rabbitmq > /dev/null
  METADATA=$(docker ps -q -f name=ida-metadata)
  REPLICATION=$(docker ps -q -f name=ida-replication)
  docker kill $METADATA $REPLICATION > /dev/null
  docker rm $METADATA $REPLICATION > /dev/null
}

initialize_test_accounts () {
  echo "8. IDA NextCloud container: Initializing test accounts for development environment..."
  docker exec -u www-data -it $(docker ps -q -f name=ida-nextcloud) /var/ida/tests/utils/initialize_test_accounts > /dev/null
}

install_shell_config
install_nextcloud
install_php_config
fix_permissions
enable_nextcloud_apps
index_database
initialize_rabbitmq
initialize_test_accounts
