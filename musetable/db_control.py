"""
Control various operations on a database

TODO:
    - __init__
"""

import psycopg2
from psycopg2 import sql
from musetable.db_decorator import PostgresDB
import re

from musetable.const import PROJECT_ID, SECRET_ID, VERSION_ID

db = PostgresDB(PROJECT_ID, SECRET_ID, VERSION_ID)

class DatabaseControl:
    """
    The DatabaseControl class performs various operations for controling a
    PostgreSQL database, such as creating and deleting tables, and inserting values
    """

    def __init__(self):
        pass

    @db.with_cursor
    def list_users(self, cursor):
        query = sql.SQL("SELECT rolname FROM pg_roles WHERE rolcanlogin = true;")
        try:
            cursor.execute(query)
            users = cursor.fetchall()
            print(f"Users able to login to database:")
            for user in users:
                print(f"- {user[0]}")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while listing users:", error)


    @db.with_cursor
    def list_tables(self, cursor):
        query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"

        try:
            cursor.execute(query)
            results = cursor.fetchall()
            print(f"All tables in database:")
            print(results)
        except (Exception, psycopg2.Error) as error:
            print(f"Error while listing tables:", error)


    @db.with_cursor
    def create_tables(self, cursor, sql_filepath):
        with open(sql_filepath, 'r') as file:
            sql_file = file.read()
        try:
            cursor.execute(sql_file)
            print(f"Tables created using file {sql_filepath}!")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while creating tables using file {sql_filepath}:", error)


    @db.with_cursor
    def delete_all_tables(self, cursor):
        table_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        cursor.execute(table_query)
        tables = cursor.fetchall()
        count = 0
        for table in tables:
            try:
                table_str = table[0]
                drop_query = sql.SQL("DROP TABLE {table_name} CASCADE").format(
                    table_name = sql.Identifier(table_str)
                )
                cursor.execute(drop_query)
                count += 1
                print(f"Table {table_str} deleted!")
            except (Exception, psycopg2.Error) as error:
                print(f"Error while deleting tables:", error)

        if count == len(tables):
            print("All tables deleted, boss!")

    @db.with_cursor
    def list_columns(self, cursor, table_name):
        query = sql.SQL("select * from {table}").format(
                table=sql.Identifier(table_name)
            )
        try:
            cursor.execute(query)
            column_names = [desc[0] for desc in cursor.description]
            print(f"Listing columns in table '{table_name}':")
            for column in column_names:
                print(f"- {column}")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while listing columns in table '{table_name}':", error)


    @db.with_cursor
    def list_table_values(self, cursor, table_name):
        query = sql.SQL("SELECT * FROM {table};").format(
            table=sql.Identifier(table_name)
        )
        try:
            cursor.execute(query)
            results = cursor.fetchall()
            print(f"Listing values from table '{table_name}':")
            for row in results:
                print(row)
        except (Exception, psycopg2.Error) as error:
            print(f"Error while listing values:", error)

    @db.with_cursor
    def delete_all_values_one_table(self, cursor, table_name):
        query = sql.SQL("DELETE FROM {table}").format(
            table=sql.Identifier(table_name)
        )
        try:
            cursor.execute(query)
            print(f"All values successfully deleted from table {table_name}")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while deleting values from table {table_name}:", error)

    @db.with_cursor
    def delete_all_values_all_tables(self, cursor):
        table_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        cursor.execute(table_query)
        table_names = [t[0] for t in cursor.fetchall()]

        for table_name in table_names[::-1]:
            delete_query = sql.SQL("DELETE FROM {table} CASCADE").format(
                table=sql.Identifier(table_name)
            )
            try:
                cursor.execute(delete_query)

            except psycopg2.errors.ForeignKeyViolation as e:

                # get names of child table and constraint
                match = re.search(r'"(\w+)"', e.pgerror)
                if match:
                    child_table = match.group(1)
                match = re.search(r'"(\w+)"', e.pgcode)
                if match:
                    constraint_name = match.group(1)

                # remove the foreign key constraint
                fk_query = sql.SQL("ALTER TABLE {} DROP CONSTRAINT {};").format(
                    sql.Identifier(child_table),
                    sql.Identifier(constraint_name)
                )
                cursor.execute(fk_query)

                # delete
                cursor.execute(delete_query)

        print("all data deleted, boss!")

    @db.with_cursor
    def delete_all_values_by_section_id(self, cursor, section_id):

        # get tables with section_id columns
        table_query = """
        SELECT t.table_name
        FROM information_schema.tables t
        INNER JOIN information_schema.columns c ON c.table_name = t.table_name
        WHERE c.column_name = 'section_id'
            AND t.table_schema = 'public'
        """
        cursor.execute(table_query)
        table_names = [t[0] for t in cursor.fetchall()]

        # delete section_id rows from child tables of 'sections' table
        for table_name in table_names:
            child_delete_query = sql.SQL("DELETE FROM {table} WHERE section_id = {sec_id};").format(
                table=sql.Identifier(table_name),
                sec_id=sql.Literal(section_id)
            )
            try:
                cursor.execute(child_delete_query)
                print(f"All section_id '{section_id}' values deleted from table'{table_name}'")
            except (Exception, psycopg2.Error) as error:
                print(f"Error while deleting section_id '{section_id}' values from table '{table_name}':", error)

        # delete id rows from 'sections' table
        parent_delete_query = sql.SQL("DELETE FROM sections WHERE id = {sec_id};").format(
            sec_id=sql.Literal(section_id),
        )
        try:
            cursor.execute(parent_delete_query)
            print(f"All section_id '{section_id}' values deleted from table 'sections'")
        except (Exception, psycopg2.Error) as error:
            print(f"Error while deleting section_id '{section_id}' values from table 'sections':", error)


if __name__ == "__main__":

    import os
    from const import ROOT_DIR

    db_control = DatabaseControl()



    ### creating and listing

    # tables
    # sql_filepath = os.path.join(ROOT_DIR, 'data', 'create_db_tables_pg.sql')
    # db_control.create_tables(sql_filepath=sql_filepath)  # ok
    # db_control.list_tables()  # ok


    # columns
    # db_control.list_columns(table_name="sections")  # ok

    # values
    # db_control.list_table_values(table_name="phrases")  # ok

    ### deleting

    # values
    # db_control.delete_all_values_one_table(table_name="phrases")  # ok
    # db_control.delete_all_values_by_section_id(section_id='grjd21-verse')  # ok
    db_control.delete_all_values_all_tables()  # ok
    db_control.list_table_values(table_name="tracks")

    # tables
    # db_control.delete_all_tables() #ok
    # db_control.list_tables()
