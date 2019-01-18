<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Administrator <Administrator@WINDOWS-2012>
 * @author Arthur Schiwon <blizzz@arthur-schiwon.de>
 * @author Bart Visscher <bartv@thisnet.nl>
 * @author Bernhard Posselt <dev@bernhard-posselt.com>
 * @author Brice Maron <brice@bmaron.net>
 * @author Christoph Wurst <christoph@owncloud.com>
 * @author François Kubler <francois@kubler.org>
 * @author Jakob Sack <mail@jakobsack.de>
 * @author Joas Schilling <coding@schilljs.com>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Martin Mattel <martin.mattel@diemattels.at>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
 * @author Roeland Jago Douma <roeland@famdouma.nl>
 * @author Sean Comeau <sean@ftlnetworks.ca>
 * @author Serge Martin <edb@sigluy.net>
 * @author Thomas Müller <thomas.mueller@tmit.eu>
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

namespace OC;

use bantu\IniGetWrapper\IniGetWrapper;
use Exception;
use OC\App\AppStore\Bundles\BundleFetcher;
use OCP\Defaults;
use OCP\IL10N;
use OCP\ILogger;
use OCP\Security\ISecureRandom;

class Setup {
	/** @var SystemConfig */
	protected $config;
	/** @var IniGetWrapper */
	protected $iniWrapper;
	/** @var IL10N */
	protected $l10n;
	/** @var Defaults */
	protected $defaults;
	/** @var ILogger */
	protected $logger;
	/** @var ISecureRandom */
	protected $random;

	/**
	 * @param SystemConfig $config
	 * @param IniGetWrapper $iniWrapper
	 * @param IL10N $l10n
	 * @param Defaults $defaults
	 * @param ILogger $logger
	 * @param ISecureRandom $random
	 */
	public function __construct(SystemConfig $config,
						 IniGetWrapper $iniWrapper,
						 IL10N $l10n,
						 Defaults $defaults,
						 ILogger $logger,
						 ISecureRandom $random
		) {
		$this->config = $config;
		$this->iniWrapper = $iniWrapper;
		$this->l10n = $l10n;
		$this->defaults = $defaults;
		$this->logger = $logger;
		$this->random = $random;
	}

	static $dbSetupClasses = [
		'mysql' => \OC\Setup\MySQL::class,
		'pgsql' => \OC\Setup\PostgreSQL::class,
		'oci'   => \OC\Setup\OCI::class,
		'sqlite' => \OC\Setup\Sqlite::class,
		'sqlite3' => \OC\Setup\Sqlite::class,
	];

	/**
	 * Wrapper around the "class_exists" PHP function to be able to mock it
	 * @param string $name
	 * @return bool
	 */
	protected function class_exists($name) {
		return class_exists($name);
	}

	/**
	 * Wrapper around the "is_callable" PHP function to be able to mock it
	 * @param string $name
	 * @return bool
	 */
	protected function is_callable($name) {
		return is_callable($name);
	}

	/**
	 * Wrapper around \PDO::getAvailableDrivers
	 *
	 * @return array
	 */
	protected function getAvailableDbDriversForPdo() {
		return \PDO::getAvailableDrivers();
	}

	/**
	 * Get the available and supported databases of this instance
	 *
	 * @param bool $allowAllDatabases
	 * @return array
	 * @throws Exception
	 */
	public function getSupportedDatabases($allowAllDatabases = false) {
		$availableDatabases = array(
			'sqlite' =>  array(
				'type' => 'pdo',
				'call' => 'sqlite',
				'name' => 'SQLite'
			),
			'mysql' => array(
				'type' => 'pdo',
				'call' => 'mysql',
				'name' => 'MySQL/MariaDB'
			),
			'pgsql' => array(
				'type' => 'pdo',
				'call' => 'pgsql',
				'name' => 'PostgreSQL'
			),
			'oci' => array(
				'type' => 'function',
				'call' => 'oci_connect',
				'name' => 'Oracle'
			)
		);
		if ($allowAllDatabases) {
			$configuredDatabases = array_keys($availableDatabases);
		} else {
			$configuredDatabases = $this->config->getValue('supportedDatabases',
				array('sqlite', 'mysql', 'pgsql'));
		}
		if(!is_array($configuredDatabases)) {
			throw new Exception('Supported databases are not properly configured.');
		}

		$supportedDatabases = array();

		foreach($configuredDatabases as $database) {
			if(array_key_exists($database, $availableDatabases)) {
				$working = false;
				$type = $availableDatabases[$database]['type'];
				$call = $availableDatabases[$database]['call'];

				if ($type === 'function') {
					$working = $this->is_callable($call);
				} elseif($type === 'pdo') {
					$working = in_array($call, $this->getAvailableDbDriversForPdo(), TRUE);
				}
				if($working) {
					$supportedDatabases[$database] = $availableDatabases[$database]['name'];
				}
			}
		}

		return $supportedDatabases;
	}

