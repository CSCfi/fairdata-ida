#!/usr/bin/env bash
#
# https://gist.github.com/domenic/ec8b0fc8ab45f39403dd
#

# Exit with nonzero exit code if anything fails
set -e

# Move the code coverage report to a local folder
mv ../../tests/_output/coverage/* reports/code\ coverage

# Create a *new* Git repo
git init

# Inside this git repo we'll pretend to be a new user
git config user.name "Travis CI"
git config user.email "travis-gallery-reporter@nextcloud.com"

# The first and only commit to this new Git repo contains all the
# files present with the commit message "Deploy to GitHub Pages".
git add .

# Initialising wiki submodule
git submodule add https://github.com/nextcloud/gallery.wiki.git wiki

git commit -m "Nextcloud Gallery documentation"

# Force push from the current repo's master branch to the remote
# repo's gh-pages branch. (All previous history on the gh-pages branch
# will be lost, since we are overwriting it.) We redirect any output to
# /dev/null to hide any sensitive credential data that might otherwise be exposed.
git push --force --quiet "https://${GH_TOKEN}@${GH_REF}" master:gh-pages > /dev/null 2>&1
