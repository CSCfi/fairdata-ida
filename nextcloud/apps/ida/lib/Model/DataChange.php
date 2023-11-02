<?php
/**
 * This file is part of the IDA research data storage service
 *
 * Copyright (C) 2023 Ministry of Education and Culture, Finland
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
class DataChange extends Entity implements JsonSerializable
{
    protected $timestamp;
    protected $project;
    protected $user;
    protected $change;
    protected $pathname;
    protected $target;
    protected $mode;

    const CHANGES = [
        "init",
        "add",
        "modify",
        "rename",
        "move",
        "copy",
        "delete"
    ];

    const TARGET_CHANGES = [
        "rename",
        "move",
        "copy"
    ];

    const MODES = [
        "api",
        "cli",
        "gui",
        "system"
    ];

    /**
     * Get JSON representation
     *
     * @return mixed
     */
    public function jsonSerialize() {
        $values = array();
        $values["timestamp"] = $this->timestamp;
        $values["project"] = $this->project;
        $values["user"] = $this->user;
        $values["change"] = $this->change;
        $values["pathname"] = $this->pathname;
        if ($this->target !== null) {
            $values["target"] = $this->target;
        }
        $values["mode"] = $this->mode;
        return $values;
    }

}
