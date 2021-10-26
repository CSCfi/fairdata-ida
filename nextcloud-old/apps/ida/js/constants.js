/*
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
 * @author    CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
 * @license   GNU Affero General Public License, version 3
 * @link      https://research.csc.fi/
 */

(function () {

    OCA.IDAConstants = OCA.IDAConstants || {};

    OCA.IDAConstants.DISALLOWED_NAMES = 'ADMIN SYSTEM';    // whitespace separated list of names in uppercase
    OCA.IDAConstants.STAGING_FOLDER_SUFFIX = '+';          // appended to project name to construct staging share folder name
    OCA.IDAConstants.PROJECT_USER_PREFIX = 'PSO_';         // "PSO" = "Project Share Owner"
    OCA.IDAConstants.USER_QUOTA = 0;                       // Normal users require no storage allocation
    OCA.IDAConstants.MAX_FILE_COUNT = 5000;                // Maximum number of files allowed for a single action

})();

