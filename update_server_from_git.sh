#!/bin/bash
#testing server
cd /home/de317070/webapps/getopinionated/getopinionated/getopinionated
git fetch
newUpdatesAvailable=`git diff HEAD FETCH_HEAD`
if [ "$newUpdatesAvailable" != "" ]
then
	git reset --hard
	git pull
	$HOME/webapps/getopinionated/apache2/bin/restart
fi