<?php

declare(strict_types=1);

/**
 * @copyright Copyright (c) 2019 Julius Härtl <jus@bitgrid.net>
 *
 * @author Julius Härtl <jus@bitgrid.net>
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
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 *
 */

namespace OCA\Text\Service;

use Exception;
use OC\Files\Node\File;
use OCA\Text\DocumentHasUnsavedChangesException;
use OCA\Text\DocumentSaveConflictException;
use OCA\Text\VersionMismatchException;
use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\FileDisplayResponse;
use OCP\AppFramework\Http\NotFoundResponse;
use OCP\Constants;
use OCP\Files\NotFoundException;
use OCP\ILogger;
use OCP\IRequest;
use OCP\Lock\LockedException;

class ApiService {
	protected $request;
	protected $sessionService;
	protected $documentService;
	protected $logger;

	public function __construct(IRequest $request, SessionService $sessionService, DocumentService $documentService, ILogger $logger) {
		$this->request = $request;
		$this->sessionService = $sessionService;
		$this->documentService = $documentService;
		$this->logger = $logger;
	}

	public function create($fileId = null, $filePath = null, $token = null, $guestName = null, bool $forceRecreate = false): DataResponse {
		try {
			$readOnly = true;
			/** @var File $file */
			if ($token) {
				$file = $this->documentService->getFileByShareToken($token, $this->request->getParam('filePath'));

				/*
				 * Check if we have proper read access (files drop)
				 * If not then well 404 it is.
				 */
				try {
					$this->documentService->checkSharePermissions($token, Constants::PERMISSION_READ);
				} catch (NotFoundException $e) {
					return new DataResponse([], Http::STATUS_NOT_FOUND);
				}

				try {
					$this->documentService->checkSharePermissions($token, Constants::PERMISSION_UPDATE);
					$readOnly = false;
				} catch (NotFoundException $e) {
				}
			} elseif ($fileId) {
				$file = $this->documentService->getFileById($fileId);
				$readOnly = !$file->isUpdateable();
			} else {
				return new DataResponse('No valid file argument provided', 500);
			}

			$this->sessionService->removeInactiveSessions($file->getId());
			$activeSessions = $this->sessionService->getActiveSessions($file->getId());
			if ($forceRecreate || count($activeSessions) === 0) {
				try {
					$this->documentService->resetDocument($file->getId(), $forceRecreate);
				} catch (DocumentHasUnsavedChangesException $e) {
				}
			}

			$document = $this->documentService->createDocument($file);
		} catch (Exception $e) {
			$this->logger->logException($e);
			return new DataResponse('Failed to create the document session', 500);
		}

		$session = $this->sessionService->initSession($document->getId(), $guestName);
		return new DataResponse([
			'document' => $document,
			'session' => $session,
			'readOnly' => $readOnly
		]);
	}

	public function fetch($documentId, $sessionId, $sessionToken) {
		if ($this->sessionService->isValidSession($documentId, $sessionId, $sessionToken)) {
			$this->sessionService->removeInactiveSessions($documentId);
			try {
				$file = $this->documentService->getBaseFile($documentId);
			} catch (NotFoundException $e) {
				return new NotFoundResponse();
			}
			return new FileDisplayResponse($file, 200, ['Content-Type' => 'text/plain']);
		}
		return new NotFoundResponse();
	}

	public function close($documentId, $sessionId, $sessionToken): DataResponse {
		$this->sessionService->closeSession($documentId, $sessionId, $sessionToken);
		$this->sessionService->removeInactiveSessions($documentId);
		$activeSessions = $this->sessionService->getActiveSessions($documentId);
		if (count($activeSessions) === 0) {
			try {
				$this->documentService->resetDocument($documentId);
			} catch (DocumentHasUnsavedChangesException $e) {
			}
		}
		return new DataResponse([]);
	}

	/**
	 * @throws NotFoundException
	 * @throws \OCP\AppFramework\Db\DoesNotExistException
	 */
	public function push($documentId, $sessionId, $sessionToken, $version, $steps, $token = null): DataResponse {
		$session = $this->sessionService->getSession($documentId, $sessionId, $sessionToken);
		$file = $this->documentService->getFileForSession($session, $token);
		if ($this->sessionService->isValidSession($documentId, $sessionId, $sessionToken) && !$this->documentService->isReadOnly($file, $token)) {
			try {
				$steps = $this->documentService->addStep($documentId, $sessionId, $steps, $version);
			} catch (VersionMismatchException $e) {
				return new DataResponse($e->getMessage(), $e->getStatus());
			}
			return new DataResponse($steps);
		}
		return new DataResponse([], 403);
	}

	public function sync($documentId, $sessionId, $sessionToken, $version = 0, $autosaveContent = null, bool $force = false, bool $manualSave = false, $token = null): DataResponse {
		if (!$this->sessionService->isValidSession($documentId, $sessionId, $sessionToken)) {
			return new DataResponse([], 403);
		}

		try {
			$result = [
				'steps' => $this->documentService->getSteps($documentId, $version),
				'sessions' => $this->sessionService->getAllSessions($documentId),
				'document' => $this->documentService->get($documentId)
			];

			$session = $this->sessionService->getSession($documentId, $sessionId, $sessionToken);
			$file = $this->documentService->getFileForSession($session, $token);
		} catch (NotFoundException $e) {
			$this->logger->logException($e, ['level' => ILogger::INFO]);
			return new DataResponse([
				'message' => 'File not found'
			], 404);
		} catch (DoesNotExistException $e) {
			$this->logger->logException($e, ['level' => ILogger::INFO]);
			return new DataResponse([
				'message' => 'Document no longer exists'
			], 404);
		}

		try {
			$result['document'] = $this->documentService->autosave($file, $documentId, $version, $autosaveContent, $force, $manualSave, $token, $this->request->getParam('filePath'));
		} catch (DocumentSaveConflictException $e) {
			try {
				$result['outsideChange'] = $file->getContent();
			} catch (LockedException $e) {
				// Ignore locked exception since it might happen due to an autosave action happening at the same time
			}
		} catch (NotFoundException $e) {
			return new DataResponse([], 404);
		} catch (Exception $e) {
			$this->logger->logException($e);
			return new DataResponse([
				'message' => 'Failed to autosave document'
			], 500);
		}

		return new DataResponse($result, isset($result['outsideChange']) ? 409 : 200);
	}

	/**
	 * @throws \OCP\AppFramework\Db\DoesNotExistException
	 */
	public function updateSession(int $documentId, int $sessionId, string $sessionToken, string $guestName): DataResponse {
		if (!$this->sessionService->isValidSession($documentId, $sessionId, $sessionToken)) {
			return new DataResponse([], 500);
		}

		if ($guestName === '') {
			return new DataResponse([ 'message' => 'A guest name needs to be provided'], 500);
		}
		return new DataResponse($this->sessionService->updateSession($documentId, $sessionId, $sessionToken, $guestName));
	}
}
