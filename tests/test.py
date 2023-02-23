import os

from musetable.const import ROOT_DIR
from musetable.preprocess import PreprocessXML as Preprocess
from musetable_ETL_function.preprocess_cf import PreprocessXML as Preprocess_cf

mxl_filepath = os.path.join(ROOT_DIR, 'tests', 'test_data', 'Juban District - Verse.mxl')
playlist_filepath = os.path.join(ROOT_DIR, 'tests', 'test_data', 'playlist.csv')

def test_preprocess():
    preproc = Preprocess(mxl_filepath, playlist_filepath)
    preproc_data = preproc.preprocess_data()

    # test shape of data for tracks table
    assert len(preproc_data[0]) == 1
    assert len(preproc_data[0][0]) == 5

    # test shape of data for sections table
    assert len(preproc_data[1]) == 1
    assert len(preproc_data[1][0]) == 13

    # test shape of data for phrases table
    assert len(preproc_data[2]) == 2
    assert len(preproc_data[2][0]) == 5

    # test shape of data for notes table
    assert len(preproc_data[3]) == 40
    assert len(preproc_data[3][0]) == 14

    # test shape of data for harmony table
    assert len(preproc_data[4]) == 6
    assert len(preproc_data[4][0]) == 11

def test_preprocess_cf():
    preproc = Preprocess_cf(mxl_filepath, playlist_filepath)
    preproc_data = preproc.preprocess_data()

    # test shape of data for tracks table
    assert len(preproc_data[0][0]) == 1
    assert len(preproc_data[0][0][0]) == 5

    # test shape of data for sections table
    assert len(preproc_data[0][1]) == 1
    assert len(preproc_data[0][1][0]) == 13

    # test shape of data for phrases table
    assert len(preproc_data[0][2]) == 2
    assert len(preproc_data[0][2][0]) == 5

    # test shape of data for notes table
    assert len(preproc_data[0][3]) == 40
    assert len(preproc_data[0][3][0]) == 14

    # test shape of data for harmony table
    assert len(preproc_data[0][4]) == 6
    assert len(preproc_data[0][4][0]) == 11

    # test table names
    assert preproc_data[1] == ['tracks', 'sections', 'phrases', 'notes', 'harmony']

if __name__ == "__main__":
    pass
    # test_preprocess()  # ok
    # test_preprocess_cf()  # ok

    # preproc_data = test_preprocess_cf()
    # print(preproc_data[1])
