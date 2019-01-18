<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Joas Schilling <coding@schilljs.com>
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

namespace OCA\Activity;

use OCA\Activity\Extension\LegacyParser;
use OCA\Activity\Parameter\IParameter;
use OCP\Activity\IEvent;
use OCP\Activity\IManager;
use OCP\IL10N;

class GroupHelper {
	/** @var IEvent[] */
	protected $event = [];
	/** @var int */
	protected $lastEvent = 0;

	/** @var bool */
	protected $allowGrouping;

	/** @var IL10N */
	protected $l;

	/** @var \OCP\Activity\IManager */
	protected $activityManager;

	/** @var \OCA\Activity\DataHelper */
	protected $dataHelper;

	/** @var LegacyParser */
	protected $legacyParser;

	/**
	 * @param IL10N $l
	 * @param \OCP\Activity\IManager $activityManager
	 * @param \OCA\Activity\DataHelper $dataHelper
	 * @param LegacyParser $legacyParser
	 */
	public function __construct(IL10N $l, IManager $activityManager, DataHelper $dataHelper, LegacyParser $legacyParser) {
		$this->allowGrouping = true;

		$this->l = $l;
		$this->activityManager = $activityManager;
		$this->dataHelper = $dataHelper;
		$this->legacyParser = $legacyParser;
	}

	/**
	 * @param string $user
	 */
	public function setUser($user) {
		$this->dataHelper->setUser($user);
	}

	/**
	 * @param IL10N $l
	 */
	public function setL10n(IL10N $l) {
		$this->l = $l;
		$this->dataHelper->setL10n($l);
	}

	/**
	 * Add an activity to the internal array
	 *
	 * @param array $activity
	 */
	public function addActivity($activity) {
		$id = (int) $activity['activity_id'];
		$event = $this->arrayToEvent($activity);
		$language = $this->l->getLanguageCode();

		foreach ($this->activityManager->getProviders() as $provider) {
			try {
				$this->activityManager->setFormattingObject($event->getObjectType(), $event->getObjectId());
				if ($this->allowGrouping && $this->lastEvent !== 0 && isset($this->event[$this->lastEvent])) {
					$event = $provider->parse($language, $event, $this->event[$this->lastEvent]);
				} else {
					$event = $provider->parse($language, $event);
				}
				$this->activityManager->setFormattingObject('', 0);

				$child = $event->getChildEvent();
				if ($child instanceof IEvent) {
					unset($this->event[$this->lastEvent]);
				}
			} catch (\InvalidArgumentException $e) {
			}
		}

		if (!$event->getParsedSubject()) {
			try {
				$this->activityManager->setFormattingObject($event->getObjectType(), $event->getObjectId());
				$event = $this->legacyParser->parse($language, $event);
				$this->activityManager->setFormattingObject('', 0);
			} catch (\InvalidArgumentException $e) {
				\OC::$server->getLogger()->debug('Failed to parse activity');
				return;
			}
		}

		$this->event[$id] = $event;
		$this->lastEvent = $id;
	}

	/**
	 * Get the prepared activities
	 *
	 * @return array translated activities ready for use
	 */
	public function getActivities() {
		$return = [];
		foreach ($this->event as $id => $event) {
			$return[] = $this->eventToArray($event, $id);
		}
		$this->event = [];

		return $return;
	}

	/**
	 * @param array $row
	 * @return IEvent
	 */
	protected function arrayToEvent(array $row) {
		$event = $this->activityManager->generateEvent();
		$event->setApp((string) $row['app'])
			->setType((string) $row['type'])
			->setAffectedUser((string) $row['affecteduser'])
			->setAuthor((string) $row['user'])
			->setTimestamp((int) $row['timestamp'])
			->setSubject((string) $row['subject'], json_decode($row['subjectparams'], true))
			->setMessage((string) $row['message'], json_decode($row['messageparams'], true))
			->setObject((string) $row['object_type'], (int) $row['object_id'], (string) $row['file'])
			->setLink((string) $row['link']);

		return $event;
	}

	/**
	 * @param IEvent $event
	 * @return array
	 */
	protected function eventToArray(IEvent $event, $id) {
		return [
			'activity_id' => $id,
			'app' => $event->getApp(),
			'type' => $event->getType(),
			'affecteduser' => $event->getAffectedUser(),
			'user' => $event->getAuthor(),
			'timestamp' => $event->getTimestamp(),
			'subject' => $event->getParsedSubject(),
			'subject_rich' => [
				(string) $event->getRichSubject(),
				(array) $event->getRichSubjectParameters(),
			],
			'message' => $event->getParsedMessage(),
			'message_rich' => [
				(string) $event->getRichMessage(),
				(array) $event->getRichMessageParameters(),
			],
			'object_type' => $event->getObjectType(),
			'object_id' => $event->getObjectId(),
			'object_name' => $event->getObjectName(),
			'objects' => $this->getObjectsFromChildren($event),
			'link' => $event->getLink(),
			'icon' => $event->getIcon(),
		];
	}

	/**
	 * @param IEvent $event
	 * @return array
	 */
	protected function getObjectsFromChildren(IEvent $event) {
		$child = $event->getChildEvent();
		if ($child instanceof IEvent) {
			$objects = $this->getObjectsFromChildren($child);
			$objects[$event->getObjectId()] = $event->getObjectName();
			return $objects;
		} else {
			return [$event->getObjectId() => $event->getObjectName()];
		}
	}
}
