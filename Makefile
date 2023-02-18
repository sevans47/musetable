PROJECT_ID=audio-projects-363306
BUCKET_NAME=musetable_test

set_project:
	@gcloud config set project ${PROJECT_ID}

cloud_functions_deploy:
	@gcloud functions deploy musetable-ETL-function \
		--entry-point ETL_gcs_to_bigquery \
		--runtime python38 \
		--max-instances 1 \
		--trigger-event google.storage.object.finalize \
		--trigger-resource ${BUCKET_NAME} \
		--memory 256MB \
		--source musetable-ETL-function

cloud_functions_logs:
	@gcloud functions logs read

FILE_NAME ?= $(shell bash -c 'read -p "File name to upload: "  input; echo $$input')

gcs_upload_file:
	@clear
	@gsutil cp data/${FILE_NAME} gs://${BUCKET_NAME}
