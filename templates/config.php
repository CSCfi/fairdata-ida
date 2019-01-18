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
$CONFIG = array(
    'datadirectory'                     => '/mnt/storage_vol01/ida',
    'overwrite.cli.url'                 => 'http://localhost',
    'dbtype'                            => 'mysql',
    'theme'                             => 'ida',
    'htaccess.RewriteBase'              => '/',
    'knowledgebaseenabled'              => false,
    'enable_avatars'                    => false,
    'allow_user_to_change_display_name' => false,
    'updatechecker'                     => false,
    'enable_previews'                   => false,
    'filelocking.enabled'               => false,
    'integrity.check.disabled'          => true,
    'skeletondirectory'                 => '',
    'trusted_domains'                   => array(
        0 => 'localhost',
    ),
    'apps_paths'                        => array(
        0 => array(
            'path'     => '/var/ida/nextcloud/apps',
            'url'      => '/apps',
            'writable' => false,
        ),
        1 => array(
            'path'     => '/var/ida/nextcloud/custom_apps',
            'url'      => '/custom_apps',
            'writable' => true,
        ),
    ),
    'ida'                               => array(
        'PROJECT_USER_PASS'  => 'test',
        'RABBIT_HOST'        => 'localhost',
        'RABBIT_PORT'        => 5672,
        'RABBIT_VHOST'       => 'ida-vhost',
        'RABBIT_WORKER_PASS' => 'test',
        'RABBIT_WORKER_USER' => 'worker',
        'URL_BASE_FILE'      => 'http://localhost/remote.php/webdav',
        'URL_BASE_SHARE'     => 'http://localhost/ocs/v1.php/apps/files_sharing/api/v1/shares',
        'URL_BASE_GROUP'     => 'http://localhost/ocs/v1.php/cloud/groups',
        'SIMULATE_AGENTS'    => 0, // If set to 1, the Nextcloud app will automatically mark all actions as complete
    ),
    'debug'                             => false,
    'logfile'                           => '/mnt/storage_vol01/log/nextcloud.log',
    'loglevel'                          => 2,
    'maintenance'                       => false,
);
