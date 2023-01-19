"""
Insert data into database
"""
import psycopg2
from psycopg2 import sql, extras
from db_decorator import PostgresDB
from preprocess import PreprocessXML

from const import PROJECT_ID, SECRET_ID, VERSION_ID

db = PostgresDB(PROJECT_ID, SECRET_ID, VERSION_ID)

class InsertValues:
    """
    InsertValues class inserts the values created by PreprocessXML into the
    musetable database
    """

    def __init__(self, mxl_filepath, playlist_filepath):
        self.preproc = PreprocessXML(mxl_filepath, playlist_filepath)
        self.data_dicts = self.preproc.stream_to_dict()


    @db.with_cursor
    def make_tables_dict(self, cursor) -> tuple:
        """
        Create dictionary of all tables and their columns in a database.  Important
        for ensuring the correct order of column names when inserting data.

        Returns:
        --------
        table_names (list): all table names in the database
        tables_dict (dict): keys are table names, values are lists of column names
        """

        tables_dict = {}

        # retrieve table names from database and store in 'tables' list
        query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        cursor.execute(query)
        table_names = [table[0] for table in cursor.fetchall()]

        # retrieve column names from each table in the database
        for table_name in table_names:
            query = sql.SQL("SELECT * FROM {table};").format(
                table=sql.Identifier(table_name)
            )
            cursor.execute(query)
            column_names = [desc[0] for desc in cursor.description]
            tables_dict[table_name] = column_names

        return (table_names, tables_dict)


    def preprocess_sql_data(self, tables_dict: dict, table_names: list) -> list:
        """
        Prepare data in dictionaries returned from stream_to_dict() so they are the correct
        format for inserting into the database.

        Parameters:
        -----------
        tables_dict     (dict): dictionary of all tables and columns from the database. Used to ensure the correct order
        table_names      (str): list of names of all tables in correct order

        Returns:
        --------
        preprocessed_data   (list): Each element is a list of tuples:
                                    - one list represents one table
                                    - one tuple represents one row
        """
        preprocessed_data = []

        print("preprocessing data ... ")
        for table_name, data_dict in zip(table_names, self.data_dicts):

            # list of tuples for each data_dict
            data_chunk = []

            if table_name in ["tracks", "sections"]:
                data_chunk.append(tuple(data_dict.values()))
                preprocessed_data.append(data_chunk)
                continue

            for i in range(len(data_dict['section_id'])):
                row = []

                # ensure data is in the correct column order by using tables_dict lists
                for col in tables_dict[table_name]:
                    row.append(data_dict[col][i])
                data_chunk.append(tuple(row))

            preprocessed_data.append(data_chunk)

        print("data preprocessed")
        return preprocessed_data


    def insert_data(self, preprocessed_data, table_names):

        # iterate through each table and insert data
        print("inserting data into database ... ")
        with db.connection() as connection:
            with connection.cursor() as cursor:
                for table_name, data in zip(table_names, preprocessed_data):

                    query = sql.SQL("INSERT INTO {table} VALUES ({values});").format(
                        table=sql.Identifier(table_name),
                        values=sql.SQL(', ').join(sql.Placeholder() * len(data[0]))
                    )
                    # print(query.as_string(connection))  # check how query looks as a string


                    # # avoid inserting duplicate track data
                    try:
                        extras.execute_batch(cursor, query, data)
                        print(f"- inserted data into table {table_name}")
                    except psycopg2.errors.UniqueViolation:
                        # rollback the current transaction and continue with loop
                        connection.rollback()
                        continue
                print("data insertion complete")


    @ db.with_cursor
    def validate_data_insert(self, cursor, preprocessed_data, table_names):

        print("validating data insertion ... ")
        # store track_id and section_id as variables
        track_id = preprocessed_data[0][0][0]
        section_id = preprocessed_data[1][0][0]

        # create list of ids to zip with table names for the queries
        id_cols = ['id', 'id', 'section_id', 'section_id', 'section_id']
        id_vals = [track_id, section_id, section_id, section_id, section_id]

        # execute query to fetch all rows for
        db_data = []
        # with psycopg2.connect(host=host, database=dbname, user=user, password=password) as conn:
        #     with conn.cursor() as cursor:
        for table_name, id_col, id_val in zip(table_names, id_cols, id_vals):
            query = sql.SQL("SELECT * FROM {table} WHERE {column} = %s").format(
                table=sql.Identifier(table_name),
                column=sql.Identifier(id_col)
            )
            cursor.execute(query, (id_val,))
            results = cursor.fetchall()
            db_data.append(results)

    #     return db_data

        # compare preprocessed_data to database data
        for i in range(len(table_names)):

            # check that length and values match
            validate_length = len(preprocessed_data[i]) == len(db_data[i])
            validate_values = preprocessed_data[i] == db_data[i]

            if validate_length and validate_values:
                continue
            elif validate_length == False:
                print(f"error inserting data in table {table_names[i]}")
                return 1
            elif validate_values == False:
                print(f"error with data types in table {table_names[i]}")
                return 2

        print("Data successfully added to database!")

    def file_to_sql(self):
        """
        Using an MusicXML file and the csv of the playlist, preprocess and insert all the data into the musetable database

        Parameters:
        ----------
        mxl_filepath       (str): filepath to the local MusicXML file
        playlist_filepath  (str): filepath to a csv of the playlist containing spotify track information
        """

        # create dictionary of table and column names from database
        table_names, tables_dict = self.make_tables_dict()

        # preprocess data for SQL INSERT statement
        preprocessed_data = self.preprocess_sql_data(tables_dict, table_names)

        # insert data into database
        self.insert_data(preprocessed_data, table_names)

        # validate that the data was inserted correctly
        self.validate_data_insert(preprocessed_data=preprocessed_data, table_names=table_names)

if __name__ == "__main__":

    import os
    from const import ROOT_DIR
    from db_control import DatabaseControl

    mxl_filepath = os.path.join(ROOT_DIR, 'data', 'Juban District - Chorus.mxl')
    playlist_filepath = os.path.join(ROOT_DIR, 'data', 'playlist.csv')

    inserter = InsertValues(mxl_filepath, playlist_filepath)
    inserter.file_to_sql()
    # table_names, tables_dict = inserter.make_tables_dict()
    # preprocessed_data = inserter.preprocess_sql_data(tables_dict, table_names)
    # inserter.insert_data(preprocessed_data=preprocessed_data, table_names=table_names)


    db_control = DatabaseControl()
    # db_control.list_tables()
    db_control.list_table_values(table_name="tracks")
    db_control.list_table_values(table_name="phrases")
