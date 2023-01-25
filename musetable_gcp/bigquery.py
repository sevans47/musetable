"""
Create datasets and load data using Google BigQuery
"""

from google.cloud import bigquery
from google.cloud import storage
from google.api_core import exceptions
from musetable.preprocess import PreprocessXML
import json
import os

from const import ROOT_DIR

class BigQuery:
    "BigQuery class performs CRUD operations for the musetable dataset on BigQuery"

    def __init__(self, project_id, dataset_name):
        self.project_id = project_id
        self.client = bigquery.Client(project=project_id)
        self.dataset_id = f"{self.client.project}.{dataset_name}"


    def create_dataset(self, loc="US"):
        # create a Dataset object
        dataset = bigquery.Dataset(self.dataset_id)

        # specify location
        dataset.location = loc

        # Make an API request
        dataset = self.client.create_dataset(dataset, timeout=30)
        print(f"Created dataset {self.dataset_id}")


    def create_tables(self, schema_filepath):
        with open(schema_filepath, 'r') as file:
            schema_file = json.load(file)
        for table_name, column_list in schema_file.items():
            table_id = f"{self.dataset_id}.{table_name}"
            schema = []
            for column in column_list:
                schema.append(bigquery.SchemaField(f"{column['name']}", f"{column['type']}"))

            table = bigquery.Table(table_id, schema=schema)
            table = self.client.create_table(table)  # Make an API request
            print(f"Created table {table_id}")
        print("All tables created")


    def load_data_from_file(self, mxl_filepath, playlist_filepath):
        """
        Using a local MusicXML file, preprocess it and store it in Google BigQuery
        """
        self.preproc = PreprocessXML(mxl_filepath, playlist_filepath)
        self.preprocessed_data = self.preproc.preprocess_data()
        self.table_names, self._ = self.preproc.make_tables_dict()
        for i, table_name in enumerate(self.table_names):
            table_id = f"{self.dataset_id}.{table_name}"
            table = self.client.get_table(table_id)
            self.client.insert_rows(table, self.preprocessed_data[i])
            print(f"{len(self.preprocessed_data[i])} rows added to table {table_id}")
        print("Data load complete")


    def check_gcs_for_file(self, filename: str, bucket_name: str):

        gsclient = storage.Client(project=self.project_id)
        try:
            bucket = storage.Bucket(gsclient, bucket_name)
            stats = storage.Blob(name=filename, bucket=bucket).exists(gsclient)
            if stats:
                print(f"file {filename} exists")
            else:
                print(f"file {filename} not found")
        finally:
            gsclient.close()

        return stats


    def download_gcs_object(self, blob_source_name, bucket_name):

        # set download location to "temp" folder in "data"
        filename = blob_source_name.split("/")[-1]
        download_directory = os.path.join(ROOT_DIR, "data", "temp")
        isExist = os.path.exists(download_directory)
        if not isExist:
            os.makedirs(download_directory)
        download_location = os.path.join(download_directory, filename)

        # connect to storage client
        gsclient = storage.Client(project=self.project_id)
        try:
            # get bucket
            bucket = gsclient.get_bucket(bucket_name)

            # get blob
            blob = bucket.blob(blob_source_name)

            # download blob
            blob.download_to_filename(download_location)
            # print(f"blob {blob_source_name} downloaded to {download_location}")

        except exceptions.NotFound:
            print(f"either bucket {bucket_name} or blob {blob_source_name} not found")

        finally:
            gsclient.close()


    def load_data_from_gcs(self, blob_source_name, bucket_name):
        """
        Get MusicXML file stored in google cloud storage, preprocess it, and
        load it into google BigQuery.
        """
        # check that file exists in bucket
        exists = self.check_gcs_for_file(blob_source_name, bucket_name)
        if exists == False:
            print(f"{blob_source_name} not found in {bucket_name}")
            return 1

        # download mxl file and playlist file to temp folder
        self.download_gcs_object(blob_source_name, bucket_name)
        self.download_gcs_object("data/playlist.csv", bucket_name)

        # get mxl_filepath and playlist_filepath
        filename = blob_source_name.split("/")[-1]
        mxl_filepath = os.path.join(ROOT_DIR, "data", "temp", filename)
        playlist_filepath = os.path.join(ROOT_DIR, "data", "temp", "playlist.csv")

        # preprocess and load file into bigquery
        self.load_data_from_file(mxl_filepath, playlist_filepath)

        # remove temp files
        os.remove(mxl_filepath)
        os.remove(playlist_filepath)


if __name__ == "__main__":
    from const import ROOT_DIR, BUCKET_NAME, PROJECT_ID
    import os

    dataset_name = "test_dataset"

    gbq = BigQuery(PROJECT_ID, dataset_name)
    # gbq.create_dataset()  # ok

    # schema_filepath = os.path.join(ROOT_DIR, 'data', 'gbq_tables_schema.json')
    # gbq.create_tables(schema_filepath)  # ok

    # mxl_filepath = os.path.join(ROOT_DIR, 'data', 'Juban District - Verse.mxl')
    # playlist_filepath = os.path.join(ROOT_DIR, 'data', 'playlist.csv')
    # gbq.load_data_from_file(mxl_filepath, playlist_filepath)  # ok

    # blob_source_name = "data/Juban District - Chorus.mxl"
    # gbq.download_gcs_object(blob_source_name, BUCKET_NAME)  # ok
    # gbq.load_data_from_gcs(blob_source_name, BUCKET_NAME)  # ok
