<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Jörn Friedrich Dreyer <jfd@butonic.de>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Michael U <mdusher@users.noreply.github.com>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Robin McCorkell <robin@mccorkell.me.uk>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
 * @author Vincent Chan <plus.vincchan@gmail.com>
 * @author Volkan Gezer <volkangezer@gmail.com>
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

namespace OC\User;

use OC\Hooks\PublicEmitter;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IUser;
use OCP\IUserBackend;
use OCP\IUserManager;
use OCP\IConfig;
use OCP\UserInterface;

/**
 * Class Manager
 *
 * Hooks available in scope \OC\User:
 * - preSetPassword(\OC\User\User $user, string $password, string $recoverPassword)
 * - postSetPassword(\OC\User\User $user, string $password, string $recoverPassword)
 * - preDelete(\OC\User\User $user)
 * - postDelete(\OC\User\User $user)
 * - preCreateUser(string $uid, string $password)
 * - postCreateUser(\OC\User\User $user, string $password)
 * - change(\OC\User\User $user)
 *
 * @package OC\User
 */
class Manager extends PublicEmitter implements IUserManager {
	/**
	 * @var \OCP\UserInterface[] $backends
	 */
	private $backends = array();

	/**
	 * @var \OC\User\User[] $cachedUsers
	 */
	private $cachedUsers = array();

	/**
	 * @var \OCP\IConfig $config
	 */
	private $config;

	/**
	 * @param \OCP\IConfig $config
	 */
	public function __construct(IConfig $config) {
		$this->config = $config;
		$cachedUsers = &$this->cachedUsers;
		$this->listen('\OC\User', 'postDelete', function ($user) use (&$cachedUsers) {
			/** @var \OC\User\User $user */
			unset($cachedUsers[$user->getUID()]);
		});
	}

	/**
	 * Get the active backends
	 * @return \OCP\UserInterface[]
	 */
	public function getBackends() {
		return $this->backends;
	}

	/**
	 * register a user backend
	 *
	 * @param \OCP\UserInterface $backend
	 */
	public function registerBackend($backend) {
		$this->backends[] = $backend;
	}

	/**
	 * remove a user backend
	 *
	 * @param \OCP\UserInterface $backend
	 */
	public function removeBackend($backend) {
		$this->cachedUsers = array();
		if (($i = array_search($backend, $this->backends)) !== false) {
			unset($this->backends[$i]);
		}
	}

	/**
	 * remove all user backends
	 */
	public function clearBackends() {
		$this->cachedUsers = array();
		$this->backends = array();
	}

	/**
	 * get a user by user id
	 *
	 * @param string $uid
	 * @return \OC\User\User|null Either the user or null if the specified user does not exist
	 */
	public function get($uid) {
		if (is_null($uid) || $uid === '' || $uid === false) {
			return null;
		}
		if (isset($this->cachedUsers[$uid])) { //check the cache first to prevent having to loop over the backends
			return $this->cachedUsers[$uid];
		}
		foreach ($this->backends as $backend) {
			if ($backend->userExists($uid)) {
				return $this->getUserObject($uid, $backend);
			}
		}
		return null;
	}

	/**
	 * get or construct the user object
	 *
	 * @param string $uid
	 * @param \OCP\UserInterface $backend
	 * @param bool $cacheUser If false the newly created user object will not be cached
	 * @return \OC\User\User
	 */
	protected function getUserObject($uid, $backend, $cacheUser = true) {
		if (isset($this->cachedUsers[$uid])) {
			return $this->cachedUsers[$uid];
		}

		if (method_exists($backend, 'loginName2UserName')) {
			$loginName = $backend->loginName2UserName($uid);
			if ($loginName !== false) {
				$uid = $loginName;
			}
			if (isset($this->cachedUsers[$uid])) {
				return $this->cachedUsers[$uid];
			}
		}

		$user = new User($uid, $backend, $this, $this->config);
		if ($cacheUser) {
			$this->cachedUsers[$uid] = $user;
		}
		return $user;
	}

	/**
	 * check if a user exists
	 *
	 * @param string $uid
	 * @return bool
	 */
	public function userExists($uid) {
		$user = $this->get($uid);
		return ($user !== null);
	}

	/**
	 * Check if the password is valid for the user
	 *
	 * @param string $loginName
	 * @param string $password
	 * @return mixed the User object on success, false otherwise
	 */
	public function checkPassword($loginName, $password) {
		$result = $this->checkPasswordNoLogging($loginName, $password);

		if ($result === false) {
			\OC::$server->getLogger()->warning('Login failed: \''. $loginName .'\' (Remote IP: \''. \OC::$server->getRequest()->getRemoteAddress(). '\')', ['app' => 'core']);
		}

		return $result;
	}

	/**
	 * Check if the password is valid for the user
	 *
	 * @internal
	 * @param string $loginName
	 * @param string $password
	 * @return mixed the User object on success, false otherwise
	 */
	public function checkPasswordNoLogging($loginName, $password) {
		$loginName = str_replace("\0", '', $loginName);
		$password = str_replace("\0", '', $password);

		foreach ($this->backends as $backend) {
			if ($backend->implementsActions(Backend::CHECK_PASSWORD)) {
				$uid = $backend->checkPassword($loginName, $password);
				if ($uid !== false) {
					return $this->getUserObject($uid, $backend);
				}
			}
		}

		return false;
	}

