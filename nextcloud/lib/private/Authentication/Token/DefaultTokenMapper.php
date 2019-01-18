<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Christoph Wurst <christoph@owncloud.com>
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

namespace OC\Authentication\Token;

use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Db\Mapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;
use OCP\IUser;

class DefaultTokenMapper extends Mapper {

	public function __construct(IDBConnection $db) {
		parent::__construct($db, 'authtoken');
	}

	/**
	 * Invalidate (delete) a given token
	 *
	 * @param string $token
	 */
	public function invalidate($token) {
		/* @var $qb IQueryBuilder */
		$qb = $this->db->getQueryBuilder();
		$qb->delete('authtoken')
			->where($qb->expr()->eq('token', $qb->createParameter('token')))
			->setParameter('token', $token)
			->execute();
	}

	/**
	 * @param int $olderThan
	 * @param int $remember
	 */
	public function invalidateOld($olderThan, $remember = IToken::DO_NOT_REMEMBER) {
		/* @var $qb IQueryBuilder */
		$qb = $this->db->getQueryBuilder();
		$qb->delete('authtoken')
			->where($qb->expr()->lt('last_activity', $qb->createNamedParameter($olderThan, IQueryBuilder::PARAM_INT)))
			->andWhere($qb->expr()->eq('type', $qb->createNamedParameter(IToken::TEMPORARY_TOKEN, IQueryBuilder::PARAM_INT)))
			->andWhere($qb->expr()->eq('remember', $qb->createNamedParameter($remember, IQueryBuilder::PARAM_INT)))
			->execute();
	}

	/**
	 * Get the user UID for the given token
	 *
	 * @param string $token
	 * @throws DoesNotExistException
	 * @return DefaultToken
	 */
	public function getToken($token) {
		/* @var $qb IQueryBuilder */
		$qb = $this->db->getQueryBuilder();
		$result = $qb->select('id', 'uid', 'login_name', 'password', 'name', 'type', 'remember', 'token', 'last_activity', 'last_check', 'scope')
			->from('authtoken')
			->where($qb->expr()->eq('token', $qb->createNamedParameter($token)))
			->execute();

		$data = $result->fetch();
		$result->closeCursor();
		if ($data === false) {
			throw new DoesNotExistException('token does not exist');
		}
;
		return DefaultToken::fromRow($data);
	}

	/**
	 * Get the token for $id
	 *
	 * @param string $id
	 * @throws DoesNotExistException
	 * @return DefaultToken
	 */
	public function getTokenById($id) {
		/* @var $qb IQueryBuilder */
		$qb = $this->db->getQueryBuilder();
		$result = $qb->select('id', 'uid', 'login_name', 'password', 'name', 'type', 'token', 'last_activity', 'last_check', 'scope')
			->from('authtoken')
			->where($qb->expr()->eq('id', $qb->createNamedParameter($id)))
			->execute();

		$data = $result->fetch();
		$result->closeCursor();
		if ($data === false) {
			throw new DoesNotExistException('token does not exist');
		};
		return DefaultToken::fromRow($data);
	}

	/**
	 * Get all token of a user
	 *
	 * The provider may limit the number of result rows in case of an abuse
	 * where a high number of (session) tokens is generated
	 *
	 * @param IUser $user
	 * @return DefaultToken[]
	 */
	public function getTokenByUser(IUser $user) {
		/* @var $qb IQueryBuilder */
		$qb = $this->db->getQueryBuilder();
		$qb->select('id', 'uid', 'login_name', 'password', 'name', 'type', 'remember', 'token', 'last_activity', 'last_check', 'scope')
			->from('authtoken')
			->where($qb->expr()->eq('uid', $qb->createNamedParameter($user->getUID())))
			->setMaxResults(1000);
		$result = $qb->execute();
		$data = $result->fetchAll();
		$result->closeCursor();

		$entities = array_map(function ($row) {
			return DefaultToken::fromRow($row);
		}, $data);

		return $entities;
	}

	/**
	 * @param IUser $user
	 * @param int $id
	 */
	public function deleteById(IUser $user, $id) {
		/* @var $qb IQueryBuilder */
		$qb = $this->db->getQueryBuilder();
		$qb->delete('authtoken')
			->where($qb->expr()->eq('id', $qb->createNamedParameter($id)))
			->andWhere($qb->expr()->eq('uid', $qb->createNamedParameter($user->getUID())));
		$qb->execute();
	}

	/**
	 * delete all auth token which belong to a specific client if the client was deleted
	 *
	 * @param string $name
	 */
	public function deleteByName($name) {
		$qb = $this->db->getQueryBuilder();
		$qb->delete('authtoken')
			->where($qb->expr()->eq('name', $qb->createNamedParameter($name), IQueryBuilder::PARAM_STR));
		$qb->execute();
	}

}
