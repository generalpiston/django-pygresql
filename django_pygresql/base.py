"""
PostgreSQL database backend for Django.
"""
import sys

from dateutil.parser import parse
from django.db import utils
from django.db.backends import *
from django.db.backends.signals import connection_created
from operations import DatabaseOperations
from client import DatabaseClient
from creation import DatabaseCreation
from version import get_version
from introspection import DatabaseIntrospection
from django.utils.log import getLogger
# from django.utils.safestring import SafeUnicode, SafeString
from django.utils.timezone import utc

try:
    import pgdb as Database
except ImportError, e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Error loading pgdb module: %s" % e)

DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError

logger = getLogger('django.db.backends')


def utc_tzinfo_factory(offset):
    if offset != 0:
        raise AssertionError("database connection isn't set to UTC")
    return utc


class PyGreSQLCursor(Database.pgdbCursor):
    def row_factory(self, row):
        if self.description:
            index = 0
            for description in self.description:
                if description[1] in Database.TIMESTAMP\
                        or description[1] in Database.DATE\
                        or description[1] in Database.TIME:
                    row[index] = parse(row[index])
                index += 1
            return row
        else:
            return row


class CursorWrapper(object):
    """
    A thin wrapper around PyGreSQL's normal cursor class so that we can catch
    particular exception instances and reraise them with the right types.
    """

    def __init__(self, cursor):
        self.cursor = cursor
        self.query = None

    def execute(self, query, args=None):
        try:
            self.query = query
            return self.cursor.execute(query, args)
        except Database.IntegrityError, e:
            raise utils.IntegrityError, utils.IntegrityError(*tuple(e)), sys.exc_info()[2]
        except Database.DatabaseError, e:
            raise utils.DatabaseError, utils.DatabaseError(*tuple(e)), sys.exc_info()[2]

    def executemany(self, query, args):
        try:
            self.query = query
            return self.cursor.executemany(query, args)
        except Database.IntegrityError, e:
            raise utils.IntegrityError, utils.IntegrityError(*tuple(e)), sys.exc_info()[2]
        except Database.DatabaseError, e:
            raise utils.DatabaseError, utils.DatabaseError(*tuple(e)), sys.exc_info()[2]

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            return getattr(self.cursor, attr)

    def __iter__(self):
        return iter(self.cursor)

class DatabaseFeatures(BaseDatabaseFeatures):
    needs_datetime_string_cast = False
    can_return_id_from_insert = True
    requires_rollback_on_dirty_transaction = True
    has_real_datatype = True
    can_defer_constraint_checks = True
    has_select_for_update = True
    has_select_for_update_nowait = True
    has_bulk_insert = True
    supports_tablespaces = True
    can_distinct_on_fields = True

