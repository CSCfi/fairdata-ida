<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Christoph Wurst <christoph@owncloud.com>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
 * @author Tobias Kaminsky <tobias@kaminsky.me>
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

namespace OCA\Files\Controller;

use OCP\AppFramework\Http;
use OCP\AppFramework\Controller;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\NotFoundException;
use OCP\IConfig;
use OCP\IRequest;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\FileDisplayResponse;
use OCP\AppFramework\Http\Response;
use OCA\Files\Service\TagService;
use OCP\IPreview;
use OCP\Share\IManager;
use OC\Files\Node\Node;
use OCP\IUserSession;

/**
 * Class ApiController
 *
 * @package OCA\Files\Controller
 */
class ApiController extends Controller {
	/** @var TagService */
	private $tagService;
	/** @var IManager **/
	private $shareManager;
	/** @var IPreview */
	private $previewManager;
	/** IUserSession */
	private $userSession;
	/** IConfig */
	private $config;
	/** @var Folder */
	private $userFolder;

	/**
	 * @param string $appName
	 * @param IRequest $request
	 * @param IUserSession $userSession
	 * @param TagService $tagService
	 * @param IPreview $previewManager
	 * @param IManager $shareManager
	 * @param IConfig $config
	 * @param Folder $userFolder
	 */
	public function __construct($appName,
								IRequest $request,
								IUserSession $userSession,
								TagService $tagService,
								IPreview $previewManager,
								IManager $shareManager,
								IConfig $config,
								Folder $userFolder) {
		parent::__construct($appName, $request);
		$this->userSession = $userSession;
		$this->tagService = $tagService;
		$this->previewManager = $previewManager;
		$this->shareManager = $shareManager;
		$this->config = $config;
		$this->userFolder = $userFolder;
	}

	/**
	 * Gets a thumbnail of the specified file
	 *
	 * @since API version 1.0
	 *
	 * @NoAdminRequired
	 * @NoCSRFRequired
	 * @StrictCookieRequired
	 *
	 * @param int $x
	 * @param int $y
	 * @param string $file URL-encoded filename
	 * @return DataResponse|FileDisplayResponse
	 */
	public function getThumbnail($x, $y, $file) {
		if($x < 1 || $y < 1) {
			return new DataResponse(['message' => 'Requested size must be numeric and a positive value.'], Http::STATUS_BAD_REQUEST);
		}

		try {
			$file = $this->userFolder->get($file);
			if ($file instanceof Folder) {
				throw new NotFoundException();
			}

			/** @var File $file */
			$preview = $this->previewManager->getPreview($file, $x, $y, true);

			return new FileDisplayResponse($preview, Http::STATUS_OK, ['Content-Type' => $preview->getMimeType()]);
		} catch (NotFoundException $e) {
			return new DataResponse(['message' => 'File not found.'], Http::STATUS_NOT_FOUND);
		} catch (\Exception $e) {
			return new DataResponse([], Http::STATUS_BAD_REQUEST);
		}
	}

	/**
	 * Updates the info of the specified file path
	 * The passed tags are absolute, which means they will
	 * replace the actual tag selection.
	 *
	 * @NoAdminRequired
	 *
	 * @param string $path path
	 * @param array|string $tags array of tags
	 * @return DataResponse
	 */
	public function updateFileTags($path, $tags = null) {
		$result = [];
		// if tags specified or empty array, update tags
		if (!is_null($tags)) {
			try {
				$this->tagService->updateFileTags($path, $tags);
			} catch (\OCP\Files\NotFoundException $e) {
				return new DataResponse([
					'message' => $e->getMessage()
				], Http::STATUS_NOT_FOUND);
			} catch (\OCP\Files\StorageNotAvailableException $e) {
				return new DataResponse([
					'message' => $e->getMessage()
				], Http::STATUS_SERVICE_UNAVAILABLE);
			} catch (\Exception $e) {
				return new DataResponse([
					'message' => $e->getMessage()
				], Http::STATUS_NOT_FOUND);
			}
			$result['tags'] = $tags;
		}
		return new DataResponse($result);
	}

	/**
	 * @param \OCP\Files\Node[] $nodes
	 * @return array
	 */
	private function formatNodes(array $nodes) {
		return array_values(array_map(function (Node $node) {
			/** @var \OC\Files\Node\Node $shareTypes */
			$shareTypes = $this->getShareTypes($node);
			$file = \OCA\Files\Helper::formatFileInfo($node->getFileInfo());
			$parts = explode('/', dirname($node->getPath()), 4);
			if (isset($parts[3])) {
				$file['path'] = '/' . $parts[3];
			} else {
				$file['path'] = '/';
			}
			if (!empty($shareTypes)) {
				$file['shareTypes'] = $shareTypes;
			}
			return $file;
		}, $nodes));
	}

	/**
	 * Returns a list of recently modifed files.
	 *
	 * @NoAdminRequired
	 *
	 * @return DataResponse
	 */
	public function getRecentFiles() {
		$nodes = $this->userFolder->getRecent(100);
		$files = $this->formatNodes($nodes);
		return new DataResponse(['files' => $files]);
	}

	/**
	 * Return a list of share types for outgoing shares
	 *
	 * @param Node $node file node
	 *
	 * @return int[] array of share types
	 */
	private function getShareTypes(Node $node) {
		$userId = $this->userSession->getUser()->getUID();
		$shareTypes = [];
		$requestedShareTypes = [
			\OCP\Share::SHARE_TYPE_USER,
			\OCP\Share::SHARE_TYPE_GROUP,
			\OCP\Share::SHARE_TYPE_LINK,
			\OCP\Share::SHARE_TYPE_REMOTE,
			\OCP\Share::SHARE_TYPE_EMAIL
		];
		foreach ($requestedShareTypes as $requestedShareType) {
			// one of each type is enough to find out about the types
			$shares = $this->shareManager->getSharesBy(
				$userId,
				$requestedShareType,
				$node,
				false,
				1
			);
			if (!empty($shares)) {
				$shareTypes[] = $requestedShareType;
			}
		}
		return $shareTypes;
	}

	/**
	 * Change the default sort mode
	 *
	 * @NoAdminRequired
	 *
	 * @param string $mode
	 * @param string $direction
	 * @return Response
	 */
	public function updateFileSorting($mode, $direction) {
		$allowedMode = ['name', 'size', 'mtime'];
		$allowedDirection = ['asc', 'desc'];
		if (!in_array($mode, $allowedMode) || !in_array($direction, $allowedDirection)) {
			$response = new Response();
			$response->setStatus(Http::STATUS_UNPROCESSABLE_ENTITY);
			return $response;
		}
		$this->config->setUserValue($this->userSession->getUser()->getUID(), 'files', 'file_sorting', $mode);
		$this->config->setUserValue($this->userSession->getUser()->getUID(), 'files', 'file_sorting_direction', $direction);
		return new Response();
	}

	/**
	 * Toggle default for showing/hiding hidden files
	 *
	 * @NoAdminRequired
	 *
	 * @param bool $show
	 */
	public function showHiddenFiles($show) {
		$this->config->setUserValue($this->userSession->getUser()->getUID(), 'files', 'show_hidden', (int) $show);
		return new Response();
	}

}
