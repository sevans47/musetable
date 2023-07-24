import os

my_path = os.path.dirname(os.path.abspath(__file__))  # get path to directory with const.py
ROOT_DIR = os.path.abspath(os.path.join(my_path, os.pardir))  # get path to parent dir of const.py

SCOPE = 'local'
# SCOPE = 'flask'  # changing scope will adjust how file upload works
