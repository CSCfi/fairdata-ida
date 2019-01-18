<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Jesús Macias <jmacias@solidgear.es>
 * @author Jörn Friedrich Dreyer <jfd@butonic.de>
 * @author Michael Gapczynski <GapczynskiM@gmail.com>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Philipp Kapfer <philipp.kapfer@gmx.at>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Robin McCorkell <robin@mccorkell.me.uk>
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

namespace OCA\Files_External\Lib\Storage;

use Icewind\SMB\Exception\AlreadyExistsException;
use Icewind\SMB\Exception\ConnectException;
use Icewind\SMB\Exception\Exception;
use Icewind\SMB\Exception\ForbiddenException;
use Icewind\SMB\Exception\NotFoundException;
use Icewind\SMB\IFileInfo;
use Icewind\SMB\NativeServer;
use Icewind\SMB\Server;
use Icewind\Streams\CallbackWrapper;
use Icewind\Streams\IteratorDirectory;
use OC\Cache\CappedMemoryCache;
use OC\Files\Filesystem;
use OC\Files\Storage\Common;
use OCA\Files_External\Lib\Notify\SMBNotifyHandler;
use OCP\Files\Notify\IChange;
use OCP\Files\Notify\IRenameChange;
use OCP\Files\Storage\INotifyStorage;
use OCP\Files\StorageNotAvailableException;

class SMB extends Common implements INotifyStorage {
	/**
	 * @var \Icewind\SMB\Server
	 */
	protected $server;

	/**
	 * @var \Icewind\SMB\Share
	 */
	protected $share;

	/**
	 * @var string
	 */
	protected $root;

	/**
	 * @var \Icewind\SMB\FileInfo[]
	 */
	protected $statCache;

	public function __construct($params) {
		if (isset($params['host']) && isset($params['user']) && isset($params['password']) && isset($params['share'])) {
			if (Server::NativeAvailable()) {
				$this->server = new NativeServer($params['host'], $params['user'], $params['password']);
			} else {
				$this->server = new Server($params['host'], $params['user'], $params['password']);
			}
			$this->share = $this->server->getShare(trim($params['share'], '/'));

			$this->root = isset($params['root']) ? $params['root'] : '/';
			if (!$this->root || $this->root[0] != '/') {
				$this->root = '/' . $this->root;
			}
			if (substr($this->root, -1, 1) != '/') {
				$this->root .= '/';
			}
		} else {
			throw new \Exception('Invalid configuration');
		}
		$this->statCache = new CappedMemoryCache();
		parent::__construct($params);
	}

	/**
	 * @return string
	 */
	public function getId() {
		// FIXME: double slash to keep compatible with the old storage ids,
		// failure to do so will lead to creation of a new storage id and
		// loss of shares from the storage
		return 'smb::' . $this->server->getUser() . '@' . $this->server->getHost() . '//' . $this->share->getName() . '/' . $this->root;
	}

	/**
	 * @param string $path
	 * @return string
	 */
	protected function buildPath($path) {
		return Filesystem::normalizePath($this->root . '/' . $path, true, false, true);
	}

	protected function relativePath($fullPath) {
		if ($fullPath === $this->root) {
			return '';
		} else if (substr($fullPath, 0, strlen($this->root)) === $this->root) {
			return substr($fullPath, strlen($this->root));
		} else {
			return null;
		}
	}

	/**
	 * @param string $path
	 * @return \Icewind\SMB\IFileInfo
	 * @throws StorageNotAvailableException
	 */
	protected function getFileInfo($path) {
		try {
			$path = $this->buildPath($path);
			if (!isset($this->statCache[$path])) {
				$this->statCache[$path] = $this->share->stat($path);
			}
			return $this->statCache[$path];
		} catch (ConnectException $e) {
			throw new StorageNotAvailableException($e->getMessage(), $e->getCode(), $e);
		}
	}

	/**
	 * @param string $path
	 * @return \Icewind\SMB\IFileInfo[]
	 * @throws StorageNotAvailableException
	 */
	protected function getFolderContents($path) {
		try {
			$path = $this->buildPath($path);
			$files = $this->share->dir($path);
			foreach ($files as $file) {
				$this->statCache[$path . '/' . $file->getName()] = $file;
			}
			return array_filter($files, function (IFileInfo $file) {
				return !$file->isHidden();
			});
		} catch (ConnectException $e) {
			throw new StorageNotAvailableException($e->getMessage(), $e->getCode(), $e);
		}
	}

