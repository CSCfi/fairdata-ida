<?php
/**
 * @copyright Copyright (c) 2016, ownCloud, Inc.
 *
 * @author Joas Schilling <coding@schilljs.com>
 * @author Lukas Reschke <lukas@statuscode.ch>
 * @author Morris Jobke <hey@morrisjobke.de>
 * @author Robin Appelman <robin@icewind.nl>
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

namespace OC\Core\Command\App;

use OC\Installer;
use OCP\App\AppPathNotFoundException;
use OCP\App\IAppManager;
use OCP\IGroup;
use OCP\IGroupManager;
use Stecman\Component\Symfony\Console\BashCompletion\Completion\CompletionAwareInterface;
use Stecman\Component\Symfony\Console\BashCompletion\CompletionContext;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputArgument;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

class Enable extends Command implements CompletionAwareInterface {

	/** @var IAppManager */
	protected $appManager;

	/** @var IGroupManager */
	protected $groupManager;

	/** @var int */
	protected $exitCode = 0;

	/**
	 * @param IAppManager $appManager
	 * @param IGroupManager $groupManager
	 */
	public function __construct(IAppManager $appManager, IGroupManager $groupManager) {
		parent::__construct();
		$this->appManager = $appManager;
		$this->groupManager = $groupManager;
	}

	protected function configure(): void {
		$this
			->setName('app:enable')
			->setDescription('enable an app')
			->addArgument(
				'app-id',
				InputArgument::REQUIRED | InputArgument::IS_ARRAY,
				'enable the specified app'
			)
			->addOption(
				'groups',
				'g',
				InputOption::VALUE_REQUIRED | InputOption::VALUE_IS_ARRAY,
				'enable the app only for a list of groups'
			);
	}

	protected function execute(InputInterface $input, OutputInterface $output) {
		$appIds = $input->getArgument('app-id');
		$groups = $this->resolveGroupIds($input->getOption('groups'));

		foreach ($appIds as $appId) {
			$this->enableApp($appId, $groups, $output);
		}

		return $this->exitCode;
	}

	/**
	 * @param string $appId
	 * @param array $groupIds
	 * @param OutputInterface $output
	 */
	private function enableApp(string $appId, array $groupIds, OutputInterface $output): void {
		$groupNames = array_map(function (IGroup $group) {
			return $group->getDisplayName();
		}, $groupIds);


		try {
			/** @var Installer $installer */
			$installer = \OC::$server->query(Installer::class);

			if (false === $installer->isDownloaded($appId)) {
				$installer->downloadApp($appId);
			}

			$installer->installApp($appId);

			if ($groupIds === []) {
				$this->appManager->enableApp($appId);
				$output->writeln($appId . ' enabled');
			} else {
				$this->appManager->enableAppForGroups($appId, $groupIds);
				$output->writeln($appId . ' enabled for groups: ' . implode(', ', $groupNames));
			}
		} catch (AppPathNotFoundException $e) {
			$output->writeln($appId . ' not found');
			$this->exitCode = 1;
		} catch (\Exception $e) {
			$output->writeln($e->getMessage());
			$this->exitCode = 1;
		}
	}

	/**
	 * @param array $groupIds
	 * @return array
	 */
	private function resolveGroupIds(array $groupIds): array {
		$groups = [];
		foreach ($groupIds as $groupId) {
			$group = $this->groupManager->get($groupId);
			if ($group instanceof IGroup) {
				$groups[] = $group;
			}
		}
		return $groups;
	}

	/**
	 * @param string $optionName
	 * @param CompletionContext $context
	 * @return string[]
	 */
	public function completeOptionValues($optionName, CompletionContext $context) {
		if ($optionName === 'groups') {
			return array_map(function (IGroup $group) {
				return $group->getGID();
			}, $this->groupManager->search($context->getCurrentWord()));
		}
		return [];
	}

	/**
	 * @param string $argumentName
	 * @param CompletionContext $context
	 * @return string[]
	 */
	public function completeArgumentValues($argumentName, CompletionContext $context) {
		if ($argumentName === 'app-id') {
			$allApps = \OC_App::getAllApps();
			return array_diff($allApps, \OC_App::getEnabledApps(true, true));
		}
		return [];
	}
}