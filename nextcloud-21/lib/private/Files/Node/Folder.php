<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Christoph Wurst <christoph@winzerhof-wurst.at>
 * @author Georg Ehrke <oc.list@georgehrke.com>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Julius Härtl <jus@bitgrid.net>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Robin McCorkell <robin@mccorkell.me.uk>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
 * @author Vincent Petry <vincent@nextcloud.com>
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
 * along with this program. If not, see <http://www.gnu.org/licenses/>
 *
 */

namespace OC\Files\Node;

use OC\DB\QueryBuilder\Literal;
use OC\Files\Search\SearchBinaryOperator;
use OC\Files\Search\SearchComparison;
use OC\Files\Search\SearchQuery;
use OC\Files\Storage\Wrapper\Jail;
use OC\Files\Storage\Storage;
use OCA\Files_Sharing\SharedStorage;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Files\Cache\ICacheEntry;
use OCP\Files\FileInfo;
use OCP\Files\Mount\IMountPoint;
use OCP\Files\NotFoundException;
use OCP\Files\NotPermittedException;
use OCP\Files\Search\ISearchBinaryOperator;
use OCP\Files\Search\ISearchComparison;
use OCP\Files\Search\ISearchOperator;
use OCP\Files\Search\ISearchQuery;
use OCP\IUserManager;

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
		} elseif (strpos($path, $this->path . '/') !== 0) {
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
	 * @return Node[]
	 * @throws \OCP\Files\NotFoundException
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
			$this->sendHooks(['preWrite', 'preCreate'], [$nonExisting]);
			if (!$this->view->mkdir($fullPath)) {
				throw new NotPermittedException('Could not create folder');
			}
			$node = new Folder($this->root, $this->view, $fullPath);
			$this->sendHooks(['postWrite', 'postCreate'], [$node]);
			return $node;
		} else {
			throw new NotPermittedException('No create permission for folder');
		}
	}

	/**
	 * @param string $path
	 * @param string | resource | null $content
	 * @return \OC\Files\Node\File
	 * @throws \OCP\Files\NotPermittedException
	 */
	public function newFile($path, $content = null) {
		if (empty($path)) {
			throw new NotPermittedException('Could not create as provided path is empty');
		}
		if ($this->checkPermissions(\OCP\Constants::PERMISSION_CREATE)) {
			$fullPath = $this->getFullPath($path);
			$nonExisting = new NonExistingFile($this->root, $this->view, $fullPath);
			$this->sendHooks(['preWrite', 'preCreate'], [$nonExisting]);
			if ($content !== null) {
				$result = $this->view->file_put_contents($fullPath, $content);
			} else {
				$result = $this->view->touch($fullPath);
			}
			if ($result === false) {
				throw new NotPermittedException('Could not create path');
			}
			$node = new File($this->root, $this->view, $fullPath);
			$this->sendHooks(['postWrite', 'postCreate'], [$node]);
			return $node;
		}
		throw new NotPermittedException('No create permission for path');
	}

	private function queryFromOperator(ISearchOperator $operator, string $uid = null): ISearchQuery {
		if ($uid === null) {
			$user = null;
		} else {
			/** @var IUserManager $userManager */
			$userManager = \OC::$server->query(IUserManager::class);
			$user = $userManager->get($uid);
		}
		return new SearchQuery($operator, 0, 0, [], $user);
	}

	/**
	 * search for files with the name matching $query
	 *
	 * @param string|ISearchQuery $query
	 * @return \OC\Files\Node\Node[]
	 */
	public function search($query) {
		if (is_string($query)) {
			$query = $this->queryFromOperator(new SearchComparison(ISearchComparison::COMPARE_LIKE, 'name', '%' . $query . '%'));
		}

		// Limit+offset for queries with ordering
		//
		// Because we currently can't do ordering between the results from different storages in sql
		// The only way to do ordering is requesting the $limit number of entries from all storages
		// sorting them and returning the first $limit entries.
		//
		// For offset we have the same problem, we don't know how many entries from each storage should be skipped
		// by a given $offset, so instead we query $offset + $limit from each storage and return entries $offset..($offset+$limit)
		// after merging and sorting them.
		//
		// This is suboptimal but because limit and offset tend to be fairly small in real world use cases it should
		// still be significantly better than disabling paging altogether

		$limitToHome = $query->limitToHome();
		if ($limitToHome && count(explode('/', $this->path)) !== 3) {
			throw new \InvalidArgumentException('searching by owner is only allows on the users home folder');
		}

		$rootLength = strlen($this->path);
		$mount = $this->root->getMount($this->path);
		$storage = $mount->getStorage();
		$internalPath = $mount->getInternalPath($this->path);
		$internalPath = rtrim($internalPath, '/');
		if ($internalPath !== '') {
			$internalPath = $internalPath . '/';
		}

		$subQueryLimit = $query->getLimit() > 0 ? $query->getLimit() + $query->getOffset() : 0;
		$rootQuery = new SearchQuery(
			new SearchBinaryOperator(ISearchBinaryOperator::OPERATOR_AND, [
				new SearchComparison(ISearchComparison::COMPARE_LIKE, 'path', $internalPath . '%'),
				$query->getSearchOperation(),
			]
			),
			$subQueryLimit,
			0,
			$query->getOrder(),
			$query->getUser()
		);

		$files = [];

		$cache = $storage->getCache('');

		$results = $cache->searchQuery($rootQuery);
		foreach ($results as $result) {
			$files[] = $this->cacheEntryToFileInfo($mount, '', $internalPath, $result);
		}

		if (!$limitToHome) {
			$mounts = $this->root->getMountsIn($this->path);
			foreach ($mounts as $mount) {
				$subQuery = new SearchQuery(
					$query->getSearchOperation(),
					$subQueryLimit,
					0,
					$query->getOrder(),
					$query->getUser()
				);

				$storage = $mount->getStorage();
				if ($storage) {
					$cache = $storage->getCache('');

					$relativeMountPoint = ltrim(substr($mount->getMountPoint(), $rootLength), '/');
					$results = $cache->searchQuery($subQuery);
					foreach ($results as $result) {
						$files[] = $this->cacheEntryToFileInfo($mount, $relativeMountPoint, '', $result);
					}
				}
			}
		}

		$order = $query->getOrder();
		if ($order) {
			usort($files, function (FileInfo $a,FileInfo  $b) use ($order) {
				foreach ($order as $orderField) {
					$cmp = $orderField->sortFileInfo($a, $b);
					if ($cmp !== 0) {
						return $cmp;
					}
				}
				return 0;
			});
		}
		$files = array_values(array_slice($files, $query->getOffset(), $query->getLimit() > 0 ? $query->getLimit() : null));

		return array_map(function (FileInfo $file) {
			return $this->createNode($file->getPath(), $file);
		}, $files);
	}

	private function cacheEntryToFileInfo(IMountPoint $mount, string $appendRoot, string $trimRoot, ICacheEntry $cacheEntry): FileInfo {
		$trimLength = strlen($trimRoot);
		$cacheEntry['internalPath'] = $cacheEntry['path'];
		$cacheEntry['path'] = $appendRoot . substr($cacheEntry['path'], $trimLength);
		return new \OC\Files\FileInfo($this->path . '/' . $cacheEntry['path'], $mount->getStorage(), $cacheEntry['internalPath'], $cacheEntry, $mount);
	}

	/**
	 * search for files by mimetype
	 *
	 * @param string $mimetype
	 * @return Node[]
	 */
	public function searchByMime($mimetype) {
		if (strpos($mimetype, '/') === false) {
			$query = $this->queryFromOperator(new SearchComparison(ISearchComparison::COMPARE_LIKE, 'mimetype', $mimetype . '/%'));
		} else {
			$query = $this->queryFromOperator(new SearchComparison(ISearchComparison::COMPARE_EQUAL, 'mimetype', $mimetype));
		}
		return $this->search($query);
	}

	/**
	 * search for files by tag
	 *
	 * @param string|int $tag name or tag id
	 * @param string $userId owner of the tags
	 * @return Node[]
	 */
	public function searchByTag($tag, $userId) {
		$query = $this->queryFromOperator(new SearchComparison(ISearchComparison::COMPARE_EQUAL, 'tagname', $tag), $userId);
		return $this->search($query);
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

		// when a user has access trough the same storage trough multiple paths
		// (such as an external storage that is both mounted for a user and shared to the user)
		// the mount cache will only hold a single entry for the storage
		// this can lead to issues as the different ways the user has access to a storage can have different permissions
		//
		// so instead of using the cached entries directly, we instead filter the current mounts by the rootid of the cache entry

		$mountRootIds = array_map(function ($mount) {
			return $mount->getRootId();
		}, $mountsContainingFile);
		$mountRootPaths = array_map(function ($mount) {
			return $mount->getRootInternalPath();
		}, $mountsContainingFile);
		$mountRoots = array_combine($mountRootIds, $mountRootPaths);

		$mounts = $this->root->getMountsIn($this->path);
		$mounts[] = $this->root->getMount($this->path);

		$mountsContainingFile = array_filter($mounts, function ($mount) use ($mountRoots) {
			return isset($mountRoots[$mount->getStorageRootId()]);
		});

		if (count($mountsContainingFile) === 0) {
			if ($user === $this->getAppDataDirectoryName()) {
				return $this->getByIdInRootMount((int)$id);
			}
			return [];
		}

		$nodes = array_map(function (IMountPoint $mount) use ($id, $mountRoots) {
			$rootInternalPath = $mountRoots[$mount->getStorageRootId()];
			$cacheEntry = $mount->getStorage()->getCache()->get((int)$id);
			if (!$cacheEntry) {
				return null;
			}

			// cache jails will hide the "true" internal path
			$internalPath = ltrim($rootInternalPath . '/' . $cacheEntry->getPath(), '/');
			$pathRelativeToMount = substr($internalPath, strlen($rootInternalPath));
			$pathRelativeToMount = ltrim($pathRelativeToMount, '/');
			$absolutePath = rtrim($mount->getMountPoint() . $pathRelativeToMount, '/');
			return $this->root->createNode($absolutePath, new \OC\Files\FileInfo(
				$absolutePath, $mount->getStorage(), $cacheEntry->getPath(), $cacheEntry, $mount,
				\OC::$server->getUserManager()->get($mount->getStorage()->getOwner($pathRelativeToMount))
			));
		}, $mountsContainingFile);

		$nodes = array_filter($nodes);

		$folders = array_filter($nodes, function (Node $node) {
			return $this->getRelativePath($node->getPath());
		});
		usort($folders, function ($a, $b) {
			return $b->getPath() <=> $a->getPath();
		});
		return $folders;
	}

	protected function getAppDataDirectoryName(): string {
		$instanceId = \OC::$server->getConfig()->getSystemValueString('instanceid');
		return 'appdata_' . $instanceId;
	}

	/**
	 * In case the path we are currently in is inside the appdata_* folder,
	 * the original getById method does not work, because it can only look inside
	 * the user's mount points. But the user has no mount point for the root storage.
	 *
	 * So in that case we directly check the mount of the root if it contains
	 * the id. If it does we check if the path is inside the path we are working
	 * in.
	 *
	 * @param int $id
	 * @return array
	 */
	protected function getByIdInRootMount(int $id): array {
		$mount = $this->root->getMount('');
		$cacheEntry = $mount->getStorage()->getCache($this->path)->get($id);
		if (!$cacheEntry) {
			return [];
		}

		$absolutePath = '/' . ltrim($cacheEntry->getPath(), '/');
		$currentPath = rtrim($this->path, '/') . '/';

		if (strpos($absolutePath, $currentPath) !== 0) {
			return [];
		}

		return [$this->root->createNode(
			$absolutePath, new \OC\Files\FileInfo(
			$absolutePath,
			$mount->getStorage(),
			$cacheEntry->getPath(),
			$cacheEntry,
			$mount
		))];
	}

	public function getFreeSpace() {
		return $this->view->free_space($this->path);
	}

	public function delete() {
		if ($this->checkPermissions(\OCP\Constants::PERMISSION_DELETE)) {
			$this->sendHooks(['preDelete']);
			$fileInfo = $this->getFileInfo();
			$this->view->rmdir($this->path);
			$nonExisting = new NonExistingFolder($this->root, $this->view, $this->path, $fileInfo);
			$this->sendHooks(['postDelete'], [$nonExisting]);
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

		/*
		 * Construct an array of the storage id with their prefix path
		 * This helps us to filter in the final query
		 */
		$filters = array_map(function (IMountPoint $mount) {
			$storage = $mount->getStorage();

			$storageId = $storage->getCache()->getNumericStorageId();
			$prefix = '';

			if ($storage->instanceOfStorage(Jail::class)) {
				$prefix = $storage->getUnJailedPath('');
			}

			return [
				'storageId' => $storageId,
				'pathPrefix' => $prefix,
			];
		}, $mounts);

		// Search in batches of 500 entries
		$searchLimit = 500;
		$results = [];
		$searchResultCount = 0;
		$count = 0;
		do {
			$searchResult = $this->recentSearch($searchLimit, $offset, $folderMimetype, $filters);

			// Exit condition if there are no more results
			if (count($searchResult) === 0) {
				break;
			}

			$searchResultCount += count($searchResult);

			$parseResult = $this->recentParse($searchResult, $mountMap, $mimetypeLoader);

			foreach ($parseResult as $result) {
				$results[] = $result;
			}

			$offset += $searchLimit;
			$count++;
		} while (count($results) < $limit && ($searchResultCount < (3 * $limit) || $count < 5));

		return array_slice($results, 0, $limit);
	}

	private function recentSearch($limit, $offset, $folderMimetype, $filters) {
		$dbconn = \OC::$server->getDatabaseConnection();
		$builder = $dbconn->getQueryBuilder();
		$query = $builder
			->select('f.*')
			->from('filecache', 'f');

		/*
		 * Here is where we construct the filtering.
		 * Note that this is expensive filtering as it is a lot of like queries.
		 * However the alternative is we do this filtering and parsing later in php with the risk of looping endlessly
		 */
		$storageFilters = $builder->expr()->orX();
		foreach ($filters as $filter) {
			$storageFilter = $builder->expr()->andX(
				$builder->expr()->eq('f.storage', $builder->createNamedParameter($filter['storageId']))
			);

			if ($filter['pathPrefix'] !== '') {
				$storageFilter->add(
					$builder->expr()->like('f.path', $builder->createNamedParameter($dbconn->escapeLikeParameter($filter['pathPrefix']) . '/%'))
				);
			}

			$storageFilters->add($storageFilter);
		}

		$query->andWhere($storageFilters);

		$query->andWhere($builder->expr()->orX(
		// handle non empty folders separate
			$builder->expr()->neq('f.mimetype', $builder->createNamedParameter($folderMimetype, IQueryBuilder::PARAM_INT)),
			$builder->expr()->eq('f.size', new Literal(0))
		))
			->andWhere($builder->expr()->notLike('f.path', $builder->createNamedParameter('files_versions/%')))
			->andWhere($builder->expr()->notLike('f.path', $builder->createNamedParameter('files_trashbin/%')))
			->orderBy('f.mtime', 'DESC')
			->setMaxResults($limit)
			->setFirstResult($offset);

		$result = $query->execute();
		$rows = $result->fetchAll();
		$result->closeCursor();

		return $rows;
	}

	private function recentParse($result, $mountMap, $mimetypeLoader) {
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
			$cacheEntry = $node->getMountPoint()->getStorage()->getCache()->get($node->getId());
			if (!$cacheEntry) {
				return false;
			}
			$relative = $this->getRelativePath($node->getPath());
			return $relative !== null && $relative !== '/'
				&& ($cacheEntry->getPermissions() & \OCP\Constants::PERMISSION_READ) === \OCP\Constants::PERMISSION_READ;
		}));
	}

	private function getAbsolutePath(IMountPoint $mount, $path) {
		$storage = $mount->getStorage();
		if ($storage->instanceOfStorage('\OC\Files\Storage\Wrapper\Jail')) {
			if ($storage->instanceOfStorage(SharedStorage::class)) {
				$storage->getSourceStorage();
			}
			/** @var \OC\Files\Storage\Wrapper\Jail $storage */
			$jailRoot = $storage->getUnjailedPath('');
			$rootLength = strlen($jailRoot) + 1;
			if ($path === $jailRoot) {
				return $mount->getMountPoint();
			} elseif (substr($path, 0, $rootLength) === $jailRoot . '/') {
				return $mount->getMountPoint() . substr($path, $rootLength);
			} else {
				return null;
			}
		} else {
			return $mount->getMountPoint() . $path;
		}
	}
}