	/**
	 * search by user id
	 *
	 * @param string $pattern
	 * @param int $limit
	 * @param int $offset
	 * @return \OC\User\User[]
	 */
	public function search($pattern, $limit = null, $offset = null) {
		$users = array();
		foreach ($this->backends as $backend) {
			$backendUsers = $backend->getUsers($pattern, $limit, $offset);
			if (is_array($backendUsers)) {
				foreach ($backendUsers as $uid) {
					$users[$uid] = $this->getUserObject($uid, $backend);
				}
			}
		}

		uasort($users, function ($a, $b) {
			/**
			 * @var \OC\User\User $a
			 * @var \OC\User\User $b
			 */
			return strcmp($a->getUID(), $b->getUID());
		});
		return $users;
	}

	/**
	 * search by displayName
	 *
	 * @param string $pattern
	 * @param int $limit
	 * @param int $offset
	 * @return \OC\User\User[]
	 */
	public function searchDisplayName($pattern, $limit = null, $offset = null) {
		$users = array();
		foreach ($this->backends as $backend) {
			$backendUsers = $backend->getDisplayNames($pattern, $limit, $offset);
			if (is_array($backendUsers)) {
				foreach ($backendUsers as $uid => $displayName) {
					$users[] = $this->getUserObject($uid, $backend);
				}
			}
		}

		usort($users, function ($a, $b) {
			/**
			 * @var \OC\User\User $a
			 * @var \OC\User\User $b
			 */
			return strcmp(strtolower($a->getDisplayName()), strtolower($b->getDisplayName()));
		});
		return $users;
	}

	/**
	 * @param string $uid
	 * @param string $password
	 * @throws \InvalidArgumentException
	 * @return bool|IUser the created user or false
	 */
	public function createUser($uid, $password) {
		$localBackends = [];
		foreach ($this->backends as $backend) {
			if ($backend instanceof Database) {
				// First check if there is another user backend
				$localBackends[] = $backend;
				continue;
			}

			if ($backend->implementsActions(Backend::CREATE_USER)) {
				return $this->createUserFromBackend($uid, $password, $backend);
			}
		}

		foreach ($localBackends as $backend) {
			if ($backend->implementsActions(Backend::CREATE_USER)) {
				return $this->createUserFromBackend($uid, $password, $backend);
			}
		}

		return false;
	}

	/**
	 * @param string $uid
	 * @param string $password
	 * @param UserInterface $backend
	 * @return IUser|null
	 * @throws \InvalidArgumentException
	 */
	public function createUserFromBackend($uid, $password, UserInterface $backend) {
		$l = \OC::$server->getL10N('lib');

		// Check the name for bad characters
		// Allowed are: "a-z", "A-Z", "0-9" and "_.@-'"
		if (preg_match('/[^a-zA-Z0-9 _\.@\-\']/', $uid)) {
			throw new \InvalidArgumentException($l->t('Only the following characters are allowed in a username:'
				. ' "a-z", "A-Z", "0-9", and "_.@-\'"'));
		}
		// No empty username
		if (trim($uid) === '') {
			throw new \InvalidArgumentException($l->t('A valid username must be provided'));
		}
		// No whitespace at the beginning or at the end
		if (trim($uid) !== $uid) {
			throw new \InvalidArgumentException($l->t('Username contains whitespace at the beginning or at the end'));
		}
		// Username only consists of 1 or 2 dots (directory traversal)
		if ($uid === '.' || $uid === '..') {
			throw new \InvalidArgumentException($l->t('Username must not consist of dots only'));
		}
		// No empty password
		if (trim($password) === '') {
			throw new \InvalidArgumentException($l->t('A valid password must be provided'));
		}

		// Check if user already exists
		if ($this->userExists($uid)) {
			throw new \InvalidArgumentException($l->t('The username is already being used'));
		}

		$this->emit('\OC\User', 'preCreateUser', [$uid, $password]);
		$backend->createUser($uid, $password);
		$user = $this->getUserObject($uid, $backend);
		if ($user instanceof IUser) {
			$this->emit('\OC\User', 'postCreateUser', [$user, $password]);
		}
		return $user;
	}

	/**
	 * returns how many users per backend exist (if supported by backend)
	 *
	 * @param boolean $hasLoggedIn when true only users that have a lastLogin
	 *                entry in the preferences table will be affected
	 * @return array|int an array of backend class as key and count number as value
	 *                if $hasLoggedIn is true only an int is returned
	 */
	public function countUsers($hasLoggedIn = false) {
		if ($hasLoggedIn) {
			return $this->countSeenUsers();
		}
		$userCountStatistics = [];
		foreach ($this->backends as $backend) {
			if ($backend->implementsActions(Backend::COUNT_USERS)) {
				$backendUsers = $backend->countUsers();
				if($backendUsers !== false) {
					if($backend instanceof IUserBackend) {
						$name = $backend->getBackendName();
					} else {
						$name = get_class($backend);
					}
					if(isset($userCountStatistics[$name])) {
						$userCountStatistics[$name] += $backendUsers;
					} else {
						$userCountStatistics[$name] = $backendUsers;
					}
				}
			}
		}
		return $userCountStatistics;
	}

