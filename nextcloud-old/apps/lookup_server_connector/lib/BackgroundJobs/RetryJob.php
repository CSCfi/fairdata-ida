<?php
/**
 * @copyright Copyright (c) 2016 Bjoern Schiessle <bjoern@schiessle.org>
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

namespace OCA\LookupServerConnector\BackgroundJobs;


use OC\BackgroundJob\Job;
use OC\BackgroundJob\JobList;
use OCP\BackgroundJob\IJobList;
use OCP\Http\Client\IClientService;
use OCP\IConfig;
use OCP\ILogger;

class RetryJob extends Job {
	/** @var IClientService */
	private $clientService;
	/** @var IJobList */
	private $jobList;
	/** @var string */
	private $lookupServer;
	/** @var int how much time should be between two, will be increased for each retry */
	private $interval = 100;
	/** @var IConfig */
	private $config;

	/**
	 * @param IClientService $clientService
	 * @param IJobList $jobList
	 * @param IConfig $config
	 */
	public function __construct(IClientService $clientService,
								IJobList $jobList,
								IConfig $config) {
		$this->clientService = $clientService;
		$this->jobList = $jobList;
		$this->config = $config;

		if ($config->getSystemValue('has_internet_connection', true) === false) {
			return;
		}

		$this->lookupServer = $config->getSystemValue('lookup_server', 'https://lookup.nextcloud.com');
		if (!empty($this->lookupServer)) {
			$this->lookupServer = rtrim($this->lookupServer, '/');
			$this->lookupServer .= '/users';
		}
	}

	/**
	 * run the job, then remove it from the jobList
	 *
	 * @param JobList $jobList
	 * @param ILogger|null $logger
	 */
	public function execute($jobList, ILogger $logger = null) {
		if ($this->shouldRun($this->argument)) {
			parent::execute($jobList, $logger);
			$jobList->remove($this, $this->argument);
		}
	}

	protected function run($argument) {
		if ($this->killBackgroundJob((int)$argument['retryNo'])) {
			return;
		}

		$client = $this->clientService->newClient();

		try {
			$client->post($this->lookupServer,
				[
					'body' => json_encode($argument['dataArray']),
					'timeout' => 10,
					'connect_timeout' => 3,
				]
			);
		} catch (\Exception $e) {
			$this->jobList->add(RetryJob::class,
				[
					'dataArray' => $argument['dataArray'],
					'retryNo' => $argument['retryNo'] + 1,
					'lastRun' => time(),
				]
			);

		}
	}

	/**
	 * test if it is time for the next run
	 *
	 * @param array $argument
	 * @return bool
	 */
	protected function shouldRun($argument) {
		$retryNo = (int)$argument['retryNo'];
		$delay = $this->interval * 6 ** $retryNo;
		return !isset($argument['lastRun']) || ((time() - $argument['lastRun']) > $delay);
	}

	/**
	 * check if we should kill the background job
	 *
	 * The lookup server should no longer be contacted if:
	 *
	 * - max retries are reached (set to 5)
	 * - lookup server was disabled by the admin
	 * - no valid lookup server URL given
	 *
	 * @param int $retryCount
	 * @return bool
	 */
	protected function killBackgroundJob($retryCount) {
		$maxTriesReached = $retryCount >= 5;
		$lookupServerDisabled = $this->config->getAppValue('files_sharing', 'lookupServerUploadEnabled', 'yes') !== 'yes';

		return $maxTriesReached || $lookupServerDisabled || empty($this->lookupServer);
	}
}
