<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Pierre Jochem <pierrejochem@msn.com>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
 * @author Vincent Petry <pvince81@owncloud.com>
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

namespace OCA\DAV\Connector\Sabre;

use OCP\ILogger;
use Sabre\DAV\Exception;
use Sabre\HTTP\Response;

class ExceptionLoggerPlugin extends \Sabre\DAV\ServerPlugin {
	protected $nonFatalExceptions = [
		'Sabre\DAV\Exception\NotAuthenticated' => true,
		// If tokenauth can throw this exception (which is basically as
		// NotAuthenticated. So not fatal.
		'OCA\DAV\Connector\Sabre\Exception\PasswordLoginForbidden' => true,
		// the sync client uses this to find out whether files exist,
		// so it is not always an error, log it as debug
		'Sabre\DAV\Exception\NotFound' => true,
		// this one mostly happens when the same file is uploaded at
		// exactly the same time from two clients, only one client
		// wins, the second one gets "Precondition failed"
		'Sabre\DAV\Exception\PreconditionFailed' => true,
		// forbidden can be expected when trying to upload to
		// read-only folders for example
		'Sabre\DAV\Exception\Forbidden' => true,
		// Happens when an external storage or federated share is temporarily
		// not available
		'Sabre\DAV\Exception\StorageNotAvailableException' => true,
	];

	/** @var string */
	private $appName;

	/** @var ILogger */
	private $logger;

	/**
	 * @param string $loggerAppName app name to use when logging
	 * @param ILogger $logger
	 */
	public function __construct($loggerAppName, $logger) {
		$this->appName = $loggerAppName;
		$this->logger = $logger;
	}

	/**
	 * This initializes the plugin.
	 *
	 * This function is called by \Sabre\DAV\Server, after
	 * addPlugin is called.
	 *
	 * This method should set up the required event subscriptions.
	 *
	 * @param \Sabre\DAV\Server $server
	 * @return void
	 */
	public function initialize(\Sabre\DAV\Server $server) {

		$server->on('exception', array($this, 'logException'), 10);
	}

	/**
	 * Log exception
	 *
	 */
	public function logException(\Exception $ex) {
		$exceptionClass = get_class($ex);
		$level = \OCP\Util::FATAL;
		if (isset($this->nonFatalExceptions[$exceptionClass])) {
			$level = \OCP\Util::DEBUG;
		}

		$this->logger->logException($ex, [
			'app' => $this->appName,
			'level' => $level,
		]);
	}
}
