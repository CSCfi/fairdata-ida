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

namespace OCA\IDA\View;

use OCP\IURLGenerator;
use OCP\Template;

/**
 * Class Navigation
 */
class Navigation
{
    /**
     * URL Generator for getting action lists
     *
     * @var IURLGenerator
     */
    protected $URLGenerator;
    
    /**
     * Construct
     *
     * @param IURLGenerator $URLGenerator url generator for getting action lists
     */
    public function __construct(IURLGenerator $URLGenerator) {
        $this->URLGenerator = $URLGenerator;
    }
    
    /**
     * Get a filled navigation menu
     *
     * @param null|string $status Navigation entry
     *
     * @return \OCP\Template
     */
    public function getTemplate($status = 'pending') {
        $template = new Template('ida', 'navigation', '');
        $entries = $this->getLinkList();
        $template->assign('activeNavigation', $status);
        $template->assign('navigations', $entries);
        
        return $template;
    }
    
    /**
     * Get all items for the navigation menu
     *
     * @return array navigation bar entries (id, name, url)
     */
    public function getLinkList() {
        $entries = [
            [
                'id'   => 'pending',
                'name' => 'Pending Actions',
                'url'  => $this->URLGenerator->linkToRoute('ida.View.getActionTable', array('status' => 'pending'))
            ],
            [
                'id'   => 'completed',
                'name' => 'Completed Actions',
                'url'  => $this->URLGenerator->linkToRoute('ida.View.getActionTable', array('status' => 'completed'))
            ],
            [
                'id'   => 'cleared',
                'name' => 'Cleared Actions',
                'url'  => $this->URLGenerator->linkToRoute('ida.View.getActionTable', array('status' => 'cleared'))
            ],
            [
                'id'   => 'failed',
                'name' => 'Failed Actions',
                'url'  => $this->URLGenerator->linkToRoute('ida.View.getActionTable', array('status' => 'failed'))
            ],
        ];
        
        return $entries;
    }
}

