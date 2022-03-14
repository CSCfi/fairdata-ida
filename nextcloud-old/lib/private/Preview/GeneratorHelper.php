<?php
/**
 * @copyright Copyright (c) 2016, Roeland Jago Douma <roeland@famdouma.nl>
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
namespace OC\Preview;

use OC\Files\View;
use OCP\Files\File;
use OCP\Files\IRootFolder;
use OCP\Files\SimpleFS\ISimpleFile;
use OCP\IConfig;
use OCP\IImage;
use OCP\Image as OCPImage;
use OCP\Preview\IProvider;

/**
 * Very small wrapper class to make the generator fully unit testable
 */
class GeneratorHelper {

	/** @var IRootFolder */
	private $rootFolder;

	/** @var IConfig */
	private $config;

	public function __construct(IRootFolder $rootFolder, IConfig $config) {
		$this->rootFolder = $rootFolder;
		$this->config = $config;
	}

	/**
	 * @param IProvider $provider
	 * @param File $file
	 * @param int $maxWidth
	 * @param int $maxHeight
	 * @return bool|IImage
	 */
	public function getThumbnail(IProvider $provider, File $file, $maxWidth, $maxHeight) {
		list($view, $path) = $this->getViewAndPath($file);
		return $provider->getThumbnail($path, $maxWidth, $maxHeight, false, $view);
	}

	/**
	 * @param File $file
	 * @return array
	 * This is required to create the old view and path
	 */
	private function getViewAndPath(File $file) {
		$view = new View($file->getParent()->getPath());
		$path = $file->getName();

		return [$view, $path];
	}

	/**
	 * @param ISimpleFile $maxPreview
	 * @return IImage
	 */
	public function getImage(ISimpleFile $maxPreview) {
		$image = new OCPImage();
		$image->loadFromData($maxPreview->getContent());
		return $image;
	}

	/**
	 * @param $provider
	 * @return IProvider
	 */
	public function getProvider($provider) {
		return $provider();
	}
}
