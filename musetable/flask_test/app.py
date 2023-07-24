# Uploading musicxml files appears to be problematic for streamlit.
# It should work for flask, though!  But need to do some extra work, it seems

import streamlit as st
import music21 as m21

uploaded_file = st.file_uploader("Choose a Music XML")
if uploaded_file is not None:
    # To read file as bytes:
    bytes_data = uploaded_file.getvalue()
    s = m21.converter.parseData(bytes_data)
    # st.write(s.metadata.title)
    # st.write(s.metadata.composer)
