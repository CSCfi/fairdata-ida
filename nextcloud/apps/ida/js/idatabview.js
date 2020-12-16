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

    var TEMPLATE =
        '<div id="spinnerWrapper"><div id="spinner"></div></div>' +

        '<div id="stagingFolder" style="display: none" tabindex="0">' +
        '<table class="idaTable">' +
        '<tr><td align="center">' +
        '<input type="button" value="' + t('ida', 'Freeze') + '" id="freezeFolderButton"/>' +
        '</td></tr>' +
        '</table>' +
        '<div class="idaWarning"><p><b>' +
        t('ida', 'NOTICE') + '</b>: ' +
        t('ida', 'Be absolutely sure you want to freeze the folder before proceeding.') +
        '</p><p>' +
        t('ida', 'Freezing will move all files within the selected folder to the frozen area, making all files read-only and visible to other services, and will initiate several background operations.') +
        '</p><p>' +
        t('ida', 'Frozen files will be replicated to separate physical storage to guard against loss of data due to hardware failure.') +
        '</p><p>' +
        t('ida', 'The action cannot be terminated before it is complete. Depending on the amount of data, the background operations may take several hours.') +
        '</p><p>' +
        t('ida', 'Once initiated, the progress of the action can be checked from the <a href="../ida/actions/pending">Pending Actions</a> view.') +
        '</p></div>' +
        '</div>' +

        '<div id="stagingFile" style="display: none" tabindex="0">' +
        '<table class="idaTable">' +
        '<tr><td align="center">' +
        '<input type="button" value="' + t('ida', 'Freeze') + '" id="freezeFileButton"/>' +
        '</td></tr>' +
        '</table>' +
        '<div class="idaWarning"><p><b>' +
        t('ida', 'NOTICE') + '</b>: ' +
        t('ida', 'Be absolutely sure you want to freeze the file before proceeding.') +
        '</p><p>' +
        t('ida', 'Freezing will move the selected file to the frozen area, making it read-only and visible to other services, and will initiate several background operations.') +
        '</p><p>' +
        t('ida', 'The frozen file will be replicated to separate physical storage to guard against loss of data due to hardware failure.') +
        '</p><p>' +
        t('ida', 'The action cannot be terminated before it is complete. Depending on the size of the file, the background operations may take several hours.') +
        '</p><p>' +
        t('ida', 'Once initiated, the progress of the action can be checked from the <a href="../ida/actions/pending">Pending Actions</a> view.') +
        '</p></div>' +
        '</div>' +

        '<div id="frozenFilePending" style="display: none" tabindex="0">' +
        '<table class="idaTable">' +
        '<tr><th>' + t('ida', 'Action') + ':</th><td id="frozenFilePendingAction"></td></tr>' +
        '</table>' +
        '<p>' +
        t('ida', 'This file is part of an ongoing action.') +
        '</p><p>' +
        t('ida', 'Additional information will be available once the action is complete.') +
        '</p><p>' +
        t('ida', 'The progress of the ongoing action can be viewed by clicking on the action ID above.') +
        '</p></div>' +
        '</div>' +

        '<div id="frozenFolder" style="display: none" tabindex="0">' +
        '<table class="idaTable">' +
        '<tr><td>' +
        '<input type="button" value="' + t('ida', 'Unfreeze') + '" id="unfreezeFolderButton"/>' +
        '<input type="button" value="' + t('ida', 'Delete') + '" id="deleteFolderButton"/>' +
        '</td></tr>' +
        '</table>' +
        '<div class="idaWarning"><p><b>' +
        t('ida', 'NOTICE') + '</b>: ' +
        t('ida', 'Be absolutely sure you want to unfreeze or delete all files within the selected folder before proceeding with either option.') +
        '</p><p><b>' +
        t('ida', 'Unfrozen and deleted files will no longer to be accessible to other services, making all external references to them invalid. All replicated copies of unfrozen and deleted files will be removed.') +
        '</b></p><p>' +
        t('ida', 'Unfreezing will move all files within the selected folder back to the staging area, making them fully editable.') + ' ' +
        t('ida', 'Deleting will entirely remove all files within the selected folder from the service.') + ' ' +
        t('ida', 'Either action will initiate several background operations.') +
        '</p><p>' +
        t('ida', 'The action cannot be terminated before it is complete. Depending on the amount of data, the background operations may take several hours.') +
        '</p><p><b>' +
        t('ida', 'THIS ACTION CANNOT BE UNDONE.') +
        '</b></p><p>' +
        t('ida', 'Once initiated, the progress of the action can be checked from the <a href="../ida/actions/pending">Pending Actions</a> view.') +
        '</p></div>' +
        '</div>' +

        '<div id="frozenFile" style="display: none" tabindex="0">' +
        '<table class="idaTable">' +
        '<tr><th>' + t('ida', 'Action') + ':</th><td id="frozenFileAction"></td></tr>' +
        '<tr><th>' + t('ida', 'File ID') + ':</th><td id="frozenFileId"></td></tr>' +
        '<tr><th>' + t('ida', 'Frozen') + ':</th><td id="frozenFileFrozen"></td></tr>' +
        '<tr><th>' + t('ida', 'Size') + ':</th><td id="frozenFileSize"></td></tr>' +
        '<tr><th>' + t('ida', 'Checksum') + ':</th><td id="frozenFileChecksum"></td></tr>' +
        '<tr><td colspan="2" align="center">' +
        '<input type="button" value="' + t('ida', 'Unfreeze') + '" id="unfreezeFileButton"/>' +
        '<input type="button" value="' + t('ida', 'Delete') + '" id="deleteFileButton"/>' +
        '</td></tr>' +
        '</table>' +
        '<div class="idaWarning"><p><b>' +
        t('ida', 'NOTICE') + '</b>: ' +
        t('ida', 'Be absolutely sure you want to unfreeze or delete the file before proceeding with either option.') +
        '</p><p><b>' +
        t('ida', 'Unfrozen and deleted files will no longer to be accessible to other services, making all external references to them invalid. All replicated copies of unfrozen and deleted files will be removed.') +
        '</b></p><p>' +
        t('ida', 'Unfreezing will move the selected file back to the staging area, making it fully editable.') + ' ' +
        t('ida', 'Deleting will entirely remove the selected file from the service.') + ' ' +
        t('ida', 'Either action will initiate several background operations.') +
        '</p><p>' +
        t('ida', 'The action cannot be terminated before it is complete. Depending on the size of the file, the background operations may take several hours.') +
        '</p><p><b>' +
        t('ida', 'THIS ACTION CANNOT BE UNDONE.') +
        '</b></p><p>' +
        t('ida', 'Once initiated, the progress of the action can be checked from the <a href="../ida/actions/pending">Pending Actions</a> view.') +
        '</p></div>' +
        '</table>' +
        '</div>' +

        '<div id="debug" style="display: none"></div>';

    function freezeFolder(e) {
        OC.dialogs.confirm(
            t('ida', 'Are you sure you want to freeze all files within this folder, moving them to the frozen area and making them read-only?') + ' ' +
            t('ida', 'The action cannot be terminated before it is complete. Depending on the amount of data, the background operations may take several hours.'),
            t('ida', 'Freeze Folder?'),
            function (result) {
                if (result) {
                    $(freezeFolderButton).prop('disabled', true);
                    executeAction(e.data.param, 'freeze');
                }
            },
            true
        );
    }

    function freezeFile(e) {
        OC.dialogs.confirm(
            t('ida', 'Are you sure you want to freeze this file, moving it to the frozen area and making it read-only?') + ' ' +
            t('ida', 'The action cannot be terminated before it is complete. Depending on the size of the file, the background operations may take several hours.'),
            t('ida', 'Freeze File?'),
            function (result) {
                if (result) {
                    $(freezeFileButton).prop('disabled', true);
                    executeAction(e.data.param, 'freeze');
                }
            },
            true
        );
    }

    function unfreezeFolder(e) {
        OC.dialogs.confirm(
            t('ida', 'Are you sure you want to unfreeze all files within this folder, and move them back to the staging area?') + ' ' +
            t('ida', 'The action cannot be terminated before it is complete. Depending on the amount of data, the background operations may take several hours.') + ' ' +
            t('ida', 'THIS ACTION CANNOT BE UNDONE.'),
            t('ida', 'Unfreeze Folder?'),
            function (result) {
                if (result) {
                    $(unfreezeFolderButton).prop('disabled', true);
                    $(deleteFolderButton).prop('disabled', true);
                    executeAction(e.data.param, 'unfreeze');
                }
            },
            true
        );
    }

    function unfreezeFile(e) {
        OC.dialogs.confirm(
            t('ida', 'Are you sure you want to unfreeze this file, and move it back to the staging area?') + ' ' +
            t('ida', 'The action cannot be terminated before it is complete. Depending on the size of the file, the background operations may take several hours.') + ' ' +
            t('ida', 'THIS ACTION CANNOT BE UNDONE.'),
            t('ida', 'Unfreeze File?'),
            function (result) {
                if (result) {
                    $(unfreezeFileButton).prop('disabled', true);
                    $(deleteFileButton).prop('disabled', true);
                    executeAction(e.data.param, 'unfreeze');
                }
            },
            true
        );
    }

    function deleteFolder(e) {
        OC.dialogs.confirm(
            t('ida', 'Are you sure you want to delete this folder, permanently removing it and all files within it from the service?') + ' ' +
            t('ida', 'The action cannot be terminated before it is complete. Depending on the amount of data, the background operations may take several hours.') + ' ' +
            t('ida', 'THIS ACTION CANNOT BE UNDONE.'),
            t('ida', 'Delete Folder?'),
            function (result) {
                if (result) {
                    $(deleteFolderButton).prop('disabled', true);
                    executeAction(e.data.param, 'delete');
                }
            },
            true
        );
    }

    function deleteFile(e) {
        OC.dialogs.confirm(
            t('ida', 'Are you sure you want to delete this file, permanently removing it from the service?') + ' ' +
            t('ida', 'The action cannot be terminated before it is complete. Depending on the size of the file, the background operations may take several hours.') + ' ' +
            t('ida', 'THIS ACTION CANNOT BE UNDONE.'),
            t('ida', 'Delete File?'),
            function (result) {
                if (result) {
                    $(deleteFileButton).prop('disabled', true);
                    executeAction(e.data.param, 'delete');
                }
            },
            true
        );
    }

    function checkDatasets(nodeId, project, pathname) {
        var datasets = null;
        $.ajax({
            async: false,
            cache: false,
            url: OC.generateUrl('/apps/ida/api/datasets'),
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ nextcloudNodeId: nodeId, project: project, pathname: pathname }),
            success: function (data) {
                datasets = data;
            },
            error: function (data) {
                console.log(data);
            }
        });
        return datasets;
    }

    function buildDatasetLinkListing(datasets) {
        listing = '';
        domain = 'fd-test.csc.fi';
        count = datasets.length;
        limit = count;
        if (count > 5) {
            limit = 5;
        }
        for (i = 0; i < limit; i++) {
            pid = datasets[i]['pid'];
            listing = listing
                + '<a style="color: #007FAD; padding-left: 20px;" href="https://etsin.'
                + domain
                + '/dataset/'
                + pid
                + '?preview=1" target="_blank">'
                + datasets[i]['title']
                + '</a><br>';
        }
        if (count > limit) {
            listing = listing + '<span style="color: gray; padding-left: 20px;">(' + (count - limit) + ' ' + t('ida', 'not shown') + ')</span><br>';
        }
        return listing;
    }

    function executeAction(fileInfo, action, datasetsChecked = false) {
        $(spinner).show();
        var fullpath = fileInfo.getFullPath();
        var project = OCA.IDA.Util.extractProjectName(fullpath);
        var pathname = OCA.IDA.Util.stripRootFolder(fullpath);
        var nodeId = fileInfo.get('id');
        if (action === 'freeze' || datasetsChecked) {
            $.ajax({
                cache: false,
                url: OC.generateUrl('/apps/ida/api/' + action),
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ nextcloudNodeId: nodeId, project: project, pathname: pathname }),
                success: function (data) {
                    $(spinner).hide();
                    if (data['action'] === 'freeze') {
                        OC.dialogs.confirmHtml(
                            t('ida', 'The data has been successfully frozen and moved to the frozen project space.') + ' ' +
                            t('ida', 'Depending on the amount of data, the background operations may still take several hours.') + ' ' +
                            t('ida', 'The initiated action is') + ' <a style="color: #007FAD;" href="/apps/ida/action/' + data['pid'] + '">' + data['pid'] + '</a>. ' +
                            t('ida', 'It is safe to log out from the IDA service and close your browser. Ongoing background operations will not be affected.') + '<br><br>' +
                            t('ida', 'Do you wish to view the data in its frozen location?'),
                            t('ida', 'Action initiated successfully. Show frozen data?'),
                            function (result) {
                                if (result) {
                                    var url = '/apps/files/?dir=' + encodeURIComponent('/' + data['project'] + OCA.IDA.Util.getParentPathname(data['pathname']));
                                    $(spinner).show();
                                    window.location.assign(url);
                                }
                                else {
                                    $(spinner).show();
                                    window.location.reload(true);
                                }
                            },
                            true
                        );
                    }
                    else if (data['action'] === 'unfreeze') {
                        OC.dialogs.confirmHtml(
                            t('ida', 'The data has been successfully unfrozen and moved back to the project staging space.') + ' ' +
                            t('ida', 'Depending on the amount of data, the background operations may still take several hours.') + ' ' +
                            t('ida', 'The initiated action is') + ' <a style="color: #007FAD;" href="/apps/ida/action/' + data['pid'] + '">' + data['pid'] + '</a>. ' +
                            t('ida', 'It is safe to log out from the IDA service and close your browser. Ongoing background operations will not be affected.') + '<br><br>' +
                            t('ida', 'Do you wish to view the data in its staging location?'),
                            t('ida', 'Action initiated successfully. Show unfrozen data?'),
                            function (result) {
                                if (result) {
                                    var url = '/apps/files/?dir=' + encodeURIComponent('/' + data['project'] + OCA.IDAConstants.STAGING_FOLDER_SUFFIX + OCA.IDA.Util.getParentPathname(data['pathname']));
                                    $(spinner).show();
                                    window.location.assign(url);
                                }
                                else {
                                    $(spinner).show();
                                    window.location.reload(true);
                                }
                            },
                            true
                        );
                    }
                    else { // action === 'delete')
                        OC.dialogs.message(
                            t('ida', 'The files have been successfully deleted.') + ' ' +
                            t('ida', 'Depending on the amount of data, the background operations may still take several hours.') + ' ' +
                            t('ida', 'The initiated action is') + ' <a style="color: #007FAD;" href="/apps/ida/action/' + data['pid'] + '">' + data['pid'] + '</a>. ' +
                            t('ida', 'It is safe to log out from the IDA service and close your browser. Ongoing background operations will not be affected.'),
                            t('ida', 'Action initiated successfully. Files deleted.'),
                            'info',
                            OCdialogs.OK_BUTTON,
                            function (result) {
                                $(spinner).show();
                                window.location.reload(true);
                            },
                            true,
                            true
                        );
                    }
                    return true;
                },
                error: function (data) {
                    $(spinner).hide();
                    if (action === 'freeze') {
                        OC.dialogs.alert(
                            t('ida', 'Unable to freeze the specified files:' + ' ' + data.responseJSON.message),
                            t('ida', 'Action Failed'),
                            function (result) {
                                $(spinner).hide();
                                $(freezeFileButton).prop('disabled', false);
                                $(freezeFolderButton).prop('disabled', false);
                            },
                            true
                        );
                    }
                    else if (action === 'unfreeze') {
                        OC.dialogs.alert(
                            t('ida', 'Unable to unfreeze the specified files:' + ' ' + data.responseJSON.message),
                            t('ida', 'Action Failed'),
                            function (result) {
                                $(spinner).hide();
                                $(unfreezeFileButton).prop('disabled', false);
                                $(unfreezeFolderButton).prop('disabled', false);
                                $(deleteFileButton).prop('disabled', false);
                                $(deleteFolderButton).prop('disabled', false);
                            },
                            true
                        );
                    }
                    else { // action === 'delete')
                        OC.dialogs.alert(
                            t('ida', 'Unable to delete the specified files:' + ' ' + data.responseJSON.message),
                            t('ida', 'Action Failed'),
                            function (result) {
                                $(spinner).hide();
                                $(unfreezeFileButton).prop('disabled', false);
                                $(unfreezeFolderButton).prop('disabled', false);
                                $(deleteFileButton).prop('disabled', false);
                                $(deleteFolderButton).prop('disabled', false);
                            },
                            true
                        );
                    }
                    return false;
                }
            });
        }
        else {

            // Check if any files included in the action scope belong to any datasets defined in Metax
            var affectedDatasets = checkDatasets(nodeId, project, pathname);

            if (affectedDatasets == null) {
                OC.dialogs.alert(
                    t('ida', 'An error occurred when checking for datasets which may be deprecated by the requested action.'),
                    t('ida', 'Action Failed'),
                    function (result) {
                        $(spinner).hide();
                        $(unfreezeFileButton).prop('disabled', false);
                        $(unfreezeFolderButton).prop('disabled', false);
                        $(deleteFileButton).prop('disabled', false);
                        $(deleteFolderButton).prop('disabled', false);
                    },
                    true
                );
                return false;
            }

            var affectedDatasetsCount = affectedDatasets.length;

            // If no datasets will be affected by the action, call function again
            // indicating dataset check completed
            if (affectedDatasetsCount === 0) {
                executeAction(fileInfo, action, true);
            }

            // Else, construct and present notification/confirmation modal about potentially affected datasets
            // If user chooses to proceed, call function again indicating dataset check completed
            // Else if user chooses to cancel the action, do nothing
            else {
                $(spinner).hide();
                var pasDatasets = [];
                var pasDatasetsPending = false;
                var max = affectedDatasets.length;
                for (var i = 0; i < max; i++) {
                    if (affectedDatasets[i]['pas'] == true) {
                        pasDatasets.push(affectedDatasets[i]);
                        pasDatasetsPending = true;
                    }
                }
                if (pasDatasetsPending) {
                    OC.dialogs.alertHtml(
                        '<span style="color: #b70c00; font-weight: bold; padding-right: 50px;">'
                        + t('ida', 'The specified action is not allowed because it would deprecate the datasets listed below, for which the digital preservation process is ongoing.')
                        + '<br><br>'
                        + buildDatasetLinkListing(pasDatasets)
                        + '<br><br><span style="color: black; padding-left: 20px;">'
                        + t('ida', 'If you have questions, please contact <a href="mailto:pas-support@csc.fi" target="_blank" style="color: #007FAD;">pas-support@csc.fi</a>')
                        + '</span></span>',
                        t('ida', 'Action not allowed: Datasets would be deprecated!'),
                        function (result) {
                            $(unfreezeFolderButton).prop('disabled', false);
                            $(unfreezeFileButton).prop('disabled', false);
                            $(deleteFolderButton).prop('disabled', false);
                            $(deleteFileButton).prop('disabled', false);
                        },
                        true
                    );
                }
                else {
                    OC.dialogs.confirmHtml(
                        '<span style="color: #b70c00; font-weight: bold; padding-right: 50px;">'
                        + t('ida', 'One or more files included in the specified action belong to a dataset. Proceeding with the specified action will permanently deprecate the datasets listed below.')
                        + ' '
                        + t('ida', 'THIS ACTION CANNOT BE UNDONE.')
                        + '</span><br><br><br>'
                        + buildDatasetLinkListing(affectedDatasets)
                        + '<br><br><span style="color: #b70c00; font-weight: bold; padding-left: 20px;">'
                        + t('ida', 'Do you wish to proceed?')
                        + '</span><br><br>',
                        t('ida', 'Warning: Datasets will be deprecated!'),
                        function (result) {
                            if (result) {
                                $(spinner).show();
                                executeAction(fileInfo, action, true);
                            }
                            else {
                                $(unfreezeFolderButton).prop('disabled', false);
                                $(unfreezeFileButton).prop('disabled', false);
                                $(deleteFolderButton).prop('disabled', false);
                                $(deleteFileButton).prop('disabled', false);
                            }
                        },
                        true
                    );
                }
            }
        }
    }

    /**
     * @class OCA.IDA.IDATabView
     * @memberof OCA.IDA
     * @classdesc
     *
     * Shows publication information for file
     *
     */
    var IDATabView = OCA.Files.DetailTabView.extend(
        /** @lends OCA.IDA.IDATabView.prototype */{
            id: 'idaTabView',
            className: 'idaTabView tab',

            _label: 'ida',

            events: {},

            getLabel: function () {
                return t('ida', 'Freezing');
            },

            nextPage: function () {
            },

            _onClickShowMoreVersions: function (ev) {
            },

            _onClickRevertVersion: function (ev) {
            },

            _toggleLoading: function (state) {
            },

            _onRequest: function () {
            },

            _onEndRequest: function () {
            },

            _onAddModel: function (model) {
            },

            itemTemplate: function (data) {
            },

            setFileInfo: function (fileInfo) {
                if (fileInfo) {
                    this.fileInfo = fileInfo;
                    this.render();
                }
            },

            _formatItem: function (version) {
            },

            /**
             * Renders the node details tab view
             */
            render: function () {

                this.$el.html(TEMPLATE);

                var fileInfo = this.fileInfo;
                var fullPath = fileInfo.getFullPath();

                $(spinner).hide();

                $(freezeFolderButton).bind('click', { param: fileInfo }, freezeFolder);
                $(freezeFileButton).bind('click', { param: fileInfo }, freezeFile);
                $(unfreezeFolderButton).bind('click', { param: fileInfo }, unfreezeFolder);
                $(unfreezeFileButton).bind('click', { param: fileInfo }, unfreezeFile);
                $(deleteFolderButton).bind('click', { param: fileInfo }, deleteFolder);
                $(deleteFileButton).bind('click', { param: fileInfo }, deleteFile);

                var isFolder = this.fileInfo.isDirectory();
                var isFrozen = OCA.IDA.Util.testIfFrozen(fullPath);

                if (isFrozen) {


                    if (isFolder) {
                        $(frozenFolder).show();
                        $(frozenFolder).focus();
                    }

                    else {

                        // Fetch frozen file details...

                        $.ajax({

                            cache: false,
                            url: OC.generateUrl('/apps/ida/api/files/byNextcloudNodeId/' + this.fileInfo.id),
                            type: 'GET',
                            contentType: 'application/json',

                            success: function (fileInfo) {

                                var filePid = fileInfo['pid'];
                                var actionPid = fileInfo['action'];
                                var fileFrozen = OCA.IDA.Util.localizeTimestamp(fileInfo['frozen']);
                                var fileSize = fileInfo['size'];
                                var fileChecksum = fileInfo['checksum'];

                                // Fetch action details...

                                $.ajax({

                                    cache: false,
                                    url: OC.generateUrl('/apps/ida/api/actions/' + actionPid),
                                    type: 'GET',
                                    contentType: 'application/json',

                                    success: function (actionInfo) {

                                        var isPending = actionInfo ? !(actionInfo['completed'] || actionInfo['failed'] || actionInfo['cleared']) : false;

                                        if (isPending) {
                                            $(frozenFilePendingAction).html('<a href="/apps/ida/action/' + actionPid + '">' + actionPid + '</a>');
                                            $(frozenFilePending).show();
                                            $(frozenFilePending).focus();
                                        }
                                        else {
                                            $(frozenFileAction).html('<a href="/apps/ida/action/' + actionPid + '">' + actionPid + '</a>');
                                            $(frozenFileId).html(filePid);
                                            $(frozenFileFrozen).html(fileFrozen);
                                            $(frozenFileSize).html(fileSize);
                                            $(frozenFileChecksum).html(fileChecksum);
                                            $(frozenFile).show();
                                            $(frozenFile).focus();
                                        }
                                    },

                                    error: function (x) {
                                        // This shouldn't ever happen, but we'll fail gracefully...
                                        $(frozenFile).show();
                                        $(frozenFile).focus();
                                    }
                                });
                            },

                            error: function (x) {
                                // This shouldn't ever happen, but we'll fail gracefully...
                                $(frozenFile).show();
                                $(frozenFile).focus();
                            }
                        });
                    }
                }
                else {
                    if (isFolder) {
                        $(stagingFolder).show();
                        $(stagingFolder).focus();
                    }
                    else {
                        $(stagingFile).show();
                        $(stagingFile).focus();
                    }
                }

                this.delegateEvents();
            }

        });

    OCA.IDA = OCA.IDA || {};

    OCA.IDA.IDATabView = IDATabView;

})();


