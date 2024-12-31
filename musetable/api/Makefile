GCP_PROJECT_ID=audio-projects-363306
DOCKER_IMAGE_NAME=musetable-api
GCP_REGION=europe-west1
DOCKER_REPO_NAME=musetable-repo
DOCKER_VERSION_ID=1.0

make_gar_repo:
	gcloud artifacts repositories create ${DOCKER_REPO_NAME} --repository-format=docker --location=${GCP_REGION} --description="Musetable docker repo"

build_docker_image:
	docker build -t ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${DOCKER_REPO_NAME}/${DOCKER_IMAGE_NAME}:${DOCKER_VERSION_ID} .

run_docker_image:
	docker run -e PORT=80 -p 8080:80 ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${DOCKER_REPO_NAME}/${DOCKER_IMAGE_NAME}:${DOCKER_VERSION_ID}

push_docker_image:
	docker push ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${DOCKER_REPO_NAME}/${DOCKER_IMAGE_NAME}:${DOCKER_VERSION_ID}
