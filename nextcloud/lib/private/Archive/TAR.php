<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Bart Visscher <bartv@thisnet.nl>
 * @author Christian Weiske <cweiske@cweiske.de>
 * @author Christopher Schäpers <kondou@ts.unde.re>
 * @author Felix Moeller <mail@felixmoeller.de>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Jörn Friedrich Dreyer <jfd@butonic.de>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Remco Brenninkmeijer <requist1@starmail.nl>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Robin McCorkell <robin@mccorkell.me.uk>
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

namespace OC\Archive;

use Icewind\Streams\CallbackWrapper;

class TAR extends Archive {
	const PLAIN = 0;
	const GZIP = 1;
	const BZIP = 2;

	private $fileList;
	private $cachedHeaders;

	/**
	 * @var \Archive_Tar tar
	 */
	private $tar = null;
	private $path;

	/**
	 * @param string $source
	 */
	function __construct($source) {
		$types = array(null, 'gz', 'bz2');
		$this->path = $source;
		$this->tar = new \Archive_Tar($source, $types[self::getTarType($source)]);
	}

	/**
	 * try to detect the type of tar compression
	 *
	 * @param string $file
	 * @return integer
	 */
	static public function getTarType($file) {
		if (strpos($file, '.')) {
			$extension = substr($file, strrpos($file, '.'));
			switch ($extension) {
				case '.gz':
				case '.tgz':
					return self::GZIP;
				case '.bz':
				case '.bz2':
					return self::BZIP;
				case '.tar':
					return self::PLAIN;
				default:
					return self::PLAIN;
			}
		} else {
			return self::PLAIN;
		}
	}

	/**
	 * add an empty folder to the archive
	 *
	 * @param string $path
	 * @return bool
	 */
	function addFolder($path) {
		$tmpBase = \OC::$server->getTempManager()->getTemporaryFolder();
		if (substr($path, -1, 1) != '/') {
			$path .= '/';
		}
		if ($this->fileExists($path)) {
			return false;
		}
		$parts = explode('/', $path);
		$folder = $tmpBase;
		foreach ($parts as $part) {
			$folder .= '/' . $part;
			if (!is_dir($folder)) {
				mkdir($folder);
			}
		}
		$result = $this->tar->addModify(array($tmpBase . $path), '', $tmpBase);
		rmdir($tmpBase . $path);
		$this->fileList = false;
		$this->cachedHeaders = false;
		return $result;
	}

	/**
	 * add a file to the archive
	 *
	 * @param string $path
	 * @param string $source either a local file or string data
	 * @return bool
	 */
	function addFile($path, $source = '') {
		if ($this->fileExists($path)) {
			$this->remove($path);
		}
		if ($source and $source[0] == '/' and file_exists($source)) {
			$source = file_get_contents($source);
		}
		$result = $this->tar->addString($path, $source);
		$this->fileList = false;
		$this->cachedHeaders = false;
		return $result;
	}

	/**
	 * rename a file or folder in the archive
	 *
	 * @param string $source
	 * @param string $dest
	 * @return bool
	 */
	function rename($source, $dest) {
		//no proper way to delete, rename entire archive, rename file and remake archive
		$tmp = \OCP\Files::tmpFolder();
		$this->tar->extract($tmp);
		rename($tmp . $source, $tmp . $dest);
		$this->tar = null;
		unlink($this->path);
		$types = array(null, 'gz', 'bz');
		$this->tar = new \Archive_Tar($this->path, $types[self::getTarType($this->path)]);
		$this->tar->createModify(array($tmp), '', $tmp . '/');
		$this->fileList = false;
		$this->cachedHeaders = false;
		return true;
	}

	/**
	 * @param string $file
	 */
	private function getHeader($file) {
		if (!$this->cachedHeaders) {
			$this->cachedHeaders = $this->tar->listContent();
		}
		foreach ($this->cachedHeaders as $header) {
			if ($file == $header['filename']
				or $file . '/' == $header['filename']
				or '/' . $file . '/' == $header['filename']
				or '/' . $file == $header['filename']
			) {
				return $header;
			}
		}
		return null;
	}

	/**
	 * get the uncompressed size of a file in the archive
	 *
	 * @param string $path
	 * @return int
	 */
	function filesize($path) {
		$stat = $this->getHeader($path);
		return $stat['size'];
	}

	/**
	 * get the last modified time of a file in the archive
	 *
	 * @param string $path
	 * @return int
	 */
	function mtime($path) {
		$stat = $this->getHeader($path);
		return $stat['mtime'];
	}

