<?php
/**
 * @copyright Copyright (c) 2017 Arthur Schiwon <blizzz@arthur-schiwon.de>
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
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

namespace OC\Collaboration\Collaborators;


use OCP\Collaboration\Collaborators\ISearchPlugin;
use OCP\Collaboration\Collaborators\ISearchResult;
use OCP\Collaboration\Collaborators\SearchResultType;
use OCP\Federation\ICloudFederationProviderManager;
use OCP\Federation\ICloudIdManager;
use OCP\Share;

class RemoteGroupPlugin implements ISearchPlugin {
	protected $shareeEnumeration;

	/** @var ICloudIdManager */
	private $cloudIdManager;
	/** @var bool */
	private $enabled = false;

	public function __construct(ICloudFederationProviderManager $cloudFederationProviderManager, ICloudIdManager $cloudIdManager) {
		try {
			$fileSharingProvider = $cloudFederationProviderManager->getCloudFederationProvider('file');
			$supportedShareTypes = $fileSharingProvider->getSupportedShareTypes();
			if (in_array('group', $supportedShareTypes)) {
				$this->enabled = true;
			}
		} catch (\Exception $e) {
			// do nothing, just don't enable federated group shares
		}
		$this->cloudIdManager = $cloudIdManager;
	}

	public function search($search, $limit, $offset, ISearchResult $searchResult) {
		$result = ['wide' => [], 'exact' => []];
		$resultType = new SearchResultType('remote_groups');

		if ($this->enabled && $this->cloudIdManager->isValidCloudId($search) && $offset === 0) {
			$result['exact'][] = [
				'label' => $search,
				'value' => [
					'shareType' => Share::SHARE_TYPE_REMOTE_GROUP,
					'shareWith' => $search,
				],
			];
		}

		$searchResult->addResultSet($resultType, $result['wide'], $result['exact']);

		return true;
	}

}
