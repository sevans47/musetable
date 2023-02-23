import tempfile
from google.cloud import storage, bigquery
from const_cf import BUCKET_NAME, PROJECT_ID, DATASET_NAME

def save_blob_to_tmp(event) -> str:
    # Retreive MusicXML file from gcs
    file_name = event['name']
    bucket = storage.Client().bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)

    # Download the MusicXML file to a temporary file
    _, temp_local_filename = tempfile.mkstemp(suffix='.mxl')
    blob.download_to_filename(temp_local_filename)

    print(f"Retrieved file {file_name} from bucket {BUCKET_NAME}")

    return temp_local_filename


def insert_data_into_bigquery(preprocessed_data, table_names):

    # ensure preprocessed_data can be added into bigquery
    if len(preprocessed_data) != len(table_names):
        print("Error: preprocessed data doesn't match number of tables")
        return 1

    # connect to client and get dataset id
    bq_client = bigquery.Client(project=PROJECT_ID)
    dataset_id = f"{bq_client.project}.{DATASET_NAME}"

    # iterate through tables and insert data
    for i, table_name in enumerate(table_names):

        # save table id for GBQ
        table_id = f"{dataset_id}.{table_name}"

        # fetch GBQ table
        table = bq_client.get_table(table_id)

        # insert data into table
        bq_client.insert_rows(table, preprocessed_data[i])
        print(f"{len(preprocessed_data[i])} rows added to table {table_id}")

    print("Data load complete")
