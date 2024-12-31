FROM python:3.8.18-slim-bullseye

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./api.py /code/api.py
COPY ./const.py /code/const.py
COPY ./preprocess.py /code/preprocess.py

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "80"]
