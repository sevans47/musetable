import music21 as m21
from typing import Union
import numpy as np

from const import ROOT_DIR, SCOPE, DATA_DICT

class PreprocessXML:
    """PreprocessXML converts a MusicXML file into a dictionary"""

    def __init__(self, mxl_filepath: str, comprehensive=False):

        # if comprehensive=False, returns basic tables. If True, returns additional tables as well
        self.comprehensive = comprehensive

        # get m21 part from mxl file
        self.part, self.part_recurse = self.load_mxl_from_file(mxl_filepath)

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
        self.data_dict = DATA_DICT

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


    def make_offset_dict(self, rehearsal_marks, spanners, expression_marks):

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


    def get_track_offset(self, ele):
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

        return [np.sum(
                    np.greater_equal(self.offset_dict['mp_start_offsets'], sec_start) & np.less(self.offset_dict['mp_start_offsets'], sec_end)
                ) for sec_start, sec_end in zip(self.offset_dict['sec_start_offsets'], self.offset_dict['sec_end_offsets'])
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
        self.data_dict['tracks']['bpm'].append(mm.number if mm is not None else float(0))
        self.data_dict['tracks']['bpm_ql'].append(mm.referent.quarterLength if mm is not None else float(0))
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

        # get pitch classes for note and chord root and put the in a numpy array
        pc_array = np.array([ele.pitch.pitchClass, current_chord.root().pitchClass])

        # check if the difference is greater than 6 (ie max difference between pitch classes)
        if np.abs(np.diff(pc_array)) > 6:
            # subtract the larger number by 12, making the distance between 0-6
            pc_array[pc_array.argmax()] = pc_array[pc_array.argmax()] - 12

        return np.abs(np.diff(pc_array))[0]


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
            prev_note_start_offset = self.data_dict['notes']['note_start_offset'][-1]
            prev_note_end_offset = self.data_dict['notes']['note_end_offset'][-1]
            next_sec_offset = start_offsets[current_index + 1] if current_index < len(start_offsets) - 2 else self.track_dur
            if prev_note_start_offset < next_sec_offset and prev_note_end_offset > next_sec_offset:
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

        # make it negative if current root / bass is lower than prev root / bass
        prev_root_dist = -prev_root_dist if prev_root > curr_root else prev_root_dist
        prev_bass_dist = -prev_bass_dist if prev_bass > curr_bass else prev_bass_dist

        return (prev_root_dist, prev_bass_dist)


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

        # input data into chords dictionary
        self.data_dict['chords']['chord_id'].append(self.id_dict['current_chord_id'])
        self.data_dict['chords']['sec_id'].append(self.id_dict['current_sec_id'])
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
            pass




    def validate_input(self):
        # TODO: check the following:
        # a) all lists in each dict are same length,
        # b) list length is > 0 (if, for example, len(self.rehearsal_marks) == 0, maybe some section lists will be empty)
        # c) list data types are correct
        # d) if time - could check that number of unique values in a given list matches something (e.g. the sum of notes['sec_end_note'] should be the same length as self.rehearsal_marks)
        pass


if __name__ == "__main__":
    import os

    xml_filepath = os.path.join(ROOT_DIR, "data", "pasta piece.mxl")
    preproc = PreprocessXML(xml_filepath)
    preproc.input_all()
    # print(preproc.offset_dict['sec_end_offsets'])
    # print(len(preproc.data_dict['notes']['sec_start_note']))
    # print(preproc.data_dict['notes']['sec_end_note'])

    for v in preproc.data_dict['harmonic_phrases'].values():
        print(len(v))
    # print(preproc.data_dict['sections'])
    print(preproc.data_dict['harmonic_phrases'])
