<?php
/**
 * @copyright Copyright (c) 2016 Robin Appelman <robin@icewind.nl>
 *
 * @author Robin Appelman <robin@icewind.nl>
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

namespace OC\Settings;

use OCP\IDBConnection;

class Mapper {
	const TABLE_ADMIN_SETTINGS = 'admin_settings';
	const TABLE_ADMIN_SECTIONS = 'admin_sections';

	/** @var IDBConnection */
	private $dbc;

	/**
	 * @param IDBConnection $dbc
	 */
	public function __construct(IDBConnection $dbc) {
		$this->dbc = $dbc;
	}

	/**
	 * Get the configured admin settings from the database for the provided section
	 *
	 * @param string $section
	 * @return array[] [['class' => string, 'priority' => int], ...]
	 */
	public function getAdminSettingsFromDB($section) {
		$query = $this->dbc->getQueryBuilder();
		$query->select(['class', 'priority'])
			->from(self::TABLE_ADMIN_SETTINGS)
			->where($query->expr()->eq('section', $this->dbc->getQueryBuilder()->createParameter('section')))
			->setParameter('section', $section);

		$result = $query->execute();
		return $result->fetchAll();
	}

	/**
	 * Get the configured admin sections from the database
	 *
	 * @return array[] [['class' => string, 'priority' => int], ...]
	 */
	public function getAdminSectionsFromDB() {
		$query = $this->dbc->getQueryBuilder();
		$query->selectDistinct('s.class')
			->addSelect('s.priority')
			->from(self::TABLE_ADMIN_SECTIONS, 's')
			->from(self::TABLE_ADMIN_SETTINGS, 'f')
			->where($query->expr()->eq('s.id', 'f.section'));
		$result = $query->execute();
		return array_map(function ($row) {
			$row['priority'] = (int)$row['priority'];
			return $row;
		}, $result->fetchAll());
	}

	/**
	 * @param string $table Mapper::TABLE_ADMIN_SECTIONS or Mapper::TABLE_ADMIN_SETTINGS
	 * @param array $values
	 */
	public function add($table, array $values) {
		$query = $this->dbc->getQueryBuilder();
		$values = array_map(function ($value) use ($query) {
			return $query->createNamedParameter($value);
		}, $values);
		$query->insert($table)->values($values);
		$query->execute();
	}

	/**
	 * returns the registered classes in the given table
	 *
	 * @param $table Mapper::TABLE_ADMIN_SECTIONS or Mapper::TABLE_ADMIN_SETTINGS
	 * @return string[]
	 */
	public function getClasses($table) {
		$q = $this->dbc->getQueryBuilder();
		$resultStatement = $q->select('class')
			->from($table)
			->execute();
		$data = $resultStatement->fetchAll();
		$resultStatement->closeCursor();

		return array_map(function ($row) {
			return $row['class'];
		}, $data);
	}

	/**
	 * Check if a class is configured in the database
	 *
	 * @param string $table Mapper::TABLE_ADMIN_SECTIONS or Mapper::TABLE_ADMIN_SETTINGS
	 * @param string $className
	 * @return bool
	 */
	public function has($table, $className) {
		$query = $this->dbc->getQueryBuilder();
		$query->select('class')
			->from($table)
			->where($query->expr()->eq('class', $query->createNamedParameter($className)))
			->setMaxResults(1);

		$result = $query->execute();
		$row = $result->fetch();
		$result->closeCursor();

		return (bool)$row;
	}

	/**
	 * deletes an settings or admin entry from the given table
	 *
	 * @param $table Mapper::TABLE_ADMIN_SECTIONS or Mapper::TABLE_ADMIN_SETTINGS
	 * @param $className
	 */
	public function remove($table, $className) {
		$query = $this->dbc->getQueryBuilder();
		$query->delete($table)
			->where($query->expr()->eq('class', $query->createNamedParameter($className)));

		$query->execute();
	}

	/**
	 * @param $table Mapper::TABLE_ADMIN_SECTIONS or Mapper::TABLE_ADMIN_SETTINGS
	 * @param $idCol
	 * @param $id
	 * @param $values
	 */
	public function update($table, $idCol, $id, $values) {
		$query = $this->dbc->getQueryBuilder();
		$query->update($table);
		foreach ($values as $key => $value) {
			$query->set($key, $query->createNamedParameter($value));
		}
		$query
			->where($query->expr()->eq($idCol, $query->createParameter($idCol)))
			->setParameter($idCol, $id)
			->execute();
	}

}
