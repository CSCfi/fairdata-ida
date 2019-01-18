/*
 * Copyright (c) 2016 Lukas Reschke <lukas@statuscode.ch>
 *
 * This file is licensed under the Affero General Public License version 3
 * or later.
 *
 * See the COPYING-README file.
 *
 */

(function ($) {
	var TEMPLATE =
		'<li data-toggle="tooltip" title="{{name}}" data-name="{{name}}">' +
		'{{#if isUploading}}' +
		'<span class="icon-loading-small"></span> {{name}}' +
		'{{else}}' +
		'<img src="{{iconSrc}}"/> {{name}}' +
		'{{/if}}' +
		'</li>';
	var Drop = {
		/** @type {Function} **/
		_template: undefined,
	
		addFileToUpload: function(e, data) {
			var errors = [];
			var output = this.template();
			
			var filesClient = new OC.Files.Client({
				host: OC.getHost(),
				port: OC.getPort(),
				userName: $('#sharingToken').val(),
				// note: password not be required, the endpoint
				// will recognize previous validation from the session
				root: OC.getRootPath() + '/public.php/webdav',
				useHTTPS: OC.getProtocol() === 'https'
			});
			
			var name = data.files[0].name;
			try {
				// FIXME: not so elegant... need to refactor that method to return a value
				Files.isFileNameValid(name);
			}
			catch (errorMessage) {
				OC.Notification.show(errorMessage, {type: 'error'});
				return false;
			}
			var base = OC.getProtocol() + '://' + OC.getHost();
			data.url = base + OC.getRootPath() + '/public.php/webdav/' + encodeURI(name);
	
			data.multipart = false;
	
			if (!data.headers) {
				data.headers = {};
			}
	
			var userName = filesClient.getUserName();
			var password = filesClient.getPassword();
			if (userName) {
				// copy username/password from DAV client
				data.headers['Authorization'] =
					'Basic ' + btoa(userName + ':' + (password || ''));
			}
	
			$('#drop-upload-done-indicator').addClass('hidden');
			$('#drop-upload-progress-indicator').removeClass('hidden');

			$('#public-upload ul').append(output({isUploading: true, name: data.files[0].name}));
			$('[data-toggle="tooltip"]').tooltip();
			data.submit();
	
			return true;
		},
		
		updateFileItem: function (fileName, fileItem) {
			$('#public-upload ul li[data-name="' + fileName + '"]').replaceWith(fileItem);
			$('[data-toggle="tooltip"]').tooltip();
		},
		
		initialize: function () {
			$(document).bind('drop dragover', function (e) {
				// Prevent the default browser drop action:
				e.preventDefault();
			});
			var output = this.template();
			$('#public-upload').fileupload({
				type: 'PUT',
				dropZone: $('#public-upload'),
				sequentialUploads: true,
				add: function(e, data) {
					Drop.addFileToUpload(e, data);
					//we return true to keep trying to upload next file even
					//if addFileToUpload did not like the privious one
					return true;
				},
				done: function(e, data) {
					// Created
					var mimeTypeUrl = OC.MimeType.getIconUrl(data.files[0].type);
					var fileItem = output({isUploading: false, iconSrc: mimeTypeUrl, name: data.files[0].name});
					Drop.updateFileItem(data.files[0].name, fileItem);
				},
				fail: function(e, data) {
					OC.Notification.showTemporary(OC.L10N.translate(
							'files_sharing',
							'Could not upload "{filename}"',
							{filename: data.files[0].name}
							));
					var errorIconSrc = OC.imagePath('core', 'actions/error.svg');
					var fileItem = output({isUploading: false, iconSrc: errorIconSrc, name: data.files[0].name});
					Drop.updateFileItem(data.files[0].name, fileItem);
				},
				progressall: function (e, data) {
					var progress = parseInt(data.loaded / data.total * 100, 10);
					if(progress === 100) {
						$('#drop-upload-done-indicator').removeClass('hidden');
						$('#drop-upload-progress-indicator').addClass('hidden');
					} else {
						$('#drop-upload-done-indicator').addClass('hidden');
						$('#drop-upload-progress-indicator').removeClass('hidden');
					}
				}
			});
			$('#public-upload .button.icon-upload').click(function(e) {
				e.preventDefault();
				$('#public-upload #emptycontent input').focus().trigger('click');
			});
		},

		/**
		 * @returns {Function} from Handlebars
		 * @private
		 */
		template: function () {
			if (!this._template) {
				this._template = Handlebars.compile(TEMPLATE);
			}
			return this._template;
		}
	};

	OCA.FilesSharingDrop = Drop;

	$(document).ready(function() {
		if($('#upload-only-interface').val() === "1") {
			$('.avatardiv').avatar($('#sharingUserId').val(), 128, true);
		}

		OCA.FilesSharingDrop.initialize();
	});
})(jQuery);
