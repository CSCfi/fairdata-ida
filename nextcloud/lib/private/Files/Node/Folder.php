<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Joas Schilling <coding@schilljs.com>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Robin McCorkell <robin@mccorkell.me.uk>
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

namespace OC\Files\Node;

use OC\DB\QueryBuilder\Literal;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\FileInfo;
use OCP\Files\Mount\IMountPoint;
use OCP\Files\NotFoundException;
use OCP\Files\NotPermittedException;
use OCP\Files\Search\ISearchOperator;

class Folder extends Node implements \OCP\Files\Folder {
	/**
	 * Creates a Folder that represents a non-existing path
	 *
	 * @param string $path path
	 * @return string non-existing node class
	 */
	protected function createNonExistingNode($path) {
		return new NonExistingFolder($this->root, $this->view, $path);
	}

	/**
	 * @param string $path path relative to the folder
	 * @return string
	 * @throws \OCP\Files\NotPermittedException
	 */
	public function getFullPath($path) {
		if (!$this->isValidPath($path)) {
			throw new NotPermittedException('Invalid path');
		}
		return $this->path . $this->normalizePath($path);
	}

	/**
	 * @param string $path
	 * @return string
	 */
	public function getRelativePath($path) {
		if ($this->path === '' or $this->path === '/') {
			return $this->normalizePath($path);
		}
		if ($path === $this->path) {
			return '/';
		} else if (strpos($path, $this->path . '/') !== 0) {
			return null;
		} else {
			$path = substr($path, strlen($this->path));
			return $this->normalizePath($path);
		}
	}

	/**
	 * check if a node is a (grand-)child of the folder
	 *
	 * @param \OC\Files\Node\Node $node
	 * @return bool
	 */
	public function isSubNode($node) {
		return strpos($node->getPath(), $this->path . '/') === 0;
	}

	/**
	 * get the content of this directory
	 *
	 * @throws \OCP\Files\NotFoundException
	 * @return Node[]
	 */
	public function getDirectoryListing() {
		$folderContent = $this->view->getDirectoryContent($this->path);

		return array_map(function (FileInfo $info) {
			if ($info->getMimetype() === 'httpd/unix-directory') {
				return new Folder($this->root, $this->view, $info->getPath(), $info);
			} else {
				return new File($this->root, $this->view, $info->getPath(), $info);
			}
		}, $folderContent);
	}

	/**
	 * @param string $path
	 * @param FileInfo $info
	 * @return File|Folder
	 */
	protected function createNode($path, FileInfo $info = null) {
		if (is_null($info)) {
			$isDir = $this->view->is_dir($path);
		} else {
			$isDir = $info->getType() === FileInfo::TYPE_FOLDER;
		}
		if ($isDir) {
			return new Folder($this->root, $this->view, $path, $info);
		} else {
			return new File($this->root, $this->view, $path, $info);
		}
	}

	/**
	 * Get the node at $path
	 *
	 * @param string $path
	 * @return \OC\Files\Node\Node
	 * @throws \OCP\Files\NotFoundException
	 */
	public function get($path) {
		return $this->root->get($this->getFullPath($path));
	}

	/**
	 * @param string $path
	 * @return bool
	 */
	public function nodeExists($path) {
		try {
			$this->get($path);
			return true;
		} catch (NotFoundException $e) {
			return false;
		}
	}

	/**
	 * @param string $path
	 * @return \OC\Files\Node\Folder
	 * @throws \OCP\Files\NotPermittedException
	 */
	public function newFolder($path) {
		if ($this->checkPermissions(\OCP\Constants::PERMISSION_CREATE)) {
			$fullPath = $this->getFullPath($path);
			$nonExisting = new NonExistingFolder($this->root, $this->view, $fullPath);
			$this->root->emit('\OC\Files', 'preWrite', array($nonExisting));
			$this->root->emit('\OC\Files', 'preCreate', array($nonExisting));
			$this->view->mkdir($fullPath);
			$node = new Folder($this->root, $this->view, $fullPath);
			$this->root->emit('\OC\Files', 'postWrite', array($node));
			$this->root->emit('\OC\Files', 'postCreate', array($node));
			return $node;
		} else {
			throw new NotPermittedException('No create permission for folder');
		}
	}

	/**
	 * @param string $path
	 * @return \OC\Files\Node\File
	 * @throws \OCP\Files\NotPermittedException
	 */
	public function newFile($path) {
		if ($this->checkPermissions(\OCP\Constants::PERMISSION_CREATE)) {
			$fullPath = $this->getFullPath($path);
			$nonExisting = new NonExistingFile($this->root, $this->view, $fullPath);
			$this->root->emit('\OC\Files', 'preWrite', array($nonExisting));
			$this->root->emit('\OC\Files', 'preCreate', array($nonExisting));
			$this->view->touch($fullPath);
			$node = new File($this->root, $this->view, $fullPath);
			$this->root->emit('\OC\Files', 'postWrite', array($node));
			$this->root->emit('\OC\Files', 'postCreate', array($node));
			return $node;
		} else {
			throw new NotPermittedException('No create permission for path');
		}
	}

