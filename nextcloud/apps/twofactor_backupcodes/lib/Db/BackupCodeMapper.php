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

namespace OCA\TwoFactorBackupCodes\Db;

use OCP\AppFramework\Db\Mapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;
use OCP\IUser;

class BackupCodeMapper extends Mapper {

	public function __construct(IDBConnection $db) {
		parent::__construct($db, 'twofactor_backupcodes');
	}

	/**
	 * @param IUser $user
	 * @return BackupCode[]
	 */
	public function getBackupCodes(IUser $user) {
		/* @var IQueryBuilder $qb */
		$qb = $this->db->getQueryBuilder();

		$qb->select('id', 'user_id', 'code', 'used')
			->from('twofactor_backupcodes')
			->where($qb->expr()->eq('user_id', $qb->createNamedParameter($user->getUID())));
		$result = $qb->execute();

		$rows = $result->fetchAll();
		$result->closeCursor();

		return array_map(function ($row) {
			return BackupCode::fromRow($row);
		}, $rows);
	}

	/**
	 * @param IUser $user
	 */
	public function deleteCodes(IUser $user) {
		$this->deleteCodesByUserId($user->getUID());
	}

	/**
	 * @param string $uid
	 */
	public function deleteCodesByUserId($uid) {
		/* @var IQueryBuilder $qb */
		$qb = $this->db->getQueryBuilder();

		$qb->delete('twofactor_backupcodes')
			->where($qb->expr()->eq('user_id', $qb->createNamedParameter($uid)));
		$qb->execute();
	}

}
