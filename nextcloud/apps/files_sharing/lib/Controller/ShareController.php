<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Bjoern Schiessle <bjoern@schiessle.org>
 * @author Björn Schießle <bjoern@schiessle.org>
 * @author Georg Ehrke <georg@owncloud.com>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Piotr Filiciak <piotr@filiciak.pl>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
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

namespace OCA\Files_Sharing\Controller;

use OC\Files\Node\Folder;
use OC_Files;
use OC_Util;
use OCA\FederatedFileSharing\FederatedShareProvider;
use OCP\Defaults;
use OCP\IL10N;
use OCP\Template;
use OCP\Share;
use OCP\AppFramework\Controller;
use OCP\IRequest;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\AppFramework\Http\RedirectResponse;
use OCP\AppFramework\Http\NotFoundResponse;
use OCP\IURLGenerator;
use OCP\IConfig;
use OCP\ILogger;
use OCP\IUserManager;
use OCP\ISession;
use OCP\IPreview;
use OCA\Files_Sharing\Activity\Providers\Downloads;
use \OCP\Files\NotFoundException;
use OCP\Files\IRootFolder;
use OCP\Share\Exceptions\ShareNotFound;
use Symfony\Component\EventDispatcher\EventDispatcherInterface;

/**
 * Class ShareController
 *
 * @package OCA\Files_Sharing\Controllers
 */
class ShareController extends Controller {

	/** @var IConfig */
	protected $config;
	/** @var IURLGenerator */
	protected $urlGenerator;
	/** @var IUserManager */
	protected $userManager;
	/** @var ILogger */
	protected $logger;
	/** @var \OCP\Activity\IManager */
	protected $activityManager;
	/** @var \OCP\Share\IManager */
	protected $shareManager;
	/** @var ISession */
	protected $session;
	/** @var IPreview */
	protected $previewManager;
	/** @var IRootFolder */
	protected $rootFolder;
	/** @var FederatedShareProvider */
	protected $federatedShareProvider;
	/** @var EventDispatcherInterface */
	protected $eventDispatcher;
	/** @var IL10N */
	protected $l10n;
	/** @var Defaults */
	protected $defaults;

	/**
	 * @param string $appName
	 * @param IRequest $request
	 * @param IConfig $config
	 * @param IURLGenerator $urlGenerator
	 * @param IUserManager $userManager
	 * @param ILogger $logger
	 * @param \OCP\Activity\IManager $activityManager
	 * @param \OCP\Share\IManager $shareManager
	 * @param ISession $session
	 * @param IPreview $previewManager
	 * @param IRootFolder $rootFolder
	 * @param FederatedShareProvider $federatedShareProvider
	 * @param EventDispatcherInterface $eventDispatcher
	 * @param IL10N $l10n
	 * @param Defaults $defaults
	 */
	public function __construct($appName,
								IRequest $request,
								IConfig $config,
								IURLGenerator $urlGenerator,
								IUserManager $userManager,
								ILogger $logger,
								\OCP\Activity\IManager $activityManager,
								\OCP\Share\IManager $shareManager,
								ISession $session,
								IPreview $previewManager,
								IRootFolder $rootFolder,
								FederatedShareProvider $federatedShareProvider,
								EventDispatcherInterface $eventDispatcher,
								IL10N $l10n,
								Defaults $defaults) {
		parent::__construct($appName, $request);

		$this->config = $config;
		$this->urlGenerator = $urlGenerator;
		$this->userManager = $userManager;
		$this->logger = $logger;
		$this->activityManager = $activityManager;
		$this->shareManager = $shareManager;
		$this->session = $session;
		$this->previewManager = $previewManager;
		$this->rootFolder = $rootFolder;
		$this->federatedShareProvider = $federatedShareProvider;
		$this->eventDispatcher = $eventDispatcher;
		$this->l10n = $l10n;
		$this->defaults = $defaults;
	}

	/**
	 * @PublicPage
	 * @NoCSRFRequired
	 *
	 * @param string $token
	 * @return TemplateResponse|RedirectResponse
	 */
	public function showAuthenticate($token) {
		$share = $this->shareManager->getShareByToken($token);

		if($this->linkShareAuth($share)) {
			return new RedirectResponse($this->urlGenerator->linkToRoute('files_sharing.sharecontroller.showShare', array('token' => $token)));
		}

		return new TemplateResponse($this->appName, 'authenticate', array(), 'guest');
	}