	/**
	 * @param \Icewind\SMB\IFileInfo $info
	 * @return array
	 */
	protected function formatInfo($info) {
		$result = [
			'size' => $info->getSize(),
			'mtime' => $info->getMTime(),
		];
		if ($info->isDirectory()) {
			$result['type'] = 'dir';
		} else {
			$result['type'] = 'file';
		}
		return $result;
	}

	/**
	 * Rename the files. If the source or the target is the root, the rename won't happen.
	 *
	 * @param string $source the old name of the path
	 * @param string $target the new name of the path
	 * @return bool true if the rename is successful, false otherwise
	 */
	public function rename($source, $target) {
		if ($this->isRootDir($source) || $this->isRootDir($target)) {
			return false;
		}

		$absoluteSource = $this->buildPath($source);
		$absoluteTarget = $this->buildPath($target);
		try {
			$result = $this->share->rename($absoluteSource, $absoluteTarget);
		} catch (AlreadyExistsException $e) {
			$this->remove($target);
			$result = $this->share->rename($absoluteSource, $absoluteTarget);
		} catch (\Exception $e) {
			return false;
		}
		unset($this->statCache[$absoluteSource], $this->statCache[$absoluteTarget]);
		return $result;
	}

	/**
	 * @param string $path
	 * @return array
	 */
	public function stat($path) {
		$result = $this->formatInfo($this->getFileInfo($path));
		if ($this->remoteIsShare() && $this->isRootDir($path)) {
			$result['mtime'] = $this->shareMTime();
		}
		return $result;
	}

	/**
	 * get the best guess for the modification time of the share
	 *
	 * @return int
	 */
	private function shareMTime() {
		$highestMTime = 0;
		$files = $this->share->dir($this->root);
		foreach ($files as $fileInfo) {
			if ($fileInfo->getMTime() > $highestMTime) {
				$highestMTime = $fileInfo->getMTime();
			}
		}
		return $highestMTime;
	}

	/**
	 * Check if the path is our root dir (not the smb one)
	 *
	 * @param string $path the path
	 * @return bool
	 */
	private function isRootDir($path) {
		return $path === '' || $path === '/' || $path === '.';
	}

	/**
	 * Check if our root points to a smb share
	 *
	 * @return bool true if our root points to a share false otherwise
	 */
	private function remoteIsShare() {
		return $this->share->getName() && (!$this->root || $this->root === '/');
	}

	/**
	 * @param string $path
	 * @return bool
	 */
	public function unlink($path) {
		if ($this->isRootDir($path)) {
			return false;
		}

		try {
			if ($this->is_dir($path)) {
				return $this->rmdir($path);
			} else {
				$path = $this->buildPath($path);
				unset($this->statCache[$path]);
				$this->share->del($path);
				return true;
			}
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		} catch (ConnectException $e) {
			throw new StorageNotAvailableException($e->getMessage(), $e->getCode(), $e);
		}
	}

	/**
	 * check if a file or folder has been updated since $time
	 *
	 * @param string $path
	 * @param int $time
	 * @return bool
	 */
	public function hasUpdated($path, $time) {
		if (!$path and $this->root === '/') {
			// mtime doesn't work for shares, but giving the nature of the backend,
			// doing a full update is still just fast enough
			return true;
		} else {
			$actualTime = $this->filemtime($path);
			return $actualTime > $time;
		}
	}

	/**
	 * @param string $path
	 * @param string $mode
	 * @return resource|false
	 */
	public function fopen($path, $mode) {
		$fullPath = $this->buildPath($path);
		try {
			switch ($mode) {
				case 'r':
				case 'rb':
					if (!$this->file_exists($path)) {
						return false;
					}
					return $this->share->read($fullPath);
				case 'w':
				case 'wb':
					$source = $this->share->write($fullPath);
					return CallBackWrapper::wrap($source, null, null, function () use ($fullPath) {
						unset($this->statCache[$fullPath]);
					});
				case 'a':
				case 'ab':
				case 'r+':
				case 'w+':
				case 'wb+':
				case 'a+':
				case 'x':
				case 'x+':
				case 'c':
				case 'c+':
					//emulate these
					if (strrpos($path, '.') !== false) {
						$ext = substr($path, strrpos($path, '.'));
					} else {
						$ext = '';
					}
					if ($this->file_exists($path)) {
						if (!$this->isUpdatable($path)) {
							return false;
						}
						$tmpFile = $this->getCachedFile($path);
					} else {
						if (!$this->isCreatable(dirname($path))) {
							return false;
						}
						$tmpFile = \OCP\Files::tmpFile($ext);
					}
					$source = fopen($tmpFile, $mode);
					$share = $this->share;
					return CallbackWrapper::wrap($source, null, null, function () use ($tmpFile, $fullPath, $share) {
						unset($this->statCache[$fullPath]);
						$share->put($tmpFile, $fullPath);
						unlink($tmpFile);
					});
			}
			return false;
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		} catch (ConnectException $e) {
			throw new StorageNotAvailableException($e->getMessage(), $e->getCode(), $e);
		}
	}