	/**
	 * get the files in a folder
	 *
	 * @param string $path
	 * @return array
	 */
	function getFolder($path) {
		$files = $this->getFiles();
		$folderContent = array();
		$pathLength = strlen($path);
		foreach ($files as $file) {
			if ($file[0] == '/') {
				$file = substr($file, 1);
			}
			if (substr($file, 0, $pathLength) == $path and $file != $path) {
				$result = substr($file, $pathLength);
				if ($pos = strpos($result, '/')) {
					$result = substr($result, 0, $pos + 1);
				}
				if (array_search($result, $folderContent) === false) {
					$folderContent[] = $result;
				}
			}
		}
		return $folderContent;
	}

	/**
	 * get all files in the archive
	 *
	 * @return array
	 */
	function getFiles() {
		if ($this->fileList) {
			return $this->fileList;
		}
		if (!$this->cachedHeaders) {
			$this->cachedHeaders = $this->tar->listContent();
		}
		$files = array();
		foreach ($this->cachedHeaders as $header) {
			$files[] = $header['filename'];
		}
		$this->fileList = $files;
		return $files;
	}

	/**
	 * get the content of a file
	 *
	 * @param string $path
	 * @return string
	 */
	function getFile($path) {
		return $this->tar->extractInString($path);
	}

	/**
	 * extract a single file from the archive
	 *
	 * @param string $path
	 * @param string $dest
	 * @return bool
	 */
	function extractFile($path, $dest) {
		$tmp = \OCP\Files::tmpFolder();
		if (!$this->fileExists($path)) {
			return false;
		}
		if ($this->fileExists('/' . $path)) {
			$success = $this->tar->extractList(array('/' . $path), $tmp);
		} else {
			$success = $this->tar->extractList(array($path), $tmp);
		}
		if ($success) {
			rename($tmp . $path, $dest);
		}
		\OCP\Files::rmdirr($tmp);
		return $success;
	}

	/**
	 * extract the archive
	 *
	 * @param string $dest
	 * @return bool
	 */
	function extract($dest) {
		return $this->tar->extract($dest);
	}

	/**
	 * check if a file or folder exists in the archive
	 *
	 * @param string $path
	 * @return bool
	 */
	function fileExists($path) {
		$files = $this->getFiles();
		if ((array_search($path, $files) !== false) or (array_search($path . '/', $files) !== false)) {
			return true;
		} else {
			$folderPath = $path;
			if (substr($folderPath, -1, 1) != '/') {
				$folderPath .= '/';
			}
			$pathLength = strlen($folderPath);
			foreach ($files as $file) {
				if (strlen($file) > $pathLength and substr($file, 0, $pathLength) == $folderPath) {
					return true;
				}
			}
		}
		if ($path[0] != '/') { //not all programs agree on the use of a leading /
			return $this->fileExists('/' . $path);
		} else {
			return false;
		}
	}

	/**
	 * remove a file or folder from the archive
	 *
	 * @param string $path
	 * @return bool
	 */
	function remove($path) {
		if (!$this->fileExists($path)) {
			return false;
		}
		$this->fileList = false;
		$this->cachedHeaders = false;
		//no proper way to delete, extract entire archive, delete file and remake archive
		$tmp = \OCP\Files::tmpFolder();
		$this->tar->extract($tmp);
		\OCP\Files::rmdirr($tmp . $path);
		$this->tar = null;
		unlink($this->path);
		$this->reopen();
		$this->tar->createModify(array($tmp), '', $tmp);
		return true;
	}

	/**
	 * get a file handler
	 *
	 * @param string $path
	 * @param string $mode
	 * @return resource
	 */
	function getStream($path, $mode) {
		if (strrpos($path, '.') !== false) {
			$ext = substr($path, strrpos($path, '.'));
		} else {
			$ext = '';
		}
		$tmpFile = \OCP\Files::tmpFile($ext);
		if ($this->fileExists($path)) {
			$this->extractFile($path, $tmpFile);
		} elseif ($mode == 'r' or $mode == 'rb') {
			return false;
		}
		if ($mode == 'r' or $mode == 'rb') {
			return fopen($tmpFile, $mode);
		} else {
			$handle = fopen($tmpFile, $mode);
			return CallbackWrapper::wrap($handle, null, null, function () use ($path, $tmpFile) {
				$this->writeBack($tmpFile, $path);
			});
		}
	}

	/**
	 * write back temporary files
	 */
	function writeBack($tmpFile, $path) {
		$this->addFile($path, $tmpFile);
		unlink($tmpFile);
	}

	/**
	 * reopen the archive to ensure everything is written
	 */
	private function reopen() {
		if ($this->tar) {
			$this->tar->_close();
			$this->tar = null;
		}
		$types = array(null, 'gz', 'bz');
		$this->tar = new \Archive_Tar($this->path, $types[self::getTarType($this->path)]);
	}
}