	/**
	 * @PublicPage
	 * @UseSession
	 * @BruteForceProtection(action=publicLinkAuth)
	 *
	 * Authenticates against password-protected shares
	 * @param string $token
	 * @param string $password
	 * @return RedirectResponse|TemplateResponse|NotFoundResponse
	 */
	public function authenticate($token, $password = '') {

		// Check whether share exists
		try {
			$share = $this->shareManager->getShareByToken($token);
		} catch (ShareNotFound $e) {
			return new NotFoundResponse();
		}

		$authenticate = $this->linkShareAuth($share, $password);

		if($authenticate === true) {
			return new RedirectResponse($this->urlGenerator->linkToRoute('files_sharing.sharecontroller.showShare', array('token' => $token)));
		}

		$response = new TemplateResponse($this->appName, 'authenticate', array('wrongpw' => true), 'guest');
		$response->throttle();
		return $response;
	}

	/**
	 * Authenticate a link item with the given password.
	 * Or use the session if no password is provided.
	 *
	 * This is a modified version of Helper::authenticate
	 * TODO: Try to merge back eventually with Helper::authenticate
	 *
	 * @param \OCP\Share\IShare $share
	 * @param string|null $password
	 * @return bool
	 */
	private function linkShareAuth(\OCP\Share\IShare $share, $password = null) {
		if ($password !== null) {
			if ($this->shareManager->checkPassword($share, $password)) {
				$this->session->set('public_link_authenticated', (string)$share->getId());
			} else {
				$this->emitAccessShareHook($share, 403, 'Wrong password');
				return false;
			}
		} else {
			// not authenticated ?
			if ( ! $this->session->exists('public_link_authenticated')
				|| $this->session->get('public_link_authenticated') !== (string)$share->getId()) {
				return false;
			}
		}
		return true;
	}

	/**
	 * throws hooks when a share is attempted to be accessed
	 *
	 * @param \OCP\Share\IShare|string $share the Share instance if available,
	 * otherwise token
	 * @param int $errorCode
	 * @param string $errorMessage
	 * @throws \OC\HintException
	 * @throws \OC\ServerNotAvailableException
	 */
	protected function emitAccessShareHook($share, $errorCode = 200, $errorMessage = '') {
		$itemType = $itemSource = $uidOwner = '';
		$token = $share;
		$exception = null;
		if($share instanceof \OCP\Share\IShare) {
			try {
				$token = $share->getToken();
				$uidOwner = $share->getSharedBy();
				$itemType = $share->getNodeType();
				$itemSource = $share->getNodeId();
			} catch (\Exception $e) {
				// we log what we know and pass on the exception afterwards
				$exception = $e;
			}
		}
		\OC_Hook::emit('OCP\Share', 'share_link_access', [
			'itemType' => $itemType,
			'itemSource' => $itemSource,
			'uidOwner' => $uidOwner,
			'token' => $token,
			'errorCode' => $errorCode,
			'errorMessage' => $errorMessage,
		]);
		if(!is_null($exception)) {
			throw $exception;
		}
	}

	/**
	 * Validate the permissions of the share
	 *
	 * @param Share\IShare $share
	 * @return bool
	 */
	private function validateShare(\OCP\Share\IShare $share) {
		return $share->getNode()->isReadable() && $share->getNode()->isShareable();
	}

