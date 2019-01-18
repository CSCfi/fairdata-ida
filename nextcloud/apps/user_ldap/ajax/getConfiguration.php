<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Christopher Schäpers <kondou@ts.unde.re>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Morris Jobke <hey@morrisjobke.de>
 *
 * @license AGPL-3.0
 *
 * This code is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License, version 3,
 * as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License, version 3,
 * along with this program.  If not, see <http://www.gnu.org/licenses/>
 *
 */

// Check user and app status
OCP\JSON::checkAdminUser();
OCP\JSON::checkAppEnabled('user_ldap');
OCP\JSON::callCheck();

$prefix = (string)$_POST['ldap_serverconfig_chooser'];
$ldapWrapper = new OCA\User_LDAP\LDAP();
$connection = new \OCA\User_LDAP\Connection($ldapWrapper, $prefix);
$configuration = $connection->getConfiguration();
if (isset($configuration['ldap_agent_password']) && $configuration['ldap_agent_password'] !== '') {
	// hide password
	$configuration['ldap_agent_password'] = '**PASSWORD SET**';
}
OCP\JSON::success(array('configuration' => $configuration));