	/**
	 * Gathers system information like database type and does
	 * a few system checks.
	 *
	 * @return array of system info, including an "errors" value
	 * in case of errors/warnings
	 */
	public function getSystemInfo($allowAllDatabases = false) {
		$databases = $this->getSupportedDatabases($allowAllDatabases);

		$dataDir = $this->config->getValue('datadirectory', \OC::$SERVERROOT.'/data');

		$errors = array();

		// Create data directory to test whether the .htaccess works
		// Notice that this is not necessarily the same data directory as the one
		// that will effectively be used.
		if(!file_exists($dataDir)) {
			@mkdir($dataDir);
		}
		$htAccessWorking = true;
		if (is_dir($dataDir) && is_writable($dataDir)) {
			// Protect data directory here, so we can test if the protection is working
			\OC\Setup::protectDataDirectory();

			try {
				$util = new \OC_Util();
				$htAccessWorking = $util->isHtaccessWorking(\OC::$server->getConfig());
			} catch (\OC\HintException $e) {
				$errors[] = array(
					'error' => $e->getMessage(),
					'hint' => $e->getHint()
				);
				$htAccessWorking = false;
			}
		}

		if (\OC_Util::runningOnMac()) {
			$errors[] = array(
				'error' => $this->l10n->t(
					'Mac OS X is not supported and %s will not work properly on this platform. ' .
					'Use it at your own risk! ',
					$this->defaults->getName()
				),
				'hint' => $this->l10n->t('For the best results, please consider using a GNU/Linux server instead.')
			);
		}

		if($this->iniWrapper->getString('open_basedir') !== '' && PHP_INT_SIZE === 4) {
			$errors[] = array(
				'error' => $this->l10n->t(
					'It seems that this %s instance is running on a 32-bit PHP environment and the open_basedir has been configured in php.ini. ' .
					'This will lead to problems with files over 4 GB and is highly discouraged.',
					$this->defaults->getName()
				),
				'hint' => $this->l10n->t('Please remove the open_basedir setting within your php.ini or switch to 64-bit PHP.')
			);
		}

		return array(
			'hasSQLite' => isset($databases['sqlite']),
			'hasMySQL' => isset($databases['mysql']),
			'hasPostgreSQL' => isset($databases['pgsql']),
			'hasOracle' => isset($databases['oci']),
			'databases' => $databases,
			'directory' => $dataDir,
			'htaccessWorking' => $htAccessWorking,
			'errors' => $errors,
		);
	}