	/**
	 * @PublicPage
	 * @NoCSRFRequired
	 *
	 * @param string $token
	 * @param string $path
	 * @return TemplateResponse|RedirectResponse|NotFoundResponse
	 * @throws NotFoundException
	 * @throws \Exception
	 */
	public function showShare($token, $path = '') {
		\OC_User::setIncognitoMode(true);

		// Check whether share exists
		try {
			$share = $this->shareManager->getShareByToken($token);
		} catch (ShareNotFound $e) {
			$this->emitAccessShareHook($token, 404, 'Share not found');
			return new NotFoundResponse();
		}

		// Share is password protected - check whether the user is permitted to access the share
		if ($share->getPassword() !== null && !$this->linkShareAuth($share)) {
			return new RedirectResponse($this->urlGenerator->linkToRoute('files_sharing.sharecontroller.authenticate',
				array('token' => $token)));
		}

		if (!$this->validateShare($share)) {
			throw new NotFoundException();
		}
		// We can't get the path of a file share
		try {
			if ($share->getNode() instanceof \OCP\Files\File && $path !== '') {
				$this->emitAccessShareHook($share, 404, 'Share not found');
				throw new NotFoundException();
			}
		} catch (\Exception $e) {
			$this->emitAccessShareHook($share, 404, 'Share not found');
			throw $e;
		}

		$shareTmpl = [];
		$shareTmpl['displayName'] = $this->userManager->get($share->getShareOwner())->getDisplayName();
		$shareTmpl['owner'] = $share->getShareOwner();
		$shareTmpl['filename'] = $share->getNode()->getName();
		$shareTmpl['directory_path'] = $share->getTarget();
		$shareTmpl['mimetype'] = $share->getNode()->getMimetype();
		$shareTmpl['previewSupported'] = $this->previewManager->isMimeSupported($share->getNode()->getMimetype());
		$shareTmpl['dirToken'] = $token;
		$shareTmpl['sharingToken'] = $token;
		$shareTmpl['server2serversharing'] = $this->federatedShareProvider->isOutgoingServer2serverShareEnabled();
		$shareTmpl['protected'] = $share->getPassword() !== null ? 'true' : 'false';
		$shareTmpl['dir'] = '';
		$shareTmpl['nonHumanFileSize'] = $share->getNode()->getSize();
		$shareTmpl['fileSize'] = \OCP\Util::humanFileSize($share->getNode()->getSize());

		// Show file list
		$hideFileList = false;
		if ($share->getNode() instanceof \OCP\Files\Folder) {
			/** @var \OCP\Files\Folder $rootFolder */
			$rootFolder = $share->getNode();

			try {
				$folderNode = $rootFolder->get($path);
			} catch (\OCP\Files\NotFoundException $e) {
				$this->emitAccessShareHook($share, 404, 'Share not found');
				throw new NotFoundException();
			}

			$shareTmpl['dir'] = $rootFolder->getRelativePath($folderNode->getPath());

			/*
			 * The OC_Util methods require a view. This just uses the node API
			 */
			$freeSpace = $share->getNode()->getStorage()->free_space($share->getNode()->getInternalPath());
			if ($freeSpace < \OCP\Files\FileInfo::SPACE_UNLIMITED) {
				$freeSpace = max($freeSpace, 0);
			} else {
				$freeSpace = (INF > 0) ? INF: PHP_INT_MAX; // work around https://bugs.php.net/bug.php?id=69188
			}

			$hideFileList = $share->getPermissions() & \OCP\Constants::PERMISSION_READ ? false : true;
			$maxUploadFilesize = $freeSpace;

			$folder = new Template('files', 'list', '');
			$folder->assign('dir', $rootFolder->getRelativePath($folderNode->getPath()));
			$folder->assign('dirToken', $token);
			$folder->assign('permissions', \OCP\Constants::PERMISSION_READ);
			$folder->assign('isPublic', true);
			$folder->assign('hideFileList', $hideFileList);
			$folder->assign('publicUploadEnabled', 'no');
			$folder->assign('uploadMaxFilesize', $maxUploadFilesize);
			$folder->assign('uploadMaxHumanFilesize', \OCP\Util::humanFileSize($maxUploadFilesize));
			$folder->assign('freeSpace', $freeSpace);
			$folder->assign('usedSpacePercent', 0);
			$folder->assign('trash', false);
			$shareTmpl['folder'] = $folder->fetchPage();
		}

		$shareTmpl['hideFileList'] = $hideFileList;
		$shareTmpl['shareOwner'] = $this->userManager->get($share->getShareOwner())->getDisplayName();
		$shareTmpl['downloadURL'] = $this->urlGenerator->linkToRouteAbsolute('files_sharing.sharecontroller.downloadShare', ['token' => $token]);
		$shareTmpl['shareUrl'] = $this->urlGenerator->linkToRouteAbsolute('files_sharing.sharecontroller.showShare', ['token' => $token]);
		$shareTmpl['maxSizeAnimateGif'] = $this->config->getSystemValue('max_filesize_animated_gifs_public_sharing', 10);
		$shareTmpl['previewEnabled'] = $this->config->getSystemValue('enable_previews', true);
		$shareTmpl['previewMaxX'] = $this->config->getSystemValue('preview_max_x', 1024);
		$shareTmpl['previewMaxY'] = $this->config->getSystemValue('preview_max_y', 1024);
		$shareTmpl['disclaimer'] = $this->config->getAppValue('core', 'shareapi_public_link_disclaimertext', null);
		if ($shareTmpl['previewSupported']) {
			$shareTmpl['previewImage'] = $this->urlGenerator->linkToRouteAbsolute( 'files_sharing.PublicPreview.getPreview',
				['x' => 200, 'y' => 200, 'file' => $shareTmpl['directory_path'], 't' => $shareTmpl['dirToken']]);
		} else {
			$shareTmpl['previewImage'] = $this->urlGenerator->getAbsoluteURL($this->urlGenerator->imagePath('core', 'favicon-fb.png'));
		}

		// Load files we need
		\OCP\Util::addScript('files', 'file-upload');
		\OCP\Util::addStyle('files_sharing', 'publicView');
		\OCP\Util::addScript('files_sharing', 'public');
		\OCP\Util::addScript('files', 'fileactions');
		\OCP\Util::addScript('files', 'fileactionsmenu');
		\OCP\Util::addScript('files', 'jquery.fileupload');
		\OCP\Util::addScript('files_sharing', 'files_drop');

		if (isset($shareTmpl['folder'])) {
			// JS required for folders
			\OCP\Util::addStyle('files', 'merged');
			\OCP\Util::addScript('files', 'filesummary');
			\OCP\Util::addScript('files', 'breadcrumb');
			\OCP\Util::addScript('files', 'fileinfomodel');
			\OCP\Util::addScript('files', 'newfilemenu');
			\OCP\Util::addScript('files', 'files');
			\OCP\Util::addScript('files', 'filelist');
			\OCP\Util::addScript('files', 'keyboardshortcuts');
		}

		// OpenGraph Support: http://ogp.me/
		\OCP\Util::addHeader('meta', ['property' => "og:title", 'content' => $this->defaults->getName() . ' - ' . $this->defaults->getSlogan()]);
		\OCP\Util::addHeader('meta', ['property' => "og:description", 'content' => $this->l10n->t('%s is publicly shared', [$shareTmpl['filename']])]);
		\OCP\Util::addHeader('meta', ['property' => "og:site_name", 'content' => $this->defaults->getName()]);
		\OCP\Util::addHeader('meta', ['property' => "og:url", 'content' => $shareTmpl['shareUrl']]);
		\OCP\Util::addHeader('meta', ['property' => "og:type", 'content' => "object"]);
		\OCP\Util::addHeader('meta', ['property' => "og:image", 'content' => $shareTmpl['previewImage']]);

		$this->eventDispatcher->dispatch('OCA\Files_Sharing::loadAdditionalScripts');

		$csp = new \OCP\AppFramework\Http\ContentSecurityPolicy();
		$csp->addAllowedFrameDomain('\'self\'');
		$response = new TemplateResponse($this->appName, 'public', $shareTmpl, 'base');
		$response->setContentSecurityPolicy($csp);

		$this->emitAccessShareHook($share);

		return $response;
	}