	/**
	 * search for files with the name matching $query
	 *
	 * @param string|ISearchOperator $query
	 * @return \OC\Files\Node\Node[]
	 */
	public function search($query) {
		if (is_string($query)) {
			return $this->searchCommon('search', array('%' . $query . '%'));
		} else {
			return $this->searchCommon('searchQuery', array($query));
		}
	}

	/**
	 * search for files by mimetype
	 *
	 * @param string $mimetype
	 * @return Node[]
	 */
	public function searchByMime($mimetype) {
		return $this->searchCommon('searchByMime', array($mimetype));
	}

	/**
	 * search for files by tag
	 *
	 * @param string|int $tag name or tag id
	 * @param string $userId owner of the tags
	 * @return Node[]
	 */
	public function searchByTag($tag, $userId) {
		return $this->searchCommon('searchByTag', array($tag, $userId));
	}

	/**
	 * @param string $method cache method
	 * @param array $args call args
	 * @return \OC\Files\Node\Node[]
	 */
	private function searchCommon($method, $args) {
		$files = array();
		$rootLength = strlen($this->path);
		$mount = $this->root->getMount($this->path);
		$storage = $mount->getStorage();
		$internalPath = $mount->getInternalPath($this->path);
		$internalPath = rtrim($internalPath, '/');
		if ($internalPath !== '') {
			$internalPath = $internalPath . '/';
		}
		$internalRootLength = strlen($internalPath);

		$cache = $storage->getCache('');

		$results = call_user_func_array(array($cache, $method), $args);
		foreach ($results as $result) {
			if ($internalRootLength === 0 or substr($result['path'], 0, $internalRootLength) === $internalPath) {
				$result['internalPath'] = $result['path'];
				$result['path'] = substr($result['path'], $internalRootLength);
				$result['storage'] = $storage;
				$files[] = new \OC\Files\FileInfo($this->path . '/' . $result['path'], $storage, $result['internalPath'], $result, $mount);
			}
		}

		$mounts = $this->root->getMountsIn($this->path);
		foreach ($mounts as $mount) {
			$storage = $mount->getStorage();
			if ($storage) {
				$cache = $storage->getCache('');

				$relativeMountPoint = substr($mount->getMountPoint(), $rootLength);
				$results = call_user_func_array(array($cache, $method), $args);
				foreach ($results as $result) {
					$result['internalPath'] = $result['path'];
					$result['path'] = $relativeMountPoint . $result['path'];
					$result['storage'] = $storage;
					$files[] = new \OC\Files\FileInfo($this->path . '/' . $result['path'], $storage, $result['internalPath'], $result, $mount);
				}
			}
		}

		return array_map(function (FileInfo $file) {
			return $this->createNode($file->getPath(), $file);
		}, $files);
	}

	/**
	 * @param int $id
	 * @return \OC\Files\Node\Node[]
	 */
	public function getById($id) {
		$mountCache = $this->root->getUserMountCache();
		if (strpos($this->getPath(), '/', 1) > 0) {
			list(, $user) = explode('/', $this->getPath());
		} else {
			$user = null;
		}
		$mountsContainingFile = $mountCache->getMountsForFileId((int)$id, $user);
		$mounts = $this->root->getMountsIn($this->path);
		$mounts[] = $this->root->getMount($this->path);
		/** @var IMountPoint[] $folderMounts */
		$folderMounts = array_combine(array_map(function (IMountPoint $mountPoint) {
			return $mountPoint->getMountPoint();
		}, $mounts), $mounts);

		/** @var ICachedMountInfo[] $mountsContainingFile */
		$mountsContainingFile = array_values(array_filter($mountsContainingFile, function (ICachedMountInfo $cachedMountInfo) use ($folderMounts) {
			return isset($folderMounts[$cachedMountInfo->getMountPoint()]);
		}));

		if (count($mountsContainingFile) === 0) {
			return [];
		}

		// we only need to get the cache info once, since all mounts we found point to the same storage

		$mount = $folderMounts[$mountsContainingFile[0]->getMountPoint()];
		$cacheEntry = $mount->getStorage()->getCache()->get((int)$id);
		if (!$cacheEntry) {
			return [];
		}
		// cache jails will hide the "true" internal path
		$internalPath = ltrim($mountsContainingFile[0]->getRootInternalPath() . '/' . $cacheEntry->getPath(), '/');

		$nodes = array_map(function (ICachedMountInfo $cachedMountInfo) use ($cacheEntry, $folderMounts, $internalPath) {
			$mount = $folderMounts[$cachedMountInfo->getMountPoint()];
			$pathRelativeToMount = substr($internalPath, strlen($cachedMountInfo->getRootInternalPath()));
			$pathRelativeToMount = ltrim($pathRelativeToMount, '/');
			$absolutePath = $cachedMountInfo->getMountPoint() . $pathRelativeToMount;
			return $this->root->createNode($absolutePath, new \OC\Files\FileInfo(
				$absolutePath, $mount->getStorage(), $cacheEntry->getPath(), $cacheEntry, $mount,
				\OC::$server->getUserManager()->get($mount->getStorage()->getOwner($pathRelativeToMount))
			));
		}, $mountsContainingFile);

		return array_filter($nodes, function (Node $node) {
			return $this->getRelativePath($node->getPath());
		});
	}

