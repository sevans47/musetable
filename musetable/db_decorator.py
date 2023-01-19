"""
Class for connecting to a database or database cluster
"""

import psycopg2
from google.cloud import secretmanager
from contextlib import contextmanager
from functools import wraps
import json

class PostgresDB:
    "PostgresDB class connects to a database by means of a decorator"

    def __init__(self, project_id: str, secret_id: str, version_id: int, db_port=5432):
        self.db_port = db_port
        self.secret_details = self.get_secrets(project_id, secret_id, version_id)

    def get_secrets(self, project_id: str, secret_id: str, version_id: int) -> dict:
        """
        Using GCP's Secret Manager, get secret details for connecting to the Spotify API

        Parameters:
        -----------
        project_id  : GCP project id with the Secret Manager API containing Spotify API secrets
        secret_id   : id for secrets
        version_id  : version number for secrets

        Returns:
        --------
        secret_details  : dictionary containing secret details
        """
        # create secret manager client object
        client = secretmanager.SecretManagerServiceClient()

        # get secret details
        secret_name = f'projects/{project_id}/secrets/{secret_id}/versions/{version_id}'

        # access secret
        response = client.access_secret_version(name=secret_name)

        # load secret
        secret_details = json.loads(response.payload.data.decode('utf-8'))

        return secret_details

    @contextmanager
    def connection(self):
        "Create connection to database in a context manager"
        connection = psycopg2.connect(
            port=self.db_port,
            **self.secret_details
            ### below is for testing ###
            # host=self.secret_details['host'],
            # port=self.db_port,
            # database='testdb',
            # user='test_user',
            # password='test_password',
        )
        connection.autocommit = True
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def cursor(self):
        "Create cursor object in a context manager"
        with self.connection() as connection:
            cursor = connection.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

    def with_cursor(self, func):
        "Decorator function for connecting to db"
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.cursor() as cursor:
                kwargs["cursor"] = cursor
                return func(*args, **kwargs)
        return wrapper

    @contextmanager
    def connection_super(self):
        "Create connection as database superuser"
        connection = psycopg2.connect(
            host=self.secret_details['host'],
            port=self.db_port,
            user='postgres',
            password=self.secret_details['password']
        )
        connection.autocommit = True
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def cursor_super(self):
        "Create cursor object for superuser connection"
        with self.connection_super() as connection:
            cursor = connection.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

    def with_cursor_super(self, func):
        "Decorator function for connecting to db cluster as superuser"
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.cursor_super() as cursor:
                kwargs["cursor"] = cursor
                return func(*args, **kwargs)
        return wrapper
