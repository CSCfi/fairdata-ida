<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Georg Ehrke <georg@owncloud.com>
 * @author Kamil Domanski <kdomanski@kdemail.net>
 * @author Lukas Reschke <lukas@statuscode.ch>
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
OCP\JSON::checkAdminUser();
OCP\JSON::callCheck();

$lastConfirm = (int) \OC::$server->getSession()->get('last-password-confirm');
if ($lastConfirm < (time() - 30 * 60 + 15)) { // allow 15 seconds delay
	$l = \OC::$server->getL10N('core');
	OC_JSON::error(array( 'data' => array( 'message' => $l->t('Password confirmation is required'))));
	exit();
}

if (!array_key_exists('appid', $_POST)) {
	OC_JSON::error();
	exit;
}

$appIds = (array)$_POST['appid'];
foreach($appIds as $appId) {
	$appId = OC_App::cleanAppId($appId);
	OC_App::disable($appId);
}
OC_JSON::success();
