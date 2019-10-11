<?php
declare(strict_types=1);
/**
 * @copyright Copyright (c) 2018, Roeland Jago Douma <roeland@famdouma.nl>
 *
 * @author Roeland Jago Douma <roeland@famdouma.nl>
 *
 * @license GNU AGPL version 3 or any later version
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

namespace OCA\TwoFactorBackupCodes\Listener;

use OCA\TwoFactorBackupCodes\Event\CodesGenerated;
use OCP\Notification\IManager;
use Symfony\Component\EventDispatcher\Event;

class ClearNotifications implements IListener {

	/** @var IManager */
	private $manager;

	public function __construct(IManager $manager) {
		$this->manager = $manager;
	}

	public function handle(Event $event) {
		if (!($event instanceof CodesGenerated)) {
			return;
		}

		$notification = $this->manager->createNotification();
		$notification->setApp('twofactor_backupcodes')
			->setUser($event->getUser()->getUID())
			->setObject('create', 'codes');
		$this->manager->markProcessed($notification);
	}
}
