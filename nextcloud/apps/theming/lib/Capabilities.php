<?php
/**
 * @copyright Copyright (c) 2016, Joas Schilling <coding@schilljs.com>
 *
 * @author Joas Schilling <coding@schilljs.com>
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

namespace OCA\Theming;

use OCP\Capabilities\ICapability;
use OCP\IConfig;
use OCP\IURLGenerator;

/**
 * Class Capabilities
 *
 * @package OCA\Theming
 */
class Capabilities implements ICapability {

	/** @var ThemingDefaults */
	protected $theming;

	/** @var Util */
	protected $util;

	/** @var IURLGenerator */
	protected $url;

	/** @var IConfig */
	protected $config;

	/**
	 * @param ThemingDefaults $theming
	 * @param Util $util
	 * @param IURLGenerator $url
	 * @param IConfig $config
	 */
	public function __construct(ThemingDefaults $theming, Util $util, IURLGenerator $url, IConfig $config) {
		$this->theming = $theming;
		$this->util = $util;
		$this->url = $url;
		$this->config = $config;
	}

	/**
	 * Return this classes capabilities
	 *
	 * @return array
	 */
	public function getCapabilities() {
		$backgroundLogo = $this->config->getAppValue('theming', 'backgroundMime', false);

		return [
			'theming' => [
				'name' => $this->theming->getName(),
				'url' => $this->theming->getBaseUrl(),
				'slogan' => $this->theming->getSlogan(),
				'color' => $this->theming->getColorPrimary(),
				'color-text' => $this->util->invertTextColor($this->theming->getColorPrimary()) ? '#000000' : '#FFFFFF',
				'logo' => $this->url->getAbsoluteURL($this->theming->getLogo()),
				'background' => $backgroundLogo === 'backgroundColor' ?
					$this->theming->getColorPrimary() :
					$this->url->getAbsoluteURL($this->theming->getBackground()),
			],
		];
	}
}
