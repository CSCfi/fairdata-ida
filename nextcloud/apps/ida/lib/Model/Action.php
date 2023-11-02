<?php
/**
 * This file is part of the IDA research data storage service
 *
 * Copyright (C) 2018 Ministry of Education and Culture, Finland
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, either version 3 of the License,
 * or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 *
 * PHP Version 7
 *
 * @category  Owncloud
 * @package   IDA
 * @author    CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
 * @license   GNU Affero General Public License, version 3
 * @link      https://research.csc.fi/
 */

namespace OCA\IDA\Model;

use JsonSerializable;
use OCP\AppFramework\Db\Entity;

/**
 * A database entity for an IDA action
 */
class Action extends Entity implements JsonSerializable
{
    protected $pid;
    protected $action;
    protected $project;
    protected $user;
    protected $node;
    protected $pathname;
    protected $initiated;
    protected $storage;
    protected $pids;
    protected $checksums;
    protected $metadata;
    protected $replication;
    protected $completed;
    protected $failed;
    protected $cleared;
    protected $error;
    protected $retry;
    protected $retrying;

    /**
     * Get JSON representation
     *
     * @return mixed
     */
    public function jsonSerialize() {
        $values = array();

        $values["id"] = $this->id;
        $values["pid"] = $this->pid;
        $values["action"] = $this->action;
        $values["project"] = $this->project;
        $values["user"] = $this->user;
        $values["node"] = (int)$this->node;
        $values["pathname"] = $this->pathname;
        $values["initiated"] = $this->initiated;
        if ($this->storage !== null) {
            $values["storage"] = $this->storage;
        }
        if ($this->pids !== null) {
            $values["pids"] = $this->pids;
        }
        if ($this->checksums !== null) {
            $values["checksums"] = $this->checksums;
        }
        if ($this->metadata !== null) {
            $values["metadata"] = $this->metadata;
        }
        if ($this->replication !== null) {
            $values["replication"] = $this->replication;
        }
        if ($this->completed !== null) {
            $values["completed"] = $this->completed;
        }
        if ($this->failed !== null) {
            $values["failed"] = $this->failed;
        }
        if ($this->cleared !== null) {
            $values["cleared"] = $this->cleared;
        }
        if ($this->error !== null) {
            $values["error"] = $this->error;
        }
        if ($this->retry !== null) {
            $values["retry"] = $this->retry;
        }
        if ($this->retrying !== null) {
            $values["retrying"] = $this->retrying;
        }

        return $values;
    }

    /**
     * Return true if the action is pending, else return false. We look at the individual operation timestamps
     * rather than the completed timestamp, both to guard against erroneous setting of the completed timestamp when
     * one or more operations are not completed, and also to enable this method to be used to determine if the
     * completed timestamp can be set.
     *
     * @return bool
     */
    public function isPending() {

        // Any action that has failed is by definition pending and not completed.
        if ($this->failed != null) {
            return true;
        }

        // All actions require successful local storage operations and metadata publication/update to be considered completed.
        if ($this->storage === null || $this->metadata === null) {
            return true;
        }

        // In addition, Freeze actions require successful PID and checksum generation and replication to be considered completed.
        if ($this->action === 'freeze' && ($this->checksums === null || $this->pids === null || $this->replication === null)) {
            return true;
        }

        return false;
    }

}
