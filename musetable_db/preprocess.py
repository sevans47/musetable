"""
Load a MusicXML file, and create a series of dictionaries. Each dictionary
represents one table in the musetable database, and the data therein will
be inserted into the database using the insert.py module
"""

import os
import music21 as m21
import pandas as pd
import psycopg2
from psycopg2 import sql
from musetable_db.db_decorator import PostgresDB

from musetable_db.const import PROJECT_ID, SECRET_ID, VERSION_ID

db = PostgresDB(PROJECT_ID, SECRET_ID, VERSION_ID)

class PreprocessXML:
    """PreprocessXML prepares a MusicXML file to be inserted into a database"""

    def __init__(self, mxl_filepath: str, playlist_filepath: str, from_cgs = False):
        """
        Parameters:
        -----------
        mxl_filepath        : path to MusicXML file
        playlist_filepath   : path to playlist csv, which has track data collected
                              using the Spotify API
        """
        self.mxl_filepath = mxl_filepath
        self.playlist_filepath = playlist_filepath

    def load_mxl_from_file(self) -> m21.stream.Part:
        """
        Load MusicXML file, extract the top part, and add metadata to it"
        """

        # load MusicXML file and extract metadata
        s = m21.converter.parse(self.mxl_filepath)
        title = s.metadata.title
        composer = s.metadata.composer

        # create part and add metadata to it
        part = s.parts[0]
        part.insert(0, m21.metadata.Metadata())
        part.metadata.title = title
        part.metadata.composer = composer

        return part

    def read_playlist_csv(self) -> pd.DataFrame:
        """
        Load csv of playlist data and store as a DataFrame.  Playlist data was
        collected using the Spotify API
        """
        return pd.read_csv(self.playlist_filepath)

    def generate_section_id(self, part: m21.stream.Part, playlist_df: pd.DataFrame) -> str:
        """
        Create an id to be used for each section of a track.  Format of the id is:
        - first letter of each word of artist's name
        - first letter of each word track name
        - last two digits of release year
        - section type
        e.g. Ginger Root - Juban District -> grjd21-chorus
        Parameters:
        -----------
        part        : music21 Part object, which contains all the data from the MusicXML file
        playlist_df : DataFrame of playlist information
        """
        # get track name from part's metadata
        track_name = part.metadata.title.split(' - ')[0].lower()

        # find track info in playlist_df
        track = playlist_df[playlist_df['name'].str.lower() == track_name].reset_index(drop=True)

        # create id
        id_pre = "".join([word[0].lower() for word in track.loc[0, 'artist'].split()]) + "".join([word[0].lower() for word in track.loc[0, 'name'].split()])
        id_post = track.loc[0, 'release_date'][2:4]

        return f"{id_pre}{id_post}-{part.metadata.title.split(' - ')[1].replace(' ', '').lower()}"

    def make_track_dict(self, part: m21.stream.Part, playlist_df: pd.DataFrame) -> dict:
        """
        Create a dictionary of track information to put in the database
        Parameters:
        -----------
        part        : music21 Part object, which contains all the data from the MusicXML file
        playlist_df : DataFrame of playlist information
        """
        # get track name from part's metadata
        track_name = part.metadata.title.split(' - ')[0].lower()

        # find track info in playlist_df
        track = playlist_df[playlist_df['name'].str.lower() == track_name].reset_index(drop=True)

        # create the dictionary
        track_dict = {
            'id': track.loc[0, 'id'],
            'artist': track.loc[0, 'artist'],
            'track_name': track.loc[0, 'name'],
            'album_name': track.loc[0, 'album'],
            'release_date': track.loc[0, 'release_date']
        }

        return track_dict

    def make_phrases_list(self, part: m21.stream.Part) -> list:
        """
        Create a list of phrase locations for the section.  Each phrase location
        is a list of two numbers: the offset for the first and last notes of the phrase.

        A phrase is a group of notes that makes up one musical idea, or one
        musical sentence.  For this project, phrases are designated in the score
        using slurs, which can be identified in the music21 Part object with
        the spanners attribute.

        Parameters:
        -----------
        part    : music21 Part object, which contains all the data from the MusicXML file
        """
        # loop through spanners and save offsets for first and last notes
        phrases_list = []

        for spanner in part.spanners:

            # get first and last notes of the phrase
            first_note = spanner.getFirst()
            last_note = spanner.getLast()

            # get measure numbers for first and last notes of the phrase
            first_note_measure = part.measure(first_note.measureNumber)
            last_note_measure = part.measure(last_note.measureNumber)

            # measure offset = number of quarterLengths from the beginning of the piece
            # note offset = number of quarterLengths from the beginning of the measure
            phrases_list.append(
                [
                    float(first_note_measure.offset) + float(first_note.offset),
                    float(last_note_measure.offset) + float(last_note.offset)
                ]
            )

        return phrases_list

    def get_offset(self, part, element) -> float:
        """
        Get offset from beginning of section for an element in a music21 Part object.

        Parameters:
        -----------
        part    : music21 Part object, which contains all the data from the MusicXML file
        element : any element from using the part.recurse() iterator
        """
        # add measure offset (from beginning of section) to element offset (from beginning of measure)
        offset = float(part.measure(element.measureNumber).offset) + float(element.offset)

        return offset

    def get_phrase(self, phrases_list: list, ele_offset: float) -> int:
        """
        Identifies the phrase number for any element in part.recurse().

        Parameters:
        -----------
        phrases_list    : nested list of offsets for start and end of each phrase
        ele_offset      : offset in quarterLengths from begining of section for the element
        """

        # While iterating through phrases list, keep track of how many phrases element isn't in
        not_in_phrase_count = 0

        # Loop through phrases list to find which phrase element is in
        for ind, offsets in enumerate(phrases_list):
            if ele_offset >= offsets[0] and ele_offset <= offsets[1]:
                phrase = ind + 1
            else:
                not_in_phrase_count += 1

        # If element isn't in any phrase, return 0
        if len(phrases_list) == not_in_phrase_count:
            phrase = 0

        return phrase

    def get_harmony_durations(self, offsets: list, section_duration: float) -> list:
        """
        Return list of durations in quarterLengths for each chord symbol in the music.

        Parameters:
        -----------
        offsets          : Distance of chord symbol from start of the section in quarterLengths
        section_duration : Total duration in quarterLengths for the section
        """
        # Loop through chord symbol offsets and store distance between each in harmony_durations
        harmony_durations = []
        for ind, offset in enumerate(offsets):
            if ind == len(offsets) - 1:
                harmony_durations.append(section_duration - offset)
            else:
                dur = offsets[ind + 1] - offset
                harmony_durations.append(dur)

        return harmony_durations

    def stream_to_dict(self) -> tuple:
        """
        Main function of the preprocess module.  Takes a MusicXML file, and generates
        the following dictionaries:
        - track_dict: information about the track
        - section_dict: information about the section of the track (e.g. verse, chorus, etc.)
        - phrases_dict: information about each phrase in the section
        - note_dict: information about each note in the section
        - harmony_dict: information about the chord symbols in the section
        """
        # create some useful variables
        part = self.load_mxl_from_file()  # music21 Part object, which has all the data from the mxl file
        playlist_df = self.read_playlist_csv()  # dataframe of track info from Spotify

        pitch_range = part.analyze(method='ambitus')  # melodic range of section
        track_name = part.metadata.title.split(' - ')[0]  # name of track
        section_id = self.generate_section_id(part, playlist_df)  # unique id for this section
        phrases_list = self.make_phrases_list(part)  # get phrase information

        # set up all dictionaries
        track_dict = self.make_track_dict(part, playlist_df)

        section_dict = {
            'id': section_id,
            'track_id': track_dict['id'],
            'title': track_name,
            'section': part.metadata.title.split(' - ')[1],
            'composer': part.metadata.composer,
            'duration_ql': part.duration.quarterLength,
            'num_phrases': len(phrases_list),
            'range_interval': pitch_range.name,
            'range_midi_low': pitch_range.pitchStart.midi,
            'range_midi_high': pitch_range.pitchEnd.midi,
            'time_signature': None
        }

        phrases_dict = {
            'section_id': [],
            'phrase_num': [],
            'phrase_length': [],
            'phrase_start_offset': [],
            'phrase_end_offset': []
        }

        note_dict = {
            'section_id': [],
            'note_name': [],
            'octave': [],
            'midi_num': [],
            'pitch_class': [],
            'duration_ql': [],
            'phrase_num': [],
            'measure': [],
            'beat': [],
            'offset_ql': [],
            'chord_name': [],
            'nct': [],
            'from_root_name': [],
            'from_root_pc': []
        }

        harmony_dict = {
            'section_id': [],
            'chord_name': [],
            'chord_kind': [],
            'chord_root': [],
            'chord_bass': [],
            'pitches': [],
            'phrase_num': [],
            'measure': [],
            'beat': [],
            'offset_ql': [],
        }


        # iterate over part for section_dict
        for ele in part.recurse():
            if isinstance(ele, m21.tempo.MetronomeMark):
                section_dict['bpm'] = str(ele.number)
                section_dict['bpm_ql'] = str(ele.referent.quarterLength)
            if isinstance(ele, m21.meter.TimeSignature) and section_dict['time_signature'] == None:
                section_dict['time_signature'] = ele.ratioString

        # iterate over phrases_list for phrases_dict
        for ind, phrase in enumerate(phrases_list):
            phrases_dict['section_id'].append(section_id)
            phrases_dict['phrase_num'].append(ind + 1)
            phrases_dict['phrase_length'].append(phrase[1] - phrase[0])
            phrases_dict['phrase_start_offset'].append(phrase[0])
            phrases_dict['phrase_end_offset'].append(phrase[1])


        # store chord info while iterating
        # TODO: get rid of chord dictionary, just use harmony_dict instead
            # NOTE: for NCT, F in [F#, A, C#] is False, but F in 'F#, A, C#' is True
        chord = {}

        # iterate over part for note_dict and harmony_dict
        for ele in part.recurse():

            # deal with chord symbols
            if isinstance(ele, m21.harmony.ChordSymbol):
                chord['chord_name'] = ele.figure
                chord['chord_kind'] = ele.chordKind
                chord['root'] = ele.root().name
                chord['bass'] = ele.bass().name
                chord['pitches'] = [p.name for p in ele.pitches]

                harmony_dict['section_id'].append(section_id)
                harmony_dict['chord_name'].append(ele.figure)
                harmony_dict['chord_kind'].append(ele.chordKind)
                harmony_dict['chord_root'].append(ele.root().name)
                harmony_dict['chord_bass'].append(ele.bass().name)
                harmony_dict['pitches'].append(", ".join([p.name for p in ele.pitches]))

                harm_offset = self.get_offset(part, ele)
                harm_phrase_num = self.get_phrase(phrases_list, harm_offset)
                harmony_dict['phrase_num'].append(harm_phrase_num)
                harmony_dict['measure'].append(ele.measureNumber)
                harmony_dict['beat'].append(float(ele.beat))
                harmony_dict['offset_ql'].append(harm_offset)

            # deal with info applicable to notes and rests
            if isinstance(ele, m21.note.Rest) or isinstance(ele, m21.note.Note):

                # if note is tie continue / stop, skip note but add duration to previous note
                if ele.tie and (ele.tie.type == 'stop' or ele.tie.type == 'continue'):
                    note_dict['duration_ql'][-1] += float(ele.duration.quarterLength)
                    continue

                note_dict['section_id'].append(section_id)
                note_dict['note_name'].append(ele.name)
                note_dict['duration_ql'].append(float(ele.duration.quarterLength))
                note_dict['measure'].append(ele.measureNumber)
                note_dict['beat'].append(float(ele.beat))

                note_offset = self.get_offset(part, ele)
                note_dict['offset_ql'].append(note_offset)

                note_phrase_num = self.get_phrase(phrases_list, note_offset)
                note_dict['phrase_num'].append(note_phrase_num)

                try:
                    note_dict['chord_name'].append(chord['chord_name'])
                except KeyError:
                    note_dict['chord_name'].append('-1')

            # deal with rest info
            if isinstance(ele, m21.note.Rest):
                note_dict['octave'].append(-1)
                note_dict['midi_num'].append(-1)
                note_dict['pitch_class'].append(-1)
                note_dict['nct'].append(-1)
                note_dict['from_root_name'].append('-1')
                note_dict['from_root_pc'].append(-1)

            # deal with note info
            if isinstance(ele, m21.note.Note):
                note_dict['octave'].append(ele.octave)
                note_dict['midi_num'].append(ele.pitch.midi)
                note_dict['pitch_class'].append(ele.pitch.pitchClass)

                NCT = 0 if ele.name in chord['pitches'] else 1
                note_dict['nct'].append(NCT)

                pitches = [m21.pitch.Pitch(chord['root']).midi, m21.pitch.Pitch(ele.name).midi]
                while pitches[0] > pitches[1]:
                    pitches[0] = pitches[0]-12
                note_dict['from_root_name'].append(m21.chord.Chord(pitches).commonName)
                note_dict['from_root_pc'].append(pitches[1] - pitches[0])

        # get duration for each harmony - m21.harmony.ChordSymbol's duration is always 0.0, so need to do it myself!
        harmony_durations = self.get_harmony_durations(harmony_dict['offset_ql'], section_dict['duration_ql'])
        harmony_dict['duration_ql'] = harmony_durations

        data_dicts = (track_dict, section_dict, phrases_dict, note_dict, harmony_dict)

        return data_dicts

    @db.with_cursor
    def make_tables_dict(self, cursor) -> tuple:
        """
        Create dictionary of all tables and their columns in a database.  Important
        for ensuring the correct order of column names when inserting data.

        Returns:
        --------
        table_names (list): all table names in the database
        tables_dict (dict): keys are table names, values are lists of column names
        """

        tables_dict = {}

        # retrieve table names from database and store in 'tables' list
        query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        cursor.execute(query)
        table_names = [table[0] for table in cursor.fetchall()]

        # retrieve column names from each table in the database
        for table_name in table_names:
            query = sql.SQL("SELECT * FROM {table};").format(
                table=sql.Identifier(table_name)
            )
            cursor.execute(query)
            column_names = [desc[0] for desc in cursor.description]
            tables_dict[table_name] = column_names

        return (table_names, tables_dict)

    def preprocess_data(self) -> list:
        """
        Prepare data in dictionaries returned from stream_to_dict() so they are the correct
        format for inserting into the database.

        Parameters:
        -----------
        tables_dict     (dict): dictionary of all tables and columns from the database. Used to ensure the correct order
        table_names      (str): list of names of all tables in correct order

        Returns:
        --------
        preprocessed_data   (list): Each element is a list of tuples:
                                    - one list represents one table
                                    - one tuple represents one row
        """
        preprocessed_data = []

        # prepare data variables for preprocessing
        table_names, tables_dict = self.make_tables_dict()
        data_dicts = self.stream_to_dict()

        print("preprocessing data ... ")
        for table_name, data_dict in zip(table_names, data_dicts):

            # list of tuples for each data_dict
            data_chunk = []

            if table_name in ["tracks", "sections"]:
                data_chunk.append(tuple(data_dict.values()))
                preprocessed_data.append(data_chunk)
                continue

            for i in range(len(data_dict['section_id'])):
                row = []

                # ensure data is in the correct column order by using tables_dict lists
                for col in tables_dict[table_name]:
                    row.append(data_dict[col][i])
                data_chunk.append(tuple(row))

            preprocessed_data.append(data_chunk)

        print("data preprocessed")
        return preprocessed_data

if __name__ == "__main__":

    from const import ROOT_DIR

    # get filepaths
    mxl_filepath = os.path.join(ROOT_DIR, 'data', 'Juban District - Verse.mxl')
    csv_filepath = os.path.join(ROOT_DIR, 'data', 'playlist.csv')

    # instantiate PreprocessXML class
    preproc = PreprocessXML(mxl_filepath, csv_filepath)

    # create data dictionaries
    # data_dicts = preproc.stream_to_dict()
    # for data_dict in data_dicts:
    #     print(data_dict.keys())

    # preprocess data
    preproc_data = preproc.preprocess_data()
    print(preproc_data[2])