	/**
	 * @PublicPage
	 * @NoCSRFRequired
	 *
	 * @param string $token
	 * @param string $files
	 * @param string $path
	 * @param string $downloadStartSecret
	 * @return void|\OCP\AppFramework\Http\Response
	 * @throws NotFoundException
	 */
	public function downloadShare($token, $files = null, $path = '', $downloadStartSecret = '') {
		\OC_User::setIncognitoMode(true);

		$share = $this->shareManager->getShareByToken($token);

		if(!($share->getPermissions() & \OCP\Constants::PERMISSION_READ)) {
			return new \OCP\AppFramework\Http\DataResponse('Share is read-only');
		}

		// Share is password protected - check whether the user is permitted to access the share
		if ($share->getPassword() !== null && !$this->linkShareAuth($share)) {
			return new RedirectResponse($this->urlGenerator->linkToRoute('files_sharing.sharecontroller.authenticate',
				['token' => $token]));
		}

		$files_list = null;
		if (!is_null($files)) { // download selected files
			$files_list = json_decode($files);
			// in case we get only a single file
			if ($files_list === null) {
				$files_list = [$files];
			}
		}

		$userFolder = $this->rootFolder->getUserFolder($share->getShareOwner());
		$originalSharePath = $userFolder->getRelativePath($share->getNode()->getPath());

		if (!$this->validateShare($share)) {
			throw new NotFoundException();
		}

		// Single file share
		if ($share->getNode() instanceof \OCP\Files\File) {
			// Single file download
			$this->singleFileDownloaded($share, $share->getNode());
		}
		// Directory share
		else {
			/** @var \OCP\Files\Folder $node */
			$node = $share->getNode();

			// Try to get the path
			if ($path !== '') {
				try {
					$node = $node->get($path);
				} catch (NotFoundException $e) {
					$this->emitAccessShareHook($share, 404, 'Share not found');
					return new NotFoundResponse();
				}
			}

			$originalSharePath = $userFolder->getRelativePath($node->getPath());

			if ($node instanceof \OCP\Files\File) {
				// Single file download
				$this->singleFileDownloaded($share, $share->getNode());
			} else if (!empty($files_list)) {
				$this->fileListDownloaded($share, $files_list, $node);
			} else {
				// The folder is downloaded
				$this->singleFileDownloaded($share, $share->getNode());
			}
		}

		/* FIXME: We should do this all nicely in OCP */
		OC_Util::tearDownFS();
		OC_Util::setupFS($share->getShareOwner());

		/**
		 * this sets a cookie to be able to recognize the start of the download
		 * the content must not be longer than 32 characters and must only contain
		 * alphanumeric characters
		 */
		if (!empty($downloadStartSecret)
			&& !isset($downloadStartSecret[32])
			&& preg_match('!^[a-zA-Z0-9]+$!', $downloadStartSecret) === 1) {

			// FIXME: set on the response once we use an actual app framework response
			setcookie('ocDownloadStarted', $downloadStartSecret, time() + 20, '/');
		}

		$this->emitAccessShareHook($share);

		$server_params = array( 'head' => $this->request->getMethod() == 'HEAD' );

		/**
		 * Http range requests support
		 */
		if (isset($_SERVER['HTTP_RANGE'])) {
			$server_params['range'] = $this->request->getHeader('Range');
		}

		// download selected files
		if (!is_null($files) && $files !== '') {
			// FIXME: The exit is required here because otherwise the AppFramework is trying to add headers as well
			// after dispatching the request which results in a "Cannot modify header information" notice.
			OC_Files::get($originalSharePath, $files_list, $server_params);
			exit();
		} else {
			// FIXME: The exit is required here because otherwise the AppFramework is trying to add headers as well
			// after dispatching the request which results in a "Cannot modify header information" notice.
			OC_Files::get(dirname($originalSharePath), basename($originalSharePath), $server_params);
			exit();
		}
	}

