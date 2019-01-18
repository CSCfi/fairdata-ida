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
use OCP\Activity\IEventMerger;
use OCP\Activity\IManager;
use OCP\IL10N;
use OCP\IURLGenerator;
use OCP\IUserManager;
use OCP\L10N\IFactory;

class Event extends Base {

	const SUBJECT_OBJECT_ADD = 'object_add';
	const SUBJECT_OBJECT_UPDATE = 'object_update';
	const SUBJECT_OBJECT_DELETE = 'object_delete';

	/** @var IFactory */
	protected $languageFactory;

	/** @var IL10N */
	protected $l;

	/** @var IURLGenerator */
	protected $url;

	/** @var IManager */
	protected $activityManager;

	/** @var IEventMerger */
	protected $eventMerger;

	/**
	 * @param IFactory $languageFactory
	 * @param IURLGenerator $url
	 * @param IManager $activityManager
	 * @param IUserManager $userManager
	 * @param IEventMerger $eventMerger
	 */
	public function __construct(IFactory $languageFactory, IURLGenerator $url, IManager $activityManager, IUserManager $userManager, IEventMerger $eventMerger) {
		parent::__construct($userManager);
		$this->languageFactory = $languageFactory;
		$this->url = $url;
		$this->activityManager = $activityManager;
		$this->eventMerger = $eventMerger;
	}

	/**
	 * @param string $language
	 * @param IEvent $event
	 * @param IEvent|null $previousEvent
	 * @return IEvent
	 * @throws \InvalidArgumentException
	 * @since 11.0.0
	 */
	public function parse($language, IEvent $event, IEvent $previousEvent = null) {
		if ($event->getApp() !== 'dav' || $event->getType() !== 'calendar_event') {
			throw new \InvalidArgumentException();
		}

		$this->l = $this->languageFactory->get('dav', $language);

		if ($this->activityManager->getRequirePNG()) {
			$event->setIcon($this->url->getAbsoluteURL($this->url->imagePath('core', 'places/calendar-dark.png')));
		} else {
			$event->setIcon($this->url->getAbsoluteURL($this->url->imagePath('core', 'places/calendar-dark.svg')));
		}

		if ($event->getSubject() === self::SUBJECT_OBJECT_ADD . '_event') {
			$subject = $this->l->t('{actor} created event {event} in calendar {calendar}');
		} else if ($event->getSubject() === self::SUBJECT_OBJECT_ADD . '_event_self') {
			$subject = $this->l->t('You created event {event} in calendar {calendar}');
		} else if ($event->getSubject() === self::SUBJECT_OBJECT_DELETE . '_event') {
			$subject = $this->l->t('{actor} deleted event {event} from calendar {calendar}');
		} else if ($event->getSubject() === self::SUBJECT_OBJECT_DELETE . '_event_self') {
			$subject = $this->l->t('You deleted event {event} from calendar {calendar}');
		} else if ($event->getSubject() === self::SUBJECT_OBJECT_UPDATE . '_event') {
			$subject = $this->l->t('{actor} updated event {event} in calendar {calendar}');
		} else if ($event->getSubject() === self::SUBJECT_OBJECT_UPDATE . '_event_self') {
			$subject = $this->l->t('You updated event {event} in calendar {calendar}');
		} else {
			throw new \InvalidArgumentException();
		}

		$parsedParameters = $this->getParameters($event);
		$this->setSubjects($event, $subject, $parsedParameters);

		$event = $this->eventMerger->mergeEvents('event', $event, $previousEvent);

		return $event;
	}

	/**
	 * @param IEvent $event
	 * @return array
	 */
	protected function getParameters(IEvent $event) {
		$subject = $event->getSubject();
		$parameters = $event->getSubjectParameters();

		switch ($subject) {
			case self::SUBJECT_OBJECT_ADD . '_event':
			case self::SUBJECT_OBJECT_DELETE . '_event':
			case self::SUBJECT_OBJECT_UPDATE . '_event':
				return [
					'actor' => $this->generateUserParameter($parameters[0]),
					'calendar' => $this->generateCalendarParameter($event->getObjectId(), $parameters[1]),
					'event' => $this->generateObjectParameter($parameters[2]),
				];
			case self::SUBJECT_OBJECT_ADD . '_event_self':
			case self::SUBJECT_OBJECT_DELETE . '_event_self':
			case self::SUBJECT_OBJECT_UPDATE . '_event_self':
				return [
					'calendar' => $this->generateCalendarParameter($event->getObjectId(), $parameters[1]),
					'event' => $this->generateObjectParameter($parameters[2]),
				];
		}

		throw new \InvalidArgumentException();
	}
}
