-- Postgres Table Creation Script
--

--
-- Table structure for table tracks
--

CREATE TABLE tracks (
  id VARCHAR(45) NOT NULL,
  artist VARCHAR(45) NOT NULL,
  track_name VARCHAR(45) NOT NULL,
  album_name VARCHAR(45) NOT NULL,
  release_date VARCHAR(45) NOT NULL,
  PRIMARY KEY (id)
);


--
-- Table structure for table sections
--

CREATE TABLE sections (
  id VARCHAR(45) NOT NULL,
  track_id VARCHAR(45) NOT NULL,
  title VARCHAR(45) NOT NULL,
  section VARCHAR(45) NOT NULL,
  composer VARCHAR(45) NOT NULL,
  duration_ql FLOAT NOT NULL,
  num_phrases INT NOT NULL,
  range_interval VARCHAR(45) NOT NULL,
  range_midi_low INT NOT NULL,
  range_midi_high INT NOT NULL,
  time_signature VARCHAR(45) NOT NULL,
  bpm VARCHAR(45) NOT NULL,
  bpm_ql VARCHAR(45) NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY (track_id) REFERENCES tracks(id)
);

--
-- Table structure for table phrases
--

CREATE TABLE phrases (
  section_id VARCHAR(45) NOT NULL,
  phrase_num INT NOT NULL,
  phrase_length FLOAT NOT NULL,
  phrase_start_offset FLOAT NOT NULL,
  phrase_end_offset FLOAT NOT NULL,
  FOREIGN KEY (section_id) REFERENCES sections(id)
);

--
-- Table structure for table notes
--

CREATE TABLE notes (
  section_id VARCHAR(45) NOT NULL,
  note_name VARCHAR(45) NOT NULL,
  octave INT NOT NULL,
  midi_num INT NOT NULL,
  pitch_class INT NOT NULL,
  duration_ql FLOAT NOT NULL,
  phrase_num INT NOT NULL,
  measure INT NOT NULL,
  beat FLOAT NOT NULL,
  offset_ql FLOAT NOT NULL,
  chord_name VARCHAR(45) NOT NULL,
  nct INT NOT NULL,
  from_root_name VARCHAR(45) NOT NULL,
  from_root_pc INT NOT NULL,
  FOREIGN KEY (section_id) REFERENCES sections(id)
);

--
-- Table structure for table harmony
--

CREATE TABLE harmony (
  section_id VARCHAR(45) NOT NULL,
  chord_name VARCHAR(45) NOT NULL,
  chord_kind VARCHAR(45) NOT NULL,
  chord_root VARCHAR(45) NOT NULL,
  chord_bass VARCHAR(45) NOT NULL,
  pitches VARCHAR(45) NOT NULL,
  phrase_num INT NOT NULL,
  measure INT NOT NULL,
  beat FLOAT NOT NULL,
  offset_ql FLOAT NOT NULL,
  duration_ql FLOAT NOT NULL,
  FOREIGN KEY (section_id) REFERENCES sections(id)
);
