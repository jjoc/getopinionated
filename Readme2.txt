GetOpinionated
An online vote system supporting liquid democracy and document collaboration.

GetOpinionated (Liquid Democracy System)


Installing dependencies in OS Ubuntu 12.04 (32b)
Ubuntu 12.04 comes with python v 2.7.3 by default.
Furthermore, getopinionated has been developed on python 2.7.


You need a number of python modules installed on your system to be able to run getopinionated;


Assuming... you have python 2.7, run the following for Django:

(X) sudo apt-get update
(X) sudo apt-get install python-pip
(X) sudo pip install django==1.4
(X) sudo apt-get update
(X) sudo apt-get install python-django-south
(X) sudo apt-get install python-django-auth-openid
(X) sudo apt-get install python-oauth2
(X) python --version


[optional] Scipy 0.12.0 or higher
(X) sudo apt-get install python-numpy python-scipy python-matplotlib ipython ipython-notebook python-pandas python-sympy python-nose
(X) python -c "import numpy; print numpy.version.version"
(X) python -c "import scipy; print scipy.version.version"
(X) sudo pip install --upgrade scipy (from 0.9.0 to 0.13.x)

[optional] NeuroDebian 
(X) wget -O- http://neuro.debian.net/lists/precise.de-m.libre | sudo tee /etc/apt/sources.list.d/neurodebian.sources.list
(X) sudo apt-key adv --recv-keys --keyserver pgp.mit.edu 2649A5A9
(X) sudo apt-get update
(X) sudo apt-get upgrade
(X) sudo apt-get install python-pandas
(X) sudo apt-get upgrade


[optional] Python imaging 
(?) sudo apt-get install python-imaging
(X) sudo apt-get build-dep python-imaging
(X) sudo apt-get install libjpeg62 libjpeg62-dev
(X) sudo apt-get update
(E) You must put some 'source' URIs in your sources.list


[optional] Aptitude 

(X) sudo apt-get install aptitude
(X) sudo aptitude install python-pythonmagick python-markdown python-textile python-docutils
(X) sudo aptitude show python-imaging


And Install the other dependencies as follows:

(X) sudo pip install south django-authopenid oauth2
(X) TO-DO: add howto install scipy (although this seems to be optional)

[optional] GIT Clone;)
(X) sudo apt-get install git-core
(X) git clone https://github.com/jjoc/getopinionated


Getting started


[IMPORTANT] Make sure to add a local_settings.py file.
(X) cd getopinionated/getopinionated
(X) sudo cp -a local_settings.py.template local_settings.py
(X) sudo vi local_settings.py
( ) #ENABLE_SOUTH = True # use south on online databases (just uncomment)


To run the development server, run

(X) python manage.py
(X) python manage.py localserver
(X) python manage.py runserver 8000


This will create the database, populate it with the data in testdata.json and execute manage.py runserver.


Notes & tricks;) for setting up a production server

(X) python manage.py runserver 1.2.3.4:8000 (where 1.2.3.4 is your IP Server)
( ) git clone https://github.com/jjoc/getopinionated/tree/production (Not Tested)




(?) Install all optional dependencies as well.
(?) For more info on this, take a look at a template file.
(?) Set up cronjob to call the following at least every 5 minutes:
(X) python manage.py updatevoting


TO-DO: add howto access via web, etc. (although this seems to be insignificant)
-
-
-
-
-





