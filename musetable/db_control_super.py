"""
Control various operations on a database cluster as a superuser
"""

import psycopg2
from psycopg2 import sql
from db_decorator import PostgresDB

from const import PROJECT_ID, SECRET_ID, VERSION_ID

db = PostgresDB(PROJECT_ID, SECRET_ID, VERSION_ID)

class DatabaseControlSuper:
    """
    The DatabaseControlSuper class performs various operations for controling a
    PostgreSQL database cluster, such as creating and deleting databases and users.
    """

    def __init__(self):
        pass

    @db.with_cursor_super
    def list_databases(self, cursor):
        query = "SELECT datname FROM pg_database;"
        cursor.execute(query)
        databases = cursor.fetchall()
        print("Database list:")
        for database in databases:
            print(database[0])

    @db.with_cursor_super
    def create_database(self, cursor, dbname):
        query = sql.SQL("CREATE DATABASE {database};").format(
            database=sql.Identifier(dbname)
        )
        try:
            cursor.execute(query)
            print("Database created successfully!")
        except (Exception, psycopg2.Error) as error:
            print("Error while creating PostgreSQL database:", error)


    @db.with_cursor_super
    def delete_database(self, cursor, dbname):
        query = sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname))
        try:
            cursor.execute(query)
            print(f"Database {dbname} deleted successfully!")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while deleting database {dbname}:", error)


    @db.with_cursor_super
    def list_all_users(self, cursor):
        query = "SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%';"
        cursor.execute(query)
        users = cursor.fetchall()
        print("All users for database cluster:")
        for user in users:
            print(f"- {user[0]}")


    @db.with_cursor_super
    def create_user(self, cursor, username, password):
        query = sql.SQL("CREATE USER {user} WITH ENCRYPTED PASSWORD {pw};").format(
            user=sql.Identifier(username),
            pw=sql.Literal(password)
        )
        try:
            cursor.execute(query)
            print(f"User {username} created successfully!")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while creating user {username}:", error)


    @db.with_cursor_super
    def grant_user_permissions(self, cursor, username, dbname):
        query = sql.SQL("GRANT ALL ON DATABASE {database} TO {user};").format(
            database=sql.Identifier(dbname),
            user=sql.Identifier(username)
        )
        try:
            cursor.execute(query)
            print(f"User {username} granted permissions for database {dbname}!")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while granting permissions for user {username}:", error)


    @db.with_cursor_super
    def delete_user(self, cursor, username, dbname):
        revoke_query = sql.SQL("REVOKE ALL PRIVILEGES ON database {} FROM {}").format(
            sql.Identifier(dbname),
            sql.Identifier(username)
        )
        try:
            cursor.execute(revoke_query)
            print(f"Privileges successfully revoked for user {username} from database {dbname}")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while revoking privileges for user {username} from database {dbname}:", error)

        drop_query = sql.SQL("DROP USER {}").format(sql.Identifier(username))
        try:
            cursor.execute(drop_query)
            print(f"User {username} deleted successfully. So long!")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while deleting user {username}:", error)

if __name__ == "__main__":

    db_control_super = DatabaseControlSuper()

     ### creating and listing

    # databases
    dbname="testdb"
    # db_control_super.create_database(dbname=dbname)
    db_control_super.list_databases()  # ok

    # users
    username='test_user'
    password='test_password'
    # db_control_super.create_user(username=username, password=password)  # ok
    # db_control_super.grant_user_permissions(username='test_user', dbname=dbname)  # ok
    # db_control_super.list_all_users()


    ### deleting

    # users
    # db_control_super.create_user(username='goober', password='goober4u')
    # db_control_super.list_users()
    # db_control_super.delete_user(username=username, dbname=dbname)  # ok
    # db_control_super.list_all_users()

    # database
    # db_control_super.delete_database(dbname=dbname)  # ok
    # db_control_super.list_databases()
