import music21 as m21
from typing import Union

from const import ROOT_DIR, SCOPE

class PreprocessXML:
    """PreprocessXML converts a MusicXML file into a dictionary"""

    def __init__(self, mxl_filepath: str):

        self.part, self.part_recurse = self.load_mxl_from_file(mxl_filepath)

        self.artist = self.part.metadata.composer
        self.track_name = self.part.metadata.title
        self.track_dur = float(self.part.duration.quarterLength)
        self.id_prefix = self.create_id_prefix(self.artist, self.track_name)
        self.first_measure_dict = self.get_first_measure_info(self.part)
        self.m1b1_factor = self.get_m1b1_factor()
        self.id_dict = self.initialize_id_dict()

    def load_mxl_from_file(self, mxl_filepath: str) -> Union[m21.stream.Part, m21.stream.iterator.RecursiveIterator]:

        # create stream and extract metadata
        s = m21.converter.parse(mxl_filepath).stripTies()
        title = s.metadata.title
        composer = s.metadata.composer

        # create part and insert metadata
        part = s.parts[0]
        part.insert(0, m21.metadata.Metadata())
        part.metadata.title = title
        part.metadata.composer = composer

        return (part, part.recurse())


    def create_id_prefix(self, artist, track_name):

        # get first two letters for each word of artist's name
        artist_prefix = ''.join([s[:2] for s in artist.lower().split()])

        # return piece title without vowels
        vowels = ('a', 'e', 'i', 'o', 'u')
        track_prefix = ''.join([s for s in track_name.replace(" ","").lower() if s not in vowels])

        return artist_prefix + track_prefix


    def create_ids(self, id_prefix: str, mode: str, ele=None, index_num=None, offsets=None) -> str:
        if mode.lower() == 'track':
            return id_prefix + "-track"
        if mode.lower() == 'sec':
            # 'ele' parameter should be a rehearsal mark
            # 'offsets' parameter should be sec_start_offsets
            # 'index_num' parameter should be current_sec_index
    #         return f"{id_prefix}-sec-{ele.content.replace(' ','').lower()}-{get_track_offset(ele)}"
            return f"{id_prefix}-sec-{ele.content.replace(' ','').lower()}-{offsets[index_num]}"
        if mode.lower() == 'mp':
            # 'index_num' parameter should be current_mp_index
            # 'offsets' parameter should be mp_start_offsets
            return f"{id_prefix}-mp{index_num}-{offsets[index_num]}"
        if mode.lower() == 'note':
            track_offset = self.get_track_offset(ele)
            note_name = ele.name.lower()
            return f"{id_prefix}-{note_name}-{track_offset}"
        if mode.lower() == 'hp':
            return f"{id_prefix}-hp{index_num}-{offsets[index_num]}"
        if mode.lower() == 'chord':
            return f"{id_prefix}-chord-{ele.figure.replace(' ','').lower()}-{self.get_track_offset(ele)}"


    def get_first_measure_info(self, part: m21.stream.Part) -> dict:

        # get first measure info stored as variables
        first_measure = None
        first_measure_dur = None
        first_measure_is_pickup = None

        for i, ele in enumerate(part):
            if isinstance(ele, m21.stream.Measure):
                first_measure = ele
                first_measure_dur = ele.duration.quarterLength
                first_measure_is_pickup = True if ele.measureNumber == 0 else False
                key_sig = [sig for sig in first_measure.elements if type(sig) == m21.key.KeySignature]
                time_sig = [sig for sig in first_measure.elements if type(sig) == m21.meter.TimeSignature]
                break

        return {
            'first_measure': first_measure,
            'first_measure_dur': first_measure_dur,
            'first_measure_is_pickup': first_measure_is_pickup,
            'key_signature': key_sig,
            'time_signature': time_sig
        }


    def get_m1b1_factor(self) -> float:
        return self.first_measure_dict['first_measure_dur'] if self.first_measure_dict['first_measure_is_pickup'] else 0.0


    def initialize_id_dict(self) -> dict:
        return {
            'current_sec_id': None,
            'current_sec_index': 0,
            'current_mp_id': None,
            'current_mp_index': -1,
            'current_hp_id': None,
            'current_hp_index': -1,
            'current_chord_id': None,
            'current_chord': None
        }


    def get_track_offset(self, ele):
        return float(ele.activeSite.offset + ele.offset)
