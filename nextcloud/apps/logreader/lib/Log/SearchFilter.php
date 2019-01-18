<?php
/**
 * @author Robin Appelman <icewind@owncloud.com>
 *
 * @copyright Copyright (c) 2015, ownCloud, Inc.
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

namespace OCA\LogReader\Log;

class SearchFilter extends \FilterIterator {
	/**
	 * @var string
	 */
	private $query;

	/**
	 * @var string[]
	 */
	private $levels;

	/**
	 * @param \Iterator $iterator
	 * @param string $query
	 */
	public function __construct(\Iterator $iterator, $query) {
		parent::__construct($iterator);
		$this->rewind();
		$this->query = strtolower($query);
		$this->levels = ['Debug', 'Info', 'Warning', 'Error', 'Fatal'];
	}

	private function formatLevel($level) {
		return isset($this->levels[$level]) ? $this->levels[$level] : 'Unknown';
	}

	public function accept() {
		if (!$this->query) {
			return true;
		}
		$value = $this->current();
		return stripos($value['message'], $this->query) !== false
			|| stripos($value['app'], $this->query) !== false
			|| stripos($value['reqId'], $this->query) !== false
			|| stripos($value['user'], $this->query) !== false
			|| stripos($value['url'], $this->query) !== false
			|| stripos($this->formatLevel($value['level']), $this->query) !== false;
	}
}
