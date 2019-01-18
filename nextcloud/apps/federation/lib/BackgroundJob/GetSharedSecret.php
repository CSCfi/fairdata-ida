<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Björn Schießle <bjoern@schiessle.org>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
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


namespace OCA\Federation\BackgroundJob;

use GuzzleHttp\Exception\ClientException;
use OC\BackgroundJob\JobList;
use OC\BackgroundJob\Job;
use OCA\Federation\DbHandler;
use OCA\Federation\TrustedServers;
use OCP\AppFramework\Http;
use OCP\BackgroundJob\IJobList;
use OCP\Http\Client\IClient;
use OCP\Http\Client\IResponse;
use OCP\ILogger;
use OCP\IURLGenerator;
use OCP\OCS\IDiscoveryService;

/**
 * Class GetSharedSecret
 *
 * request shared secret from remote Nextcloud
 *
 * @package OCA\Federation\Backgroundjob
 */
class GetSharedSecret extends Job{

	/** @var IClient */
	private $httpClient;

	/** @var IJobList */
	private $jobList;

	/** @var IURLGenerator */
	private $urlGenerator;

	/** @var TrustedServers  */
	private $trustedServers;

	/** @var DbHandler */
	private $dbHandler;

	/** @var IDiscoveryService  */
	private $ocsDiscoveryService;

	/** @var ILogger */
	private $logger;

	/** @var bool */
	protected $retainJob = false;

	private $format = '?format=json';

	private $defaultEndPoint = '/ocs/v2.php/apps/federation/api/v1/shared-secret';

	/**
	 * RequestSharedSecret constructor.
	 *
	 * @param IClient $httpClient
	 * @param IURLGenerator $urlGenerator
	 * @param IJobList $jobList
	 * @param TrustedServers $trustedServers
	 * @param ILogger $logger
	 * @param DbHandler $dbHandler
	 * @param IDiscoveryService $ocsDiscoveryService
	 */
	public function __construct(
		IClient $httpClient = null,
		IURLGenerator $urlGenerator = null,
		IJobList $jobList = null,
		TrustedServers $trustedServers = null,
		ILogger $logger = null,
		DbHandler $dbHandler = null,
		IDiscoveryService $ocsDiscoveryService = null
	) {
		$this->logger = $logger ? $logger : \OC::$server->getLogger();
		$this->httpClient = $httpClient ? $httpClient : \OC::$server->getHTTPClientService()->newClient();
		$this->jobList = $jobList ? $jobList : \OC::$server->getJobList();
		$this->urlGenerator = $urlGenerator ? $urlGenerator : \OC::$server->getURLGenerator();
		$this->dbHandler = $dbHandler ? $dbHandler : new DbHandler(\OC::$server->getDatabaseConnection(), \OC::$server->getL10N('federation'));
		$this->ocsDiscoveryService = $ocsDiscoveryService ? $ocsDiscoveryService : \OC::$server->query(\OCP\OCS\IDiscoveryService::class);
		if ($trustedServers) {
			$this->trustedServers = $trustedServers;
		} else {
			$this->trustedServers = new TrustedServers(
				$this->dbHandler,
				\OC::$server->getHTTPClientService(),
				$this->logger,
				$this->jobList,
				\OC::$server->getSecureRandom(),
				\OC::$server->getConfig(),
				\OC::$server->getEventDispatcher()
			);
		}
	}

	/**
	 * run the job, then remove it from the joblist
	 *
	 * @param JobList $jobList
	 * @param ILogger $logger
	 */
	public function execute($jobList, ILogger $logger = null) {
		$target = $this->argument['url'];
		// only execute if target is still in the list of trusted domains
		if ($this->trustedServers->isTrustedServer($target)) {
			$this->parentExecute($jobList, $logger);
		}

		if (!$this->retainJob) {
			$jobList->remove($this, $this->argument);
		}
	}

	/**
	 * call execute() method of parent
	 *
	 * @param JobList $jobList
	 * @param ILogger $logger
	 */
	protected function parentExecute($jobList, $logger = null) {
		parent::execute($jobList, $logger);
	}

	protected function run($argument) {
		$target = $argument['url'];
		$source = $this->urlGenerator->getAbsoluteURL('/');
		$source = rtrim($source, '/');
		$token = $argument['token'];

		$endPoints = $this->ocsDiscoveryService->discover($target, 'FEDERATED_SHARING');
		$endPoint = isset($endPoints['shared-secret']) ? $endPoints['shared-secret'] : $this->defaultEndPoint;

		// make sure that we have a well formated url
		$url = rtrim($target, '/') . '/' . trim($endPoint, '/') . $this->format;

		$result = null;
		try {
			$result = $this->httpClient->get(
				$url,
				[
					'query' =>
						[
							'url' => $source,
							'token' => $token
						],
					'timeout' => 3,
					'connect_timeout' => 3,
				]
			);

			$status = $result->getStatusCode();

		} catch (ClientException $e) {
			$status = $e->getCode();
			if ($status === Http::STATUS_FORBIDDEN) {
				$this->logger->info($target . ' refused to exchange a shared secret with you.', ['app' => 'federation']);
			} else {
				$this->logger->info($target . ' responded with a ' . $status . ' containing: ' . $e->getMessage(), ['app' => 'federation']);
			}
		} catch (\Exception $e) {
			$status = Http::STATUS_INTERNAL_SERVER_ERROR;
			$this->logger->logException($e, ['app' => 'federation']);
		}

		// if we received a unexpected response we try again later
		if (
			$status !== Http::STATUS_OK
			&& $status !== Http::STATUS_FORBIDDEN
		) {
			$this->retainJob = true;
		}  else {
			// reset token if we received a valid response
			$this->dbHandler->addToken($target, '');
		}

		if ($status === Http::STATUS_OK && $result instanceof IResponse) {
			$body = $result->getBody();
			$result = json_decode($body, true);
			if (isset($result['ocs']['data']['sharedSecret'])) {
				$this->trustedServers->addSharedSecret(
						$target,
						$result['ocs']['data']['sharedSecret']
				);
			} else {
				$this->logger->error(
						'remote server "' . $target . '"" does not return a valid shared secret',
						['app' => 'federation']
				);
				$this->trustedServers->setServerStatus($target, TrustedServers::STATUS_FAILURE);
			}
		}

	}
}