	/**
	 * @param $options
	 * @return array
	 */
	public function install($options) {
		$l = $this->l10n;

		$error = array();
		$dbType = $options['dbtype'];

		if(empty($options['adminlogin'])) {
			$error[] = $l->t('Set an admin username.');
		}
		if(empty($options['adminpass'])) {
			$error[] = $l->t('Set an admin password.');
		}
		if(empty($options['directory'])) {
			$options['directory'] = \OC::$SERVERROOT."/data";
		}

		if (!isset(self::$dbSetupClasses[$dbType])) {
			$dbType = 'sqlite';
		}

		$username = htmlspecialchars_decode($options['adminlogin']);
		$password = htmlspecialchars_decode($options['adminpass']);
		$dataDir = htmlspecialchars_decode($options['directory']);

		$class = self::$dbSetupClasses[$dbType];
		/** @var \OC\Setup\AbstractDatabase $dbSetup */
		$dbSetup = new $class($l, 'db_structure.xml', $this->config,
			$this->logger, $this->random);
		$error = array_merge($error, $dbSetup->validate($options));

		// validate the data directory
		if (
			(!is_dir($dataDir) and !mkdir($dataDir)) or
			!is_writable($dataDir)
		) {
			$error[] = $l->t("Can't create or write into the data directory %s", array($dataDir));
		}

		if(count($error) != 0) {
			return $error;
		}

		$request = \OC::$server->getRequest();

		//no errors, good
		if(isset($options['trusted_domains'])
		    && is_array($options['trusted_domains'])) {
			$trustedDomains = $options['trusted_domains'];
		} else {
			$trustedDomains = [$request->getInsecureServerHost()];
		}

		//use sqlite3 when available, otherwise sqlite2 will be used.
		if($dbType=='sqlite' and class_exists('SQLite3')) {
			$dbType='sqlite3';
		}

		//generate a random salt that is used to salt the local user passwords
		$salt = $this->random->generate(30);
		// generate a secret
		$secret = $this->random->generate(48);

		//write the config file
		$this->config->setValues([
			'passwordsalt'		=> $salt,
			'secret'			=> $secret,
			'trusted_domains'	=> $trustedDomains,
			'datadirectory'		=> $dataDir,
			'overwrite.cli.url'	=> $request->getServerProtocol() . '://' . $request->getInsecureServerHost() . \OC::$WEBROOT,
			'dbtype'			=> $dbType,
			'version'			=> implode('.', \OCP\Util::getVersion()),
		]);

		try {
			$dbSetup->initialize($options);
			$dbSetup->setupDatabase($username);
		} catch (\OC\DatabaseSetupException $e) {
			$error[] = array(
				'error' => $e->getMessage(),
				'hint' => $e->getHint()
			);
			return($error);
		} catch (Exception $e) {
			$error[] = array(
				'error' => 'Error while trying to create admin user: ' . $e->getMessage(),
				'hint' => ''
			);
			return($error);
		}

		//create the user and group
		$user =  null;
		try {
			$user = \OC::$server->getUserManager()->createUser($username, $password);
			if (!$user) {
				$error[] = "User <$username> could not be created.";
			}
		} catch(Exception $exception) {
			$error[] = $exception->getMessage();
		}

		if(count($error) == 0) {
			$config = \OC::$server->getConfig();
			$config->setAppValue('core', 'installedat', microtime(true));
			$config->setAppValue('core', 'lastupdatedat', microtime(true));
			$config->setAppValue('core', 'vendor', $this->getVendor());

			$group =\OC::$server->getGroupManager()->createGroup('admin');
			$group->addUser($user);

			// Install shipped apps and specified app bundles
			Installer::installShippedApps();
			$installer = new Installer(
				\OC::$server->getAppFetcher(),
				\OC::$server->getHTTPClientService(),
				\OC::$server->getTempManager(),
				\OC::$server->getLogger(),
				\OC::$server->getConfig()
			);
			$bundleFetcher = new BundleFetcher(\OC::$server->getL10N('lib'));
			$defaultInstallationBundles = $bundleFetcher->getDefaultInstallationBundle();
			foreach($defaultInstallationBundles as $bundle) {
				try {
					$installer->installAppBundle($bundle);
				} catch (Exception $e) {}
			}

			// create empty file in data dir, so we can later find
			// out that this is indeed an ownCloud data directory
			file_put_contents($config->getSystemValue('datadirectory', \OC::$SERVERROOT.'/data').'/.ocdata', '');

			// Update .htaccess files
			Setup::updateHtaccess();
			Setup::protectDataDirectory();

			self::installBackgroundJobs();

			//and we are done
			$config->setSystemValue('installed', true);

			// Create a session token for the newly created user
			// The token provider requires a working db, so it's not injected on setup
			/* @var $userSession User\Session */
			$userSession = \OC::$server->getUserSession();
			$defaultTokenProvider = \OC::$server->query('OC\Authentication\Token\DefaultTokenProvider');
			$userSession->setTokenProvider($defaultTokenProvider);
			$userSession->login($username, $password);
			$userSession->createSessionToken($request, $userSession->getUser()->getUID(), $username, $password);
		}

		return $error;
	}

	public static function installBackgroundJobs() {
		\OC::$server->getJobList()->add('\OC\Authentication\Token\DefaultTokenCleanupJob');
	}

	/**
	 * @return string Absolute path to htaccess
	 */
	private function pathToHtaccess() {
		return \OC::$SERVERROOT.'/.htaccess';
	}

