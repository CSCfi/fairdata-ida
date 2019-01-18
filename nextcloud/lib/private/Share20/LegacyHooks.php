<?php
/**
 * @copyright 2017, Roeland Jago Douma <roeland@famdouma.nl>
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
namespace OC\Share20;

use OCP\Share\IShare;
use Symfony\Component\EventDispatcher\EventDispatcher;
use Symfony\Component\EventDispatcher\GenericEvent;

class LegacyHooks {
	/** @var EventDispatcher */
	private $eventDispatcher;

	/**
	 * LegacyHooks constructor.
	 *
	 * @param EventDispatcher $eventDispatcher
	 */
	public function __construct(EventDispatcher $eventDispatcher) {
		$this->eventDispatcher = $eventDispatcher;

		$this->eventDispatcher->addListener('OCP\Share::preUnshare', [$this, 'preUnshare']);
		$this->eventDispatcher->addListener('OCP\Share::postUnshare', [$this, 'postUnshare']);
	}

	/**
	 * @param GenericEvent $e
	 */
	public function preUnshare(GenericEvent $e) {
		/** @var IShare $share */
		$share = $e->getSubject();

		$formatted = $this->formatHookParams($share);
		\OC_Hook::emit('OCP\Share', 'pre_unshare', $formatted);
	}

	/**
	 * @param GenericEvent $e
	 */
	public function postUnshare(GenericEvent $e) {
		/** @var IShare $share */
		$share = $e->getSubject();

		$formatted = $this->formatHookParams($share);

		/** @var IShare[] $deletedShares */
		$deletedShares = $e->getArgument('deletedShares');

		$formattedDeletedShares = array_map(function($share) {
			return $this->formatHookParams($share);
		}, $deletedShares);

		$formatted['deletedShares'] = $formattedDeletedShares;

		\OC_Hook::emit('OCP\Share', 'post_unshare', $formatted);
	}

	private function formatHookParams(IShare $share) {
		// Prepare hook
		$shareType = $share->getShareType();
		$sharedWith = '';
		if ($shareType === \OCP\Share::SHARE_TYPE_USER ||
			$shareType === \OCP\Share::SHARE_TYPE_GROUP ||
			$shareType === \OCP\Share::SHARE_TYPE_REMOTE) {
			$sharedWith = $share->getSharedWith();
		}

		$hookParams = [
			'id' => $share->getId(),
			'itemType' => $share->getNodeType(),
			'itemSource' => $share->getNodeId(),
			'shareType' => $shareType,
			'shareWith' => $sharedWith,
			'itemparent' => method_exists($share, 'getParent') ? $share->getParent() : '',
			'uidOwner' => $share->getSharedBy(),
			'fileSource' => $share->getNodeId(),
			'fileTarget' => $share->getTarget()
		];
		return $hookParams;
	}
}
