<?php
/**
 * @copyright Copyright (c) 2017, Robin Appelman <robin@icewind.nl>
 *
 * @license GNU AGPL version 3 or any later version
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

namespace OC\Federation;

use OCP\Federation\ICloudId;

class CloudId implements ICloudId {
	/** @var string */
	private $id;
	/** @var string */
	private $user;
	/** @var string */
	private $remote;

	/**
	 * CloudId constructor.
	 *
	 * @param string $id
	 * @param string $user
	 * @param string $remote
	 */
	public function __construct($id, $user, $remote) {
		$this->id = $id;
		$this->user = $user;
		$this->remote = $remote;
	}

	/**
	 * The full remote cloud id
	 *
	 * @return string
	 */
	public function getId() {
		return $this->id;
	}

	public function getDisplayId() {
		return str_replace('https://', '', str_replace('http://', '', $this->getId()));
	}

	/**
	 * The username on the remote server
	 *
	 * @return string
	 */
	public function getUser() {
		return $this->user;
	}

	/**
	 * The base address of the remote server
	 *
	 * @return string
	 */
	public function getRemote() {
		return $this->remote;
	}
}
