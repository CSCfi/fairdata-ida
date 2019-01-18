<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Bart Visscher <bartv@thisnet.nl>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
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

namespace OC\Template;

use OCP\ILogger;

class CSSResourceLocator extends ResourceLocator {

	/** @var SCSSCacher */
	protected $scssCacher;

	/**
	 * @param ILogger $logger
	 * @param string $theme
	 * @param array $core_map
	 * @param array $party_map
	 * @param SCSSCacher $scssCacher
	 */
	public function __construct(ILogger $logger, $theme, $core_map, $party_map, $scssCacher) {
		$this->scssCacher = $scssCacher;

		parent::__construct($logger, $theme, $core_map, $party_map);
	}

	/**
	 * @param string $style
	 */
	public function doFind($style) {
		$app = substr($style, 0, strpos($style, '/'));
		if (strpos($style, '3rdparty') === 0
			&& $this->appendIfExist($this->thirdpartyroot, $style.'.css')
			|| $this->cacheAndAppendScssIfExist($this->serverroot, $style.'.scss', $app)
			|| $this->cacheAndAppendScssIfExist($this->serverroot, 'core/'.$style.'.scss')
			|| $this->appendIfExist($this->serverroot, $style.'.css')
			|| $this->appendIfExist($this->serverroot, 'core/'.$style.'.css')
		) {
			return;
		}
		$style = substr($style, strpos($style, '/')+1);
		$app_path = \OC_App::getAppPath($app);
		$app_url = \OC_App::getAppWebPath($app);

		if ($app_path === false && $app_url === false) {
			$this->logger->error('Could not find resource {resource} to load', [
				'resource' => $app . '/' . $style . '.css',
				'app' => 'cssresourceloader',
			]);
			return;
		}

		if(!$this->cacheAndAppendScssIfExist($app_path, $style.'.scss', $app)) {
			$this->append($app_path, $style.'.css', $app_url);
		}
	}

	/**
	 * @param string $style
	 */
	public function doFindTheme($style) {
		$theme_dir = 'themes/'.$this->theme.'/';
		$this->appendIfExist($this->serverroot, $theme_dir.'apps/'.$style.'.css')
			|| $this->appendIfExist($this->serverroot, $theme_dir.$style.'.css')
			|| $this->appendIfExist($this->serverroot, $theme_dir.'core/'.$style.'.css');
	}

	/**
	 * cache and append the scss $file if exist at $root
	 *
	 * @param string $root path to check
	 * @param string $file the filename
	 * @return bool True if the resource was found and cached, false otherwise
	 */
	protected function cacheAndAppendScssIfExist($root, $file, $app = 'core') {
		if (is_file($root.'/'.$file)) {
			if($this->scssCacher !== null) {
				if($this->scssCacher->process($root, $file, $app)) {

					$this->append($root, $this->scssCacher->getCachedSCSS($app, $file), false, true, true);
					return true;
				} else {
					$this->logger->warning('Failed to compile and/or save '.$root.'/'.$file, ['app' => 'core']);
					return false;
				}
			} else {
				$this->logger->debug('Scss is disabled for '.$root.'/'.$file.', ignoring', ['app' => 'core']);
				return true;
			}
		}
		return false;
	}

	public function append($root, $file, $webRoot = null, $throw = true, $scss = false) {
		if (!$scss) {
			parent::append($root, $file, $webRoot, $throw);
		} else {
			if (!$webRoot) {
				$tmpRoot = realpath($root);
				/*
				 * traverse the potential web roots upwards in the path
				 *
				 * example:
				 *   - root: /srv/www/apps/myapp
				 *   - available mappings: ['/srv/www']
				 *
				 * First we check if a mapping for /srv/www/apps/myapp is available,
				 * then /srv/www/apps, /srv/www/apps, /srv/www, ... until we find a
				 * valid web root
				 */
				do {
					if (isset($this->mapping[$tmpRoot])) {
						$webRoot = $this->mapping[$tmpRoot];
						break;
					}

					if ($tmpRoot === '/') {
						$webRoot = '';
						$this->logger->error('ResourceLocator can not find a web root (root: {root}, file: {file}, webRoot: {webRoot}, throw: {throw})', [
							'app' => 'lib',
							'root' => $root,
							'file' => $file,
							'webRoot' => $webRoot,
							'throw' => $throw ? 'true' : 'false'
						]);
						break;
					}
					$tmpRoot = dirname($tmpRoot);
				} while(true);

			}

			if ($throw && $tmpRoot === '/') {
				throw new ResourceNotFoundException($file, $webRoot);
			}

			$this->resources[] = array($tmpRoot, $webRoot, $file);
		}
	}
}
