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

return [
	'resources' => [
		'ExternalShares' => ['url' => '/api/externalShares'],
	],
	'routes' => [
		[
			'name' => 'externalShares#testRemote',
			'url' => '/testremote',
			'verb' => 'GET'
		],
		[
			'name' => 'PublicPreview#getPreview',
			'url' => '/publicpreview/{token}',
			'verb' => 'GET',
		],

		[
			'name' => 'ShareInfo#info',
			'url' => '/shareinfo',
			'verb' => 'POST',
		],
	],
	'ocs' => [
		/*
		 * OCS Share API
		 */
		[
			'name' => 'ShareAPI#getShares',
			'url'  => '/api/v1/shares',
			'verb' => 'GET',
		],
		[
			'name' => 'ShareAPI#createShare',
			'url'  => '/api/v1/shares',
			'verb' => 'POST',
		],
		[
			'name' => 'ShareAPI#getShare',
			'url'  => '/api/v1/shares/{id}',
			'verb' => 'GET',
		],
		[
			'name' => 'ShareAPI#updateShare',
			'url'  => '/api/v1/shares/{id}',
			'verb' => 'PUT',
		],
		[
			'name' => 'ShareAPI#deleteShare',
			'url'  => '/api/v1/shares/{id}',
			'verb' => 'DELETE',
		],
		/*
		 * Deleted Shares
		 */
		[
			'name' => 'DeletedShareAPI#index',
			'url'  => '/api/v1/deletedshares',
			'verb' => 'GET',
		],
		[
			'name' => 'DeletedShareAPI#undelete',
			'url'  => '/api/v1/deletedshares/{id}',
			'verb' => 'POST',
		],
		/*
		 * OCS Sharee API
		 */
		[
			'name' => 'ShareesAPI#search',
			'url' => '/api/v1/sharees',
			'verb' => 'GET',
		],
		[
			'name' => 'ShareesAPI#findRecommended',
			'url' => '/api/v1/sharees_recommended',
			'verb' => 'GET',
		],
		/*
		 * Remote Shares
		 */
		[
			'name' => 'Remote#getShares',
			'url' => '/api/v1/remote_shares',
			'verb' => 'GET',
		],
		[
			'name' => 'Remote#getOpenShares',
			'url' => '/api/v1/remote_shares/pending',
			'verb' => 'GET',
		],
		[
			'name' => 'Remote#acceptShare',
			'url' => '/api/v1/remote_shares/pending/{id}',
			'verb' => 'POST',
		],
		[
			'name' => 'Remote#declineShare',
			'url' => '/api/v1/remote_shares/pending/{id}',
			'verb' => 'DELETE',
		],
		[
			'name' => 'Remote#getShare',
			'url' => '/api/v1/remote_shares/{id}',
			'verb' => 'GET',
		],
		[
			'name' => 'Remote#unshare',
			'url' => '/api/v1/remote_shares/{id}',
			'verb' => 'DELETE',
		],
	],
];
