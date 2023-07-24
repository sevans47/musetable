PROJECT_ID=audio-projects-363306
BUCKET_NAME=musetable_test

streamlit_test:
	@streamlit run musetable/streamlit_test/app.py

test:
	@pytest -v tests/test.py

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
		--source musetable_ETL_function

cloud_functions_logs:
	@gcloud functions logs read

FILE_NAME ?= $(shell bash -c 'read -p "File name to upload: "  input; echo $$input')

musetable_file_to_sql:
	@python musetable/insert.py ${FILE_NAME}

gcs_upload_file:
	@clear
	@gsutil cp data/${FILE_NAME} gs://${BUCKET_NAME}

upload_file_gcs_and_sql:
	@clear
	@gsutil cp data/${FILE_NAME} gs://${BUCKET_NAME}
	@python musetable/insert.py ${FILE_NAME}
