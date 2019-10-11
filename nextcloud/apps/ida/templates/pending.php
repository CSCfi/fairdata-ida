<!--
This file is part of the IDA research data storage service

Copyright (C) 2018 Ministry of Education and Culture, Finland

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

@author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
@license  GNU Affero General Public License, version 3
@link     https://research.csc.fi/
-->

<div id="app" class="ida">
    
    <?php $_['appNavigation']->printPage(); ?>

    <div id="app-content">
        <div id="app-content-wrapper">

            <table class="idaTable">
                <?php if (sizeof($_['actions']) > 0) : ?>
                    <tr>
                        <th class="ida-pid"><?php p($l->t('Action ID')) ?></th>
                        <th class="ida-timestamp"><?php p($l->t('Initiated')) ?></th>
                        <th class="ida-action"><?php p($l->t('Action')) ?></th>
                        <th class="ida-project"><?php p($l->t('Project')) ?></th>
                        <th><?php p($l->t('Scope')) ?></th>
                    </tr>
                    <?php foreach ($_['actions'] as $action): ?>
                        <tr>
                            <td class="ida-fixed"><a href="/apps/ida/action/<?php p($action->getPid()) ?>"><?php p($action->getPid()) ?></a></td>
                            <td><?php p((new \DateTime($action->getInitiated()))->format('D, M j, Y, H:i') . ' UTC') ?></td>
                            <td><?php p($l->t($action->getAction())) ?></td>
                            <td><?php p($action->getProject()) ?></td>
                            <td class="ida-fixed"><?php p($action->getPathname()) ?></td>
                        </tr>
                    <?php endforeach; ?>
                <?php else: ?>
                    <tr>
                        <td><?php p($l->t('No pending actions found.')) ?></td>
                    </tr>
                <?php endif; ?>
            </table>
        </div>
    </div>
</div>
