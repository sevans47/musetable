"""
Insert data into database
"""
import psycopg2
from psycopg2 import sql, extras
from musetable.db_decorator import PostgresDB
from musetable.preprocess import PreprocessXML

from musetable.const import PROJECT_ID, SECRET_ID, VERSION_ID

db = PostgresDB(PROJECT_ID, SECRET_ID, VERSION_ID)

class InsertValues:
    """
    InsertValues class inserts the values created by PreprocessXML into the
    musetable database
    """

    def __init__(self, mxl_filepath, playlist_filepath):
        self.preproc = PreprocessXML(mxl_filepath, playlist_filepath)
        # self.data_dicts = self.preproc.stream_to_dict()
        self.preprocessed_data = self.preproc.preprocess_data()
        self.table_names, self._ = self.preproc.make_tables_dict()


    def insert_data(self):

        # iterate through each table and insert data
        print("inserting data into database ... ")
        with db.connection() as connection:
            with connection.cursor() as cursor:
                for table_name, data in zip(self.table_names, self.preprocessed_data):

                    query = sql.SQL("INSERT INTO {table} VALUES ({values});").format(
                        table=sql.Identifier(table_name),
                        values=sql.SQL(', ').join(sql.Placeholder() * len(data[0]))
                    )
                    # print(query.as_string(connection))  # check how query looks as a string


                    # avoid inserting duplicate track data
                    try:
                        extras.execute_batch(cursor, query, data)
                        print(f"- inserted data into table {table_name}")
                    except psycopg2.errors.UniqueViolation:
                        # rollback the current transaction and continue with loop
                        connection.rollback()
                        continue
                print("data insertion complete")


    @ db.with_cursor
    def validate_data_insert(self, cursor):

        print("validating data insertion ... ")
        # store track_id and section_id as variables
        track_id = self.preprocessed_data[0][0][0]
        section_id = self.preprocessed_data[1][0][0]

        # create list of ids to zip with table names for the queries
        id_cols = ['id', 'id', 'section_id', 'section_id', 'section_id']
        id_vals = [track_id, section_id, section_id, section_id, section_id]

        # execute query to fetch all rows for
        db_data = []
        # with psycopg2.connect(host=host, database=dbname, user=user, password=password) as conn:
        #     with conn.cursor() as cursor:
        for table_name, id_col, id_val in zip(self.table_names, id_cols, id_vals):
            query = sql.SQL("SELECT * FROM {table} WHERE {column} = %s").format(
                table=sql.Identifier(table_name),
                column=sql.Identifier(id_col)
            )
            cursor.execute(query, (id_val,))
            results = cursor.fetchall()
            db_data.append(results)

        # compare preprocessed_data to database data
        for i in range(len(self.table_names)):

            # check that length and values match
            validate_length = len(self.preprocessed_data[i]) == len(db_data[i])
            validate_values = self.preprocessed_data[i] == db_data[i]

            if validate_length and validate_values:
                continue
            elif validate_length == False:
                print(f"error inserting data in table {self.table_names[i]}")
                return 1
            elif validate_values == False:
                print(f"error with data types in table {self.table_names[i]}")
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

        # insert data into database
        self.insert_data()

        # validate that the data was inserted correctly
        self.validate_data_insert()

if __name__ == "__main__":

    import os
    import sys
    from const import ROOT_DIR
    from db_control import DatabaseControl

    ### insert using makefile function
    filename = sys.argv[-1]
    mxl_filepath = os.path.join(ROOT_DIR, 'data', filename)
    playlist_filepath = os.path.join(ROOT_DIR, 'data', 'playlist.csv')

    inserter = InsertValues(mxl_filepath, playlist_filepath)
    inserter.file_to_sql()

    ### insert all .mxl files ###
    # import glob
    # mxl_files = glob.glob(os.path.join("data", "*.mxl"))
    # playlist_filepath = os.path.join(ROOT_DIR, 'data', 'playlist.csv')
    # for mxl_filepath in mxl_files:
    #     inserter = InsertValues(mxl_filepath, playlist_filepath)
    #     inserter.file_to_sql()


    ### checking different functions ###
    # table_names, tables_dict = inserter.make_tables_dict()
    # preprocessed_data = inserter.preprocess_sql_data(tables_dict, table_names)
    # inserter.insert_data(preprocessed_data=preprocessed_data, table_names=table_names)

    ### check database ###
    db_control = DatabaseControl()
    # db_control.list_tables()
    db_control.list_table_values(table_name="sections")
    # db_control.list_table_values(table_name="phrases")
