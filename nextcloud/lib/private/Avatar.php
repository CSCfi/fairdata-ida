<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Christopher Schäpers <kondou@ts.unde.re>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
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

namespace OC;

use OC\User\User;
use OCP\Files\NotFoundException;
use OCP\Files\NotPermittedException;
use OCP\Files\SimpleFS\ISimpleFile;
use OCP\Files\SimpleFS\ISimpleFolder;
use OCP\IAvatar;
use OCP\IConfig;
use OCP\IImage;
use OCP\IL10N;
use OC_Image;
use OCP\ILogger;

/**
 * This class gets and sets users avatars.
 */

class Avatar implements IAvatar {
	/** @var ISimpleFolder */
	private $folder;
	/** @var IL10N */
	private $l;
	/** @var User */
	private $user;
	/** @var ILogger  */
	private $logger;
	/** @var IConfig */
	private $config;

	/**
	 * constructor
	 *
	 * @param ISimpleFolder $folder The folder where the avatars are
	 * @param IL10N $l
	 * @param User $user
	 * @param ILogger $logger
	 * @param IConfig $config
	 */
	public function __construct(ISimpleFolder $folder,
								IL10N $l,
								$user,
								ILogger $logger,
								IConfig $config) {
		$this->folder = $folder;
		$this->l = $l;
		$this->user = $user;
		$this->logger = $logger;
		$this->config = $config;
	}

	/**
	 * @inheritdoc
	 */
	public function get ($size = 64) {
		try {
			$file = $this->getFile($size);
		} catch (NotFoundException $e) {
			return false;
		}

		$avatar = new OC_Image();
		$avatar->loadFromData($file->getContent());
		return $avatar;
	}

	/**
	 * Check if an avatar exists for the user
	 *
	 * @return bool
	 */
	public function exists() {

		return $this->folder->fileExists('avatar.jpg') || $this->folder->fileExists('avatar.png');
	}

	/**
	 * sets the users avatar
	 * @param IImage|resource|string $data An image object, imagedata or path to set a new avatar
	 * @throws \Exception if the provided file is not a jpg or png image
	 * @throws \Exception if the provided image is not valid
	 * @throws NotSquareException if the image is not square
	 * @return void
	*/
	public function set ($data) {

		if($data instanceOf IImage) {
			$img = $data;
			$data = $img->data();
		} else {
			$img = new OC_Image($data);
		}
		$type = substr($img->mimeType(), -3);
		if ($type === 'peg') {
			$type = 'jpg';
		}
		if ($type !== 'jpg' && $type !== 'png') {
			throw new \Exception($this->l->t("Unknown filetype"));
		}

		if (!$img->valid()) {
			throw new \Exception($this->l->t("Invalid image"));
		}

		if (!($img->height() === $img->width())) {
			throw new NotSquareException($this->l->t("Avatar image is not square"));
		}

		$this->remove();
		$this->folder->newFile('avatar.'.$type)->putContent($data);
		$this->user->triggerChange('avatar');
	}

	/**
	 * remove the users avatar
	 * @return void
	*/
	public function remove () {
		$regex = '/^avatar\.([0-9]+\.)?(jpg|png)$/';
		$avatars = $this->folder->getDirectoryListing();

		$this->config->setUserValue($this->user->getUID(), 'avatar', 'version',
			(int)$this->config->getUserValue($this->user->getUID(), 'avatar', 'version', 0) + 1);

		foreach ($avatars as $avatar) {
			if (preg_match($regex, $avatar->getName())) {
				$avatar->delete();
			}
		}
		$this->user->triggerChange('avatar');
	}

	/**
	 * @inheritdoc
	 */
	public function getFile($size) {
		$ext = $this->getExtension();

		if ($size === -1) {
			$path = 'avatar.' . $ext;
		} else {
			$path = 'avatar.' . $size . '.' . $ext;
		}

		try {
			$file = $this->folder->getFile($path);
		} catch (NotFoundException $e) {
			if ($size <= 0) {
				throw new NotFoundException;
			}

			$avatar = new OC_Image();
			/** @var ISimpleFile $file */
			$file = $this->folder->getFile('avatar.' . $ext);
			$avatar->loadFromData($file->getContent());
			if ($size !== -1) {
				$avatar->resize($size);
			}
			try {
				$file = $this->folder->newFile($path);
				$file->putContent($avatar->data());
			} catch (NotPermittedException $e) {
				$this->logger->error('Failed to save avatar for ' . $this->user->getUID());
			}
		}

		return $file;
	}

	/**
	 * Get the extension of the avatar. If there is no avatar throw Exception
	 *
	 * @return string
	 * @throws NotFoundException
	 */
	private function getExtension() {
		if ($this->folder->fileExists('avatar.jpg')) {
			return 'jpg';
		} elseif ($this->folder->fileExists('avatar.png')) {
			return 'png';
		}
		throw new NotFoundException;
	}
}
