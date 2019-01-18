<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Björn Schießle <bjoern@schiessle.org>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
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
namespace OC\Share20;

use OC\CapabilitiesManager;
use OC\GlobalScale\Config;
use OCA\FederatedFileSharing\AddressHandler;
use OCA\FederatedFileSharing\FederatedShareProvider;
use OCA\FederatedFileSharing\Notifications;
use OCA\FederatedFileSharing\TokenHandler;
use OCA\ShareByMail\Settings\SettingsManager;
use OCA\ShareByMail\ShareByMailProvider;
use OCP\Defaults;
use OCP\Share\IProviderFactory;
use OC\Share20\Exception\ProviderException;
use OCP\IServerContainer;

/**
 * Class ProviderFactory
 *
 * @package OC\Share20
 */
class ProviderFactory implements IProviderFactory {

	/** @var IServerContainer */
	private $serverContainer;
	/** @var DefaultShareProvider */
	private $defaultProvider = null;
	/** @var FederatedShareProvider */
	private $federatedProvider = null;
	/** @var  ShareByMailProvider */
	private $shareByMailProvider;
	/** @var  \OCA\Circles\ShareByCircleProvider */
	private $shareByCircleProvider = null;
	/** @var bool */
	private $circlesAreNotAvailable = false;

	/**
	 * IProviderFactory constructor.
	 *
	 * @param IServerContainer $serverContainer
	 */
	public function __construct(IServerContainer $serverContainer) {
		$this->serverContainer = $serverContainer;
	}

	/**
	 * Create the default share provider.
	 *
	 * @return DefaultShareProvider
	 */
	protected function defaultShareProvider() {
		if ($this->defaultProvider === null) {
			$this->defaultProvider = new DefaultShareProvider(
				$this->serverContainer->getDatabaseConnection(),
				$this->serverContainer->getUserManager(),
				$this->serverContainer->getGroupManager(),
				$this->serverContainer->getLazyRootFolder()
			);
		}

		return $this->defaultProvider;
	}

	/**
	 * Create the federated share provider
	 *
	 * @return FederatedShareProvider
	 */
	protected function federatedShareProvider() {
		if ($this->federatedProvider === null) {
			/*
			 * Check if the app is enabled
			 */
			$appManager = $this->serverContainer->getAppManager();
			if (!$appManager->isEnabledForUser('federatedfilesharing')) {
				return null;
			}

			/*
			 * TODO: add factory to federated sharing app
			 */
			$l = $this->serverContainer->getL10N('federatedfilessharing');
			$addressHandler = new AddressHandler(
				$this->serverContainer->getURLGenerator(),
				$l,
				$this->serverContainer->getCloudIdManager()
			);
			$notifications = new Notifications(
				$addressHandler,
				$this->serverContainer->getHTTPClientService(),
				$this->serverContainer->query(\OCP\OCS\IDiscoveryService::class),
				$this->serverContainer->getJobList()
			);
			$tokenHandler = new TokenHandler(
				$this->serverContainer->getSecureRandom()
			);

			$this->federatedProvider = new FederatedShareProvider(
				$this->serverContainer->getDatabaseConnection(),
				$addressHandler,
				$notifications,
				$tokenHandler,
				$l,
				$this->serverContainer->getLogger(),
				$this->serverContainer->getLazyRootFolder(),
				$this->serverContainer->getConfig(),
				$this->serverContainer->getUserManager(),
				$this->serverContainer->getCloudIdManager(),
				$this->serverContainer->query(Config::class)
			);
		}

		return $this->federatedProvider;
	}

