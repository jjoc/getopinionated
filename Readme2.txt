GetOpinionated
An online vote system supporting liquid democracy and document collaboration.


Dependencies:

You need a number of python modules installed on your system to be able to run getopinionated; these are:

(X) Django 1.4
(X) python-django-south
(X) python-django-auth-openid
(X) python-oauth2
[optional] Scipy 0.12.0 or higher
(X) sudo apt-get install python-numpy python-scipy python-matplotlib ipython ipython-notebook python-pandas python-sympy python-nose
[optional] NeuroDebian 
(X) wget -O- http://neuro.debian.net/lists/precise.de-m.libre | sudo tee /etc/apt/sources.list.d/neurodebian.sources.list
(X) sudo apt-key adv --recv-keys --keyserver pgp.mit.edu 2649A5A9
(X) sudo apt-get update
[optional] python-imaging
(X) sudo apt-get build-dep python-imaging
(X) sudo apt-get install libjpeg62 libjpeg62-dev


Installing python 2.7 (& Dependencies)
Furthermore, getopinionated has been developed on python 2.7.


Installing dependencies in OS Ubuntu 12.04 (32b)
Ubuntu 12.04 comes with python v 2.7.3 by default.

Assuming... you have python 2.7, run the following for Django:

(X) sudo apt-get install python-pip
(X) sudo pip install django==1.4
(X) sudo pip install --upgrade scipy (from 0.9.0 to 0.13.x)

And Install the other dependencies as follows:

(X) sudo pip install south django-authopenid oauth2
(X) TO-DO: add howto install scipy (although this seems to be optional)

[optional] GIT Clone;)
(X) sudo apt-get install git-core
(X) git clone https://github.com/jjoc/getopinionated

Getting started

To run the development server, run

(ERROR) python manage.py localserver
     ("settings.py", line 386, in <module> TEMPLATE_DEBUG = DEBUG NameError: name 'DEBUG' is not defined)



This will create the database, populate it with the data in testdata.json and execute manage.py runserver.

Notes for setting up a production server

Make sure to add a local_settings.py file. For more info on this, take a look at a template file.
Install all optional dependencies as well
Set up cronjob to call the following at least every 5 minutes:

python manage.py updatevoting
