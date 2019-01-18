<?php
/**
 * @copyright Copyright (c) 2016 Joas Schilling <coding@schilljs.com>
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

namespace OCA\DAV\CalDAV\Activity\Provider;

use OCP\Activity\IEvent;
use OCP\Activity\IProvider;
use OCP\IUser;
use OCP\IUserManager;

abstract class Base implements IProvider {

	/** @var IUserManager */
	protected $userManager;

	/** @var string[] cached displayNames - key is the UID and value the displayname */
	protected $displayNames = [];

	/**
	 * @param IUserManager $userManager
	 */
	public function __construct(IUserManager $userManager) {
		$this->userManager = $userManager;
	}

	/**
	 * @param IEvent $event
	 * @param string $subject
	 * @param array $parameters
	 */
	protected function setSubjects(IEvent $event, $subject, array $parameters) {
		$placeholders = $replacements = [];
		foreach ($parameters as $placeholder => $parameter) {
			$placeholders[] = '{' . $placeholder . '}';
			$replacements[] = $parameter['name'];
		}

		$event->setParsedSubject(str_replace($placeholders, $replacements, $subject))
			->setRichSubject($subject, $parameters);
	}

	/**
	 * @param array $eventData
	 * @return array
	 */
	protected function generateObjectParameter($eventData) {
		if (!is_array($eventData) || !isset($eventData['id']) || !isset($eventData['name'])) {
			throw new \InvalidArgumentException();
		};

		return [
			'type' => 'calendar-event',
			'id' => $eventData['id'],
			'name' => $eventData['name'],
		];
	}

	/**
	 * @param int $id
	 * @param string $name
	 * @return array
	 */
	protected function generateCalendarParameter($id, $name) {
		return [
			'type' => 'calendar',
			'id' => $id,
			'name' => $name,
		];
	}

	/**
	 * @param string $id
	 * @return array
	 */
	protected function generateGroupParameter($id) {
		return [
			'type' => 'group',
			'id' => $id,
			'name' => $id,
		];
	}

	/**
	 * @param string $uid
	 * @return array
	 */
	protected function generateUserParameter($uid) {
		if (!isset($this->displayNames[$uid])) {
			$this->displayNames[$uid] = $this->getDisplayName($uid);
		}

		return [
			'type' => 'user',
			'id' => $uid,
			'name' => $this->displayNames[$uid],
		];
	}

	/**
	 * @param string $uid
	 * @return string
	 */
	protected function getDisplayName($uid) {
		$user = $this->userManager->get($uid);
		if ($user instanceof IUser) {
			return $user->getDisplayName();
		} else {
			return $uid;
		}
	}
}