	public function getFreeSpace() {
		return $this->view->free_space($this->path);
	}

	public function delete() {
		if ($this->checkPermissions(\OCP\Constants::PERMISSION_DELETE)) {
			$this->sendHooks(array('preDelete'));
			$fileInfo = $this->getFileInfo();
			$this->view->rmdir($this->path);
			$nonExisting = new NonExistingFolder($this->root, $this->view, $this->path, $fileInfo);
			$this->root->emit('\OC\Files', 'postDelete', array($nonExisting));
			$this->exists = false;
		} else {
			throw new NotPermittedException('No delete permission for path');
		}
	}

	/**
	 * Add a suffix to the name in case the file exists
	 *
	 * @param string $name
	 * @return string
	 * @throws NotPermittedException
	 */
	public function getNonExistingName($name) {
		$uniqueName = \OC_Helper::buildNotExistingFileNameForView($this->getPath(), $name, $this->view);
		return trim($this->getRelativePath($uniqueName), '/');
	}

	/**
	 * @param int $limit
	 * @param int $offset
	 * @return \OCP\Files\Node[]
	 */
	public function getRecent($limit, $offset = 0) {
		$mimetypeLoader = \OC::$server->getMimeTypeLoader();
		$mounts = $this->root->getMountsIn($this->path);
		$mounts[] = $this->getMountPoint();

		$mounts = array_filter($mounts, function (IMountPoint $mount) {
			return $mount->getStorage();
		});
		$storageIds = array_map(function (IMountPoint $mount) {
			return $mount->getStorage()->getCache()->getNumericStorageId();
		}, $mounts);
		/** @var IMountPoint[] $mountMap */
		$mountMap = array_combine($storageIds, $mounts);
		$folderMimetype = $mimetypeLoader->getId(FileInfo::MIMETYPE_FOLDER);

		//todo look into options of filtering path based on storage id (only search in files/ for home storage, filter by share root for shared, etc)

		$builder = \OC::$server->getDatabaseConnection()->getQueryBuilder();
		$query = $builder
			->select('f.*')
			->from('filecache', 'f')
			->andWhere($builder->expr()->in('f.storage', $builder->createNamedParameter($storageIds, IQueryBuilder::PARAM_INT_ARRAY)))
			->andWhere($builder->expr()->orX(
			// handle non empty folders separate
				$builder->expr()->neq('f.mimetype', $builder->createNamedParameter($folderMimetype, IQueryBuilder::PARAM_INT)),
				$builder->expr()->eq('f.size', new Literal(0))
			))
			->orderBy('f.mtime', 'DESC')
			->setMaxResults($limit)
			->setFirstResult($offset);

		$result = $query->execute()->fetchAll();

		$files = array_filter(array_map(function (array $entry) use ($mountMap, $mimetypeLoader) {
			$mount = $mountMap[$entry['storage']];
			$entry['internalPath'] = $entry['path'];
			$entry['mimetype'] = $mimetypeLoader->getMimetypeById($entry['mimetype']);
			$entry['mimepart'] = $mimetypeLoader->getMimetypeById($entry['mimepart']);
			$path = $this->getAbsolutePath($mount, $entry['path']);
			if (is_null($path)) {
				return null;
			}
			$fileInfo = new \OC\Files\FileInfo($path, $mount->getStorage(), $entry['internalPath'], $entry, $mount);
			return $this->root->createNode($fileInfo->getPath(), $fileInfo);
		}, $result));

		return array_values(array_filter($files, function (Node $node) {
			$relative = $this->getRelativePath($node->getPath());
			return $relative !== null && $relative !== '/';
		}));
	}

	private function getAbsolutePath(IMountPoint $mount, $path) {
		$storage = $mount->getStorage();
		if ($storage->instanceOfStorage('\OC\Files\Storage\Wrapper\Jail')) {
			/** @var \OC\Files\Storage\Wrapper\Jail $storage */
			$jailRoot = $storage->getUnjailedPath('');
			$rootLength = strlen($jailRoot) + 1;
			if ($path === $jailRoot) {
				return $mount->getMountPoint();
			} else if (substr($path, 0, $rootLength) === $jailRoot . '/') {
				return $mount->getMountPoint() . substr($path, $rootLength);
			} else {
				return null;
			}
		} else {
			return $mount->getMountPoint() . $path;
		}
	}
}
