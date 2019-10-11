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

namespace OCA\IDA\AppInfo;

use OCA\IDA\Controller\ViewController;
use OCA\IDA\Controller\ActionController;
use OCA\IDA\Controller\FileController;
use OCA\IDA\Controller\FreezingController;
use OCA\IDA\Model\ActionMapper;
use OCA\IDA\Model\FileMapper;
use OCA\IDA\View\Navigation;
use OCP\AppFramework\App;
use OCP\IContainer;
use OCP\Util;


/**
 * IDA Nextcloud App
 */
class Application extends App
{
    /**
     * Create a ownCloud application
     *
     * @param array (string) $urlParams a list of url parameters
     */
    
    public function __construct(array $urlParams = array()) {
        parent::__construct('ida', $urlParams);
        
        $container = $this->getContainer();
        $server = $container->getServer();
        
        $container->registerService(
            'ActionMapper',
            function () use ($server) {
                return new ActionMapper(
                    $server->getDatabaseConnection()
                );
            }
        );
    
        $container->registerService(
            'FileMapper',
            function () use ($server) {
                return new FileMapper(
                    $server->getDatabaseConnection()
                );
            }
        );
        
        $container->registerService(
            'ActionController',
            function (IContainer $c) use ($server) {
                return new ActionController(
                    $c->query('AppName'),
                    $server->getRequest(),
                    $c->query('ActionMapper'),
                    $c->query('CurrentUID')
                );
            }
        );
    
        $container->registerService(
            'FileController',
            function (IContainer $c) use ($server) {
                return new FileController(
                    $c->query('AppName'),
                    $server->getRequest(),
                    $c->query('FileMapper'),
                    $c->query('CurrentUID')
                );
            }
        );
    
        $container->registerService(
            'FreezingController',
            function (IContainer $c) use ($server) {
                return new FreezingController(
                    $c->query('AppName'),
                    $server->getRequest(),
                    $c->query('ActionMapper'),
                    $c->query('FileMapper'),
                    $c->query('CurrentUID'),
                    $server->getConfig()
                );
            }
        );
    
        $container->registerService(
            'ViewController',
            function (IContainer $c) use ($server) {
                return new ViewController(
                    $c->query('AppName'),
                    $c->query('Request'),
                    $c->query('ActionMapper'),
                    $c->query('FileMapper'),
                    $c->query('FreezingController'),
                    $c->query('CurrentUID'),
                    $c->query('Navigation')
                );
            }
        );
        
        $container->registerService(
            'Navigation',
            function (IContainer $c) {
                $server = $c->query('ServerContainer');
                
                return new Navigation(
                    $server->getURLGenerator()
                );
            }
        );
        
        $container->registerService(
            'CurrentUID',
            function () use ($server) {
                $user = $server->getUserSession()->getUser();
                
                return $user ? $user->getUID() : '';
            }
        );
        
    }
    
    /**
     * Register Navigation Entry
     *
     * @return null
     */
    public function registerNavigationEntry() {
        $c = $this->getContainer();
        $server = $c->getServer();
        
        $navigationEntry = function () use ($c, $server) {
            $l = \OC::$server->getL10N('ida');
            return [
                'id'    => $c->getAppName(),
                'order' => 100,
                'name'  => $l->t('Actions'),
                'href'  => '/apps/ida/actions/pending',
                'icon'  => $server->getURLGenerator()->imagePath('ida', 'appiconwhite.png'),
            ];
        };
        $server->getNavigationManager()->add($navigationEntry);
        
        return;
    }
    
    /**
     * Load additional javascript files
     *
     * @return null
     */
    public static function loadScripts() {
        Util::addScript('files', 'detailtabview');
        Util::addScript('ida', 'constants');
        Util::addScript('ida', 'idatabview');
        Util::addScript('ida', 'ida');
        Util::addStyle('ida', 'idatabview');
        return;
    }
    
}
