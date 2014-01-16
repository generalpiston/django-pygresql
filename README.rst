.. _django-pygresql: https://github.com/abec/django-pygresql

Django PyGreSQL
===============

Install
-------
1. Download the latest release of django-pygresql_.

2. Decompress the downloaded file.

::

  $ tar -xvzf django-pygresql-<release>.tar.gz

OR

::

  $ unzip django-pygresql-<release>.zip

3. Install django-pygresql. If you don't have the permissions, you will need to 'sudo' the command.

::
  
  $ cd django-pygresql-<release>
  $ python setup.py install
  $ cd -

4. In your django settings file add the following database configuration.

::

  DATABASES = {
    "default": {
      "ENGINE" : "django_pygresql,
      ...
    }
  }


Integration with South
----------------------

Add a database adapter to the django settings file.

::

  SOUTH_DATABASE_ADAPTERS = {
    'default': 'south.db.postgresql_psycopg2'
  }
