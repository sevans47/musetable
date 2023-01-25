"""

"""

from google.cloud import storage
from google.api_core import exceptions
import glob
import os

class GCloudStorage:

    def __init__(self):
        pass

    def create_bucket(self, bucket_name, project_id):
        gsclient = storage.Client(project=project_id)
        bucket = gsclient.lookup_bucket(bucket_name)
        if not bucket:
            gsclient.create_bucket(bucket_name)
            print(f"bucket {bucket_name} created in project {project_id}")
        else:
            print(f"bucket {bucket_name} already exists")
        gsclient.close()

    def upload_folder_to_bucket(self, local_folder, bucket_name, project_id):

        # get local files and filter out any folders (folders can't be blobs)
        files = glob.glob(os.path.join(local_folder, "**"), recursive=True)
        files = [file for file in files if os.path.isfile(file)]

        # specify blob names (keep 'data' folder)
        par_dir = os.path.dirname(local_folder)
        blob_names = [os.path.relpath(file, start=par_dir) for file in files]

        # connect to client and get bucket
        gsclient = storage.Client(project=project_id)
        try:
            bucket = gsclient.get_bucket(bucket_name)
            print(f"bucket '{bucket_name}' found")

            # create empty blobs in bucket
            blobs = [bucket.blob(blob_name) for blob_name in blob_names]

            # upload files as blobs to bucket
            for blob, file in zip(blobs, files):
                print(f"uploading {file} ...")
                with open(file, 'rb') as my_file:
                    blob.upload_from_file(my_file)
            print(f"Finished uploading local folder {local_folder} to bucket {bucket_name}")

        except exceptions.NotFound:
            print(f"bucket {bucket_name} not found")

        finally:
            gsclient.close()

    def upload_file_to_bucket(self, local_file, bucket_name, project_id):

        # check local_file
        if not os.path.isfile(local_file):
            print(f"local file '{local_file}' not found")
            return 1

        # get blob name
        par_dir = os.path.dirname(os.path.abspath('data'))
        blob_name = os.path.relpath(local_file, start=par_dir)

        # connect to client and get bucket
        gsclient = storage.Client(project=project_id)
        try:
            bucket = gsclient.get_bucket(bucket_name)
            print(f"bucket '{bucket_name}' found")

            # make blob
            blob = bucket.blob(blob_name)

            # upload file
            print(f"uploading {local_file} ...")
            with open(local_file, 'rb') as my_file:
                blob.upload_from_file(my_file)

            print("upload complete")

        except exceptions.NotFound:
            print(f"bucket {bucket_name} not found")

        finally:
            gsclient.close()

    def download_object(self, blob_source_name, bucket_name, project_id, download_location):
        gsclient = storage.Client(project=project_id)
        try:
            bucket = gsclient.get_bucket(bucket_name)
            print(f"bucket '{bucket_name}' found")

            # get blob
            blob = bucket.blob(blob_source_name)

            # download blob
            blob.download_to_filename(download_location)

            print("download complete")

        except exceptions.NotFound:
            print(f"bucket {bucket_name} not found")

        finally:
            gsclient.close()

    # TODO: make this function
    def read_csv(self):
        csv_uri = 'gs://udemy-gcp-de-test-bucket/retail_db/orders/part-00000'
        df = pd.read_csv(csv_uri)


if __name__ == "__main__":
    from const import PROJECT_ID, BUCKET_NAME, ROOT_DIR

    from musetable.preprocess import PreprocessXML

    gcs = GCloudStorage()

    # gcs.create_bucket("musetable", PROJECT_ID)  # ok

    # local_folder = os.path.join(ROOT_DIR, 'data')
    # gcs.upload_folder_to_bucket(local_folder, BUCKET_NAME, PROJECT_ID)  # ok

    # local_file = os.path.join(ROOT_DIR, 'data', 'test_dir', 'test.txt')
    # local_file = "data/test_dir/test.txt"
    # local_file = 'potato/tasty.eat'
    # gcs.upload_file_to_bucket(local_file, BUCKET_NAME, PROJECT_ID)  # ok

    # blob_source_name = "data/Juban District - Verse.mxl"
    # download_location = os.path.join(ROOT_DIR, "data", "temp", "Juban District - Verse.mxl")
    # gcs.download_object(blob_source_name, BUCKET_NAME, PROJECT_ID, download_location)  # ok
