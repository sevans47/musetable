import os

from preprocess_cf import PreprocessXML
from gcs_bigquery import save_blob_to_tmp, insert_data_into_bigquery

def ETL_gcs_to_bigquery(event, context):

    # extract MusicXML file from gcs and save to local file
    temp_local_filename = save_blob_to_tmp(event)

    # preprocess the data
    preproc = PreprocessXML(temp_local_filename, "playlist.csv")

    preprocessed_data, table_names = preproc.preprocess_data()

    # load preprocessed data into bigquery
    insert_data_into_bigquery(preprocessed_data, table_names)

    # remove temporary file
    os.remove(temp_local_filename)
