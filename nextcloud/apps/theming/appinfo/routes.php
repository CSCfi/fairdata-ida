<?php
/**
 * @copyright Copyright (c) 2016 Bjoern Schiessle <bjoern@schiessle.org>
 * @copyright Copyright (c) 2016 Lukas Reschke <lukas@statuscode.ch>
 *
 * @author Bjoern Schiessle <bjoern@schiessle.org>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author oparoz <owncloud@interfasys.ch>
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

return ['routes' => [
	[
		'name' => 'Theming#updateStylesheet',
		'url' => '/ajax/updateStylesheet',
		'verb' => 'POST'
	],
	[
		'name' => 'Theming#undo',
		'url' => '/ajax/undoChanges',
		'verb' => 'POST'
	],
	[
		'name' => 'Theming#updateLogo',
		'url' => '/ajax/updateLogo',
		'verb' => 'POST'
	],
	[
		'name' => 'Theming#getStylesheet',
		'url' => '/styles',
		'verb' => 'GET',
	],
	[
		'name' => 'Theming#getLogo',
		'url' => '/logo',
		'verb' => 'GET',
	],
	[
		'name' => 'Theming#getLoginBackground',
		'url' => '/loginbackground',
		'verb' => 'GET',
	],
	[
		'name' => 'Theming#getJavascript',
		'url' => '/js/theming',
		'verb' => 'GET',
	],
	[
		'name'	=> 'Icon#getFavicon',
		'url' => '/favicon/{app}',
		'verb' => 'GET',
		'defaults' => array('app' => 'core'),
	],
	[
		'name'	=> 'Icon#getTouchIcon',
		'url' => '/icon/{app}',
		'verb' => 'GET',
		'defaults' => array('app' => 'core'),
	],
	[
		'name'	=> 'Icon#getThemedIcon',
		'url' => '/img/{app}/{image}',
		'verb' => 'GET',
		'requirements' => array('image' => '.+')
	],
]];