class DatabaseWrapper(BaseDatabaseWrapper):
    vendor = 'postgresql'
    operators = {
        'exact': '= %s',
        'iexact': '= UPPER(%s)',
        'contains': 'LIKE %s',
        'icontains': 'LIKE UPPER(%s)',
        'regex': '~ %s',
        'iregex': '~* %s',
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'startswith': 'LIKE %s',
        'endswith': 'LIKE %s',
        'istartswith': 'LIKE UPPER(%s)',
        'iendswith': 'LIKE UPPER(%s)',
    }

    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)

        self.features = DatabaseFeatures(self)
        self.features.uses_autocommit = self.settings_dict["OPTIONS"].get('autocommit', False)
        self._set_isolation_level("READ COMMITTED")
        self.ops = DatabaseOperations(self)
        self.client = DatabaseClient(self)
        self.creation = DatabaseCreation(self)
        self.introspection = DatabaseIntrospection(self)
        self.validation = BaseDatabaseValidation(self)
        self._pg_version = None

    def check_constraints(self, table_names=None):
        """
        To check constraints, we set constraints to immediate. Then, when, we're done we must ensure they
        are returned to deferred.
        """
        self.cursor().execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.cursor().execute('SET CONSTRAINTS ALL DEFERRED')

    def close(self):
        self.validate_thread_sharing()
        if self.connection is None:
            return

        try:
            self.connection.close()
            self.connection = None
        except Database.Error:
            # In some cases (database restart, network connection lost etc...)
            # the connection to the database is lost without giving Django a
            # notification. If we don't set self.connection to None, the error
            # will occur a every request.
            self.connection = None
            logger.warning('pygresql error while closing the connection.',
                exc_info=sys.exc_info()
            )
            raise

    def _get_pg_version(self):
        if self._pg_version is None:
            self._pg_version = get_version(self.connection)
        return self._pg_version
    pg_version = property(_get_pg_version)

    def _cursor(self):
        settings_dict = self.settings_dict
        if self.connection is None:
            if settings_dict['NAME'] == '':
                from django.core.exceptions import ImproperlyConfigured
                raise ImproperlyConfigured("You need to specify NAME in your Django settings file.")

            options = settings_dict['OPTIONS']
            if 'autocommit' in options:
                del options['autocommit']
            if options:
                dsn = '::::%s:' % str(options)
            else:
                dsn = None

            conn_params = {
                'database': settings_dict['NAME'],
            }
            if settings_dict['USER']:
                conn_params['user'] = settings_dict['USER']
            if settings_dict['PASSWORD']:
                conn_params['password'] = settings_dict['PASSWORD']
            if settings_dict['HOST']:
                conn_params['host'] = settings_dict['HOST']
                if settings_dict['PORT'] and int(settings_dict['PORT']) > 0:
                    conn_params['host'] += ":%d" % int(settings_dict['PORT'])

            self.connection = Database.connect(dsn, **conn_params)
            # self.connection.set_client_encoding('UTF8')
            # tz = 'UTC' if settings.USE_TZ else settings_dict.get('TIME_ZONE')
            # if tz:
            #     try:
            #         get_parameter_status = self.connection.get_parameter_status
            #     except AttributeError:
            #         # psycopg2 < 2.0.12 doesn't have get_parameter_status
            #         conn_tz = None
            #     else:
            #         conn_tz = get_parameter_status('TimeZone')

            #     if conn_tz != tz:
            #         # Set the time zone in autocommit mode (see #17062)
            #         # self.connection.set_isolation_level(
            #         #         psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            #         self.connection.cursor().execute(
            #                 self.ops.isolation_level_sql(), [tz])
            #         self.connection.cursor().execute(
            #                 self.ops.set_time_zone_sql(), [tz])
            self._get_pg_version()
            connection_created.send(sender=self.__class__, connection=self)
        cursor = PyGreSQLCursor(self.connection)
        cursor.tzinfo_factory = utc_tzinfo_factory if settings.USE_TZ else None
        return CursorWrapper(cursor)

    def _enter_transaction_management(self, managed):
        """
        Switch the isolation level when needing transaction support, so that
        the same transaction is visible across all the queries.
        """
        # if self.features.uses_autocommit and managed and not self.isolation_level:
        #     self._set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)
        pass

    def _leave_transaction_management(self, managed):
        """
        If the normal operating mode is "autocommit", switch back to that when
        leaving transaction management.
        """
        # if self.features.uses_autocommit and not managed and self.isolation_level:
        #     self._set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        pass

    def _set_isolation_level(self, level):
        """
        Do all the related feature configurations for changing isolation
        levels. This doesn't touch the uses_autocommit feature, since that
        controls the movement *between* isolation levels.
        """
        # assert level in range(5)
        # try:
        #     if self.connection is not None:
        #         self.connection.set_isolation_level(level)
        # finally:
        #     self.isolation_level = level
        #     self.features.uses_savepoints = bool(level)
        pass

    def _commit(self):
        if self.connection is not None:
            try:
                return self.connection.commit()
            except Database.IntegrityError, e:
                raise utils.IntegrityError, utils.IntegrityError(*tuple(e)), sys.exc_info()[2]
