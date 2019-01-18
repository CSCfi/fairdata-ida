<?php
/**
 * @copyright 2017, Roeland Jago Douma <roeland@famdouma.nl>
 *
 * @author Roeland Jago Douma <roeland@famdouma.nl>
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
namespace OC\Core\Controller;

use OC\Files\AppData\Factory;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\NotFoundResponse;
use OCP\AppFramework\Http\FileDisplayResponse;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\Files\IAppData;
use OCP\Files\NotFoundException;
use OCP\Files\SimpleFS\ISimpleFile;
use OCP\Files\SimpleFS\ISimpleFolder;
use OCP\IRequest;

class JsController extends Controller {

	/** @var IAppData */
	protected $appData;

	/** @var ITimeFactory */
	protected $timeFactory;

	/**
	 * @param string $appName
	 * @param IRequest $request
	 * @param Factory $appDataFactory
	 * @param ITimeFactory $timeFactory
	 */
	public function __construct($appName, IRequest $request, Factory $appDataFactory, ITimeFactory $timeFactory) {
		parent::__construct($appName, $request);

		$this->appData = $appDataFactory->get('js');
		$this->timeFactory = $timeFactory;
	}

	/**
	 * @PublicPage
	 * @NoCSRFRequired
	 *
	 * @param string $fileName css filename with extension
	 * @param string $appName css folder name
	 * @return FileDisplayResponse|NotFoundResponse
	 */
	public function getJs($fileName, $appName) {
		try {
			$folder = $this->appData->getFolder($appName);
			$gzip = false;
			$file = $this->getFile($folder, $fileName, $gzip);
		} catch(NotFoundException $e) {
			return new NotFoundResponse();
		}

		$response = new FileDisplayResponse($file, Http::STATUS_OK, ['Content-Type' => 'application/javascript']);
		if ($gzip) {
			$response->addHeader('Content-Encoding', 'gzip');
		}
		$response->cacheFor(86400);
		$expires = new \DateTime();
		$expires->setTimestamp($this->timeFactory->getTime());
		$expires->add(new \DateInterval('PT24H'));
		$response->addHeader('Expires', $expires->format(\DateTime::RFC1123));
		$response->addHeader('Pragma', 'cache');
		return $response;
	}

	/**
	 * @param ISimpleFolder $folder
	 * @param string $fileName
	 * @param bool $gzip is set to true if we use the gzip file
	 * @return ISimpleFile
	 */
	private function getFile(ISimpleFolder $folder, $fileName, &$gzip) {
		$encoding = $this->request->getHeader('Accept-Encoding');

		if ($encoding !== null && strpos($encoding, 'gzip') !== false) {
			try {
				$gzip = true;
				return $folder->getFile($fileName . '.gzip'); # Safari doesn't like .gz
			} catch (NotFoundException $e) {
				// continue
			}
		}

		$gzip = false;
		return $folder->getFile($fileName);
	}
}