	public function rmdir($path) {
		if ($this->isRootDir($path)) {
			return false;
		}

		try {
			$this->statCache = array();
			$content = $this->share->dir($this->buildPath($path));
			foreach ($content as $file) {
				if ($file->isDirectory()) {
					$this->rmdir($path . '/' . $file->getName());
				} else {
					$this->share->del($file->getPath());
				}
			}
			$this->share->rmdir($this->buildPath($path));
			return true;
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		} catch (ConnectException $e) {
			throw new StorageNotAvailableException($e->getMessage(), $e->getCode(), $e);
		}
	}

	public function touch($path, $time = null) {
		try {
			if (!$this->file_exists($path)) {
				$fh = $this->share->write($this->buildPath($path));
				fclose($fh);
				return true;
			}
			return false;
		} catch (ConnectException $e) {
			throw new StorageNotAvailableException($e->getMessage(), $e->getCode(), $e);
		}
	}

	public function opendir($path) {
		try {
			$files = $this->getFolderContents($path);
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		}
		$names = array_map(function ($info) {
			/** @var \Icewind\SMB\IFileInfo $info */
			return $info->getName();
		}, $files);
		return IteratorDirectory::wrap($names);
	}

	public function filetype($path) {
		try {
			return $this->getFileInfo($path)->isDirectory() ? 'dir' : 'file';
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		}
	}

	public function mkdir($path) {
		$path = $this->buildPath($path);
		try {
			$this->share->mkdir($path);
			return true;
		} catch (ConnectException $e) {
			throw new StorageNotAvailableException($e->getMessage(), $e->getCode(), $e);
		} catch (Exception $e) {
			return false;
		}
	}

	public function file_exists($path) {
		try {
			$this->getFileInfo($path);
			return true;
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		} catch (ConnectException $e) {
			throw new StorageNotAvailableException($e->getMessage(), $e->getCode(), $e);
		}
	}

	public function isReadable($path) {
		try {
			$info = $this->getFileInfo($path);
			return !$info->isHidden();
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		}
	}

	public function isUpdatable($path) {
		try {
			$info = $this->getFileInfo($path);
			// following windows behaviour for read-only folders: they can be written into
			// (https://support.microsoft.com/en-us/kb/326549 - "cause" section)
			return !$info->isHidden() && (!$info->isReadOnly() || $this->is_dir($path));
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		}
	}

	public function isDeletable($path) {
		try {
			$info = $this->getFileInfo($path);
			return !$info->isHidden() && !$info->isReadOnly();
		} catch (NotFoundException $e) {
			return false;
		} catch (ForbiddenException $e) {
			return false;
		}
	}

	/**
	 * check if smbclient is installed
	 */
	public static function checkDependencies() {
		return (
			(bool)\OC_Helper::findBinaryPath('smbclient')
			|| Server::NativeAvailable()
		) ? true : ['smbclient'];
	}

	/**
	 * Test a storage for availability
	 *
	 * @return bool
	 */
	public function test() {
		try {
			return parent::test();
		} catch (Exception $e) {
			return false;
		}
	}

	public function listen($path, callable $callback) {
		$this->notify($path)->listen(function (IChange $change) use ($callback) {
			if ($change instanceof IRenameChange) {
				return $callback($change->getType(), $change->getPath(), $change->getTargetPath());
			} else {
				return $callback($change->getType(), $change->getPath());
			}
		});
	}

	public function notify($path) {
		$path = '/' . ltrim($path, '/');
		$shareNotifyHandler = $this->share->notify($this->buildPath($path));
		return new SMBNotifyHandler($shareNotifyHandler, $this->root);
	}
}
