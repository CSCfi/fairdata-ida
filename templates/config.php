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
<?php
$CONFIG = array (
  'passwordsalt' => '****',
  'secret' => '****',
  'trusted_domains' => array (
    0 => 'ida.fairdata.fi',
  ),
  'datadirectory' => '/mnt/storage_vol01/ida',
  'overwrite.cli.url' => 'https://ida.fairdata.fi',
  'htaccess.RewriteBase' => '/',
  'dbtype' => 'pgsql',
  'version' => '16.0.3.0',
  'dbname' => 'nextcloud',
  'dbhost' => 'ida.fairdata.fi',
  'dbport' => '',
  'dbtableprefix' => 'oc_',
  'dbuser' => 'nextcloud',
  'dbpassword' => '****',
  'knowledgebaseenabled' => false,
  'enable_avatars' => false,
  'allow_user_to_change_display_name' => false,
  'skeletondirectory' => '',
  'updatechecker' => false,
  'appstoreenabled' => false,
  'enable_previews' => false,
  'logfile' => '/mnt/storage_vol01/log/nextcloud.log',
  'loglevel' => 0,
  'log_rotate_size' => 0,
  'cron_log' => true,
  'integrity.check.disabled' => true,
  'filelocking.enabled' => false,
  'theme' => 'ida',
  'ida' => array (
    'IDA_ENVIRONMENT' => 'PRODUCTION',
    'BATCH_ACTION_TOKEN' => '****',
    'PROJECT_USER_PASS' => '****',
    'RABBIT_HOST' => 'ida.fairdata.fi',
    'RABBIT_PORT' => 5672,
    'RABBIT_VHOST' => 'ida-vhost',
    'RABBIT_WORKER_USER' => 'worker',
    'RABBIT_WORKER_PASS' => '****',
    'FILE_API' => 'https://ida.fairdata.fi/remote.php/webdav',
    'SHARE_API' => 'https://ida.fairdata.fi/ocs/v1.php/apps/files_sharing/api/v1/shares',
    'GROUP_API' => 'https://ida.fairdata.fi/ocs/v1.php/cloud/groups',
    'SIMULATE_AGENTS' => false,
  ),
  'IDA_HOME' => 'https://ida.fairdata.fi',
  'LOCAL_LOGIN' => false,        // set to true to always display local Nextcloud login (e.g. idaman, dev/test)
  'SSO_AUTHENTICATION' => true,  // set to true to always display SSO login (other SSO_ variables must be defined)
  'SSO_DOMAIN' => 'fairdata.fi',
  'SSO_API' => 'https://sso.fairdata.fi',
  'SSO_KEY' => '****', // Encryption key for JSON Web Tokens
  'SSO_PASSWORD' => '****', // Token used for SSO authenticated Nextcloud sessions
  'installed' => true,
  'instanceid' => '****',
  'maintenance' => false,
);
