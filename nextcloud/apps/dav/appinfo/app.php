<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Björn Schießle <bjoern@schiessle.org>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
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

use OCA\DAV\AppInfo\Application;
use OCA\DAV\CardDAV\CardDavBackend;
use Symfony\Component\EventDispatcher\GenericEvent;

$app = new Application();
$app->registerHooks();

\OC::$server->registerService('CardDAVSyncService', function() use ($app) {
	return $app->getSyncService();
});

$eventDispatcher = \OC::$server->getEventDispatcher();

$eventDispatcher->addListener('OCP\Federation\TrustedServerEvent::remove',
	function(GenericEvent $event) use ($app) {
		/** @var CardDavBackend $cardDavBackend */
		$cardDavBackend = $app->getContainer()->query(CardDavBackend::class);
		$addressBookUri = $event->getSubject();
		$addressBook = $cardDavBackend->getAddressBooksByUri('principals/system/system', $addressBookUri);
		if (!is_null($addressBook)) {
			$cardDavBackend->deleteAddressBook($addressBook['id']);
		}
	}
);

$cm = \OC::$server->getContactsManager();
$cm->register(function() use ($cm, $app) {
	$user = \OC::$server->getUserSession()->getUser();
	if (is_null($user)) {
		return;
	}
	if (\OC::$server->getConfig()->getAppValue('core', 'shareapi_allow_share_dialog_user_enumeration', 'yes') !== 'yes') {
		// Don't include system users
		// This prevents user enumeration in the contacts menu and the mail app
		return;
	}
	$app->setupContactsProvider($cm, $user->getUID());
});
