#!/usr/bin/env python3
# Copyright (c) 2022-2023 Sandor Balazsi (sandor.balazsi@gmail.com)
# vim: ts=4:sw=4:sts=4:et

"""Office 365 Interactive OAuth 2.0"""

import os, sys, logging, time, requests, json
from config import Config
from argparse import ArgumentParser, HelpFormatter
from oauthlib.oauth2 import WebApplicationClient
from exchangelib import Account, Configuration, FaultTolerance, DELEGATE
from exchangelib.protocol import BaseProtocol, Protocol
from exchangelib.credentials import BaseOAuth2Credentials
from cached_property import threaded_cached_property

LOGGER = logging.getLogger(__name__)
EXCHANGE_SERVER = 'outlook.office365.com'
REDIRECT_URI = 'https://login.microsoftonline.com/common/oauth2/nativeclient'
USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:107.0) Gecko/20100101 Firefox/107.0'
RETRY_POLICY_MAX_WAIT_SEC = 3600
BaseProtocol.USERAGENT = USER_AGENT
BaseProtocol.TIMEOUT = RETRY_POLICY_MAX_WAIT_SEC

class Office365Credentials(BaseOAuth2Credentials):
    def __init__(self, config):
        super().__init__(
            tenant_id=config.get('tenant_id'),
            client_id=config.get('client_id'),
            client_secret=None
        )
        self.config = config
        self.refresh_token = config.get('refresh_token')

    def login(self):
        if self.config.has('refresh_token'):
            self.refresh()
        else:
            self.code = self.authorize()
            Protocol(config=Configuration(
                server=EXCHANGE_SERVER,
                credentials=self
            )).create_session()
        return self

    def refresh(self, session=None):
        super().refresh(session)
        response = requests.post('https://login.microsoftonline.com/' \
                '{}/oauth2/token'.format(self.tenant_id),
            headers={
                 'User-Agent': USER_AGENT
            },
            data={
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'refresh_token': self.refresh_token,
                'redirect_uri': REDIRECT_URI,
                'resource': f'https://{EXCHANGE_SERVER}'
            }
        )
        response_json = json.loads(response.content)
        if not response.ok:
            LOGGER.error(response_json['error_description'])
            response.raise_for_status()
        else:
            self.on_token_auto_refreshed(response_json)

    def on_token_auto_refreshed(self, access_token):
        super().on_token_auto_refreshed(access_token)
        self.refresh_token = self.access_token['refresh_token']
        self.config.set('refresh_token', self.refresh_token).save()
        LOGGER.debug('Office 365 oauth token refreshed')

    def authorize(self):
        from subprocess import Popen, DEVNULL
        from marionette_driver.marionette import Marionette
        from urllib.parse import urlparse, parse_qs

        firefox_process = Popen([
            'firefox', '--kiosk', '--marionette',
            '--width', '500', '--height', '700', '--private-window', 'about:blank'
        ], stdout=DEVNULL, stderr=DEVNULL)

        firefox = Marionette()
        firefox.start_session()
        firefox.navigate(self.authorization_url())
        while True:
            url = firefox.get_url()
            if url.startswith(REDIRECT_URI):
                code = parse_qs(urlparse(url).query)['code'][0]
                break
            time.sleep(1)
        firefox.delete_session()
        firefox_process.terminate()
        return code

    def authorization_url(self):
        from urllib.parse import quote_plus

        return 'https://login.microsoftonline.com/' \
                '{tenant_id}/oauth2/authorize' \
                '?client_id={client_id}' \
                '&login_hint={login_hint}' \
                '&response_type={response_type}' \
                '&response_mode={response_mode}' \
                '&redirect_uri={redirect_uri}' \
                '&resource={resource}'.format(
            tenant_id=self.config.get('tenant_id'),
            client_id=self.config.get('client_id'),
            login_hint=quote_plus(self.config.get('email_address')),
            response_type='code',
            response_mode='query',
            redirect_uri=quote_plus(REDIRECT_URI),
            resource=quote_plus(f'https://{EXCHANGE_SERVER}')
        )

    @property
    def token_url(self):
        return f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/token'

    @property
    def scope(self):
        return None

    def session_params(self):
        params = super().session_params()
        params.update({
            'redirect_uri': REDIRECT_URI,
            'token_updater': self.on_token_auto_refreshed
        })
        return params

    def token_params(self):
        params = super().token_params()
        if self.code:
            params['code'] = self.code
            self.code = None
        return params

    @threaded_cached_property
    def client(self):
        return WebApplicationClient(client_id=self.client_id)

class Office365ExchangeAccount:
    def __init__(self, credentials):
        self.credentials = credentials

    def build(self):
        configuration = Configuration(
            server=EXCHANGE_SERVER,
	    retry_policy=FaultTolerance(max_wait=RETRY_POLICY_MAX_WAIT_SEC),
            credentials=self.credentials
        )
        return Account(
            primary_smtp_address=self.credentials.config.get('email_address'),
            config=configuration,
            autodiscover=False,
            access_type=DELEGATE
        )

if __name__ == '__main__':
    parser = ArgumentParser(
        formatter_class=lambda prog: HelpFormatter(prog, max_help_position=30)
    )
    parser.add_argument(
        '-c', '--config', metavar='<file>', default='o365_oauth.json',
        help='Config file (default: o365_oauth.json)'
    )
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        parser.epilog='No such config file: %s' % args.config
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
    credentials = Office365Credentials(config).login()
    LOGGER.debug('Credentials file updated successfully')
    print(credentials.access_token['access_token'])
