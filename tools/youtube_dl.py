#!/usr/bin/env python3
# Copyright (c) 2023 Sandor Balazsi (sandor.balazsi@gmail.com)
# vim: ts=4:sw=4:sts=4:et

"""Download YouTube videos that have been added to a particular playlist"""

import os, sys, logging, time, sched, signal, subprocess
from config import Config
from common import debug
from argparse import ArgumentParser, HelpFormatter
from google_oauth import GoogleCredentials
from googleapiclient.discovery import build
from threading import Thread
from functools import wraps

LOGGER = logging.getLogger(__name__)
GOOGLE_RETRIES = 10
SYNC_INTERVAL_SEC = 300
DOWNLOAD_CMD = ['yt-dlp', '-S', 'ext:mp4:m4a']

class YouTube:
    def __init__(self, config_file):
        self.config_file = config_file

    @debug('Logged in to Google')
    def login(self):
        config = Config(self.config_file).load()
        credentials = GoogleCredentials(config).login()
        self.youtube = build('youtube', 'v3', credentials=credentials)
        return self

    def playlist_by_name(self, name):
        page_token = None
        while True:
            response = self.youtube.playlists().list(
                pageToken=page_token,
                part="snippet,contentDetails",
                mine=True
            ).execute(num_retries=GOOGLE_RETRIES)
            for playlist in response.get('items', []):
                if playlist.get('snippet', {}).get('title') == name:
                    return playlist
            page_token = response.get('nextPageToken')
            if not page_token:
                raise Exception(f'No such playlist: {name}')

    @debug(lambda c: 'Fetched %d playlist items' % len(c), True)
    def playlist_items(self, playlist_id):
        items, page_token = [], None
        while True:
            response = self.youtube.playlistItems().list(
                pageToken=page_token,
                part="snippet,contentDetails",
                playlistId=playlist_id
            ).execute(num_retries=GOOGLE_RETRIES)
            items.extend(response.get('items', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                return items

    @debug(lambda i: 'Delete playlist item: %s (%s)' % (i.get('snippet').get('title'),
            i.get('snippet').get('resourceId').get('videoId')))
    def playlist_item_delete(self, playlist_item):
        self.youtube.playlistItems().delete(
            id=playlist_item.get('id')
        ).execute(num_retries=GOOGLE_RETRIES)
        return playlist_item

class YouTubeDownload:
    def __init__(self, youtube, playlist_name, target_folder):
        self.youtube = youtube
        self.playlist_id = youtube.playlist_by_name(playlist_name).get('id')
        self.target_folder = target_folder

    def asynchronous(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            thread = Thread(target=func, args=args, kwargs=kwargs)
            thread.start()
            return thread
        return wrapper

    def schedule(interval):
        def decorator(func, *args, **kwargs):
            def periodic(scheduler, interval, action, args=(), kwargs={}):
                scheduler.enter(interval, 1, periodic,
                    (scheduler, interval, action, args, kwargs))
                action(*args, **kwargs)

            @wraps(func)
            def wrapper(*args, **kwargs):
                scheduler = sched.scheduler(time.time, time.sleep)
                periodic(scheduler, interval, func, args, kwargs)
                scheduler.run()
            return wrapper
        return decorator

    @asynchronous
    @schedule(SYNC_INTERVAL_SEC)
    def run(self):
        for item in self.youtube.playlist_items(self.playlist_id):
            self.download(item.get('snippet').get('resourceId').get('videoId'))
            self.youtube.playlist_item_delete(item)

    @debug(lambda p: 'Performing command: %s' % ' '.join(p.args), True)
    def download(self, video_id):
        return subprocess.run(
            DOWNLOAD_CMD + ['https://youtu.be/' + video_id],
            cwd=self.target_folder,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

def exit_gracefully(*args):
    LOGGER.debug('Exiting...')
    sys.exit(0)

if __name__ == '__main__':
    parser = ArgumentParser(
        formatter_class=lambda prog: HelpFormatter(prog, max_help_position=34)
    )
    parser.add_argument(
        '-c', '--config', metavar='<file>', default='google_oauth.json',
        help='config file (default: google_oauth.json)'
    )
    parser.add_argument(
        '-p', '--playlist', metavar='<name>', default='Download',
        help='youtube playlist name to watch (default: Download)'
    )
    parser.add_argument(
        '-t', '--target', metavar='<folder>', default='~/Download',
        help='target folder (default: ~/Download)'
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
    for logger in [__name__, 'common', 'google_oauth']:
        logging.getLogger(logger).setLevel(logging.DEBUG)

    LOGGER.debug('Starting...')
    signal.signal(signal.SIGTERM, exit_gracefully)
    signal.signal(signal.SIGINT, exit_gracefully)

    youtube = YouTube(args.config).login()
    YouTubeDownload(youtube, args.playlist, args.target).run()
