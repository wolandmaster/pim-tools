#!/usr/bin/env python3
# Copyright (c) 2022 Sandor Balazsi (sandor.balazsi@gmail.com)

"""Google OAuth 2.0"""

import logging, os, webbrowser
from config import Config
from requests_oauthlib import OAuth2Session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

LOGGER = logging.getLogger(__name__)
AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_URI = 'https://oauth2.googleapis.com/token'
REDIRECT_URI = 'http://localhost'

class GoogleCredentials:
    def __init__(self, config, scopes):
        self.config = config
        self.refresh_token = config.get('refresh_token')
        self.scopes = scopes

    def login(self):
        if self.refresh_token:
            credentials = self.refresh()
        else:
            credentials = self.authorize()
        self.on_token_auto_refreshed(credentials)
        return credentials

    def refresh(self):
        credentials = Credentials.from_authorized_user_info({
            'client_id': self.config.get('client_id'),
            'client_secret': self.config.get('client_secret'),
            'refresh_token': self.refresh_token
        }, self.scopes)
        try:
            credentials.refresh(Request())
        except RefreshError:
            credentials = self.authorize()
        return credentials

    def authorize(self):
        webbrowser.register('firefox', None, webbrowser.Mozilla('firefox'), preferred = True)
        webbrowser.get().remote_args[-1:-1] = [
            '--kiosk', '--width', '500', '--height', '700', '--private-window'
        ]
        session = OAuth2Session(
            client_id = self.config.get('client_id'),
            scope = self.scopes,
            token_updater = self.on_token_auto_refreshed
        )
        flow = InstalledAppFlow(
            oauth2session = session,
            client_type = 'installed',
            redirect_uri = REDIRECT_URI,
            client_config = {
                'installed': {
                    'auth_uri': AUTH_URI,
                    'token_uri': TOKEN_URI,
                    'client_id': self.config.get('client_id'),
                    'client_secret': self.config.get('client_secret')
                }
            }
        )
        credentials = flow.run_local_server(port = 0, authorization_prompt_message = '')
        os.system('killall firefox')
        return credentials

    def on_token_auto_refreshed(self, credentials):
        self.refresh_token = credentials.refresh_token
        self.config.set('refresh_token', self.refresh_token).save()
        LOGGER.debug('Google oauth token refreshed')

if __name__ == '__main__':
    logging.basicConfig(
        format = '%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
        level = logging.INFO
    )
    config = Config(filename = 'google_oauth.json').load()
    scopes = ['https://www.googleapis.com/auth/calendar']
    credentials = GoogleCredentials(config, scopes).login()
    LOGGER.info('Credentials file updated successfully')
