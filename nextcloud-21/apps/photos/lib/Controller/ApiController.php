<?php

declare(strict_types=1);
/**
 * @copyright Copyright (c) 2020 John Molakvoæ <skjnldsv@protonmail.com>
 *
 * @author John Molakvoæ <skjnldsv@protonmail.com>
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
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 *
 */

namespace OCA\Photos\Controller;

use OCA\Photos\AppInfo\Application;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\JSONResponse;
use OCP\AppFramework\Http\StreamResponse;
use OCP\AppFramework\Http\ContentSecurityPolicy;
use OCP\IConfig;
use OCP\IRequest;
use OCP\IUserSession;

class ApiController extends Controller {

	/** @var IConfig */
	private $config;

	/** @var IUserSession */
	private $userSession;

	public function __construct(IRequest $request,
								IConfig $config,
								IUserSession $userSession) {
		parent::__construct(Application::APP_ID, $request);

		$this->config = $config;
		$this->userSession = $userSession;
	}

	/**
	 * @NoAdminRequired
	 *
	 * update preferences (user setting)
	 *
	 * @param string key the identifier to change
	 * @param string value the value to set
	 *
	 * @return JSONResponse an empty JSONResponse with respective http status code
	 */
	public function setUserConfig(string $key, string $value): JSONResponse {
		$user = $this->userSession->getUser();
		if (is_null($user)) {
			return new JSONResponse([], Http::STATUS_PRECONDITION_FAILED);
		}

		$userId = $user->getUid();
		$this->config->setUserValue($userId, Application::APP_ID, $key, $value);
		return new JSONResponse([], Http::STATUS_OK);
	}

	/**
	 * @NoAdminRequired
	 * @NoCSRFRequired
	 */
	public function serviceWorker(): StreamResponse {
		$response = new StreamResponse(__DIR__.'/../../js/photos-service-worker.js');
		$response->setHeaders([
			'Content-Type' => 'application/javascript',
			'Service-Worker-Allowed' => '/'
		]);
		$policy = new ContentSecurityPolicy();
		$policy->addAllowedWorkerSrcDomain("'self'");
		$policy->addAllowedScriptDomain("'self'");
		$policy->addAllowedConnectDomain("'self'");
		$response->setContentSecurityPolicy($policy);
		return $response;
	}
}
