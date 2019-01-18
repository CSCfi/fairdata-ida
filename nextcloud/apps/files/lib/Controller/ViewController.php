<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Christoph Wurst <christoph@owncloud.com>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Robin Appelman <robin@icewind.nl>
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

namespace OCA\Files\Controller;

use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\ContentSecurityPolicy;
use OCP\AppFramework\Http\RedirectResponse;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\Files\IRootFolder;
use OCP\Files\NotFoundException;
use OCP\IConfig;
use OCP\IL10N;
use OCP\IRequest;
use OCP\IURLGenerator;
use OCP\IUserSession;
use Symfony\Component\EventDispatcher\EventDispatcherInterface;
use OCP\Files\Folder;
use OCP\App\IAppManager;
use Symfony\Component\EventDispatcher\GenericEvent;

/**
 * Class ViewController
 *
 * @package OCA\Files\Controller
 */
class ViewController extends Controller {
	/** @var string */
	protected $appName;
	/** @var IRequest */
	protected $request;
	/** @var IURLGenerator */
	protected $urlGenerator;
	/** @var IL10N */
	protected $l10n;
	/** @var IConfig */
	protected $config;
	/** @var EventDispatcherInterface */
	protected $eventDispatcher;
	/** @var IUserSession */
	protected $userSession;
	/** @var IAppManager */
	protected $appManager;
	/** @var IRootFolder */
	protected $rootFolder;

	/**
	 * @param string $appName
	 * @param IRequest $request
	 * @param IURLGenerator $urlGenerator
	 * @param IL10N $l10n
	 * @param IConfig $config
	 * @param EventDispatcherInterface $eventDispatcherInterface
	 * @param IUserSession $userSession
	 * @param IAppManager $appManager
	 * @param IRootFolder $rootFolder
	 */
	public function __construct($appName,
								IRequest $request,
								IURLGenerator $urlGenerator,
								IL10N $l10n,
								IConfig $config,
								EventDispatcherInterface $eventDispatcherInterface,
								IUserSession $userSession,
								IAppManager $appManager,
								IRootFolder $rootFolder
	) {
		parent::__construct($appName, $request);
		$this->appName = $appName;
		$this->request = $request;
		$this->urlGenerator = $urlGenerator;
		$this->l10n = $l10n;
		$this->config = $config;
		$this->eventDispatcher = $eventDispatcherInterface;
		$this->userSession = $userSession;
		$this->appManager = $appManager;
		$this->rootFolder = $rootFolder;
	}

	/**
	 * @param string $appName
	 * @param string $scriptName
	 * @return string
	 */
	protected function renderScript($appName, $scriptName) {
		$content = '';
		$appPath = \OC_App::getAppPath($appName);
		$scriptPath = $appPath . '/' . $scriptName;
		if (file_exists($scriptPath)) {
			// TODO: sanitize path / script name ?
			ob_start();
			include $scriptPath;
			$content = ob_get_contents();
			@ob_end_clean();
		}
		return $content;
	}

	/**
	 * FIXME: Replace with non static code
	 *
	 * @return array
	 * @throws \OCP\Files\NotFoundException
	 */
	protected function getStorageInfo() {
		$dirInfo = \OC\Files\Filesystem::getFileInfo('/', false);
		return \OC_Helper::getStorageInfo('/', $dirInfo);
	}

