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
 * A database entity for a frozen file
 */
class File extends Entity implements JsonSerializable
{
    protected $action;
    protected $node;
    protected $pathname;
    protected $pid;
    protected $type;
    protected $project;
    protected $size;
    protected $checksum;
    protected $uploaded; // DEPRECATED
    protected $modified;
    protected $frozen;
    protected $metadata;
    protected $replicated;
    protected $removed;
    protected $cleared;

    /**
     * Get JSON representation
     *
     * @return mixed
     */
    public function jsonSerialize() {
        $values = array();

        $values["id"] = $this->id;
        $values["pid"] = $this->pid;
        $values["node"] = (int)$this->node;
        $values["action"] = $this->action;
        $values["project"] = $this->project;
        $values["pathname"] = $this->pathname;
        // It is possible, albeit rare, that some legacy records have no size recorded if/when the file size was zero.
        // So handle such rare cases here by defaulting to a file size of zero...
        $values["size"] = 0;
        if ($this->size !== null) {
            $values["size"] = (int)$this->size;
        }
        if ($this->checksum !== null) {
            // Ensure the checksum is returned as an sha256: checksum URI
            if ($this->checksum[0] === 's' && substr($this->checksum, 0, 7) === "sha256:") {
                $values["checksum"] = $this->checksum;
            }
            else {
                $values["checksum"] = 'sha256:' . $this->checksum;
            }
        }
        if ($this->modified !== null) {
            $values["modified"] = $this->modified;
        }
        if ($this->frozen !== null) {
            $values["frozen"] = $this->frozen;
        }
        if ($this->metadata !== null) {
            $values["metadata"] = $this->metadata;
        }
        if ($this->replicated !== null) {
            $values["replicated"] = $this->replicated;
        }
        if ($this->removed !== null) {
            $values["removed"] = $this->removed;
        }
        if ($this->cleared !== null) {
            $values["cleared"] = $this->cleared;
        }

        return $values;
    }

}
