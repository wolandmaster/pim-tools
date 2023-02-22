#!/usr/bin/env python3
# Copyright (c) 2022-2023 Sandor Balazsi (sandor.balazsi@gmail.com)
# vim: ts=4:sw=4:sts=4:et

"""Google OAuth 2.0"""

import os, sys, logging
from config import Config
from argparse import ArgumentParser, HelpFormatter
from requests_oauthlib import OAuth2Session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

LOGGER = logging.getLogger(__name__)
AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_URI = 'https://oauth2.googleapis.com/token'
REDIRECT_URI = 'http://localhost'

class GoogleCredentials:
    def __init__(self, config):
        self.config = config
        self.refresh_token = config.get('refresh_token')

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
        }, self.config.get('scopes'))
        try:
            credentials.refresh(Request())
        except RefreshError:
            credentials = self.authorize()
        return credentials

    def on_token_auto_refreshed(self, credentials):
        self.refresh_token = credentials.refresh_token
        self.config.set('refresh_token', self.refresh_token).save()
        LOGGER.debug('Google oauth token refreshed')

    def authorize(self):
        import webbrowser
        from google_auth_oauthlib.flow import InstalledAppFlow

        webbrowser.register('firefox', None, webbrowser.Mozilla('firefox'), preferred=True)
        webbrowser.get().remote_args[-1:-1] = [
            '--kiosk', '--width', '500', '--height', '700', '--private-window'
        ]
        session = OAuth2Session(
            client_id=self.config.get('client_id'),
            scope=self.config.get('scopes'),
            token_updater=self.on_token_auto_refreshed
        )
        flow = InstalledAppFlow(
            oauth2session=session,
            client_type='installed',
            redirect_uri=REDIRECT_URI,
            client_config={
                'installed': {
                    'auth_uri': AUTH_URI,
                    'token_uri': TOKEN_URI,
                    'client_id': self.config.get('client_id'),
                    'client_secret': self.config.get('client_secret')
                }
            }
        )
        credentials = flow.run_local_server(port=0, authorization_prompt_message='')
        os.system('killall firefox')
        return credentials

if __name__ == '__main__':
    parser = ArgumentParser(
        formatter_class=lambda prog: HelpFormatter(prog, max_help_position=30)
    )
    parser.add_argument(
        '-c', '--config', metavar='<file>', default='google_oauth.json',
        help='Config file (default: google_oauth.json)'
    )
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        parser.epilog = 'No such config file: %s' % args.config
    if parser.epilog:
        parser.print_help(sys.stderr)
        sys.exit(1)

    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-5s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.WARNING
    )
    logging.addLevelName(logging.WARNING, 'WARN')
    logging.addLevelName(logging.CRITICAL, 'FATAL')
    logging.getLogger(__name__).setLevel(logging.DEBUG)

    config = Config(filename=args.config).load()
    credentials = GoogleCredentials(config).login()
    LOGGER.debug('Credentials file updated successfully')
    print(credentials.token)
