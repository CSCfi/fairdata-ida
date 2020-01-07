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

            <table class="action-details idaTable">
                <?php if ($_['action'] != null) :
                $action = $_['action']; ?>
                <tr>
                    <th class="ida-short-heading"><?php p($l->t('Action ID')) ?></th>
                    <td class="ida-fixed"><?php p($action->getPid()) ?></td>
                    <th class="ida-long-heading"><?php p($l->t('Initiated')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getInitiated() != null) {
                            p((new \DateTime($action->getInitiated()))->format('D, M j, Y, H:i') . ' UTC');
                        } ?>
                    </td>
                </tr>
                <tr>
                    <th class="ida-short-heading"><?php p($l->t('Action')) ?></th>
                    <td><?php p($l->t($action->getAction())) ?></td>
                    <th class="ida-long-heading"><?php p($l->t('File IDs Generated')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getPids() != null) {
                            p((new \DateTime($action->getPids()))->format('D, M j, Y, H:i') . ' UTC');
                        } ?>
                    </td>
                </tr>
                <tr>
                    <th class="ida-short-heading"><?php p($l->t('Project')) ?></th>
                    <td><?php p($action->getProject()) ?></td>
                    <th class="ida-long-heading"><?php p($l->t('File Storage Updated')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getStorage() != null) {
                            p((new \DateTime($action->getStorage()))->format('D, M j, Y, H:i') . ' UTC');
                        } ?>
                    </td>
                </tr>
                <tr>
                    <th class="ida-short-heading"><?php p($l->t('User')) ?></th>
                    <td><?php p($action->getUser()) ?></td>
                    <th class="ida-long-heading"><?php p($l->t('File Checksums Generated')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getChecksums() != null) {
                            p((new \DateTime($action->getChecksums()))->format('D, M j, Y, H:i') . ' UTC');
                        } ?>
                    </td>
                </tr>
                <tr>
                    <th class="ida-short-heading"><?php p($l->t('Scope')) ?></th>
                    <td class="ida-fixed"><?php p($action->getPathname()) ?></td>
                    <th class="ida-long-heading"><?php p($l->t('File Metadata Stored')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getMetadata() != null) {
                            p((new \DateTime($action->getMetadata()))->format('D, M j, Y, H:i') . ' UTC');
                        } ?>
                    </td>
                </tr>
                <tr>
                    <th class="ida-short-heading"><?php p($l->t('Retried by')) ?></th>
                    <td class="ida-fixed">
                        <?php if ($action->getRetry() != null) : ?>
                            <a href="/apps/ida/action/<?php p($action->getRetry()) ?>"><?php p($action->getRetry()) ?></a>
                        <?php endif; ?>
                        <?php if ($action->getRetry() == null && $action->getFailed() != null && $action->getCleared() == null) : ?>
                            <span style="font-family: 'Open Sans', Frutiger, Calibri, 'Myriad Pro', Myriad, sans-serif;">
                                <a href="/apps/ida/retry/<?php p($action->getPid()) ?>"><?php p($l->t('RETRY')) ?></a>
                            </span>
                        <?php endif; ?>
                    </td>
                    <th class="ida-long-heading"><?php p($l->t('Files Replicated')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getReplication() != null) {
                            p((new \DateTime($action->getReplication()))->format('D, M j, Y, H:i') . ' UTC');
                        } ?>
                    </td>
                </tr>
                <tr>
                    <th class="ida-short-heading"><?php p($l->t('Retry of')) ?></th>
                    <td class="ida-fixed">
                        <?php if ($action->getRetrying() != null) : ?>
                            <a href="/apps/ida/action/<?php p($action->getRetrying()) ?>"><?php p($action->getRetrying()) ?></a>
                        <?php endif; ?>
                    </td>
                    <th class="ida-long-heading"><?php p($l->t('Completed')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getCompleted() != null) {
                            p((new \DateTime($action->getCompleted()))->format('D, M j, Y, H:i') . ' UTC');
                        } ?>
                    </td>
                </tr>
                <tr>
                    <th class="ida-short-heading"></th>
                    <td></td>
                    <th class="ida-long-heading"><?php p($l->t('Failed')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getFailed() != null) {
                            p((new \DateTime($action->getFailed()))->format('D, M j, Y, H:i') . ' UTC');
                        } ?>
                    </td>
                </tr>
                <tr>
                    <th class="ida-short-heading"></th>
                    <td></td>
                    <th class="ida-long-heading"><?php p($l->t('Cleared')) ?></th>
                    <td class="ida-timestamp">
                        <?php if ($action->getCleared() != null) : ?>
                            <?php p((new \DateTime($action->getCleared()))->format('D, M j, Y, H:i') . ' UTC'); ?>
                        <?php endif; ?>
                        <?php if ($action->getFailed() != null && $action->getCleared() == null && substr(\OC::$server->getUserSession()->getUser()->getUID(), 0, 4) === "PSO_"): ?>
                            <span style="font-family: 'Open Sans', Frutiger, Calibri, 'Myriad Pro', Myriad, sans-serif;">
                                <a href="/apps/ida/clear/<?php p($action->getPid()) ?>"><?php p($l->t('CLEAR')) ?></a>
                            </span>
                        <?php endif; ?>
                    </td>
                </tr>
            </table>
            
            <?php if ($action->getError() != null) : ?>
                <div id="action-error" class="ida-alert">
                    <b><?php p($l->t('Error:')) ?></b><br />
                    <pre><?php p($action->getError()) ?></pre>
                </div>
            <?php endif; ?>
            
            <?php if (sizeof($_['files']) > 0) : ?>
                <table id="action-files" class="idaTable">
                    <tr>
                        <th class="ida-pid"><?php p($l->t('File ID')) ?></th>
                        <th><?php p($l->t('File')) ?></th>
                    </tr>
                    <?php foreach ($_['files'] as $file): ?>
                        <tr>
                            <td class="ida-fixed"><?php p($file->getPid()) ?></td>
                            <td class="ida-fixed"><?php p($file->getPathname()) ?></td>
                        </tr>
                    <?php endforeach; ?>
                    <?php if (sizeof($_['files']) >= OCA\IDA\Util\Constants::MAX_FILE_COUNT) : ?>
                        <tr><td class="ida-fixed" colspan="2">... <?php p($l->t('remainder of files not shown')) ?> ...</td></tr>
                    <?php endif; ?>
                </table>
            <?php endif; ?>
            <?php else: ?>
                <tr>
                    <td><?php p($l->t('Action not found.')) ?></td>
                </tr>
            <?php endif; ?>
            </table>

        </div>
    </div>
</div>