	/**
	 * Create the federated share provider
	 *
	 * @return ShareByMailProvider
	 */
	protected function getShareByMailProvider() {
		if ($this->shareByMailProvider === null) {
			/*
			 * Check if the app is enabled
			 */
			$appManager = $this->serverContainer->getAppManager();
			if (!$appManager->isEnabledForUser('sharebymail')) {
				return null;
			}

			$settingsManager = new SettingsManager($this->serverContainer->getConfig());

			$this->shareByMailProvider = new ShareByMailProvider(
				$this->serverContainer->getDatabaseConnection(),
				$this->serverContainer->getSecureRandom(),
				$this->serverContainer->getUserManager(),
				$this->serverContainer->getLazyRootFolder(),
				$this->serverContainer->getL10N('sharebymail'),
				$this->serverContainer->getLogger(),
				$this->serverContainer->getMailer(),
				$this->serverContainer->getURLGenerator(),
				$this->serverContainer->getActivityManager(),
				$settingsManager,
				$this->serverContainer->query(Defaults::class),
				$this->serverContainer->getHasher(),
				$this->serverContainer->query(CapabilitiesManager::class)
			);
		}

		return $this->shareByMailProvider;
	}


	/**
	 * Create the circle share provider
	 *
	 * @return FederatedShareProvider
	 */
	protected function getShareByCircleProvider() {

		if ($this->circlesAreNotAvailable) {
			return null;
		}

		if (!$this->serverContainer->getAppManager()->isEnabledForUser('circles') ||
			!class_exists('\OCA\Circles\ShareByCircleProvider')
		) {
			$this->circlesAreNotAvailable = true;
			return null;
		}

		if ($this->shareByCircleProvider === null) {

			$this->shareByCircleProvider = new \OCA\Circles\ShareByCircleProvider(
				$this->serverContainer->getDatabaseConnection(),
				$this->serverContainer->getSecureRandom(),
				$this->serverContainer->getUserManager(),
				$this->serverContainer->getLazyRootFolder(),
				$this->serverContainer->getL10N('circles'),
				$this->serverContainer->getLogger(),
				$this->serverContainer->getURLGenerator()
			);
		}

		return $this->shareByCircleProvider;
	}


	/**
	 * @inheritdoc
	 */
	public function getProvider($id) {
		$provider = null;
		if ($id === 'ocinternal') {
			$provider = $this->defaultShareProvider();
		} else if ($id === 'ocFederatedSharing') {
			$provider = $this->federatedShareProvider();
		} else if ($id === 'ocMailShare') {
			$provider = $this->getShareByMailProvider();
		} else if ($id === 'ocCircleShare') {
			$provider = $this->getShareByCircleProvider();
		}

		if ($provider === null) {
			throw new ProviderException('No provider with id .' . $id . ' found.');
		}

		return $provider;
	}

	/**
	 * @inheritdoc
	 */
	public function getProviderForType($shareType) {
		$provider = null;

		if ($shareType === \OCP\Share::SHARE_TYPE_USER ||
			$shareType === \OCP\Share::SHARE_TYPE_GROUP ||
			$shareType === \OCP\Share::SHARE_TYPE_LINK
		) {
			$provider = $this->defaultShareProvider();
		} else if ($shareType === \OCP\Share::SHARE_TYPE_REMOTE) {
			$provider = $this->federatedShareProvider();
		} else if ($shareType === \OCP\Share::SHARE_TYPE_EMAIL) {
			$provider = $this->getShareByMailProvider();
		} else if ($shareType === \OCP\Share::SHARE_TYPE_CIRCLE) {
			$provider = $this->getShareByCircleProvider();
		}


		if ($provider === null) {
			throw new ProviderException('No share provider for share type ' . $shareType);
		}

		return $provider;
	}

	public function getAllProviders() {
		$shares = [$this->defaultShareProvider(), $this->federatedShareProvider()];
		$shareByMail = $this->getShareByMailProvider();
		if ($shareByMail !== null) {
			$shares[] = $shareByMail;
		}
		$shareByCircle = $this->getShareByCircleProvider();
		if ($shareByCircle !== null) {
			$shares[] = $shareByCircle;
		}

		return $shares;
	}
}
