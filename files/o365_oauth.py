#!/usr/bin/env python3
# Copyright (c) 2022 Sandor Balazsi (sandor.balazsi@gmail.com)

"""Office 365 Interactive OAuth 2.0"""

import logging, time, requests, json
from config import Config
from oauthlib.oauth2 import WebApplicationClient
from exchangelib import Account, Configuration, DELEGATE
from exchangelib.protocol import BaseProtocol
from exchangelib.credentials import BaseOAuth2Credentials
from subprocess import Popen, DEVNULL
from marionette_driver.marionette import Marionette
from urllib.parse import quote_plus, urlparse, parse_qs
from cached_property import threaded_cached_property

LOGGER = logging.getLogger(__name__)
EXCHANGE_SERVER = 'outlook.office365.com'
REDIRECT_URI = 'https://login.microsoftonline.com/common/oauth2/nativeclient'
USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:107.0) Gecko/20100101 Firefox/107.0'
BaseProtocol.USERAGENT = USER_AGENT

class Office365OAuth2Credentials(BaseOAuth2Credentials):
    def __init__(self, config):
        super().__init__(
            tenant_id = config.get('tenant_id'),
            client_id = config.get('client_id'),
            client_secret = None
        )
        self.config = config
        self.email_address = config.get('email_address')
        self.refresh_token = config.get('refresh_token')

    def refresh(self, session = None):
        super().refresh(session)
        response = requests.post('https://login.microsoftonline.com/' \
                '{}/oauth2/token'.format(self.tenant_id),
            headers = {
                 'User-Agent': USER_AGENT
            },
            data = {
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
        self.code = None
        self.refresh_token = self.access_token['refresh_token']
        self.config.set('refresh_token', self.refresh_token).save()
        LOGGER.debug('Office 365 oauth token refreshed')

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
        return params

    @threaded_cached_property
    def client(self):
        return WebApplicationClient(client_id = self.client_id)

class Office365ExchangeAccount:
    def __init__(self, config):
        self.config = config

    def login(self):
        credentials = Office365OAuth2Credentials(self.config)
        if self.config.has('refresh_token'):
            credentials.refresh()
        else:
            credentials.code = self.authorize()
        configuration = Configuration(
            server = EXCHANGE_SERVER,
            credentials = credentials
        )
        return Account(
            primary_smtp_address = self.config.get('email_address'),
            config = configuration,
            autodiscover = False,
            access_type = DELEGATE
        )

    def authorization_url(self):
        return 'https://login.microsoftonline.com/' \
                '{tenant_id}/oauth2/authorize' \
                '?client_id={client_id}' \
                '&login_hint={login_hint}' \
                '&response_type={response_type}' \
                '&response_mode={response_mode}' \
                '&redirect_uri={redirect_uri}' \
                '&resource={resource}'.format(
            tenant_id = self.config.get('tenant_id'),
            client_id = self.config.get('client_id'),
            login_hint = quote_plus(self.config.get('email_address')),
            response_type = 'code',
            response_mode = 'query',
            redirect_uri = quote_plus(REDIRECT_URI),
            resource = quote_plus(f'https://{EXCHANGE_SERVER}')
        )

    def authorize(self):
        firefox_process = Popen([
            'firefox', '--kiosk', '--marionette',
            '--width', '500', '--height', '700', '--private-window', 'about:blank'
        ], stdout = DEVNULL, stderr = DEVNULL)

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

if __name__ == '__main__':
    logging.basicConfig(
        format = '%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
        level = logging.INFO
    )
    config = Config(filename = 'o365_oauth.json').load()
    Office365ExchangeAccount(config).login()
    LOGGER.info('Credentials file updated successfully')
