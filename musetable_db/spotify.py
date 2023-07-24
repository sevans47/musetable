"""
Using the Spotify API and my Spotify Wrapped Top Songs 2022 playlist, collect
information on each track in the playlist

TODO: try using spotipy library
"""

from google.cloud import secretmanager
import json
import requests
import pandas as pd
import os

from musetable_db.const import PROJECT_ID, SPOTIFY_SECRET_ID, SPOTIFY_VERSION_ID, PLAYLIST_NAME

class SpotifyClient:
    """SpotifyClient performs operations using the Spotify API."""

    def __init__(self, project_id: str, secret_id: str, version_id: int):
        """
        Parameters:
        -----------
        project_id  : GCP project id with the Secret Manager API containing Spotify API secrets
        secret_id   : id for secrets
        version_id  : version number for secret
        """
        # get secret details
        secret_details = self.get_secrets(project_id, secret_id, version_id)

        # store secret details as instance variables
        self._authorization_token = secret_details['spotify_authorization_token']
        self._user_id = secret_details['spotify_user_id']

    def get_secrets(self, project_id: str, secret_id: str, version_id: int) -> dict:
        """
        Using GCP's Secret Manager, get secret details for connecting to the Spotify API

        Parameters:
        -----------
        project_id  : GCP project id with the Secret Manager API containing Spotify API secrets
        secret_id   : id for secrets
        version_id  : version number for secrets

        Returns:
        --------
        secret_details  : dictionary containing secret details
        """
        # create secret manager client object
        client = secretmanager.SecretManagerServiceClient()

        # get secret details
        secret_name = f'projects/{project_id}/secrets/{secret_id}/versions/{version_id}'

        # access secret
        response = client.access_secret_version(name=secret_name)

        # load secret
        secret_details = json.loads(response.payload.data.decode('utf-8'))

        return secret_details

    def get_playlist_tracks(self, playlist_name = "Your Top Songs 2022") -> dict:
        """
        Get playlist by name

        Parameters:
        -----------
        playlist_name   : name of playlist

        Return:
        -------
        playlist_dict   : Dictionary of info on all tracks in playlist
        """
        # get api url for playlist tracks
        url = "https://api.spotify.com/v1/me/playlists"
        response = self._place_get_api_request(url)
        response_json = response.json()
        playlist_tracks_url = [pl['tracks'] for pl in response_json['items'] if pl['name'] == playlist_name][0]['href']

        # get all tracks in playlist
        response = self._place_get_api_request(playlist_tracks_url)
        response_json = response.json()

        # set up dict
        playlist_dict = {
            'artist': [],
            'name': [],
            'album': [],
            'release_date': [],
            'id': []
        }

        # loop through tracks and store info in dictionary
        print("Getting info on playlist tracks ... ")
        for track in response_json['items']:
            playlist_dict['artist'].append(track['track']['artists'][0]['name'])
            playlist_dict['name'].append(track['track']['name'])
            playlist_dict['album'].append(track['track']['album']['name'])
            playlist_dict['release_date'].append(track['track']['album']['release_date'])
            playlist_dict['id'].append(track['track']['id'])

        print("Finished getting info on playlist tracks")
        return playlist_dict

    def get_playlist_track_details(self, playlist_dict: dict) -> dict:
        """
        Uses track ids to get further track info using the Spotify API

        Parameters:
        -----------
        playlist_dict   : dictionary of basic track data, from get_playlist_tracks() method

        Returns:
        --------
        track_details_dict  : dictionary of extra track data
        """

        # set up the dictionary
        track_details_dict = {
            'track_id': [],
            'popularity': [],
            'danceability': [],
            'energy': [],
            'key': [],
            'loudness': [],
            'mode': [],
            'speechiness': [],
            'acousticness': [],
            'instrumentalness': [],
            'liveness': [],
            'valence': [],
            'tempo': [],
            'duration_ms': [],
            'time_signature': [],
        }

        # keep track of loop's progress
        count = 0
        num_tracks = len(playlist_dict['id'])

        # loop over each track id, make API calls, and store data in dictionary
        print("Getting further track details ... ")
        for track_id in playlist_dict['id']:

            track_details_dict['track_id'].append(track_id)

            track_details = spotify_client.get_track(track_id)
            track_details_dict['popularity'].append(track_details['popularity'])

            track_features = spotify_client.get_track_features(track_id)
            for key in track_details_dict.keys():
                if key not in ['track_id', 'popularity']:
                    track_details_dict[key].append(track_features[key])

            if count % 10 == 0:
                print(f'track {count} of {num_tracks}')
            count += 1

        print("Finished getting further track details")
        return track_details_dict

    def save_dict_as_csv(self, data_dict: dict, filepath: str):
        """
        Use a dictionary and save the data to a csv

        Parameters:
        -----------
        filepath    : location to save csv
        """
        pd.DataFrame.from_dict(data_dict).to_csv(filepath, index=False)
        print("Saved data as csv")

    def get_track(self, track_id: str) -> dict:
        """Get track by id

        Parameters:
        -----------
        track_id    : spotify track id

        Returns:
        --------
        track_info  : information about track
        """
        url = f"https://api.spotify.com/v1/tracks/{track_id}"
        response = self._place_get_api_request(url)
        track_info = response.json()

        return track_info

    def get_track_features(self, track_id: str) -> dict:
        """Get track audio features by id

        Parameters:
        -----------
        track_id    : spotify track id

        Returns:
        --------
        track_info  : information about track
        """
        url = f"https://api.spotify.com/v1/audio-features/{track_id}"
        response = self._place_get_api_request(url)
        track_info = response.json()

        return track_info

    def get_track_analysis(self, track_id: str) -> dict:
        """Get track audio analysis by id

        Parameters:
        -----------
        track_id    : spotify track id

        Returns:
        --------
        track_info  : information about track
        """
        url = f"https://api.spotify.com/v1/audio-analysis/{track_id}"
        response = self._place_get_api_request(url)
        track_info = response.json()

        return track_info

    def _place_get_api_request(self, url: str) -> requests.models.Response:
        """Place a GET request for the Spotify API

        Parameters:
        -----------
        url : URL for the Spotify API GET request

        Returns:
        --------
        response    : Response from the GET request

        """
        response = requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._authorization_token}"
            }
        )
        return response

if __name__ == "__main__":
    # instantiate spotify client
    spotify_client = SpotifyClient(PROJECT_ID, SPOTIFY_SECRET_ID, SPOTIFY_VERSION_ID)

    # get dictionary of playlist tracks
    playlist_tracks = spotify_client.get_playlist_tracks(PLAYLIST_NAME)
    print(len(playlist_tracks['id']))

    # save as csv
    filepath = 'test_playlist.csv'
    spotify_client.save_dict_as_csv(playlist_tracks, filepath)
    os.remove(filepath)
    print("removed csv")

    # get dictionary of playlist track details
    track_details_dict = spotify_client.get_playlist_track_details(playlist_tracks)

    # # save as csv
    filepath = 'test_playlist_details.csv'
    spotify_client.save_dict_as_csv(track_details_dict, filepath)
    os.remove(filepath)
    print("removed csv")
