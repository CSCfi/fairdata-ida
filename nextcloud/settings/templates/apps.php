<?php
style('settings', 'settings');
vendor_script(
	'core',
	[
		'marked/marked.min',
	]
);
script(
	'settings',
	[
		'settings',
		'apps',
	]
);
/** @var array $_ */
?>
<script id="categories-template" type="text/x-handlebars-template">
{{#each this}}
	<li id="app-category-{{ident}}" data-category-id="{{ident}}" tabindex="0">
		<a href="#">{{displayName}}</a>
	</li>
{{/each}}

<?php if($_['appstoreEnabled']): ?>
	<li>
		<a class="app-external" target="_blank" rel="noreferrer" href="https://docs.nextcloud.org/server/12/developer_manual/"><?php p($l->t('Developer documentation'));?> ↗</a>
	</li>
<?php endif; ?>
</script>

<script id="app-template-installed" type="text/x-handlebars">
{{#if newCategory}}
<div class="apps-header">
	<div class="app-image"></div>
	<h2>{{categoryName}} <input class="enable" type="submit" data-bundleid="{{bundleId}}" data-active="true" value="<?php p($l->t('Enable all'));?>"/></h2>
	<div class="app-version"></div>
	<div class="app-level"></div>
	<div class="app-groups"></div>
	<div class="actions">&nbsp;</div>
</div>
{{/if}}
<div class="section" id="app-{{id}}">
	<div class="app-image app-image-icon"></div>
	<div class="app-name">
		{{#if detailpage}}
			<a href="{{detailpage}}" target="_blank" rel="noreferrer">{{name}}</a>
		{{else}}
			{{name}}
		{{/if}}
	</div>
	<div class="app-version">{{version}}</div>
	<div class="app-level">
		{{{level}}}{{#unless internal}}<a href="https://apps.nextcloud.com/apps/{{id}}"><?php p($l->t('View in store'));?> ↗</a>{{/unless}}
	</div>

	<div class="app-groups">
		{{#if active}}
		<div class="groups-enable">
			<input type="checkbox" class="groups-enable__checkbox checkbox" id="groups_enable-{{id}}"/>
			<label for="groups_enable-{{id}}"><?php p($l->t('Limit to groups')); ?></label>
			<input type="hidden" class="group_select" title="<?php p($l->t('All')); ?>">
		</div>
		{{/if}}
	</div>

	<div class="actions">
		<div class="app-dependencies update hidden">
			<p><?php p($l->t('This app has an update available.')); ?></p>
		</div>
		<div class="warning hidden"></div>
		<input class="update hidden" type="submit" value="<?php p($l->t('Update to %s', array('{{update}}'))); ?>" data-appid="{{id}}" />
		{{#if canUnInstall}}
		<input class="uninstall" type="submit" value="<?php p($l->t('Remove')); ?>" data-appid="{{id}}" />
		{{/if}}
		{{#if active}}
		<input class="enable" type="submit" data-appid="{{id}}" data-active="true" value="<?php p($l->t("Disable"));?>"/>
		{{else}}
		<input class="enable{{#if needsDownload}} needs-download{{/if}}" type="submit" data-appid="{{id}}" data-active="false" {{#unless canInstall}}disabled="disabled"{{/unless}} value="<?php p($l->t("Enable"));?>"/>
		{{/if}}
	</div>
</div>
</script>

<script id="app-template" type="text/x-handlebars">
	<div class="section" id="app-{{id}}">
	{{#if preview}}
	<div class="app-image{{#if previewAsIcon}} app-image-icon{{/if}} icon-loading">
	</div>
	{{/if}}
	<h2 class="app-name">
		{{#if detailpage}}
			<a href="{{detailpage}}" target="_blank" rel="noreferrer">{{name}}</a>
		{{else}}
			{{name}}
		{{/if}}
	</h2>
	<div class="app-level">
		{{{level}}}
	</div>
	{{#if ratingNumThresholdReached }}
	<div class="app-score">{{{score}}}</div>
	{{/if}}
	<div class="app-detailpage"></div>

	<div class="app-description-container hidden">
		<div class="app-version">{{version}}</div>
		{{#if profilepage}}<a href="{{profilepage}}" target="_blank" rel="noreferrer">{{/if}}
		<div class="app-author"><?php p($l->t('by %s', ['{{author}}']));?>
			{{#if licence}}
			(<?php p($l->t('%s-licensed', ['{{licence}}'])); ?>)
			{{/if}}
		</div>
		{{#if profilepage}}</a>{{/if}}
		<div class="app-description">{{{description}}}</div>
		<!--<div class="app-changed">{{changed}}</div>-->
		{{#if documentation}}
		<p class="documentation">
			<?php p($l->t("Documentation:"));?>
			{{#if documentation.user}}
			<span class="userDocumentation">
			<a id="userDocumentation" class="appslink" href="{{documentation.user}}" target="_blank" rel="noreferrer"><?php p($l->t('User documentation'));?> ↗</a>
			</span>
			{{/if}}

			{{#if documentation.admin}}
			<span class="adminDocumentation">
			<a id="adminDocumentation" class="appslink" href="{{documentation.admin}}" target="_blank" rel="noreferrer"><?php p($l->t('Admin documentation'));?> ↗</a>
			</span>
			{{/if}}

			{{#if documentation.developer}}
			<span class="developerDocumentation">
			<a id="developerDocumentation" class="appslink" href="{{documentation.developer}}" target="_blank" rel="noreferrer"><?php p($l->t('Developer documentation'));?> ↗</a>
			</span>
			{{/if}}
		</p>
		{{/if}}

		{{#if website}}
		<a id="userDocumentation" class="appslink" href="{{website}}" target="_blank" rel="noreferrer"><?php p($l->t('Visit website'));?> ↗</a>
		{{/if}}

		{{#if bugs}}
		<a id="adminDocumentation" class="appslink" href="{{bugs}}" target="_blank" rel="noreferrer"><?php p($l->t('Report a bug'));?> ↗</a>
		{{/if}}
	</div><!-- end app-description-container -->
	<div class="app-description-toggle-show" role="link"><?php p($l->t("Show description …"));?></div>
	<div class="app-description-toggle-hide hidden" role="link"><?php p($l->t("Hide description …"));?></div>

	<div class="app-dependencies update hidden">
		<p><?php p($l->t('This app has an update available.')); ?></p>
	</div>

	{{#if missingMinOwnCloudVersion}}
		<div class="app-dependencies">
			<p><?php p($l->t('This app has no minimum Nextcloud version assigned. This will be an error in the future.')); ?></p>
		</div>
	{{else}}
		{{#if missingMaxOwnCloudVersion}}
			<div class="app-dependencies">
				<p><?php p($l->t('This app has no maximum Nextcloud version assigned. This will be an error in the future.')); ?></p>
			</div>
		{{/if}}
	{{/if}}

	{{#unless canInstall}}
	<div class="app-dependencies">
	<p><?php p($l->t('This app cannot be installed because the following dependencies are not fulfilled:')); ?></p>
	<ul class="missing-dependencies">
	{{#each missingDependencies}}
	<li>{{this}}</li>
	{{/each}}
	</ul>
	</div>
	{{/unless}}

	<input class="update hidden" type="submit" value="<?php p($l->t('Update to %s', array('{{update}}'))); ?>" data-appid="{{id}}" />
	{{#if active}}
	<input class="enable" type="submit" data-appid="{{id}}" data-active="true" value="<?php p($l->t("Disable"));?>"/>
	<div class="groups-enable">
		<input type="checkbox" class="groups-enable__checkbox checkbox" id="groups_enable-{{id}}"/>
		<label for="groups_enable-{{id}}"><?php p($l->t('Enable only for specific groups')); ?></label>
	</div>
	<input type="hidden" class="group_select" title="<?php p($l->t('All')); ?>" style="width: 200px">
	{{else}}
	<input class="enable{{#if needsDownload}} needs-download{{/if}}" type="submit" data-appid="{{id}}" data-active="false" {{#unless canInstall}}disabled="disabled"{{/unless}} value="<?php p($l->t("Enable"));?>"/>
	{{/if}}
	{{#if canUnInstall}}
	<input class="uninstall" type="submit" value="<?php p($l->t('Remove')); ?>" data-appid="{{id}}" />
	{{/if}}

	<div class="warning hidden"></div>

	</div>
</script>

<div id="app-navigation" class="icon-loading" data-category="<?php p($_['category']);?>">
	<ul id="apps-categories">

	</ul>
</div>
<div id="app-content" class="icon-loading">
	<svg class="app-filter">
		<defs><filter id="invertIcon"><feColorMatrix in="SourceGraphic" type="matrix" values="-1 0 0 0 1 0 -1 0 0 1 0 0 -1 0 1 0 0 0 1 0"></feColorMatrix></filter></defs>
	</svg>
	<div id="apps-list"></div>
	<div id="apps-list-empty" class="hidden emptycontent emptycontent-search">
		<div class="icon-search"></div>
		<h2><?php p($l->t('No apps found for your version')) ?></h2>
	</div>
</div>
