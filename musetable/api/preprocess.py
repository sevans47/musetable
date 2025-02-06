import music21 as m21
from typing import Union, Mapping, Sequence
import numpy as np
import pandas as pd

from const import SCOPE, BASIC_TABLES, NULLABLE_COLUMNS, DATA_DICT, DATA_TYPE_DICT, chord_kind_dict

class PreprocessXML:
    """PreprocessXML converts a MusicXML file into a dictionary"""

    def __init__(self):
        pass


    def load_data(self, mxl_filepath: str, comprehensive=False):
        # if comprehensive=False, returns basic tables. If True, returns additional tables as well
        self.mxl_filepath = mxl_filepath
        self.comprehensive = comprehensive

        # get m21 part from mxl file
        self.part, self.part_recurse = self.load_mxl_from_file(self.mxl_filepath)

        # create instance variables
        self.artist = self.part.metadata.composer
        self.track_name = self.part.metadata.title
        self.track_dur = float(self.part.duration.quarterLength)
        self.id_prefix = self.create_id_prefix(self.artist, self.track_name)
        self.first_measure_dict = self.get_first_measure_info(self.part)
        self.m1b1_factor = self.get_m1b1_factor()
        self.id_dict = self.initialize_id_dict()
        self.rehearsal_marks = self.make_rehearsal_marks_list(self.part_recurse)  # determines sections
        self.spanners = [s for s in self.part.spanners]  # determines melodic phrases
        self.expression_marks = self.make_expression_marks_list(self.part_recurse)  # determines harmonic phrases
        self.offset_dict = self.make_offset_dict(self.rehearsal_marks, self.spanners, self.expression_marks)
        self.make_sec_offset_to_sec_id_dict()  # add this to offset_dict
        self.data_dict = DATA_DICT
        self.data_type_dict = DATA_TYPE_DICT
        self.nullable_columns = NULLABLE_COLUMNS

        # remove unneeded tables from data_dict
        if self.comprehensive == False:
            for table in list(self.data_dict.keys()):
                if table not in BASIC_TABLES:
                    self.data_dict.pop(table, None)
                    self.data_type_dict.pop(table, None)

        # # update id_dict
        # self.id_dict['current_sec_id'] = self.create_ids(
        #     self.id_prefix, mode='sec', ele=self.rehearsal_marks[self.id_dict['current_sec_index']],
        #     index_num=self.id_dict['current_sec_index'], offsets=self.offset_dict['sec_start_offsets']
        # )

        # if self.offset_dict['mp_start_offsets'][0] == 0.0:
        #     self.id_dict['current_mp_index'] = 0
        #     self.id_dict['current_mp_id'] = self.create_ids(
        #         self.id_prefix, mode='mp', index_num=self.id_dict['current_mp_index'],
        #         offsets=self.offset_dict['mp_start_offsets']
        #     )

        # if self.offset_dict['hp_start_offsets'][0] == 0.0:
        #     self.id_dict['current_hp_index'] = 0
        #     self.id_dict['current_hp_id'] = self.create_ids(
        #         self.id_prefix, mode='hp', index_num=self.id_dict['current_hp_index'],
        #         offsets=self.offset_dict['hp_start_offsets']
        #     )

        self.check_first_chord()  # update id_dict with first chord info
        self.id_dict['current_chord_id'] = self.create_ids(
            self.id_prefix, mode='chord', ele=self.id_dict['current_chord']
        )


    # the following class methods are all for the constructor
    def load_mxl_from_file(self, mxl_filepath: str, scope=SCOPE) -> Union[m21.stream.Part, m21.stream.iterator.RecursiveIterator]:

        if scope == 'local':
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
            return f"{id_prefix}-mp{index_num+1}-{offsets[index_num]}"
        if mode.lower() == 'note':
            track_offset = self.get_track_offset(ele)
            note_name = ele.name.lower()
            return f"{id_prefix}-{note_name}-{track_offset}"
        if mode.lower() == 'hp':
            return f"{id_prefix}-hp{index_num+1}-{offsets[index_num]}"
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
                try:
                    key_sig = [sig for sig in first_measure.elements if type(sig) == m21.key.KeySignature][0]
                except IndexError:
                    key_sig = None
                try:
                    time_sig = [sig for sig in first_measure.elements if type(sig) == m21.meter.TimeSignature][0]
                except IndexError:
                    time_sig = None
                try:
                    metronome_mark = [tmpo for tmpo in first_measure.elements if type(tmpo) == m21.tempo.MetronomeMark][0]
                except IndexError:
                    metronome_mark = None
                break

        return {
            'first_measure': first_measure,
            'first_measure_dur': first_measure_dur,
            'first_measure_is_pickup': first_measure_is_pickup,
            'key_sig_n_sharps': key_sig,
            'time_sig': time_sig,
            'metronome_mark': metronome_mark,
        }


    def get_m1b1_factor(self) -> float:
        return self.first_measure_dict['first_measure_dur'] if self.first_measure_dict['first_measure_is_pickup'] else 0.0


    def initialize_id_dict(self) -> dict:
        return {
            'current_sec_id': None,
            'current_sec_index': -1,
            'current_mp_id': None,
            'current_mp_index': -1,
            'current_hp_id': None,
            'current_hp_index': -1,
            'current_chord_id': None,
            'current_chord': None
        }


    def make_rehearsal_marks_list(self, part_rec: m21.stream.iterator.RecursiveIterator) -> list:
        """Put all rehearsal marks into a list, and check if there's a rehearsal mark at the very
        beginning.  If not, insert an "Intro" rehearsal mark at the beginning.
        """

        # get all rehearsal marks
        rehearsal_marks = [ele for ele in part_rec if isinstance(ele, m21.expressions.RehearsalMark)]

        # check whether first rehearsal mark is at the very beginning of the piece
        rm_at_beginning = rehearsal_marks[0].activeSite == self.first_measure_dict['first_measure'] and rehearsal_marks[0].offset == 0
        if rm_at_beginning == False:
            rm_intro = m21.expressions.RehearsalMark('Intro')
            self.first_measure_dict['first_measure'].insert(rm_intro)  # need to add to first measure to give it an active site and offset
            rehearsal_marks.insert(0, rm_intro)  # list .insert() is different from m21's .insert()!

        return rehearsal_marks


    def make_expression_marks_list(self, part_rec: m21.stream.iterator.RecursiveIterator) -> list:
        expression_marks = [
            ele for ele in part_rec if isinstance(ele, m21.expressions.TextExpression) and ele.content == 'hp'
        ]

        return expression_marks


    def check_first_chord(self) -> None:

        # get list of all chords in first measure
        cs = [
            ele for ele in self.first_measure_dict['first_measure'].elements\
                if isinstance(ele, m21.harmony.ChordSymbol) or isinstance(ele, m21.harmony.NoChord)
        ]

        # check if there's a chord symbol at the beginning of the piece, and assign as id_dict's current chord
        if len(cs) >= 1 and cs[0].offset == 0.0:
            self.id_dict['current_chord'] = cs[0]

        # add NoChord as first chord if no chord symbol at the beginning of the piece
        else:
            self.id_dict['current_chord'] = m21.harmony.NoChord()
            self.first_measure_dict['first_measure'].insert(self.id_dict['current_chord'])

        return None


    def make_offset_dict(self, rehearsal_marks, spanners, expression_marks) -> dict:

        offset_dict = {}

        # get offset and duration infor for all sections
        offset_dict['sec_start_offsets'] = np.array([self.get_track_offset(rm) for rm in rehearsal_marks])
        offset_dict['sec_end_offsets'] = np.append(offset_dict['sec_start_offsets'][1:], self.track_dur)
        offset_dict['sec_durs'] = offset_dict['sec_end_offsets'] - offset_dict['sec_start_offsets']

        ### get offset and duration info for melodic phrases
        offset_dict['mp_start_offsets'] = np.array([self.get_track_offset(s.getFirst()) for s in spanners])
        offset_dict['mp_end_note_start_offsets'] = np.array([self.get_track_offset(s.getLast()) for s in spanners])
        offset_dict['mp_end_note_end_offsets'] = np.array([self.get_track_offset(s.getLast()) + s.getLast().duration.quarterLength for s in spanners])
        offset_dict['mp_durs'] = offset_dict['mp_end_note_end_offsets'] - offset_dict['mp_start_offsets']

        # get offset and duration for harmonic phrases
        offset_dict['hp_start_offsets'] = np.array([self.get_track_offset(hp) for hp in expression_marks])
        offset_dict['hp_end_offsets'] = np.append(offset_dict['hp_start_offsets'][1:], self.track_dur)
        offset_dict['hp_durs'] = offset_dict['hp_end_offsets'] - offset_dict['hp_start_offsets']

        return offset_dict


    def make_sec_offset_to_sec_id_dict(self) -> None:
        section_ids = self.make_section_ids()
        section_start_offsets = self.offset_dict["sec_start_offsets"]
        sec_offset_to_sec_id = {sec_offset: sec_id for sec_offset, sec_id in zip(section_start_offsets, section_ids)}
        self.offset_dict["sec_offset_to_sec_id"] = sec_offset_to_sec_id
        return None


    def get_track_offset(self, ele) -> float:
        return float(ele.activeSite.offset + ele.offset)


    # the following class methods are for inputing values in the 'tracks', 'sections', 'melodic_phrases',
    # and 'harmonic_phrases' dictionaries
    def make_section_ids(self) -> list:
        "make a list of all section ids"

        return [self.create_ids(
            self.id_prefix,
            mode='sec',
            ele=self.rehearsal_marks[i],
            offsets=self.offset_dict['sec_start_offsets'],
            index_num=i
            ) for i in range(0, len(self.rehearsal_marks))
        ]


    def make_mp_ids(self) -> list:
        "make a list of all mp ids"

        return [self.create_ids(
            self.id_prefix,
            mode='mp',
            offsets=self.offset_dict['mp_start_offsets'],
            index_num=i
            ) for i in range(0, len(self.spanners))
        ]


    def make_hp_ids(self) -> list:
        "make a list of all hp ids"

        return [
            self.create_ids(
                self.id_prefix, mode='hp', index_num=i, offsets=self.offset_dict['hp_start_offsets']
            ) for i in range(len(self.expression_marks))
        ]


    def get_n_mps_per_section(self) -> list:
        "make a list of the number of mp's for each section"

        return [
            int(np.sum(
                np.greater_equal(self.offset_dict['mp_start_offsets'], sec_start) & np.less(self.offset_dict['mp_start_offsets'], sec_end)
            )) for sec_start, sec_end in zip(self.offset_dict['sec_start_offsets'], self.offset_dict['sec_end_offsets'])
        ]


    def get_n_hps_per_section(self) -> list:
        "make a list of the number of hp's for each section"

        return [np.sum(
                    np.greater_equal(self.offset_dict['hp_start_offsets'], sec_start) & np.less(self.offset_dict['hp_start_offsets'], sec_end)
                ) for sec_start, sec_end in zip(self.offset_dict['sec_start_offsets'], self.offset_dict['sec_end_offsets'])
        ]


    def make_sec_id_list_for_mp_dict(self) -> tuple:
        """return a tuple of two lists - one that has section ids for the mp dict, and one that counts the mp
        for each section.  Both of these lists should be added to the melodic_phrases dict.
        """

        n_mps_per_section = self.get_n_mps_per_section()
        section_ids = self.make_section_ids()

        mp_section_ids = []
        mp_num_in_sec_list = []
        for n_mp, section_id in zip(n_mps_per_section, section_ids):
            mp_num_in_sec = 1
            for i in range(n_mp):
                mp_section_ids.append(section_id)
                mp_num_in_sec_list.append(mp_num_in_sec)
                mp_num_in_sec += 1

        return (mp_section_ids, mp_num_in_sec_list)


    def make_sec_id_list_for_hp_dict(self) -> tuple:
        """return a tuple of two lists - one that has section ids for the hp dict, and one that counts the hp
        for each section.  Both of these lists should be added to the harmonic_phrases dict.
        """

        n_hps_per_section = self.get_n_hps_per_section()
        section_ids = self.make_section_ids()

        hp_section_ids = []
        hp_num_in_sec_list = []
        for n_hp, section_id in zip(n_hps_per_section, section_ids):
            hp_num_in_sec = 1
            for i in range(n_hp):
                hp_section_ids.append(section_id)
                hp_num_in_sec_list.append(hp_num_in_sec)
                hp_num_in_sec += 1

        return (hp_section_ids, hp_num_in_sec_list)


    def track_input(self) -> None:
        "Input values into 'tracks' dictionary"

        self.data_dict['tracks']['track_id'].append(self.create_ids(id_prefix=self.id_prefix, mode='track'))
        self.data_dict['tracks']['artist'].append(self.artist)
        self.data_dict['tracks']['track_name'].append(self.track_name)
        self.data_dict['tracks']['key_sig_n_sharps'].append(
            self.first_measure_dict['key_sig_n_sharps'].sharps if self.first_measure_dict['key_sig_n_sharps'] is not None else -100
        )
        self.data_dict['tracks']['time_sig'].append(
            self.first_measure_dict['time_sig'].ratioString if self.first_measure_dict['time_sig'] is not None else '-1'
        )
        mm = self.first_measure_dict['metronome_mark']
        self.data_dict['tracks']['bpm'].append(mm.number if mm is not None else float("0.0"))
        self.data_dict['tracks']['bpm_ql'].append(mm.referent.quarterLength if mm is not None else float("0.0"))
        self.data_dict['tracks']['track_total_dur'].append(self.track_dur)

        return None


    def section_input(self) -> None:
        "input values into 'sections' dictionary"

        # create list of section ids
        sec_ids = self.make_section_ids()

        # create list of number of melodic phrases in each section
        n_mps = self.get_n_mps_per_section()

        # input values into 'sections' dictionary
        self.data_dict['sections']['sec_id'] = sec_ids
        self.data_dict['sections']['track_id'] = [self.create_ids(self.id_prefix, mode='track')] * len(self.rehearsal_marks)
        self.data_dict['sections']['sec_name'] = [rm.content for rm in self.rehearsal_marks]
        self.data_dict['sections']['sec_total_dur'] = self.offset_dict['sec_durs'].tolist()
        self.data_dict['sections']['sec_n_mp'] = n_mps
        self.data_dict['sections']['sec_start_offset'] = self.offset_dict['sec_start_offsets'].tolist()
        self.data_dict['sections']['sec_end_offset']= self.offset_dict['sec_end_offsets'].tolist()
        self.data_dict['sections']['sec_start_m1b1_offset'] = (self.offset_dict['sec_start_offsets'] - self.m1b1_factor).tolist()
        self.data_dict['sections']['sec_end_m1b1_offset'] = (self.offset_dict['sec_end_offsets'] - self.m1b1_factor).tolist()

        return None


    def melodic_phrases_input(self) -> None:
        "input values into the 'melodic_phrases' dictionary"

        mp_ids = self.make_mp_ids()
        sec_id_list_for_mp_dict, mp_num_in_sec = self.make_sec_id_list_for_mp_dict()

        self.data_dict['melodic_phrases']['mp_id'] = mp_ids
        self.data_dict['melodic_phrases']['sec_id'] = sec_id_list_for_mp_dict
        self.data_dict['melodic_phrases']['mp_num_in_sec'] = mp_num_in_sec
        self.data_dict['melodic_phrases']['mp_total_dur'] = self.offset_dict['mp_durs'].tolist()
        self.data_dict['melodic_phrases']['mp_start_offset'] = self.offset_dict['mp_start_offsets'].tolist()
        self.data_dict['melodic_phrases']['mp_end_offset'] = self.offset_dict['mp_end_note_end_offsets'].tolist()
        self.data_dict['melodic_phrases']['mp_start_m1b1_offset'] = (self.offset_dict['mp_start_offsets'] - self.m1b1_factor).tolist()
        self.data_dict['melodic_phrases']['mp_end_m1b1_offset'] = (self.offset_dict['mp_end_note_end_offsets'] - self.m1b1_factor).tolist()

        return None


    def harmonic_phrases_input(self) -> None:
        "input values into the 'harmonic_phrases' dictionary"

        hp_ids = self.make_hp_ids()
        hp_section_ids, hp_num_in_sec_list = self.make_sec_id_list_for_hp_dict()

        self.data_dict['harmonic_phrases']['hp_id'] = hp_ids
        self.data_dict['harmonic_phrases']['sec_id'] = hp_section_ids
        self.data_dict['harmonic_phrases']['hp_num_in_sec'] = hp_num_in_sec_list
        self.data_dict['harmonic_phrases']['hp_total_dur'] = self.offset_dict['hp_durs'].tolist()
        self.data_dict['harmonic_phrases']['hp_start_offset'] = self.offset_dict['hp_start_offsets'].tolist()
        self.data_dict['harmonic_phrases']['hp_end_offset'] = self.offset_dict['hp_end_offsets'].tolist()
        self.data_dict['harmonic_phrases']['hp_start_m1b1_offset'] = (self.offset_dict['hp_start_offsets'] - self.m1b1_factor).tolist()
        self.data_dict['harmonic_phrases']['hp_end_m1b1_offset'] = (self.offset_dict['hp_end_offsets'] - self.m1b1_factor).tolist()

        return None


    # the following class methods are for inputing values into the 'notes' dictionary
    def get_nct(self, ele: m21.note.Note, current_chord: m21.harmony.ChordSymbol) -> int:
        if isinstance(current_chord, m21.harmony.NoChord):
            return -1
        pitches = [p.name for p in current_chord.pitches]
        return 0 if ele.name in pitches else 1


    def get_dist_from_root(self, ele: m21.note.Note, current_chord: m21.harmony.ChordSymbol) -> int:

        # get pitch classes for note and chord root and put them in a numpy array
        pc_array = np.array([ele.pitch.pitchClass, current_chord.root().pitchClass])

        # check if the difference is greater than 6 (ie max difference between pitch classes)
        if np.abs(np.diff(pc_array)) > 6:
            # subtract the larger number by 12, making the distance between 0-6
            pc_array[pc_array.argmax()] = pc_array[pc_array.argmax()] - 12

        return int(np.abs(np.diff(pc_array))[0])


    def get_prev_note_dir(self, prev_note_distance: int) -> str:
        "Returns up, down, or same depending on previous note"
        if prev_note_distance > 0:
            return 'up'
        elif prev_note_distance < 0:
            return 'down'
        return 'same'


    def get_prev_note_dist_type(self, prev_note_distance: int) -> str:
        "Returns step, skip, leap, or same depending on the previous note"
        abs_dist = np.abs(prev_note_distance)
        if abs_dist in [1,2]:
            return 'step'
        elif abs_dist in [3,4]:
            return 'skip'
        elif abs_dist > 4:
            return 'leap'
        return 'same'


    def get_prev_note_dist(self, ele: m21.note.Note, track_offset: float) -> tuple:
        """Calculate distance in half steps between current pitch and previous pitch.  Returns distance,
        direction, and distance type as a tuple.
        """

        # current note is first element of the track
        if track_offset == 0:
            return (-100, '-1', '-1')

        # find previous element
        prev_note_idx = -2  # use -2 because current note's midi_num has already been added to dict
        prev_note_midi = self.data_dict['notes']['midi_num'][prev_note_idx]

        # prev element is a rest
        if prev_note_midi == -1:

            # current note is first note of the track after a rest
            if len(self.data_dict['notes']['midi_num']) == 2:
                return (-100, '-1', '-1')

            # get midi for note before previous rest
            prev_note_idx -= 1
            prev_note_midi = self.data_dict['notes']['midi_num'][prev_note_idx]

        prev_note_dist = ele.pitch.midi - prev_note_midi
        prev_note_dir = self.get_prev_note_dir(prev_note_dist)
        prev_note_dist_type = self.get_prev_note_dist_type(prev_note_dist)

        return (prev_note_dist, prev_note_dir, prev_note_dist_type)


    def check_new_sec_mp(self, ele_track_offset: float, start_offsets: list, current_index: int) -> bool:

        # check if current element is start of a new section or mp
        if ele_track_offset in start_offsets:
            return True

        # check if new section or mp started during the previous element
        if len(self.data_dict['notes']['note_start_offset']) > 0:  # check we're not at the very first element of track
            prev_ele_start_offset = self.data_dict['notes']['note_start_offset'][-1]
            prev_ele_end_offset = self.data_dict['notes']['note_end_offset'][-1]
            next_sec_offset = start_offsets[current_index + 1] if current_index < len(start_offsets) - 2 else self.track_dur
            if prev_ele_start_offset < next_sec_offset and prev_ele_end_offset > next_sec_offset:
                return True

        return False


    def check_between_mps(self, mp_end_note_start_offsets: list) -> bool:

        if len(self.data_dict['notes']['note_start_offset']) > 0:  # check we're not at the very first element of track
            prev_note_start_offset = self.data_dict['notes']['note_start_offset'][-1]

            # check if previous note was last note of a mp
            if prev_note_start_offset in mp_end_note_start_offsets:
                return True

            # TODO: check what happens to spanner info when your slur ends in middle of a tied note, and you parse the part with stripTies()
            # THEN, add to the function to check if the mp ended during the previous element, and return True if so
            # This is an edge case, and is probably a user input mistake, so no need to figure it out now
        return False


    def ele_is_sec_start(self, ele_track_offset: float, sec_start_offsets: list, current_sec_id: str) -> int:

        # check if ele is first ele of the track
        if ele_track_offset == 0.0:
            return 1

        # check if previous element was a rest at end of prev section, or that overlaps between sections
        # NOTE: this will deal with current ele being a note, and:
        #   a) multiple rests at end of prev sec, and current ele at start of new sec
        #   b) multiple rests at end of prev sec, and rest(s) at start of new sec before current ele
        #   If current element is a rest and previous element was a rest, this function wouldn't run
        prev_ele_sec_id = self.data_dict['notes']['sec_id'][-2]  # -2 because current ele has already been added
        prev_ele_midi = self.data_dict['notes']['midi_num'][-1]  # -1 because current midi_num hasn't been added yet
        if prev_ele_sec_id != current_sec_id and prev_ele_midi == -1:

            # update previous element (rest) to be last element of a section
            self.data_dict['notes']['sec_end_note'][-1] = 1  # index is -1 because 'sec_start_note' comes before 'sec_end_note'
            return 1

        # check if current element is start of a new section
        if ele_track_offset in sec_start_offsets:
            return 1

        return 0


    def ele_is_sec_end(self, ele_dur: float, ele_track_offset: float, sec_end_offsets: list) -> int:

        if ele_dur + ele_track_offset in sec_end_offsets:
            return 1

        #NOTE: don't need to add more conditions, because ele_is_sec_start() deals with them

        return 0


    def add_note_rest_info(self, ele: Union[m21.note.Note, m21.note.Rest], track_offset:float) -> None:

        # append ids
        self.data_dict['notes']['note_id'].append(self.create_ids(self.id_prefix, mode='note', ele=ele))
        self.data_dict['notes']['sec_id'].append(self.id_dict['current_sec_id'])
        self.data_dict['notes']['mp_id'].append(self.id_dict['current_mp_id'])
        self.data_dict['notes']['chord_id'].append(self.id_dict['current_chord_id'])

        # other details
        self.data_dict['notes']['note_name'].append(ele.name)
        self.data_dict['notes']['duration'].append(float(ele.duration.quarterLength))  # 'float()' will automatically turn any tuple rhythm (fractions.Fraction) to a float value
        self.data_dict['notes']['measure'].append(int(ele.measureNumber))
        self.data_dict['notes']['beat'].append(float(ele.beat))
        self.data_dict['notes']['note_start_offset'].append(track_offset)
        self.data_dict['notes']['note_end_offset'].append(track_offset + ele.duration.quarterLength)
        self.data_dict['notes']['note_start_m1b1_offset'].append(track_offset - self.m1b1_factor)
        self.data_dict['notes']['note_end_m1b1_offset'].append(track_offset + ele.duration.quarterLength - self.m1b1_factor)
        self.data_dict['notes']['mp_start_note'].append(1 if track_offset in self.offset_dict['mp_start_offsets'] else 0)
        self.data_dict['notes']['mp_end_note'].append(1 if track_offset in self.offset_dict['mp_end_note_start_offsets'] else 0)
        self.data_dict['notes']['sec_start_note'].append(self.ele_is_sec_start(track_offset, self.offset_dict['sec_start_offsets'], self.id_dict['current_sec_id']))
        self.data_dict['notes']['sec_end_note'].append(self.ele_is_sec_end(float(ele.duration.quarterLength), track_offset, self.offset_dict['sec_end_offsets']))

        return None


    def add_note_only_info(self, ele: m21.note.Note, track_offset: float) -> None:
        self.data_dict['notes']['octave'].append(ele.octave)
        self.data_dict['notes']['midi_num'].append(ele.pitch.midi)
        self.data_dict['notes']['pitch_class'].append(ele.pitch.pitchClass)
        self.data_dict['notes']['nct'].append(self.get_nct(ele, self.id_dict['current_chord']))
        self.data_dict['notes']['dist_from_root'].append(self.get_dist_from_root(ele, self.id_dict['current_chord']))

        prev_note_dist, prev_note_dir, prev_note_dist_type = self.get_prev_note_dist(ele, track_offset)
        self.data_dict['notes']['prev_note_distance'].append(prev_note_dist)
        self.data_dict['notes']['prev_note_direction'].append(prev_note_dir)
        self.data_dict['notes']['prev_note_distance_type'].append(prev_note_dist_type)

        return None


    def add_rest_info(self) -> None:
        self.data_dict['notes']['octave'].append(-1)
        self.data_dict['notes']['midi_num'].append(-1)
        self.data_dict['notes']['pitch_class'].append(-1)
        self.data_dict['notes']['nct'].append(-1)
        self.data_dict['notes']['dist_from_root'].append(-1)
        self.data_dict['notes']['prev_note_distance'].append(-100)
        self.data_dict['notes']['prev_note_direction'].append('-1')
        self.data_dict['notes']['prev_note_distance_type'].append('-1')

        return None


    def note_rest_input(self, ele: Union[m21.note.Note, m21.note.Rest]) -> None:

        track_offset = self.get_track_offset(ele)

        # check if current element is start of new section
        if self.check_new_sec_mp(track_offset, self.offset_dict['sec_start_offsets'], self.id_dict['current_sec_index']):
            self.id_dict['current_sec_index'] += 1
            self.id_dict['current_sec_id'] = self.create_ids(
                self.id_prefix, mode='sec', ele=self.rehearsal_marks[self.id_dict['current_sec_index']],
                index_num=self.id_dict['current_sec_index'], offsets=self.offset_dict['sec_start_offsets']
            )

        # check if current element is start of a new melodic phrase
        if self.check_new_sec_mp(track_offset, self.offset_dict['mp_start_offsets'], self.id_dict['current_mp_index']):
            self.id_dict['current_mp_index'] = np.where(
                (np.greater_equal(track_offset, self.offset_dict['mp_start_offsets']) == True) &
                (np.less(track_offset, self.offset_dict['mp_end_note_end_offsets']) == True)
            )[0][0]
            self.id_dict['current_mp_id'] = self.create_ids(
                self.id_prefix, mode='mp', ele=None, index_num=self.id_dict['current_mp_index'],
                offsets=self.offset_dict['mp_start_offsets']
            )

        # check if current element is first element between mp's
        if self.check_between_mps(self.offset_dict['mp_end_note_start_offsets']):
            self.id_dict['current_mp_index'] = -1
            self.id_dict['current_mp_id'] = None

        # check if current element and previous element are both rests - combine them if so, and exit function
        if isinstance(ele, m21.note.Rest) and track_offset > 0.0:
            if self.data_dict['notes']['midi_num'][-1] == -1:
                self.data_dict['notes']['duration'][-1] += ele.duration.quarterLength
                self.data_dict['notes']['note_end_offset'][-1] += ele.duration.quarterLength
                self.data_dict['notes']['note_end_m1b1_offset'][-1] += ele.duration.quarterLength

                # check if it's also the final element of the track - make it a sec_end_note if so
                if ele.duration.quarterLength + track_offset == self.track_dur:
                    self.data_dict['notes']['sec_end_note'][-1] = 1
                return None

        # add data to dictionary that is same for both rests and notes
        self.add_note_rest_info(ele, track_offset)

        # get data that is relevant for notes only
        if isinstance(ele, m21.note.Note):
            self.add_note_only_info(ele, track_offset)

        # fill in fields that are not relevant to rests
        if isinstance(ele, m21.note.Rest):
            self.add_rest_info()

        return None


    # the following class methods are for inputing values into the 'chords' dictionary
    def get_chord_pitches(self, chord: Union[m21.harmony.ChordSymbol, m21.harmony.NoChord]) -> str:
        return ",".join([p.name.lower() for p in chord.notes])


    def get_chord_degrees(self, chord: Union[m21.harmony.ChordSymbol, m21.harmony.NoChord]) -> str:
        return ",".join([d for d in chord._degreesList])


    def get_prev_chord_rb_dist(self, curr_root: int, curr_bass: int, prev_root: int, prev_bass: int) -> tuple:

        # return -100 if current chord is first chord or No Chord, or previous chord is No Chord
        if -1 in locals().values():
            return (-100, -100)

        # get absolute distance
        prev_root_dist = np.abs([curr_root - prev_root, (curr_root - 12) - prev_root, curr_root - (prev_root-12)]).min()
        prev_bass_dist = np.abs([curr_bass - prev_bass, (curr_bass - 12) - prev_bass, curr_bass - (prev_bass-12)]).min()

        # determine which condition was used
        prev_root_dist_cond = np.abs([curr_root - prev_root, (curr_root - 12) - prev_root, curr_root - (prev_root-12)]).argmin()
        prev_bass_dist_cond = np.abs([curr_bass - prev_bass, (curr_bass - 12) - prev_bass, curr_bass - (prev_bass-12)]).argmin()

        # for 1st condition - make it negative if current root / bass is lower than prev root / bass
        if prev_root_dist_cond == 0:
            prev_root_dist = -prev_root_dist if prev_root > curr_root else prev_root_dist
        if prev_bass_dist_cond == 0:
            prev_bass_dist = -prev_bass_dist if prev_bass > curr_bass else prev_bass_dist

        # for 2nd and 3rd conditions - make it negative if current root / bass is higher than prev root / bass
        if prev_root_dist_cond == 1 or prev_root_dist_cond == 2:
            prev_root_dist = -prev_root_dist if curr_root > prev_root else prev_root_dist
        if prev_bass_dist_cond == 1 or prev_bass_dist_cond == 2:
            prev_bass_dist = -prev_bass_dist if curr_bass > prev_bass else prev_bass_dist

        return (int(prev_root_dist), int(prev_bass_dist))


    def input_chord_end_offset_info(self, chord_start_offsets: list, track_duration: float, m1b1_factor: float) -> None:
        "Input chord_dur, chord_end_offset, and chord_end_m1b1_offset lists into data_dict's chords dictionary"

        # create numpy arrays
        chord_start_offsets = np.array(chord_start_offsets)
        chord_end_offsets = np.append(chord_start_offsets[1:], track_duration)
        chord_durations = chord_end_offsets - chord_start_offsets
        chord_end_m1b1_offsets = chord_end_offsets - m1b1_factor
        # return (chord_durations.tolist(), chord_end_offsets.tolist(), chord_end_m1b1_offsets.tolist())

        # insert into data_dict
        self.data_dict['chords']['chord_dur'] = chord_durations.tolist()
        self.data_dict['chords']['chord_end_offset'] = chord_end_offsets.tolist()
        self.data_dict['chords']['chord_end_m1b1_offset'] = chord_end_m1b1_offsets.tolist()

        return None


    def chord_input(self, ele: Union[m21.harmony.ChordSymbol, m21.harmony.NoChord]) -> None:
        track_offset = self.get_track_offset(ele)

        # update chord id - no checks needed, do for every chord symbol, even if the chord is repeated
        self.id_dict['current_chord'] = ele
        self.id_dict['current_chord_id'] = self.create_ids(
            self.id_prefix, mode='chord', ele=ele
        )

        # update hp id - only need to check if chord's offset is in hp_start_offsets
        if track_offset in self.offset_dict['hp_start_offsets']:
            self.id_dict['current_hp_index'] += 1
            self.id_dict['current_hp_id'] = self.create_ids(
                self.id_prefix, mode='hp', index_num=self.id_dict['current_hp_index'],
                offsets=self.offset_dict['hp_start_offsets']
            )

        # ensure correct section_id
        ## if both a chord and note / rest have same offset as a section, recurse may start with chord,
        ## assigning it the previous section_id.  This code prevents that
        if track_offset in self.offset_dict["sec_start_offsets"]:
            current_sec_id = self.offset_dict["sec_offset_to_sec_id"][track_offset]
        else:
            current_sec_id = self.id_dict['current_sec_id']

        # input data into chords dictionary
        self.data_dict['chords']['chord_id'].append(self.id_dict['current_chord_id'])
        self.data_dict['chords']['sec_id'].append(current_sec_id)
        self.data_dict['chords']['hp_id'].append(self.id_dict['current_hp_id'])
        self.data_dict['chords']['chord_name'].append(ele.figure)
        self.data_dict['chords']['chord_kind'].append(ele.chordKind)
        ele_root = ele.root()
        ele_bass = ele.bass()
        self.data_dict['chords']['chord_root_name'].append(ele_root.name if ele_root is not None else '-1')
        self.data_dict['chords']['chord_bass_name'].append(ele_bass.name if ele_bass is not None else '-1')
        self.data_dict['chords']['chord_root_pc'].append(ele_root.pitchClass if ele_root is not None else -1)  # None if it's N.C. - for prev_chord stuff later
        self.data_dict['chords']['chord_bass_pc'].append(ele_bass.pitchClass if ele_bass is not None else -1)  # None if it's N.C.
        self.data_dict['chords']['pitches'].append(
            self.get_chord_pitches(ele) if isinstance(ele, m21.harmony.ChordSymbol) else None
        )
        self.data_dict['chords']['degrees'].append(
            self.get_chord_degrees(ele) if isinstance(ele, m21.harmony.ChordSymbol) else None
        )
        self.data_dict['chords']['measure'].append(ele.measureNumber)
        self.data_dict['chords']['beat'].append(ele.beat)
        self.data_dict['chords']['chord_start_offset'].append(self.get_track_offset(ele))
        self.data_dict['chords']['chord_start_m1b1_offset'].append(self.get_track_offset(ele) - self.m1b1_factor)
        self.data_dict['chords']['n_pitches'].append(len(ele.notes))

        try:
            prev_chord_root = self.data_dict['chords']['chord_root_pc'][-2]  # -2 because current chord's root has already been added
            prev_chord_bass = self.data_dict['chords']['chord_bass_pc'][-2]
            prev_chord_quality = self.data_dict['chords']['chord_kind'][-2]
        except IndexError:  # if we're at the beginning of the piece
            prev_chord_root = -1
            prev_chord_bass = -1
            prev_chord_quality = 'none'  # 'none' is what m21 returns from NoChord().chordKind

        prev_root_dist, prev_bass_dist = self.get_prev_chord_rb_dist(
            self.data_dict['chords']['chord_root_pc'][-1],
            self.data_dict['chords']['chord_bass_pc'][-1],
            prev_chord_root,
            prev_chord_bass
        )
        self.data_dict['chords']['prev_chord_elongation'].append(
            1 if any((prev_root_dist == 0, prev_bass_dist == 0)) else 0
        )
        self.data_dict['chords']['prev_chord_root_dist'].append(prev_root_dist)  # -100 means NaN
        self.data_dict['chords']['prev_chord_bass_dist'].append(prev_bass_dist)
        self.data_dict['chords']['prev_chord_rb_same_qual_diff'].append(
            1 if all((prev_root_dist == 0, prev_bass_dist==0, prev_chord_quality!=ele.chordKind)) else 0
        )
        self.data_dict['chords']['prev_chord_root_same_bass_diff'].append(
            1 if all((prev_root_dist == 0, prev_bass_dist != 0)) else 0
        )
        self.data_dict['chords']['prev_chord_bass_same_root_diff'].append(
            1 if all((prev_root_dist != 0, prev_bass_dist == 0)) else 0
        )

        return None


    # the following class methods are for inputing values into the comprehensive dictionaries
    def get_start_end_ids(self, df: pd.DataFrame, offset_col: str, id_col: str) -> tuple:
        id_min = df.loc[df[offset_col].idxmin(), id_col]
        id_max = df.loc[df[offset_col].idxmax(), id_col]
        return (id_min, id_max)


    def get_second_most_common_dur(self, notes_df: pd.DataFrame, most_common_dur_list: list) -> list:
        second_most_common_dur = []
        second_most_common_dur_count = 0

        for dur, count in notes_df["duration"].value_counts().iteritems():
            if dur in most_common_dur_list:
                continue
            elif count >= second_most_common_dur_count:
                second_most_common_dur.append(dur)
                second_most_common_dur_count = count
            else:
                break

        return second_most_common_dur


    def find_chorus(self, track_dfs: Mapping[str, pd.DataFrame]) -> tuple:
        """
        Get section id for chorus and index for chorus's data in data_dict
        Chorus is the first section named "chorus", or first section after intro
        """
        chorus_idxs = np.where(
            (track_dfs["sections"]["sec_name"].str.lower().str.contains("chorus"))
            & (~track_dfs["sections"]["sec_name"].str.lower().str.contains("pre|post"))
        )[0]
        if len(chorus_idxs) == 0:
            chorus_idx = np.where(~track_dfs["sections"]["sec_name"].str.lower().str.contains("intro"))[0][0]
        else:
            chorus_idx = chorus_idxs[0]
        chorus_id = track_dfs["sections"].loc[chorus_idx, "sec_id"]

        return (chorus_id, chorus_idx)


    def comprehensive_track_section_input(self, df_dict: Mapping[str, pd.DataFrame], mode: str) -> None:
        if mode == "track":
            current_id = df_dict["tracks"]["track_id"].iloc[0]
            field = mode
        elif mode == "section":
            current_id = df_dict["sections"]["sec_id"].iloc[0]
            field = "sec"
        else:
            raise ValueError("Invalid mode.  Please use either 'track' or 'section'")

        ### form table
        self.data_dict[f"{mode}s_form"][f"{field}_id"].append(current_id)

        # start and end ids
        notes_only_df = df_dict["notes"][df_dict["notes"]["note_name"] != "rest"]
        chords_only_df = df_dict["chords"][df_dict["chords"]["chord_name"] != "N.C."]

        if len(notes_only_df) == 0:
            notes_only_df_values = {
                "note_id": "-1", "sec_id": current_id, "mp_id": "-1", "chord_id": "-1", "note_name": "-1", "octave": -1,
                "midi_num": -1, "pitch_class": -1, "duration": 0, "measure": -1, "beat": -1, "note_start_offset": -100,
                "note_end_offset": -100, "note_start_m1b1_offset": -100, "note_end_m1b1_offset": -100, "nct": -1,
                "dist_from_root": -1, "mp_start_note": -1, "mp_end_note": -1, "sec_start_note": -1, "sec_end_note": -1,
                "prev_note_distance": -100, "prev_note_direction": "-1", "prev_note_distance_type": "-1"
            }
            assert(list(notes_only_df.columns) == list(notes_only_df_values.keys())), "Mismatched column names, check notes_only_df_values variable"
            notes_only_df = pd.DataFrame(notes_only_df_values, index=[0])

        if len(chords_only_df) == 0:  # empty chords_only_df is untested, need to check at some point
            chords_only_df_values = {
                "chord_id": "-1", "sec_id": current_id, "hp_id": "-1", "chord_name": "-1", "chord_kind": "-1",
                "chord_root_name": "-1", "chord_bass_name": "-1", "chord_root_pc": -1, "chord_bass_pc": -1,
                "pitches": "-1", "degrees": "-1", "chord_dur": 0, "measure": -1, "beat": -1, "chord_start_offset": -100,
                "chord_end_offset": -100, "chord_start_m1b1_offset": -100, "chord_end_m1b1_offset": -100, "n_pitches": -1,
                "prev_chord_elongation": -1, "prev_chord_root_dist": -100, "prev_chord_bass_dist": -100,
                "prev_chord_rb_same_qual_diff": -1, "prev_chord_root_same_bass_diff": -1, "prev_chord_bass_same_root_diff": -1
            }
            assert(list(chords_only_df.columns) == list(chords_only_df_values.keys())), "Mismatched column names, check notes_only_df_values variable"
            chords_only_df = pd.DataFrame(chords_only_df_values, index=[0])

        if len(df_dict["melodic_phrases"]) == 0:
            mp_df_values = {
                "mp_id": "-1", "sec_id": current_id, "mp_num_in_sec": -1, "mp_total_dur": 0, "mp_start_offset": -100,
                "mp_end_offset": -100, "mp_start_m1b1_offset": -100, "mp_end_m1b1_offset": -100
            }
            assert(list(df_dict["melodic_phrases"].columns) == list(mp_df_values.keys())), "Mismatched column names, check notes_only_df_values variable"
            df_dict["melodic_phrases"] = pd.DataFrame(mp_df_values, index=[0])

        start_note_id, end_note_id = self.get_start_end_ids(notes_only_df, "note_start_offset", "note_id")
        start_chord_id, end_chord_id = self.get_start_end_ids(chords_only_df, "chord_start_offset", "chord_id")

        self.data_dict[f"{mode}s_form"][f"{field}_start_note_id"].append(start_note_id)
        self.data_dict[f"{mode}s_form"][f"{field}_end_note_id"].append(end_note_id)
        self.data_dict[f"{mode}s_form"][f"{field}_start_chord_id"].append(start_chord_id)
        self.data_dict[f"{mode}s_form"][f"{field}_end_chord_id"].append(end_chord_id)

        # durations
        total_dur = df_dict["notes"]["duration"].sum()
        note_dur = notes_only_df["duration"].sum()
        rest_dur = total_dur - note_dur
        self.data_dict[f"{mode}s_form"][f"{field}_note_dur"].append(note_dur)
        self.data_dict[f"{mode}s_form"][f"{field}_note_dur_pct"].append(note_dur / total_dur)
        self.data_dict[f"{mode}s_form"][f"{field}_rest_dur"].append(rest_dur)
        self.data_dict[f"{mode}s_form"][f"{field}_rest_dur_pct"].append(rest_dur / total_dur)

        # mp rest durations
        notes_in_mp_df = df_dict["notes"][df_dict["notes"]["mp_id"].notna()]
        notes_between_mp_df = df_dict["notes"][df_dict["notes"]["mp_id"].isna()]
        rest_dur_in_mps = notes_in_mp_df[notes_in_mp_df["note_name"]=="rest"]["duration"].sum()
        rest_dur_between_mps = rest_dur - rest_dur_in_mps
        self.data_dict[f"{mode}s_form"][f"{field}_rest_dur_in_mps"].append(rest_dur_in_mps)
        self.data_dict[f"{mode}s_form"][f"{field}_rest_dur_in_mps_pct"].append(rest_dur_in_mps / rest_dur)
        self.data_dict[f"{mode}s_form"][f"{field}_rest_dur_between_mps"].append(rest_dur_between_mps)
        self.data_dict[f"{mode}s_form"][f"{field}_rest_dur_between_mps_pct"].append(rest_dur_between_mps / rest_dur)

        rest_dur_in_mps_series = notes_in_mp_df[notes_in_mp_df["note_name"]=="rest"][["mp_id", "duration"]] \
            .groupby("mp_id")["duration"].sum()
        self.data_dict[f"{mode}s_form"][f"{field}_avg_rest_dur_in_mps"].append(rest_dur_in_mps_series.mean())
        self.data_dict[f"{mode}s_form"][f"{field}_med_rest_dur_in_mps"].append(rest_dur_in_mps_series.median())

        note_mp_df = df_dict["notes"][["mp_id", "note_name", "duration"]].copy()
        note_mp_df["mp_id"] = note_mp_df["mp_id"].fillna("none")  # 'adjacent' counts sequential NA's as different
        note_mp_df["adjacent"] = (note_mp_df["mp_id"] != note_mp_df["mp_id"].shift(1)).cumsum()
        rest_dur_between_mps_series = note_mp_df[(note_mp_df["mp_id"]=="none") & (note_mp_df["note_name"]=="rest")][["adjacent", "duration"]] \
            .groupby("adjacent")["duration"].sum()
        self.data_dict[f"{mode}s_form"][f"{field}_avg_rest_dur_between_mps"].append(rest_dur_between_mps_series.mean())
        self.data_dict[f"{mode}s_form"][f"{field}_med_rest_dur_between_mps"].append(rest_dur_between_mps_series.median())

        # phrases
        self.data_dict[f"{mode}s_form"][f"{field}_n_mps"] \
            .append(df_dict["melodic_phrases"][df_dict["melodic_phrases"]["mp_id"]!="-1"]["mp_id"].count())
        self.data_dict[f"{mode}s_form"][f"{field}_n_hps"].append(df_dict["harmonic_phrases"]["hp_id"].count())

        unique_mp_df = df_dict["notes"][["mp_id", "midi_num", "duration"]] \
            .groupby("mp_id")[["midi_num", "duration"]].agg(list)
        unique_hp_df = df_dict["chords"][["hp_id", "chord_name", "chord_dur"]] \
            .groupby("hp_id")[["chord_name", "chord_dur"]].agg(list)
        n_unique_mps = (unique_mp_df["midi_num"] + unique_mp_df["duration"]).astype(str).nunique()  # ignore harmony and beat
        n_unique_hps = (unique_hp_df["chord_name"] + unique_hp_df["chord_dur"]).astype(str).nunique()  # ignore harmony and beat
        self.data_dict[f"{mode}s_form"][f"{field}_n_unique_mps"].append(n_unique_mps)
        self.data_dict[f"{mode}s_form"][f"{field}_n_unique_hps"].append(n_unique_hps)

        self.data_dict[f"{mode}s_form"][f"{field}_avg_mp_dur"].append(df_dict["melodic_phrases"]["mp_total_dur"].mean())
        self.data_dict[f"{mode}s_form"][f"{field}_avg_hp_dur"].append(df_dict["harmonic_phrases"]["hp_total_dur"].mean())
        self.data_dict[f"{mode}s_form"][f"{field}_med_mp_dur"].append(df_dict["melodic_phrases"]["mp_total_dur"].median())
        self.data_dict[f"{mode}s_form"][f"{field}_med_hp_dur"].append(df_dict["harmonic_phrases"]["hp_total_dur"].median())
        self.data_dict[f"{mode}s_form"][f"{field}_std_mp_dur"].append(df_dict["melodic_phrases"]["mp_total_dur"].std())
        self.data_dict[f"{mode}s_form"][f"{field}_std_hp_dur"].append(df_dict["harmonic_phrases"]["hp_total_dur"].std())

        # n notes and rests
        self.data_dict[f"{mode}s_form"][f"{field}_n_notes"].append(len(notes_only_df[notes_only_df["note_id"]!="-1"]))
        self.data_dict[f"{mode}s_form"][f"{field}_n_chords"].append(len(chords_only_df[chords_only_df["chord_id"]!="-1"]))

        if mode == "section":

            start_mp_id, end_mp_id = self.get_start_end_ids(df_dict["melodic_phrases"], "mp_start_offset", "mp_id")
            self.data_dict[f"{mode}s_form"][f"{field}_start_mp_id"].append(start_mp_id)
            self.data_dict[f"{mode}s_form"][f"{field}_end_mp_id"].append(end_mp_id)

            sec_avg_mp_dur = self.data_dict["sections_form"]["sec_avg_mp_dur"][-1]
            sec_avg_hp_dur = self.data_dict["sections_form"]["sec_avg_hp_dur"][-1]
            sec_med_mp_dur = self.data_dict["sections_form"]["sec_med_mp_dur"][-1]
            sec_med_hp_dur = self.data_dict["sections_form"]["sec_med_hp_dur"][-1]

            track_avg_mp_dur = self.data_dict["tracks_form"]["track_avg_mp_dur"][-1]
            track_avg_hp_dur = self.data_dict["tracks_form"]["track_avg_hp_dur"][-1]
            track_med_mp_dur = self.data_dict["tracks_form"]["track_med_mp_dur"][-1]
            track_med_hp_dur = self.data_dict["tracks_form"]["track_med_hp_dur"][-1]

            self.data_dict[f"{mode}s_form"][f"{field}_to_track_avg_mp_dur"].append(sec_avg_mp_dur / track_avg_mp_dur)
            self.data_dict[f"{mode}s_form"][f"{field}_to_track_avg_hp_dur"].append(sec_avg_hp_dur / track_avg_hp_dur)
            self.data_dict[f"{mode}s_form"][f"{field}_to_track_med_mp_dur"].append(sec_med_mp_dur / track_med_mp_dur)
            self.data_dict[f"{mode}s_form"][f"{field}_to_track_med_hp_dur"].append(sec_med_hp_dur / track_med_hp_dur)


        ### melody table
        self.data_dict[f"{mode}s_melody"][f"{field}_id"].append(current_id)

        # range
        lowest_pitch = m21.pitch.Pitch(midi=notes_only_df["midi_num"].min())
        highest_pitch = m21.pitch.Pitch(midi=notes_only_df["midi_num"].max())
        range_interval = m21.interval.Interval(lowest_pitch, highest_pitch)

        self.data_dict[f"{mode}s_melody"][f"{field}_range_interval"].append(range_interval.name)
        self.data_dict[f"{mode}s_melody"][f"{field}_range_midi"].append(range_interval.semitones)
        self.data_dict[f"{mode}s_melody"][f"{field}_highest_note_midi"].append(highest_pitch.midi)
        self.data_dict[f"{mode}s_melody"][f"{field}_lowest_note_midi"].append(lowest_pitch.midi)

        first_highest_note_id = notes_only_df[notes_only_df["midi_num"]==highest_pitch.midi]["note_id"]
        first_highest_note_id = "-1" if len(first_highest_note_id)==0 else first_highest_note_id.iloc[0]
        first_lowest_note_id = notes_only_df[notes_only_df["midi_num"]==lowest_pitch.midi]["note_id"]
        first_lowest_note_id = "-1" if len(first_lowest_note_id)==0 else first_lowest_note_id.iloc[0]
        self.data_dict[f"{mode}s_melody"][f"{field}_first_highest_note_id"].append(first_highest_note_id)
        self.data_dict[f"{mode}s_melody"][f"{field}_first_lowest_note_id"].append(first_lowest_note_id)

        first_highest_note_offset = notes_only_df[notes_only_df["midi_num"]==highest_pitch.midi]["note_start_offset"]
        first_highest_note_offset = -100 if len(first_highest_note_offset)==0 else first_highest_note_offset.iloc[0]
        first_lowest_note_offset = notes_only_df[notes_only_df["midi_num"]==lowest_pitch.midi]["note_start_offset"]
        first_lowest_note_offset = -100 if len(first_lowest_note_offset)==0 else first_lowest_note_offset.iloc[0]
        self.data_dict[f"{mode}s_melody"][f"pct_into_{field}_first_highest_note"].append(first_highest_note_offset / self.track_dur)
        self.data_dict[f"{mode}s_melody"][f"pct_into_{field}_first_lowest_note"].append(first_lowest_note_offset / self.track_dur)
        self.data_dict[f"{mode}s_melody"][f"{field}_med_mp_highest_note"] \
            .append(notes_only_df[["mp_id", "midi_num"]].groupby("mp_id")["midi_num"].max().median())
        self.data_dict[f"{mode}s_melody"][f"{field}_med_mp_lowest_note"] \
            .append(notes_only_df[["mp_id", "midi_num"]].groupby("mp_id")["midi_num"].min().median())

        n_highest_note = len(notes_only_df[notes_only_df["midi_num"]==highest_pitch.midi])
        dur_on_highest_note = notes_only_df[notes_only_df["midi_num"]==highest_pitch.midi]["duration"].sum()
        dur_on_highest_note_pct = np.nan if notes_only_df["duration"].sum()==0 else dur_on_highest_note / notes_only_df["duration"].sum()
        self.data_dict[f"{mode}s_melody"][f"{field}_n_highest_note"].append(n_highest_note)
        self.data_dict[f"{mode}s_melody"][f"{field}_dur_on_highest_note"].append(dur_on_highest_note)
        self.data_dict[f"{mode}s_melody"][f"{field}_dur_on_highest_note_pct"].append(dur_on_highest_note_pct)
        self.data_dict[f"{mode}s_melody"][f"{field}_n_notes_on_highest_note_pct"].append(n_highest_note / len(notes_only_df))

        n_lowest_note = len(notes_only_df[notes_only_df["midi_num"]==lowest_pitch.midi])
        dur_on_lowest_note = notes_only_df[notes_only_df["midi_num"]==lowest_pitch.midi]["duration"].sum()
        dur_on_lowest_note_pct = np.nan if notes_only_df["duration"].sum()==0 else dur_on_lowest_note / notes_only_df["duration"].sum()
        self.data_dict[f"{mode}s_melody"][f"{field}_n_lowest_note"].append(n_lowest_note)
        self.data_dict[f"{mode}s_melody"][f"{field}_dur_on_lowest_note"].append(dur_on_lowest_note)
        self.data_dict[f"{mode}s_melody"][f"{field}_dur_on_lowest_note_pct"].append(dur_on_lowest_note_pct)
        self.data_dict[f"{mode}s_melody"][f"{field}_n_notes_on_lowest_note_pct"].append(n_lowest_note / len(notes_only_df))

        # pitch
        most_common_pitch_list = notes_only_df["midi_num"].mode().values.tolist()
        self.data_dict[f"{mode}s_melody"][f"{field}_avg_pitch"].append(notes_only_df["midi_num"].mean().round(0).astype(int))
        self.data_dict[f"{mode}s_melody"][f"{field}_most_common_pitch"] \
            .append(", ".join([str(pitch) for pitch in most_common_pitch_list]))
        self.data_dict[f"{mode}s_melody"][f"{field}_most_common_pitch_pct"] \
            .append(len(notes_only_df[notes_only_df["midi_num"].isin(most_common_pitch_list)]) / len(notes_only_df))

        # duration
        most_common_note_dur_list = notes_only_df["duration"].mode().values.tolist()
        second_most_common_note_dur_list = self.get_second_most_common_dur(notes_only_df, most_common_note_dur_list)
        self.data_dict[f"{mode}s_melody"][f"{field}_longest_note_dur"].append(notes_only_df["duration"].max())
        self.data_dict[f"{mode}s_melody"][f"{field}_most_common_note_dur"] \
            .append(", ".join([str(dur) for dur in most_common_note_dur_list]))
        self.data_dict[f"{mode}s_melody"][f"{field}_most_common_note_dur_pct"] \
            .append(len(notes_only_df[notes_only_df["duration"].isin(most_common_note_dur_list)]) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_second_most_common_note_dur"] \
            .append(", ".join([str(dur) for dur in second_most_common_note_dur_list]))
        self.data_dict[f"{mode}s_melody"][f"{field}_second_most_common_note_dur_pct"] \
            .append(len(notes_only_df[notes_only_df["duration"].isin(second_most_common_note_dur_list)]) / len(notes_only_df))

        # nct
        n_nct_notes = (notes_only_df["nct"]==1).sum()
        dur_nct_notes = notes_only_df[notes_only_df["nct"]==1]["duration"].sum()
        dur_nct_notes_pct = np.nan if notes_only_df["duration"].sum()==0 else dur_nct_notes / notes_only_df["duration"].sum()
        self.data_dict[f"{mode}s_melody"][f"{field}_n_nct_notes"].append(n_nct_notes)
        self.data_dict[f"{mode}s_melody"][f"{field}_dur_nct_notes"].append(dur_nct_notes)
        self.data_dict[f"{mode}s_melody"][f"{field}_n_nct_notes_pct"].append(n_nct_notes / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_dur_nct_notes_pct"].append(dur_nct_notes_pct)

        # movement
        up_cond = notes_only_df["prev_note_direction"]=="up"
        down_cond = notes_only_df["prev_note_direction"]=="down"
        same_cond = notes_only_df["prev_note_direction"]=="same"
        step_cond = notes_only_df["prev_note_distance_type"]=="step"
        skip_cond = notes_only_df["prev_note_distance_type"]=="skip"
        leap_cond = notes_only_df["prev_note_distance_type"]=="leap"

        self.data_dict[f"{mode}s_melody"][f"{field}_up_pct"].append(sum(up_cond) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_down_pct"].append(sum(down_cond) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_same_pct"].append(sum(same_cond) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_up_step_pct"].append(sum(up_cond & step_cond) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_up_skip_pct"].append(sum(up_cond & skip_cond) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_up_leap_pct"].append(sum(up_cond & leap_cond) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_down_step_pct"].append(sum(down_cond & step_cond) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_down_skip_pct"].append(sum(down_cond & skip_cond) / len(notes_only_df))
        self.data_dict[f"{mode}s_melody"][f"{field}_down_leap_pct"].append(sum(down_cond & leap_cond) / len(notes_only_df))

        if mode == "section":
            track_highest_note = self.data_dict["tracks_melody"]["track_highest_note_midi"][-1]
            track_lowest_note = self.data_dict["tracks_melody"]["track_lowest_note_midi"][-1]
            track_longest_note = self.data_dict["tracks_melody"]["track_longest_note_dur"][-1]

            self.data_dict[f"{mode}s_melody"][f"{field}_has_track_highest_note"].append(notes_only_df["midi_num"].max() == track_highest_note)
            self.data_dict[f"{mode}s_melody"][f"{field}_has_track_lowest_note"].append(notes_only_df["midi_num"].min() == track_lowest_note)
            self.data_dict[f"{mode}s_melody"][f"{field}_has_track_longest_note"].append(notes_only_df["duration"].max() == track_longest_note)

        no_notes = len(notes_only_df[notes_only_df["note_id"]!="-1"]) == 0
        if no_notes:
            self.data_dict[f"{mode}s_melody"][f"{field}_range_interval"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_range_midi"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_highest_note_midi"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_lowest_note_midi"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"pct_into_{field}_first_highest_note"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"pct_into_{field}_first_lowest_note"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_med_mp_highest_note"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_med_mp_lowest_note"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_avg_pitch"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_most_common_pitch"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_most_common_pitch_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_second_most_common_note_dur"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_second_most_common_note_dur_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_n_nct_notes"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_dur_nct_notes"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_n_nct_notes_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_up_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_down_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_same_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_up_step_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_up_skip_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_up_leap_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_down_step_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_down_skip_pct"][-1] = np.nan
            self.data_dict[f"{mode}s_melody"][f"{field}_down_leap_pct"][-1] = np.nan

        ### harmony table
        self.data_dict[f"{mode}s_harmony"][f"{field}_id"].append(current_id)
        chord_center_cols = ["prev_chord_rb_same_qual_diff", "prev_chord_root_same_bass_diff", "prev_chord_bass_same_root_diff"]
        chords_only_df["new_chord_center"] = (chords_only_df[chord_center_cols].sum(axis=1)==0).cumsum()

        # durations
        self.data_dict[f"{mode}s_harmony"][f"{field}_avg_chord_dur"].append(chords_only_df["chord_dur"].mean())
        self.data_dict[f"{mode}s_harmony"][f"{field}_avg_chord_center_dur"] \
            .append(chords_only_df[["new_chord_center", "chord_dur"]].groupby("new_chord_center")["chord_dur"].sum().mean())
        self.data_dict[f"{mode}s_harmony"][f"{field}_avg_hp_dur"].append(df_dict["harmonic_phrases"]["hp_total_dur"].mean())
        self.data_dict[f"{mode}s_harmony"][f"{field}_med_chord_dur"].append(chords_only_df["chord_dur"].median())
        self.data_dict[f"{mode}s_harmony"][f"{field}_med_chord_center_dur"] \
            .append(chords_only_df[["new_chord_center", "chord_dur"]].groupby("new_chord_center")["chord_dur"].sum().median())
        self.data_dict[f"{mode}s_harmony"][f"{field}_med_hp_dur"].append(df_dict["harmonic_phrases"]["hp_total_dur"].median())

        # counts
        self.data_dict[f"{mode}s_harmony"][f"{field}_n_chords"].append(len(chords_only_df))
        self.data_dict[f"{mode}s_harmony"][f"{field}_n_unique_chords"].append(chords_only_df["chord_name"].nunique())
        self.data_dict[f"{mode}s_harmony"][f"{field}_n_chord_centers"].append(chords_only_df["new_chord_center"].nunique())

        # chord types
        self.data_dict[f"{mode}s_harmony"][f"{field}_pct_3_note_chords_or_fewer"] \
            .append(len(chords_only_df[chords_only_df["n_pitches"]<=3]) / len(chords_only_df))
        self.data_dict[f"{mode}s_harmony"][f"{field}_pct_4_note_chords_or_more"] \
            .append(len(chords_only_df[chords_only_df["n_pitches"]>3]) / len(chords_only_df))
        self.data_dict[f"{mode}s_harmony"][f"{field}_pct_maj_3_no_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["maj_3_no_7"]).sum() / len(chords_only_df))
        self.data_dict[f"{mode}s_harmony"][f"{field}_pct_min_3_no_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["min_3_no_7"]).sum() / len(chords_only_df))
        self.data_dict[f"{mode}s_harmony"][f"{field}_pct_maj_3_maj_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["maj_3_maj_7"]).sum() / len(chords_only_df))
        self.data_dict[f"{mode}s_harmony"][f"{field}_pct_min_3_min_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["min_3_min_7"]).sum() / len(chords_only_df))
        self.data_dict[f"{mode}s_harmony"][f"{field}_pct_maj_3_min_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["maj_3_min_7"]).sum() / len(chords_only_df))
        self.data_dict[f"{mode}s_harmony"][f"{field}_pct_other_quality"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["other"]).sum() / len(chords_only_df))

        return None


    def finish_comprehensive_section_input(
        self,
        track_dfs: Mapping[str, pd.DataFrame],
        all_sections_dfs: Sequence[Mapping[str, pd.DataFrame]],
    ) -> None:
        "Add fields that require comparison between the different sections"

        # identify chorus - first section named "chorus", or first section after intro
        chorus_id, chorus_idx = self.find_chorus(track_dfs)
        chorus_dfs = all_sections_dfs[chorus_idx]
        assert(chorus_dfs["sections"]["sec_id"].values[0] == chorus_id), "Chorus not identified, please investigate"

        # get chorus variables
        chorus_dur = self.data_dict["sections"]["sec_total_dur"][chorus_idx]
        chorus_avg_mp_dur = self.data_dict["sections_form"]["sec_avg_mp_dur"][chorus_idx]
        chorus_avg_hp_dur = self.data_dict["sections_form"]["sec_avg_hp_dur"][chorus_idx]
        chorus_med_mp_dur = self.data_dict["sections_form"]["sec_med_mp_dur"][chorus_idx]
        chorus_med_hp_dur = self.data_dict["sections_form"]["sec_med_hp_dur"][chorus_idx]
        chorus_range_midi = self.data_dict["sections_melody"]["sec_range_midi"][chorus_idx]
        chorus_highest_note = self.data_dict["sections_melody"]["sec_highest_note_midi"][chorus_idx]
        chorus_lowest_note = self.data_dict["sections_melody"]["sec_lowest_note_midi"][chorus_idx]
        widest_range = np.nanmax(self.data_dict["sections_melody"]["sec_range_midi"])
        narrowest_range = np.nanmin(self.data_dict["sections_melody"]["sec_range_midi"])
        chorus_first_chord_root = chorus_dfs["chords"]["chord_root_pc"].iloc[0]
        chorus_first_chord_bass = chorus_dfs["chords"]["chord_bass_pc"].iloc[0]

        last_note_offset = None

        for sec_idx in range(len(self.data_dict["sections"]["sec_id"])):
            sec_dfs = all_sections_dfs[sec_idx]

            sec_dur = self.data_dict["sections"]["sec_total_dur"][sec_idx]
            sec_avg_mp_dur = self.data_dict["sections_form"]["sec_avg_mp_dur"][sec_idx]
            sec_avg_hp_dur = self.data_dict["sections_form"]["sec_avg_hp_dur"][sec_idx]
            sec_med_mp_dur = self.data_dict["sections_form"]["sec_med_mp_dur"][sec_idx]
            sec_med_hp_dur = self.data_dict["sections_form"]["sec_med_hp_dur"][sec_idx]
            sec_range_midi = self.data_dict["sections_melody"]["sec_range_midi"][sec_idx]
            sec_highest_note = self.data_dict["sections_melody"]["sec_highest_note_midi"][sec_idx]
            sec_lowest_note = self.data_dict["sections_melody"]["sec_lowest_note_midi"][sec_idx]
            sec_has_widest_range = sec_range_midi == widest_range
            sec_has_narrowest_range = sec_range_midi == narrowest_range

            self.data_dict["sections_form"]["sec_to_chorus_dur"].append(sec_dur / chorus_dur)
            self.data_dict["sections_form"]["sec_to_chorus_avg_mp_dur"].append(sec_avg_mp_dur / chorus_avg_mp_dur)
            self.data_dict["sections_form"]["sec_to_chorus_avg_hp_dur"].append(sec_avg_hp_dur / chorus_avg_hp_dur)
            self.data_dict["sections_form"]["sec_to_chorus_med_mp_dur"].append(sec_med_mp_dur / chorus_med_mp_dur)
            self.data_dict["sections_form"]["sec_to_chorus_med_hp_dur"].append(sec_med_hp_dur / chorus_med_hp_dur)
            self.data_dict["sections_melody"]["sec_to_chorus_range_diff"].append(sec_range_midi - chorus_range_midi)
            self.data_dict["sections_melody"]["sec_to_chorus_highest_note_dist"].append(sec_highest_note - chorus_highest_note)
            self.data_dict["sections_melody"]["sec_to_chorus_lowest_note_dist"].append(sec_lowest_note - chorus_lowest_note)
            self.data_dict["sections_melody"]["sec_has_track_widest_range"].append(sec_has_widest_range)
            self.data_dict["sections_melody"]["sec_has_track_narrowest_range"].append(sec_has_narrowest_range)

            sec_first_chord_root = sec_dfs["chords"]["chord_root_pc"].iloc[0]
            sec_first_chord_bass = sec_dfs["chords"]["chord_bass_pc"].iloc[0]
            sec_to_chorus_first_chord_root_dist, sec_to_chorus_first_chord_bass_dist = self.get_prev_chord_rb_dist(
                sec_first_chord_root, sec_first_chord_bass, chorus_first_chord_root, chorus_first_chord_bass
            )
            self.data_dict["sections_harmony"]["sec_to_chorus_first_chord_root_dist"].append(sec_to_chorus_first_chord_root_dist)
            self.data_dict["sections_harmony"]["sec_to_chorus_first_chord_bass_dist"].append(sec_to_chorus_first_chord_bass_dist)

            notes_df = sec_dfs["notes"][sec_dfs["notes"]["note_name"] != "rest"]
            no_notes = len(notes_df) == 0
            if no_notes:  # section without notes
                self.data_dict["sections_form"]["rest_dur_before_sec_first_note"].append(np.nan)
                self.data_dict["sections_form"]["rest_dur_after_sec_last_note"].append(np.nan)
            elif last_note_offset is None:  # first section with notes
                first_note_start = notes_df["note_start_offset"].iloc[0]
                last_note_end = notes_df["note_end_offset"].iloc[-1]
                self.data_dict["sections_form"]["rest_dur_before_sec_first_note"].append(first_note_start)
                last_note_offset = last_note_end
            else:  # middle sections
                first_note_start = notes_df["note_start_offset"].iloc[0]
                rest_dur_before_sec = first_note_start - last_note_offset
                self.data_dict["sections_form"]["rest_dur_after_sec_last_note"].append(rest_dur_before_sec)
                self.data_dict["sections_form"]["rest_dur_before_sec_first_note"].append(rest_dur_before_sec)

                last_note_end = notes_df["note_end_offset"].iloc[-1]
                last_note_offset = last_note_end

                if sec_idx == len(self.data_dict["sections"]["sec_id"]) - 1:  # last section with notes
                    self.data_dict["sections_form"]["rest_dur_after_sec_last_note"].append(self.track_dur - last_note_end)


    def prepare_all_mps_dfs(self, track_dfs: Mapping[str, pd.DataFrame]) -> Sequence[Mapping[str, pd.DataFrame]]:
        all_mp_ids = track_dfs["melodic_phrases"]["mp_id"].values

        # get melodic_phrases and notes dfs
        all_mps_dfs = [
            {
                table: df[df["mp_id"]==mp_id] for table, df in track_dfs.items()
                if table == "melodic_phrases" or table == "notes"
            } for mp_id in all_mp_ids
        ]

        # get chords dfs
        for mp_dfs in all_mps_dfs:
            mp_start_offset = mp_dfs["melodic_phrases"]["mp_start_offset"].iloc[0]
            mp_end_offset = mp_dfs["melodic_phrases"]["mp_end_offset"].iloc[0]
            get_prev_chord = (track_dfs["chords"]["chord_start_offset"]==mp_start_offset).sum()==0

            mp_chords_idx = track_dfs["chords"][
                (track_dfs["chords"]["chord_start_offset"]>=mp_start_offset)
                & (track_dfs["chords"]["chord_start_offset"]<=mp_end_offset)
            ].index
            min_idx = mp_chords_idx.min()

            if get_prev_chord & min_idx > 0:
                prev_idx = min_idx - 1
                mp_chords_idx = [prev_idx] + list(mp_chords_idx)

            mp_chords_df = track_dfs["chords"].loc[mp_chords_idx].copy()
            mp_dfs["chords"] = mp_chords_df

        return all_mps_dfs


    def comprehensive_mp_input(self, mp_dfs: Mapping[str, pd.DataFrame]) -> None:
        # prepare variables
        mp_df = mp_dfs["melodic_phrases"].copy()
        mp_notes_df = mp_dfs["notes"].copy()
        notes_only_df = mp_notes_df[mp_notes_df["note_name"]!="rest"].copy()
        chords_only_df = mp_dfs["chords"][mp_dfs["chords"]["chord_name"] != "N.C."].copy()
        no_chords = len(chords_only_df)==0
        sec_idx = np.where(np.array(self.data_dict["sections"]["sec_id"])==mp_df["sec_id"].iloc[0])[0][0]

        # form
        start_note_id, end_note_id = self.get_start_end_ids(notes_only_df, "note_start_offset", "note_id")
        self.data_dict["melodic_phrases_details"]["mp_id"].append(mp_df["mp_id"].iloc[0])
        self.data_dict["melodic_phrases_details"]["mp_start_note_id"].append(start_note_id)
        self.data_dict["melodic_phrases_details"]["mp_end_note_id"].append(end_note_id)

        total_dur = mp_notes_df["duration"].sum()
        note_dur = notes_only_df["duration"].sum()
        rest_dur = total_dur - note_dur
        self.data_dict["melodic_phrases_details"]["mp_note_dur"].append(note_dur)
        self.data_dict["melodic_phrases_details"]["mp_note_dur_pct"].append(note_dur / total_dur)
        self.data_dict["melodic_phrases_details"]["mp_rest_dur"].append(rest_dur)
        self.data_dict["melodic_phrases_details"]["mp_rest_dur_pct"].append(rest_dur / total_dur)

        sec_start_offset = self.data_dict["sections"]["sec_start_offset"][sec_idx]
        mp_start_offset = mp_df["mp_start_offset"].iloc[0]
        self.data_dict["melodic_phrases_details"]["mp_start_section_offset"].append(mp_start_offset - sec_start_offset)

        track_avg_mp_dur = self.data_dict["tracks_form"]["track_avg_mp_dur"][-1]
        track_med_mp_dur = self.data_dict["tracks_form"]["track_med_mp_dur"][-1]
        self.data_dict["melodic_phrases_details"]["mp_to_track_avg_mp_dur"].append(total_dur / track_avg_mp_dur)
        self.data_dict["melodic_phrases_details"]["mp_to_track_med_mp_dur"].append(total_dur / track_med_mp_dur)

        # range
        lowest_pitch = m21.pitch.Pitch(midi=notes_only_df["midi_num"].min())
        highest_pitch = m21.pitch.Pitch(midi=notes_only_df["midi_num"].max())
        range_interval = m21.interval.Interval(lowest_pitch, highest_pitch)
        self.data_dict["melodic_phrases_details"]["mp_n_notes"].append(len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_range_interval"].append(range_interval.name)
        self.data_dict["melodic_phrases_details"]["mp_range_midi"].append(range_interval.semitones)
        self.data_dict["melodic_phrases_details"]["mp_highest_note_midi"].append(highest_pitch.midi)
        self.data_dict["melodic_phrases_details"]["mp_lowest_note_midi"].append(lowest_pitch.midi)

        track_highest_note = self.data_dict["tracks_melody"]["track_highest_note_midi"][-1]
        track_lowest_note = self.data_dict["tracks_melody"]["track_lowest_note_midi"][-1]
        self.data_dict["melodic_phrases_details"]["mp_has_track_highest_note"].append(highest_pitch.midi == track_highest_note)
        self.data_dict["melodic_phrases_details"]["mp_has_track_lowest_note"].append(lowest_pitch.midi == track_lowest_note)

        first_highest_note_offset = notes_only_df[notes_only_df["midi_num"]==highest_pitch.midi]["note_start_offset"].iloc[0] - mp_start_offset
        first_lowest_note_offset = notes_only_df[notes_only_df["midi_num"]==lowest_pitch.midi]["note_start_offset"].iloc[0] - mp_start_offset
        self.data_dict["melodic_phrases_details"]["pct_into_mp_first_highest_note"].append(first_highest_note_offset / total_dur)
        self.data_dict["melodic_phrases_details"]["pct_into_mp_first_lowest_note"].append(first_lowest_note_offset / total_dur)

        sec_highest_note = self.data_dict["sections_melody"]["sec_highest_note_midi"][sec_idx]
        sec_lowest_note = self.data_dict["sections_melody"]["sec_lowest_note_midi"][sec_idx]
        self.data_dict["melodic_phrases_details"]["has_sec_highest_note"].append(highest_pitch.midi == sec_highest_note)
        self.data_dict["melodic_phrases_details"]["has_sec_lowest_note"].append(lowest_pitch.midi == sec_lowest_note)

        n_highest_note = len(notes_only_df[notes_only_df["midi_num"]==highest_pitch.midi])
        n_lowest_note = len(notes_only_df[notes_only_df["midi_num"]==lowest_pitch.midi])
        dur_on_highest_note = notes_only_df[notes_only_df["midi_num"]==highest_pitch.midi]["duration"].sum()
        dur_on_lowest_note = notes_only_df[notes_only_df["midi_num"]==lowest_pitch.midi]["duration"].sum()
        self.data_dict["melodic_phrases_details"]["mp_n_highest_note"].append(n_highest_note)
        self.data_dict["melodic_phrases_details"]["mp_dur_on_highest_note"].append(dur_on_highest_note)
        self.data_dict["melodic_phrases_details"]["mp_n_notes_on_highest_note_pct"].append(n_highest_note / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_dur_on_highest_note_pct"].append(dur_on_highest_note / note_dur)
        self.data_dict["melodic_phrases_details"]["mp_n_lowest_note"].append(n_lowest_note)
        self.data_dict["melodic_phrases_details"]["mp_dur_on_lowest_note"].append(dur_on_lowest_note)
        self.data_dict["melodic_phrases_details"]["mp_n_notes_on_lowest_note_pct"].append(n_lowest_note / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_dur_on_lowest_note_pct"].append(dur_on_lowest_note / note_dur)

        # pitch
        most_common_pitch_list = notes_only_df["midi_num"].mode().values.tolist()
        self.data_dict["melodic_phrases_details"]["mp_avg_pitch"].append(notes_only_df["midi_num"].mean().round(0).astype(int))
        self.data_dict["melodic_phrases_details"]["mp_most_common_pitch"] \
            .append(", ".join([str(pitch) for pitch in most_common_pitch_list]))
        self.data_dict[f"melodic_phrases_details"]["mp_most_common_pitch_pct"] \
            .append(len(notes_only_df[notes_only_df["midi_num"].isin(most_common_pitch_list)]) / len(notes_only_df))

        # duration
        mp_longest_note = notes_only_df["duration"].max()
        sec_longest_note = self.data_dict["sections_melody"]["sec_longest_note_dur"][sec_idx]
        track_longest_note = self.data_dict["tracks_melody"]["track_longest_note_dur"][-1]
        most_common_note_dur_list = notes_only_df["duration"].mode().values.tolist()
        second_most_common_note_dur_list = self.get_second_most_common_dur(notes_only_df, most_common_note_dur_list)
        self.data_dict["melodic_phrases_details"]["mp_longest_note_dur"].append(mp_longest_note)
        self.data_dict["melodic_phrases_details"]["has_track_longest_note"].append(mp_longest_note==track_longest_note)
        self.data_dict["melodic_phrases_details"]["has_sec_longest_note"].append(mp_longest_note==sec_longest_note)
        self.data_dict["melodic_phrases_details"]["mp_most_common_note_dur"] \
            .append(", ".join([str(dur) for dur in most_common_note_dur_list]))
        self.data_dict["melodic_phrases_details"]["mp_most_common_note_dur_pct"] \
            .append(len(notes_only_df[notes_only_df["duration"].isin(most_common_note_dur_list)]) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_second_most_common_note_dur"] \
            .append(", ".join([str(dur) for dur in second_most_common_note_dur_list]))
        self.data_dict["melodic_phrases_details"]["mp_second_most_common_note_dur_pct"] \
            .append(len(notes_only_df[notes_only_df["duration"].isin(second_most_common_note_dur_list)]) / len(notes_only_df))

        # nct
        n_nct_notes = (notes_only_df["nct"]==1).sum()
        dur_nct_notes = notes_only_df[notes_only_df["nct"]==1]["duration"].sum()
        dur_nct_notes_pct = np.nan if notes_only_df["duration"].sum()==0 else dur_nct_notes / notes_only_df["duration"].sum()
        self.data_dict["melodic_phrases_details"]["mp_n_nct_notes"].append(n_nct_notes)
        self.data_dict["melodic_phrases_details"]["mp_dur_nct_notes"].append(dur_nct_notes)
        self.data_dict["melodic_phrases_details"]["mp_n_nct_notes_pct"].append(n_nct_notes / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_dur_nct_notes_pct"].append(dur_nct_notes_pct)

        # movement
        up_cond = notes_only_df["prev_note_direction"]=="up"
        down_cond = notes_only_df["prev_note_direction"]=="down"
        same_cond = notes_only_df["prev_note_direction"]=="same"
        step_cond = notes_only_df["prev_note_distance_type"]=="step"
        skip_cond = notes_only_df["prev_note_distance_type"]=="skip"
        leap_cond = notes_only_df["prev_note_distance_type"]=="leap"

        self.data_dict["melodic_phrases_details"]["mp_up_pct"].append(sum(up_cond) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_down_pct"].append(sum(down_cond) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_same_pct"].append(sum(same_cond) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_up_step_pct"].append(sum(up_cond & step_cond) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_up_skip_pct"].append(sum(up_cond & skip_cond) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_up_leap_pct"].append(sum(up_cond & leap_cond) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_down_step_pct"].append(sum(down_cond & step_cond) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_down_skip_pct"].append(sum(down_cond & skip_cond) / len(notes_only_df))
        self.data_dict["melodic_phrases_details"]["mp_down_leap_pct"].append(sum(down_cond & leap_cond) / len(notes_only_df))

        # harmony
        if no_chords:
            self.data_dict["melodic_phrases_details"]["mp_n_chords"].append(np.nan)
            self.data_dict["melodic_phrases_details"]["mp_avg_chord_dur"].append(np.nan)
            self.data_dict["melodic_phrases_details"]["mp_avg_chord_center_dur"].append(np.nan)
        else:
            chord_center_cols = ["prev_chord_rb_same_qual_diff", "prev_chord_root_same_bass_diff", "prev_chord_bass_same_root_diff"]
            chords_only_df["new_chord_center"] = (chords_only_df[chord_center_cols].sum(axis=1)==0).cumsum()
            self.data_dict["melodic_phrases_details"]["mp_n_chords"].append(len(chords_only_df))
            self.data_dict["melodic_phrases_details"]["mp_avg_chord_dur"].append(chords_only_df["chord_dur"].mean())
            self.data_dict["melodic_phrases_details"]["mp_avg_chord_center_dur"] \
                    .append(chords_only_df[["new_chord_center", "chord_dur"]].groupby("new_chord_center")["chord_dur"].sum().mean())

        return None


    def finish_comprehensive_mp_input(self, mp_df: pd.DataFrame) -> None:
        # rest durations between mps
        rest_dur_before_mp_list = (mp_df["mp_start_offset"] - mp_df["mp_end_offset"].shift(1)).fillna(mp_df["mp_start_offset"].iloc[0]).tolist()
        rest_dur_after_mp_list = (mp_df["mp_start_offset"].shift(-1, fill_value=self.track_dur) - mp_df["mp_end_offset"]).tolist()
        self.data_dict["melodic_phrases_details"]["rest_dur_before_mp"] = rest_dur_before_mp_list
        self.data_dict["melodic_phrases_details"]["rest_dur_after_mp"] = rest_dur_after_mp_list

        # ranges by section
        mp_range_df = pd.DataFrame(
            {
                "mp_id": self.data_dict["melodic_phrases_details"]["mp_id"],
                "sec_id": self.data_dict["melodic_phrases"]["sec_id"],
                "mp_range_midi": self.data_dict["melodic_phrases_details"]["mp_range_midi"]
            }
        )
        mp_range_dict = mp_range_df.groupby("sec_id")["mp_range_midi"].agg(["min", "max"]).to_dict()

        for mp_id in mp_range_df["mp_id"].values:
            mp_range = mp_range_df[mp_range_df["mp_id"]==mp_id]["mp_range_midi"].iloc[0]
            mp_sec = mp_range_df[mp_range_df["mp_id"]==mp_id]["sec_id"].iloc[0]
            has_sec_widest_range = mp_range == mp_range_dict["max"][mp_sec]
            has_sec_narrowest_range = mp_range == mp_range_dict["min"][mp_sec]
            self.data_dict["melodic_phrases_details"]["has_sec_widest_range"].append(has_sec_widest_range)
            self.data_dict["melodic_phrases_details"]["has_sec_narrowest_range"].append(has_sec_narrowest_range)

        return None


    def prepare_all_hps_dfs(self, track_dfs: Mapping[str, pd.DataFrame]) -> Sequence[Mapping[str, pd.DataFrame]]:
        all_hp_ids = track_dfs["harmonic_phrases"]["hp_id"].values

        # get harmonic_phrases and chords dfs
        all_hps_dfs = [
            {
                table: df[df["hp_id"]==hp_id] for table, df in track_dfs.items()
                if table == "harmonic_phrases" or table == "chords"
            } for hp_id in all_hp_ids
        ]

        return all_hps_dfs


    def comprehensive_hp_input(self, hp_dfs: Mapping[str, pd.DataFrame]) -> None:

        hp_df = hp_dfs["harmonic_phrases"].copy()
        hp_chords_df = hp_dfs["chords"].copy()
        chords_only_df = hp_chords_df[hp_chords_df["chord_name"] != "N.C."]
        assert(len(chords_only_df)>0), "harmonic phrase has no chords - this case hasn't been implemented yet"
        sec_idx = np.where(np.array(self.data_dict["sections"]["sec_id"])==hp_df["sec_id"].iloc[0])[0][0]

        start_chord_id, end_chord_id = self.get_start_end_ids(chords_only_df, "chord_start_offset", "chord_id")
        self.data_dict["harmonic_phrases_details"]["hp_id"].append(hp_df["hp_id"].iloc[0])
        self.data_dict["harmonic_phrases_details"]["hp_start_chord_id"].append(start_chord_id)
        self.data_dict["harmonic_phrases_details"]["hp_end_chord_id"].append(end_chord_id)
        sec_start_offset = self.data_dict["sections"]["sec_start_offset"][sec_idx]
        hp_start_offset = hp_df["hp_start_offset"].iloc[0]
        self.data_dict["harmonic_phrases_details"]["hp_start_section_offset"].append(hp_start_offset - sec_start_offset)

        hp_dur = hp_df["hp_total_dur"].iloc[0]
        track_avg_hp_dur = self.data_dict["tracks_form"]["track_avg_hp_dur"][0]
        track_med_hp_dur = self.data_dict["tracks_form"]["track_med_hp_dur"][0]
        self.data_dict["harmonic_phrases_details"]["hp_to_track_avg_hp_dur"].append(hp_dur / track_avg_hp_dur)
        self.data_dict["harmonic_phrases_details"]["hp_to_track_med_hp_dur"].append(hp_dur / track_med_hp_dur)

        chord_center_cols = ["prev_chord_rb_same_qual_diff", "prev_chord_root_same_bass_diff", "prev_chord_bass_same_root_diff"]
        chords_only_df["new_chord_center"] = (chords_only_df[chord_center_cols].sum(axis=1)==0).cumsum()
        chord_center_durs = chords_only_df.groupby(["new_chord_center"])["chord_dur"].sum()
        self.data_dict["harmonic_phrases_details"]["hp_avg_chord_dur"].append(chords_only_df["chord_dur"].mean())
        self.data_dict["harmonic_phrases_details"]["hp_avg_chord_center_dur"].append(chord_center_durs.mean())
        self.data_dict["harmonic_phrases_details"]["hp_med_chord_dur"].append(chords_only_df["chord_dur"].median())
        self.data_dict["harmonic_phrases_details"]["hp_med_chord_center_dur"].append(chord_center_durs.median())
        self.data_dict["harmonic_phrases_details"]["hp_n_chords"].append(len(chords_only_df))
        self.data_dict["harmonic_phrases_details"]["hp_n_unique_chords"].append(chords_only_df["chord_name"].nunique())
        self.data_dict["harmonic_phrases_details"]["hp_n_chord_centers"].append(len(chord_center_durs))

        self.data_dict["harmonic_phrases_details"]["hp_pct_maj_3_no_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["maj_3_no_7"]).sum() / len(chords_only_df))
        self.data_dict["harmonic_phrases_details"]["hp_pct_min_3_no_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["min_3_no_7"]).sum() / len(chords_only_df))
        self.data_dict["harmonic_phrases_details"]["hp_pct_maj_3_maj_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["maj_3_maj_7"]).sum() / len(chords_only_df))
        self.data_dict["harmonic_phrases_details"]["hp_pct_min_3_min_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["min_3_min_7"]).sum() / len(chords_only_df))
        self.data_dict["harmonic_phrases_details"]["hp_pct_maj_3_min_7"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["maj_3_min_7"]).sum() / len(chords_only_df))
        self.data_dict["harmonic_phrases_details"]["hp_pct_other_quality"] \
            .append(chords_only_df["chord_kind"].isin(chord_kind_dict["other"]).sum() / len(chords_only_df))

        self.data_dict["harmonic_phrases_details"]["pct_repeated_chords"] \
            .append(chords_only_df["chord_name"].duplicated(keep=False).sum() / len(chords_only_df))
        self.data_dict["harmonic_phrases_details"]["pct_chord_center_elongation"] \
            .append((chords_only_df["prev_chord_elongation"]==1).sum() / len(chords_only_df))
        self.data_dict["harmonic_phrases_details"]["chord_names"].append(", ".join(chords_only_df["chord_name"].values))
        self.data_dict["harmonic_phrases_details"]["chord_durs"].append(", ".join(chords_only_df["chord_dur"].astype(str).values))
        self.data_dict["harmonic_phrases_details"]["chord_center_durs"].append(", ".join(chord_center_durs.astype(str).values))
        self.data_dict["harmonic_phrases_details"]["chord_change_beats"].append(", ".join(chords_only_df["beat"].astype(str).values))
        self.data_dict["harmonic_phrases_details"]["chord_center_change_beats"] \
            .append(", ".join(chords_only_df[chords_only_df["prev_chord_elongation"]==0]["beat"].astype(str).values))
        self.data_dict["harmonic_phrases_details"]["root_motion"].append(", ".join(chords_only_df["prev_chord_root_dist"].astype(str).values))
        self.data_dict["harmonic_phrases_details"]["bass_motion"].append(", ".join(chords_only_df["prev_chord_bass_dist"].astype(str).values))
        self.data_dict["harmonic_phrases_details"]["n_chord_qualities"].append(chords_only_df["chord_kind"].nunique())

        two_note_cond = chords_only_df["n_pitches"]==2
        three_note_cond = chords_only_df["n_pitches"]==3
        four_note_cond = chords_only_df["n_pitches"]==4
        five_plus_note_cond = chords_only_df["n_pitches"]>4
        self.data_dict["harmonic_phrases_details"]["n_2_note_chords"].append(two_note_cond.sum())
        self.data_dict["harmonic_phrases_details"]["n_3_note_chords"].append(three_note_cond.sum())
        self.data_dict["harmonic_phrases_details"]["n_4_note_chords"].append(four_note_cond.sum())
        self.data_dict["harmonic_phrases_details"]["n_5plus_note_chords"].append(five_plus_note_cond.sum())
        self.data_dict["harmonic_phrases_details"]["dur_2_note_chords"].append(chords_only_df[two_note_cond]["chord_dur"].sum())
        self.data_dict["harmonic_phrases_details"]["dur_3_note_chords"].append(chords_only_df[three_note_cond]["chord_dur"].sum())
        self.data_dict["harmonic_phrases_details"]["dur_4_note_chords"].append(chords_only_df[four_note_cond]["chord_dur"].sum())
        self.data_dict["harmonic_phrases_details"]["dur_5plus_note_chords"].append(chords_only_df[five_plus_note_cond]["chord_dur"].sum())

        hp_end_offset = hp_df["hp_end_offset"].iloc[0]
        final_sec = sec_idx == len(self.data_dict["sections"]["sec_id"]) - 1
        next_sec_start_offset = self.track_dur if final_sec else self.data_dict["sections"]["sec_start_offset"][sec_idx + 1]
        self.data_dict["harmonic_phrases_details"]["hp_overlaps_next_section"].append(hp_end_offset > next_sec_start_offset)

        self.data_dict["harmonic_phrases_details"]["all_chord_dur_are_same"].append(chords_only_df["chord_dur"].nunique()==1)

        track_avg_chord_dur = self.data_dict["tracks_harmony"]["track_avg_chord_dur"][-1]
        track_med_chord_dur = self.data_dict["tracks_harmony"]["track_med_chord_dur"][-1]
        self.data_dict["harmonic_phrases_details"]["hp_to_track_avg_chord_dur"] \
            .append(chords_only_df["chord_dur"].mean() / track_avg_chord_dur)
        self.data_dict["harmonic_phrases_details"]["hp_to_track_med_chord_dur"] \
            .append(chords_only_df["chord_dur"].median() / track_med_chord_dur)

        return None


    def finish_comprehensive_hp_input(self, track_dfs: Mapping[str, pd.DataFrame]) -> None:
        chorus_id, _ = self.find_chorus(track_dfs)
        chorus_chord_root, chorus_chord_bass = track_dfs["chords"][
            (track_dfs["chords"]["sec_id"]==chorus_id)
            & (track_dfs["chords"]["chord_name"]!="N.C.")] \
        [["chord_root_pc", "chord_bass_pc"]].iloc[0, :].values

        for hp_id in track_dfs["harmonic_phrases"]["hp_id"].values:

            hp_chord_root, hp_chord_bass = track_dfs["chords"][
                (track_dfs["chords"]["hp_id"]==hp_id)
                & (track_dfs["chords"]["chord_name"]!="N.C.")] \
            [["chord_root_pc", "chord_bass_pc"]].iloc[0, :].values

            root_dist, bass_dist = self.get_prev_chord_rb_dist(
                hp_chord_root, hp_chord_bass, chorus_chord_root, chorus_chord_bass
            )

            self.data_dict["harmonic_phrases_details"]["hp_to_chorus_first_chord_root_dist"].append(root_dist)
            self.data_dict["harmonic_phrases_details"]["hp_to_chorus_first_chord_bass_dist"].append(bass_dist)

        return None


    def comprehensive_note_input(self, track_dfs: Mapping[str, pd.DataFrame]) -> None:
        for note_id in self.data_dict["notes"]["note_id"]:
            self.data_dict["notes_details"]["note_id"].append(note_id)

            note_df = track_dfs["notes"][track_dfs["notes"]["note_id"]==note_id]
            sec_idx = np.where(np.array(self.data_dict["sections"]["sec_id"])==note_df["sec_id"].iloc[0])[0][0]
            mp_idx = np.where(np.array(self.data_dict["melodic_phrases"]["mp_id"])==note_df["mp_id"].iloc[0])[0]
            mp_idx = mp_idx[0] if len(mp_idx) > 0 else None

            sec_start_offset = self.data_dict["sections"]["sec_start_offset"][sec_idx]
            mp_start_offset = None if mp_idx is None else self.data_dict["melodic_phrases"]["mp_start_offset"][mp_idx]
            note_start_offset = note_df["note_start_offset"].iloc[0]
            note_start_mp_offset = None if mp_idx is None else note_start_offset - mp_start_offset
            self.data_dict["notes_details"]["note_start_section_offset"].append(note_start_offset - sec_start_offset)
            self.data_dict["notes_details"]["note_start_mp_offset"].append(note_start_mp_offset)

            note_end_offset = note_df["note_end_offset"].iloc[0]
            chord_starts = self.data_dict["chords"]["chord_start_offset"]
            chord_ends = self.data_dict["chords"]["chord_end_offset"]
            for chord_start, chord_end in zip(chord_starts, chord_ends):
                note_starts_in_chord = note_start_offset >= chord_start and note_start_offset < chord_end
                note_ends_in_chord = note_end_offset > chord_start and note_end_offset <= chord_end
                if not note_starts_in_chord and not note_ends_in_chord:
                    continue
                if note_starts_in_chord and note_ends_in_chord:
                    spans_multi_chords = False
                else:
                    spans_multi_chords = True

            self.data_dict["notes_details"]["spans_multi_chords"].append(spans_multi_chords)

            track_highest_note = self.data_dict["tracks_melody"]["track_highest_note_midi"][-1]
            track_lowest_note = self.data_dict["tracks_melody"]["track_lowest_note_midi"][-1]
            track_longest_note = self.data_dict["tracks_melody"]["track_longest_note_dur"][-1]
            sec_highest_note = self.data_dict["sections_melody"]["sec_highest_note_midi"][sec_idx]
            sec_lowest_note = self.data_dict["sections_melody"]["sec_lowest_note_midi"][sec_idx]
            sec_longest_note = self.data_dict["sections_melody"]["sec_longest_note_dur"][sec_idx]
            mp_longest_note = None if mp_idx is None else self.data_dict["melodic_phrases_details"]["mp_longest_note_dur"][mp_idx]

            is_rest = note_df["note_name"].iloc[0] == "rest"
            note_pitch = note_df["midi_num"].iloc[0]
            note_dur = note_df["duration"].iloc[0]
            is_track_highest_note = False if is_rest else note_pitch == track_highest_note
            is_track_lowest_note = False if is_rest else note_pitch == track_lowest_note
            is_track_longest_note = False if is_rest else note_dur == track_longest_note
            is_sec_highest_note = False if is_rest else note_pitch == sec_highest_note
            is_sec_lowest_note = False if is_rest else note_pitch == sec_lowest_note
            is_sec_longest_note = False if is_rest else note_dur == sec_longest_note
            mp_longest_note = False if mp_longest_note is None or is_rest else note_dur == mp_longest_note

            self.data_dict["notes_details"]["is_track_highest_note"].append(is_track_highest_note)
            self.data_dict["notes_details"]["is_track_lowest_note"].append(is_track_lowest_note)
            self.data_dict["notes_details"]["is_track_longest_note"].append(is_track_longest_note)
            self.data_dict["notes_details"]["is_sec_highest_note"].append(is_sec_highest_note)
            self.data_dict["notes_details"]["is_sec_lowest_note"].append(is_sec_lowest_note)
            self.data_dict["notes_details"]["is_sec_longest_note"].append(is_sec_longest_note)
            self.data_dict["notes_details"]["is_phrase_longest_note"].append(mp_longest_note)

            note_direction = note_df["prev_note_direction"].iloc[0]
            note_distance_type = note_df["prev_note_distance_type"].iloc[0]
            up_cond = note_direction == "up"
            down_cond = note_direction == "down"
            step_cond = note_distance_type == "step"
            skip_cond = note_distance_type == "skip"
            leap_cond = note_distance_type == "leap"

            self.data_dict["notes_details"]["up"].append(up_cond)
            self.data_dict["notes_details"]["down"].append(down_cond)
            self.data_dict["notes_details"]["same"].append(note_direction == "same")
            self.data_dict["notes_details"]["up_step"].append(up_cond and step_cond)
            self.data_dict["notes_details"]["up_skip"].append(up_cond and skip_cond)
            self.data_dict["notes_details"]["up_leap"].append(up_cond and leap_cond)
            self.data_dict["notes_details"]["down_step"].append(down_cond and step_cond)
            self.data_dict["notes_details"]["down_skip"].append(down_cond and skip_cond)
            self.data_dict["notes_details"]["down_leap"].append(down_cond and leap_cond)


    # main function for inputing all data into data_dict
    def input_all(self):

        # loop through part_recurse and input data into the notes and chords dictionaries
        for ele in self.part_recurse:
            if isinstance(ele, m21.note.Rest) or isinstance(ele, m21.note.Note):
                self.note_rest_input(ele)

            if isinstance(ele, m21.harmony.ChordSymbol) or isinstance(ele, m21.harmony.NoChord):
                self.chord_input(ele)

        # finish inputing values into chords dictionary that we couldn't input in loop
        self.input_chord_end_offset_info(self.data_dict['chords']['chord_start_offset'], self.track_dur, self.m1b1_factor)

        # input values into tracks, sections, melodic_phrases, and harmonic_phrases dictionaries
        self.track_input()
        self.section_input()
        self.melodic_phrases_input()
        self.harmonic_phrases_input()

        # create additional tables if 'comprehensive' arg is set to True when class is initialized
        if self.comprehensive:

            # prepare dataframes
            track_dfs = {table: pd.DataFrame(self.data_dict[table]) for table in BASIC_TABLES}
            all_sections = track_dfs["sections"]["sec_id"].values
            all_sections_dfs = [
                {table: df[df["sec_id"]==sec] for table, df in track_dfs.items() if table != "tracks"}
                for sec in all_sections
            ]

            # input values into track metrics
            self.comprehensive_track_section_input(track_dfs, "track")

            # input values into section metrics
            for section_dfs in all_sections_dfs:
                self.comprehensive_track_section_input(section_dfs, "section")
            self.finish_comprehensive_section_input(track_dfs, all_sections_dfs)

            # input values into melodic phrases metrics
            all_mps_dfs = self.prepare_all_mps_dfs(track_dfs)
            for mp_dfs in all_mps_dfs:
                self.comprehensive_mp_input(mp_dfs)
            self.finish_comprehensive_mp_input(track_dfs["melodic_phrases"])

            # input values into harmonic phrases metrics
            all_hps_dfs = self.prepare_all_hps_dfs(track_dfs)
            for hp_dfs in all_hps_dfs:
                self.comprehensive_hp_input(hp_dfs)
            self.finish_comprehensive_hp_input(track_dfs)

            # input values into note metrics
            self.comprehensive_note_input(track_dfs)


    def validate_input(self) -> str:
        """
        checks the following:
            a) all lists in each dict are same length,
            b) list length is > 0 (if, for example, len(self.rehearsal_marks) == 0, maybe some section lists will be empty)
            c) list data types are correct
        TODO (maybe...):
            d) could check that number of unique values in a given list matches something (e.g. the sum of notes['sec_end_note'] should be the same length as self.rehearsal_marks)
        """
        tables = list(self.data_dict.keys())

        for table in tables:

            col_lengths = [len(col) for col in self.data_dict[table].values()]
            col_types = {col_name: list(set((type(col) for col in column))) for col_name, column in self.data_dict[table].items()}

            # check each column is same length in each table
            try:
                assert(len(set(col_lengths)) == 1), f"number of values is not the same for each column in {table}"
            except AssertionError as e:
                return str(e)

            # check that tables are longer than 0
            try:
                assert(col_lengths[0] > 0), f"table {table} has no values"
            except AssertionError as e:
                return str(e)

            # check that columns are correct data type
            for col_name, col_type in col_types.items():
                if len(col_type) == 1:
                    try:
                        assert(col_type[0] == self.data_type_dict[table][col_name]), f"'{col_name}' in table '{table}' is type {col_type[0]}, expected type {self.data_type_dict[table][col_name]}"
                    except AssertionError as e:
                        return str(e)

                else:  # nullable columns
                    try:
                        assert(type(None) in col_type), f"Value Error: '{col_name}' in table '{table}' has multiple types: {[print(c_type) for c_type in col_type]}"
                    except AssertionError as e:
                        return str(e)

                    try:
                        assert((table, col_name) in self.nullable_columns), f"Value Error: '{col_name}' in table '{table}' has null values, but isn't in list of nullable columns"
                    except AssertionError as e:
                        return str(e)

                    try:
                        assert(set(col_type) == set((self.data_type_dict[table][col_name], type(None)))), f"Value Error: '{col_name}' in table '{table}' has data types {col_type}, expected {self.data_type_dict[table][col_name]}"
                    except AssertionError as e:
                        return str(e)

        print('all values validated!')

        return 'all values validated!'


if __name__ == "__main__":
    import os
    from const import ROOT_DIR

    mxl_filepath = os.path.join(ROOT_DIR, "data", "pasta piece.mxl")
    preproc = PreprocessXML()
    preproc.load_data(mxl_filepath, comprehensive=True)
    preproc.input_all()
    message = preproc.validate_input()
    print("validation complete")
    print(message)
    # print(preproc.offset_dict['sec_end_offsets'])
    # print(len(preproc.data_dict['notes']['sec_start_note']))
    # print(preproc.data_dict['notes']['sec_end_note'])

    # for v in preproc.data_dict['harmonic_phrases'].values():
    #     print(len(v))
    # print(preproc.data_dict['sections'])
    # print(preproc.data_dict['harmonic_phrases'])
