<?php
/**
 * @copyright Copyright (c) 2018 Robin Appelman <robin@icewind.nl>
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

namespace OCA\DAV\Connector\Sabre;

use Sabre\DAV\CorePlugin;
use Sabre\DAV\FS\Directory;
use Sabre\DAV\ServerPlugin;
use Sabre\DAV\Tree;
use Sabre\HTTP\RequestInterface;
use Sabre\HTTP\ResponseInterface;

class AnonymousOptionsPlugin extends ServerPlugin {

	/**
	 * @var \Sabre\DAV\Server
	 */
	private $server;

	/**
	 * @param \Sabre\DAV\Server $server
	 * @return void
	 */
	public function initialize(\Sabre\DAV\Server $server) {
		$this->server = $server;
		// before auth
		$this->server->on('beforeMethod', [$this, 'handleAnonymousOptions'], 9);
	}

	/**
	 * @return bool
	 */
	public function isRequestInRoot($path) {
		return $path === '' || (is_string($path) && strpos($path, '/') === FALSE);
	}

	/**
	 * @throws \Sabre\DAV\Exception\Forbidden
	 * @return bool
	 */
	public function handleAnonymousOptions(RequestInterface $request, ResponseInterface $response) {
		if ($request->getHeader('Authorization') === null && $request->getMethod() === 'OPTIONS' && $this->isRequestInRoot($request->getPath())) {
			/** @var CorePlugin $corePlugin */
			$corePlugin = $this->server->getPlugin('core');
			// setup a fake tree for anonymous access
			$this->server->tree = new Tree(new Directory(''));
			$corePlugin->httpOptions($request, $response);
			$this->server->emit('afterMethod', [$request, $response]);
			$this->server->emit('afterMethod:OPTIONS', [$request, $response]);

			$this->server->sapi->sendResponse($response);
			return false;
		}
	}
}