	/**
	 * The callback is executed for each user on each backend.
	 * If the callback returns false no further users will be retrieved.
	 *
	 * @param \Closure $callback
	 * @param string $search
	 * @param boolean $onlySeen when true only users that have a lastLogin entry
	 *                in the preferences table will be affected
	 * @since 9.0.0
	 */
	public function callForAllUsers(\Closure $callback, $search = '', $onlySeen = false) {
		if ($onlySeen) {
			$this->callForSeenUsers($callback);
		} else {
			foreach ($this->getBackends() as $backend) {
				$limit = 500;
				$offset = 0;
				do {
					$users = $backend->getUsers($search, $limit, $offset);
					foreach ($users as $uid) {
						if (!$backend->userExists($uid)) {
							continue;
						}
						$user = $this->getUserObject($uid, $backend, false);
						$return = $callback($user);
						if ($return === false) {
							break;
						}
					}
					$offset += $limit;
				} while (count($users) >= $limit);
			}
		}
	}

	/**
	 * returns how many users have logged in once
	 *
	 * @return int
	 * @since 12.0.0
	 */
	public function countDisabledUsers() {
		$queryBuilder = \OC::$server->getDatabaseConnection()->getQueryBuilder();
		$queryBuilder->select($queryBuilder->createFunction('COUNT(*)'))
			->from('preferences')
			->where($queryBuilder->expr()->eq('appid', $queryBuilder->createNamedParameter('core')))
			->andWhere($queryBuilder->expr()->eq('configkey', $queryBuilder->createNamedParameter('enabled')))
			->andWhere($queryBuilder->expr()->eq('configvalue', $queryBuilder->createNamedParameter('false'), IQueryBuilder::PARAM_STR));

		$query = $queryBuilder->execute();

		$result = (int)$query->fetchColumn();
		$query->closeCursor();

		return $result;
	}

	/**
	 * returns how many users have logged in once
	 *
	 * @return int
	 * @since 11.0.0
	 */
	public function countSeenUsers() {
		$queryBuilder = \OC::$server->getDatabaseConnection()->getQueryBuilder();
		$queryBuilder->select($queryBuilder->createFunction('COUNT(*)'))
			->from('preferences')
			->where($queryBuilder->expr()->eq('appid', $queryBuilder->createNamedParameter('login')))
			->andWhere($queryBuilder->expr()->eq('configkey', $queryBuilder->createNamedParameter('lastLogin')))
			->andWhere($queryBuilder->expr()->isNotNull('configvalue'));

		$query = $queryBuilder->execute();

		$result = (int)$query->fetchColumn();
		$query->closeCursor();

		return $result;
	}

	/**
	 * @param \Closure $callback
	 * @since 11.0.0
	 */
	public function callForSeenUsers(\Closure $callback) {
		$limit = 1000;
		$offset = 0;
		do {
			$userIds = $this->getSeenUserIds($limit, $offset);
			$offset += $limit;
			foreach ($userIds as $userId) {
				foreach ($this->backends as $backend) {
					if ($backend->userExists($userId)) {
						$user = $this->getUserObject($userId, $backend, false);
						$return = $callback($user);
						if ($return === false) {
							return;
						}
					}
				}
			}
		} while (count($userIds) >= $limit);
	}

	/**
	 * Getting all userIds that have a listLogin value requires checking the
	 * value in php because on oracle you cannot use a clob in a where clause,
	 * preventing us from doing a not null or length(value) > 0 check.
	 * 
	 * @param int $limit
	 * @param int $offset
	 * @return string[] with user ids
	 */
	private function getSeenUserIds($limit = null, $offset = null) {
		$queryBuilder = \OC::$server->getDatabaseConnection()->getQueryBuilder();
		$queryBuilder->select(['userid'])
			->from('preferences')
			->where($queryBuilder->expr()->eq(
				'appid', $queryBuilder->createNamedParameter('login'))
			)
			->andWhere($queryBuilder->expr()->eq(
				'configkey', $queryBuilder->createNamedParameter('lastLogin'))
			)
			->andWhere($queryBuilder->expr()->isNotNull('configvalue')
			);

		if ($limit !== null) {
			$queryBuilder->setMaxResults($limit);
		}
		if ($offset !== null) {
			$queryBuilder->setFirstResult($offset);
		}
		$query = $queryBuilder->execute();
		$result = [];

		while ($row = $query->fetch()) {
			$result[] = $row['userid'];
		}

		$query->closeCursor();

		return $result;
	}

	/**
	 * @param string $email
	 * @return IUser[]
	 * @since 9.1.0
	 */
	public function getByEmail($email) {
		$userIds = $this->config->getUsersForUserValue('settings', 'email', $email);

		return array_map(function($uid) {
			return $this->get($uid);
		}, $userIds);
	}
}
