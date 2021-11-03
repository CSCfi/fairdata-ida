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

    OCA.IDA = OCA.IDA || {};

    /**
     * @namespace
     */
    OCA.IDA.Util = {

        /**
         * Makes all relevant notification icons visible based on the status of the projects
         * to which the current user belongs.
         */
        showNotificationIcons: function () {

            $.ajax({
                url: OC.generateUrl('/apps/ida/api/status'),
                type: 'GET',
                contentType: 'application/json',
                cache: false,
                async: false,
                success: function(response) {
                    if (response['failed'] === true) {
                        $("#ida-failed-actions-icon").show();
                    }
                    if (response['pending'] === true) {
                        $("#ida-pending-actions-icon").show();
                    }
                    if (response['suspended'] === true) {
                        $("#ida-suspended-icon").show();
                    }
                }
            });
        },

        /**
         * Returns false if the service is available, the project is not suspended, and the specified scope does not
         * intersect the scope of any initiating action; else returns an error message string.
         *
         * @param project The project name
         * @param scope   The scope to check
         */
        scopeNotOK: function (project, scope) {

            var jqxhr = $.ajax({
                url: OC.generateUrl('/apps/ida/api/checkScope?project=' + project + '&pathname=' + encodeURIComponent(scope)),
                type: 'POST',
                contentType: 'application/json',
                cache: false,
                async: false
            });

            if (jqxhr.status === 200) {
                return false;
            }

            if (jqxhr.status === 409) {
                var data = JSON.parse(jqxhr.responseText);
                return data['message'];
            }

            throw new Error(jqxhr.status + ": " + jqxhr.statusText);
        },

        /**
         * Returns true if the specified scope intersects the scope of an initiating action; else returns false.
         *
         * @param project The project name
         * @param scope   The scope to check
         */
        scopeIntersectsInitiatingAction: function (project, scope) {

            var jqxhr = $.ajax({
                url: OC.generateUrl('/apps/ida/api/checkScope?project=' + project + '&pathname=' + encodeURIComponent(scope)),
                type: 'POST',
                contentType: 'application/json',
                cache: false,
                async: false
            });

            if (jqxhr.status === 200) {
                return false;
            }

            if (jqxhr.status === 409) {
                return true;
            }

            throw new Error(jqxhr.status + ": " + jqxhr.statusText);
        },

        /**
         * Returns project title, if defined, else returns project name as title.
         *
         * @param project The project name
         */
        getProjectTitle: function (project) {

            var jqxhr = $.ajax({
                url: OC.generateUrl('/apps/ida/api/getProjectTitle?project=' + project),
                type: 'POST',
                contentType: 'application/json',
                cache: false,
                async: false
            });

            if (jqxhr.status === 200) {
                var data = JSON.parse(jqxhr.responseText);
                return data['message'];
            }

            return project;
        },

        extractProjectName: function (pathname) {
            matches = pathname.match('^\/[^\/][^\/]*');
            if (matches != null && matches.length > 0) {
                var project = matches[0];
                if (project.endsWith(OCA.IDAConstants.STAGING_FOLDER_SUFFIX)) {
                    return project.substr(1, project.length - OCA.IDAConstants.STAGING_FOLDER_SUFFIX.length - 1);
                }
                else {
                    return project.substr(1);
                }
            }
            return null;
        },

        getParentPathname: function (pathname) {
            matches = pathname.match('\/[^\/][^\/]*$');
            if (matches != null && matches.length > 0) {
                return pathname.substr(0, pathname.length - matches[0].length);
            }
            return pathname;
        },

        stripRootFolder: function (pathname) {
            if (OCA.IDA.Util.testIfRootProjectFolder(pathname)) {
                return '/';
            }
            matches = pathname.match('^\/[^\/][^\/]*\/');
            if (matches != null && matches.length > 0) {
                return pathname.substr(matches[0].length - 1);
            }
            return pathname;
        },

        extractBasename: function (pathname) {
            matches = pathname.match('[^\/][^\/]*$');
            if (matches != null && matches.length > 0) {
                return matches[0];
            }
            return pathname;
        },

        testIfRootProjectFolder: function (pathname) {
            return pathname.search('^/[^\/][^\/]*$') >= 0;
        },

        testIfFrozen: function (pathname) {
            var project = OCA.IDA.Util.extractProjectName(pathname);
            return ((pathname === '/' + project) || (pathname.startsWith('/' + project + '/')));
        },

        localizeTimestamp(timestamp) {
            var date = new Date(timestamp);
            var locale = window.navigator.userLanguage || window.navigator.language;
            var opts = {
                weekday: 'short',
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                seconds: '2-digit',
                timeZone: 'UTC'
            };
            return date.toLocaleTimeString(locale, opts) + ' UTC';
        },

        /**
         * Initialize the ida plugin.
         *
         * @param {OCA.Files.FileList} fileList file list to be extended
         */
        attach: function (fileList) {
            if (fileList.id === 'trashbin' || fileList.id === 'files.public') {
                return;
            }

            fileList.fileActions.registerAction(
                {
                    name: 'Freezing',
                    displayName: '',
                    altText: t('ida', 'Open IDA actions tab'),
                    mime: 'all',
                    permissions: OC.PERMISSION_READ,
                    icon: OC.imagePath('ida', 'appiconblue.png'),
                    type: OCA.Files.FileActions.TYPE_INLINE,
                    actionHandler: function (fileName) {
                        fileList.showDetailsView(fileName, 'idaTabView');
                    }
                }
            );

            fileList.registerTabView(new OCA.IDA.IDATabView('IDATabView', {order: -30}));
        }
    };

})();

OC.Plugins.register('OCA.Files.FileList', OCA.IDA.Util);


