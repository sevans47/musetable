from fastapi import FastAPI
from preprocess import PreprocessXML

app = FastAPI()

@app.get("/")
def root():
    return {"message": "API for musetable"}


@app.post("/preprocess")
def preprocess(mxl_filepath: str, comprehensive: bool = False):
    """
    Loads and transforms a music xml file into a dictionary, and validates the data.
    If validation passes, returns the dictionary.
    If validation fails, returns the error message.

    Args
    - mxl_filepath: filepath to music mxl file
    - comprehensive: If False, creates dict with 6 basic keys.  If True, dict has 16 keys.
    """
    preproc = PreprocessXML()
    preproc.load_data(mxl_filepath, comprehensive)
    preproc.input_all()
    validation_message = preproc.validate_input()
    if validation_message == "all values validated!":
        return preproc.data_dict
    return {"error message": validation_message}
