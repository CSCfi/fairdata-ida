<?php

/**
 * @author Christoph Wurst <christoph@winzerhof-wurst.at>
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

namespace OCA\TwoFactorBackupCodes\Service;

use BadMethodCallException;
use OCA\TwoFactorBackupCodes\Db\BackupCode;
use OCA\TwoFactorBackupCodes\Db\BackupCodeMapper;
use OCP\Activity\IManager;
use OCP\ILogger;
use OCP\IUser;
use OCP\Security\IHasher;
use OCP\Security\ISecureRandom;

class BackupCodeStorage {

	private static $CODE_LENGTH = 16;

	/** @var BackupCodeMapper */
	private $mapper;

	/** @var IHasher */
	private $hasher;

	/** @var ISecureRandom */
	private $random;

	/** @var IManager */
	private $activityManager;

	/** @var ILogger */
	private $logger;

	/**
	 * @param BackupCodeMapper $mapper
	 * @param ISecureRandom $random
	 * @param IHasher $hasher
	 * @param IManager $activityManager
	 * @param ILogger $logger
	 */
	public function __construct(BackupCodeMapper $mapper, ISecureRandom $random, IHasher $hasher,
		IManager $activityManager, ILogger $logger) {
		$this->mapper = $mapper;
		$this->hasher = $hasher;
		$this->random = $random;
		$this->activityManager = $activityManager;
		$this->logger = $logger;
	}

	/**
	 * @param IUser $user
	 * @return string[]
	 */
	public function createCodes(IUser $user, $number = 10) {
		$result = [];

		// Delete existing ones
		$this->mapper->deleteCodes($user);

		$uid = $user->getUID();
		foreach (range(1, min([$number, 20])) as $i) {
			$code = $this->random->generate(self::$CODE_LENGTH, ISecureRandom::CHAR_UPPER . ISecureRandom::CHAR_DIGITS);

			$dbCode = new BackupCode();
			$dbCode->setUserId($uid);
			$dbCode->setCode($this->hasher->hash($code));
			$dbCode->setUsed(0);
			$this->mapper->insert($dbCode);

			array_push($result, $code);
		}

		$this->publishEvent($user, 'codes_generated');

		return $result;
	}

	/**
	 * Push an event the user's activity stream
	 *
	 * @param IUser $user
	 * @param string $event
	 */
	private function publishEvent(IUser $user, $event) {
		$activity = $this->activityManager->generateEvent();
		$activity->setApp('twofactor_backupcodes')
			->setType('security')
			->setAuthor($user->getUID())
			->setAffectedUser($user->getUID())
			->setSubject($event);
		try {
			$this->activityManager->publish($activity);
		} catch (BadMethodCallException $e) {
			$this->logger->warning('could not publish backup code creation activity', ['app' => 'twofactor_backupcodes']);
			$this->logger->logException($e, ['app' => 'twofactor_backupcodes']);
		}
	}

	/**
	 * @param IUser $user
	 * @return bool
	 */
	public function hasBackupCodes(IUser $user) {
		$codes = $this->mapper->getBackupCodes($user);
		return count($codes) > 0;
	}

	/**
	 * @param IUser $user
	 * @return array
	 */
	public function getBackupCodesState(IUser $user) {
		$codes = $this->mapper->getBackupCodes($user);
		$total = count($codes);
		$used = 0;
		array_walk($codes, function (BackupCode $code) use (&$used) {
			if (1 === (int) $code->getUsed()) {
				$used++;
			}
		});
		return [
			'enabled' => $total > 0,
			'total' => $total,
			'used' => $used,
		];
	}

	/**
	 * @param IUser $user
	 * @param string $code
	 * @return bool
	 */
	public function validateCode(IUser $user, $code) {
		$dbCodes = $this->mapper->getBackupCodes($user);

		foreach ($dbCodes as $dbCode) {
			if (0 === (int) $dbCode->getUsed() && $this->hasher->verify($code, $dbCode->getCode())) {
				$dbCode->setUsed(1);
				$this->mapper->update($dbCode);
				return true;
			}
		}
		return false;
	}

}