	/**
	 * @NoCSRFRequired
	 * @NoAdminRequired
	 *
	 * @param string $dir
	 * @param string $view
	 * @param string $fileid
	 * @return TemplateResponse|RedirectResponse
	 */
	public function index($dir = '', $view = '', $fileid = null, $fileNotFound = false) {
		if ($fileid !== null) {
			try {
				return $this->showFile($fileid);
			} catch (NotFoundException $e) {
				return new RedirectResponse($this->urlGenerator->linkToRoute('files.view.index', ['fileNotFound' => true]));
			}
		}

		$nav = new \OCP\Template('files', 'appnavigation', '');

		// Load the files we need
		\OCP\Util::addStyle('files', 'merged');
		\OCP\Util::addScript('files', 'merged-index');

		// mostly for the home storage's free space
		// FIXME: Make non static
		$storageInfo = $this->getStorageInfo();

		\OCA\Files\App::getNavigationManager()->add(
			[
				'id' => 'favorites',
				'appname' => 'files',
				'script' => 'simplelist.php',
				'order' => 5,
				'name' => $this->l10n->t('Favorites')
			]
		);

		$navItems = \OCA\Files\App::getNavigationManager()->getAll();
		usort($navItems, function($item1, $item2) {
			return $item1['order'] - $item2['order'];
		});
		$nav->assign('navigationItems', $navItems);


		$nav->assign('usage', \OC_Helper::humanFileSize($storageInfo['used']));
		if ($storageInfo['quota'] === \OCP\Files\FileInfo::SPACE_UNLIMITED) {
			$totalSpace = $this->l10n->t('Unlimited');
		} else {
			$totalSpace = \OC_Helper::humanFileSize($storageInfo['total']);
		}
		$nav->assign('total_space', $totalSpace);
		$nav->assign('quota', $storageInfo['quota']);
		$nav->assign('usage_relative', $storageInfo['relative']);

		$contentItems = [];

		// render the container content for every navigation item
		foreach ($navItems as $item) {
			$content = '';
			if (isset($item['script'])) {
				$content = $this->renderScript($item['appname'], $item['script']);
			}
			$contentItem = [];
			$contentItem['id'] = $item['id'];
			$contentItem['content'] = $content;
			$contentItems[] = $contentItem;
		}

		$event = new GenericEvent(null, ['hiddenFields' => []]);
		$this->eventDispatcher->dispatch('OCA\Files::loadAdditionalScripts', $event);

		$params = [];
		$params['usedSpacePercent'] = (int)$storageInfo['relative'];
		$params['owner'] = $storageInfo['owner'];
		$params['ownerDisplayName'] = $storageInfo['ownerDisplayName'];
		$params['isPublic'] = false;
		$params['allowShareWithLink'] = $this->config->getAppValue('core', 'shareapi_allow_links', 'yes');
		$user = $this->userSession->getUser()->getUID();
		$params['defaultFileSorting'] = $this->config->getUserValue($user, 'files', 'file_sorting', 'name');
		$params['defaultFileSortingDirection'] = $this->config->getUserValue($user, 'files', 'file_sorting_direction', 'asc');
		$showHidden = (bool) $this->config->getUserValue($this->userSession->getUser()->getUID(), 'files', 'show_hidden', false);
		$params['showHiddenFiles'] = $showHidden ? 1 : 0;
		$params['fileNotFound'] = $fileNotFound ? 1 : 0;
		$params['appNavigation'] = $nav;
		$params['appContents'] = $contentItems;
		$params['hiddenFields'] = $event->getArgument('hiddenFields');

		$response = new TemplateResponse(
			$this->appName,
			'index',
			$params
		);
		$policy = new ContentSecurityPolicy();
		$policy->addAllowedFrameDomain('\'self\'');
		$response->setContentSecurityPolicy($policy);

		return $response;
	}

	/**
	 * Redirects to the file list and highlight the given file id
	 *
	 * @param string $fileId file id to show
	 * @return RedirectResponse redirect response or not found response
	 * @throws \OCP\Files\NotFoundException
	 */
	private function showFile($fileId) {
		$uid = $this->userSession->getUser()->getUID();
		$baseFolder = $this->rootFolder->getUserFolder($uid);
		$files = $baseFolder->getById($fileId);
		$params = [];

		if (empty($files) && $this->appManager->isEnabledForUser('files_trashbin')) {
			$baseFolder = $this->rootFolder->get($uid . '/files_trashbin/files/');
			$files = $baseFolder->getById($fileId);
			$params['view'] = 'trashbin';
		}

		if (!empty($files)) {
			$file = current($files);
			if ($file instanceof Folder) {
				// set the full path to enter the folder
				$params['dir'] = $baseFolder->getRelativePath($file->getPath());
			} else {
				// set parent path as dir
				$params['dir'] = $baseFolder->getRelativePath($file->getParent()->getPath());
				// and scroll to the entry
				$params['scrollto'] = $file->getName();
			}
			return new RedirectResponse($this->urlGenerator->linkToRoute('files.view.index', $params));
		}
		throw new \OCP\Files\NotFoundException();
	}
}