	/**
	 * create activity for every downloaded file
	 *
	 * @param Share\IShare $share
	 * @param array $files_list
	 * @param \OCP\Files\Folder $node
	 */
	protected function fileListDownloaded(Share\IShare $share, array $files_list, \OCP\Files\Folder $node) {
		foreach ($files_list as $file) {
			$subNode = $node->get($file);
			$this->singleFileDownloaded($share, $subNode);
		}

	}

	/**
	 * create activity if a single file was downloaded from a link share
	 *
	 * @param Share\IShare $share
	 */
	protected function singleFileDownloaded(Share\IShare $share, \OCP\Files\Node $node) {

		$fileId = $node->getId();

		$userFolder = $this->rootFolder->getUserFolder($share->getSharedBy());
		$userNodeList = $userFolder->getById($fileId);
		$userNode = $userNodeList[0];
		$ownerFolder = $this->rootFolder->getUserFolder($share->getShareOwner());
		$userPath = $userFolder->getRelativePath($userNode->getPath());
		$ownerPath = $ownerFolder->getRelativePath($node->getPath());

		$parameters = [$userPath];

		if ($share->getShareType() === \OCP\Share::SHARE_TYPE_EMAIL) {
			if ($node instanceof \OCP\Files\File) {
				$subject = Downloads::SUBJECT_SHARED_FILE_BY_EMAIL_DOWNLOADED;
			} else {
				$subject = Downloads::SUBJECT_SHARED_FOLDER_BY_EMAIL_DOWNLOADED;
			}
			$parameters[] = $share->getSharedWith();
		} else {
			if ($node instanceof \OCP\Files\File) {
				$subject = Downloads::SUBJECT_PUBLIC_SHARED_FILE_DOWNLOADED;
			} else {
				$subject = Downloads::SUBJECT_PUBLIC_SHARED_FOLDER_DOWNLOADED;
			}
		}

		$this->publishActivity($subject, $parameters, $share->getSharedBy(), $fileId, $userPath);

		if ($share->getShareOwner() !== $share->getSharedBy()) {
			$parameters[0] = $ownerPath;
			$this->publishActivity($subject, $parameters, $share->getShareOwner(), $fileId, $ownerPath);
		}
	}

	/**
	 * publish activity
	 *
	 * @param string $subject
	 * @param array $parameters
	 * @param string $affectedUser
	 * @param int $fileId
	 * @param string $filePath
	 */
	protected function publishActivity($subject,
										array $parameters,
										$affectedUser,
										$fileId,
										$filePath) {

		$event = $this->activityManager->generateEvent();
		$event->setApp('files_sharing')
			->setType('public_links')
			->setSubject($subject, $parameters)
			->setAffectedUser($affectedUser)
			->setObject('files', $fileId, $filePath);
		$this->activityManager->publish($event);
	}


}
