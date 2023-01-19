import os

my_path = os.path.dirname(os.path.abspath(__file__))  # get path to directory with const.py
ROOT_DIR = os.path.abspath(os.path.join(my_path, os.pardir))  # get path to parent dir of const.py

HOST = "localhost"
DBNAME = "musetable"

# for spotify secrets
PROJECT_ID = 'audio-projects-363306'
SPOTIFY_SECRET_ID = 'spotify_auth'
SPOTIFY_VERSION_ID = 6
PLAYLIST_NAME = "Your Top Songs 2022"

# for database secrets
SECRET_ID = "musetable_auth"
VERSION_ID = 1