	/**
	 * Append the correct ErrorDocument path for Apache hosts
	 * @return bool True when success, False otherwise
	 */
	public static function updateHtaccess() {
		$config = \OC::$server->getSystemConfig();

		// For CLI read the value from overwrite.cli.url
		if(\OC::$CLI) {
			$webRoot = $config->getValue('overwrite.cli.url', '');
			if($webRoot === '') {
				return false;
			}
			$webRoot = parse_url($webRoot, PHP_URL_PATH);
			$webRoot = rtrim($webRoot, '/');
		} else {
			$webRoot = !empty(\OC::$WEBROOT) ? \OC::$WEBROOT : '/';
		}

		$setupHelper = new \OC\Setup($config, \OC::$server->getIniWrapper(),
			\OC::$server->getL10N('lib'), \OC::$server->query(Defaults::class), \OC::$server->getLogger(),
			\OC::$server->getSecureRandom());

		$htaccessContent = file_get_contents($setupHelper->pathToHtaccess());
		$content = "#### DO NOT CHANGE ANYTHING ABOVE THIS LINE ####\n";
		$htaccessContent = explode($content, $htaccessContent, 2)[0];

		//custom 403 error page
		$content.= "\nErrorDocument 403 ".$webRoot."/core/templates/403.php";

		//custom 404 error page
		$content.= "\nErrorDocument 404 ".$webRoot."/core/templates/404.php";

		// Add rewrite rules if the RewriteBase is configured
		$rewriteBase = $config->getValue('htaccess.RewriteBase', '');
		if($rewriteBase !== '') {
			$content .= "\n<IfModule mod_rewrite.c>";
			$content .= "\n  Options -MultiViews";
			$content .= "\n  RewriteRule ^core/js/oc.js$ index.php [PT,E=PATH_INFO:$1]";
			$content .= "\n  RewriteRule ^core/preview.png$ index.php [PT,E=PATH_INFO:$1]";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !\\.(css|js|svg|gif|png|html|ttf|woff|ico|jpg|jpeg)$";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !core/img/favicon.ico$";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !core/img/manifest.json$";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/remote.php";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/public.php";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/cron.php";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/core/ajax/update.php";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/status.php";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/ocs/v1.php";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/ocs/v2.php";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/robots.txt";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/updater/";
			$content .= "\n  RewriteCond %{REQUEST_FILENAME} !/ocs-provider/";
			$content .= "\n  RewriteCond %{REQUEST_URI} !^/.well-known/acme-challenge/.*";
			$content .= "\n  RewriteRule . index.php [PT,E=PATH_INFO:$1]";
			$content .= "\n  RewriteBase " . $rewriteBase;
			$content .= "\n  <IfModule mod_env.c>";
			$content .= "\n    SetEnv front_controller_active true";
			$content .= "\n    <IfModule mod_dir.c>";
			$content .= "\n      DirectorySlash off";
			$content .= "\n    </IfModule>";
			$content .= "\n  </IfModule>";
			$content .= "\n</IfModule>";
		}

		if ($content !== '') {
			//suppress errors in case we don't have permissions for it
			return (bool) @file_put_contents($setupHelper->pathToHtaccess(), $htaccessContent.$content . "\n");
		}

		return false;
	}

	public static function protectDataDirectory() {
		//Require all denied
		$now =  date('Y-m-d H:i:s');
		$content = "# Generated by Nextcloud on $now\n";
		$content.= "# line below if for Apache 2.4\n";
		$content.= "<ifModule mod_authz_core.c>\n";
		$content.= "Require all denied\n";
		$content.= "</ifModule>\n\n";
		$content.= "# line below if for Apache 2.2\n";
		$content.= "<ifModule !mod_authz_core.c>\n";
		$content.= "deny from all\n";
		$content.= "Satisfy All\n";
		$content.= "</ifModule>\n\n";
		$content.= "# section for Apache 2.2 and 2.4\n";
		$content.= "<ifModule mod_autoindex.c>\n";
		$content.= "IndexIgnore *\n";
		$content.= "</ifModule>\n";

		$baseDir = \OC::$server->getConfig()->getSystemValue('datadirectory', \OC::$SERVERROOT . '/data');
		file_put_contents($baseDir . '/.htaccess', $content);
		file_put_contents($baseDir . '/index.html', '');
	}

	/**
	 * Return vendor from which this version was published
	 *
	 * @return string Get the vendor
	 *
	 * Copy of \OC\Updater::getVendor()
	 */
	private function getVendor() {
		// this should really be a JSON file
		require \OC::$SERVERROOT . '/version.php';
		/** @var string $vendor */
		return (string) $vendor;
	}
}
