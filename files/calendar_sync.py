#!/usr/bin/env python3
# Copyright (c) 2022-2023 Sandor Balazsi (sandor.balazsi@gmail.com)
# vim: ts=4:sw=4:sts=4:et

"""One-way synchronization of calendars (from Office 365 to Google)"""

import os, sys, logging, datetime, time, sched, signal
from config import Config
from argparse import ArgumentParser, HelpFormatter
from o365_oauth import Office365Credentials, Office365ExchangeAccount
from google_oauth import GoogleCredentials
from googleapiclient.discovery import build
from exchangelib.ewsdatetime import EWSDateTime, EWSTimeZone
from exchangelib.folders.known_folders import Calendar
from dateutil.rrule import rrule, DAILY
from threading import Thread
from functools import wraps

LOGGER = logging.getLogger(__name__)
PAST_EVENTS = datetime.timedelta(days = 7)
FUTURE_EVENTS = datetime.timedelta(days = 28)
GOOGLE_RETRIES = 10
SYNC_INTERVAL_SEC = 300

def debug(msg, runtime=False):
    def decorator(func, *args, **kwargs):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            result = func(*args, **kwargs)
            delta = datetime.timedelta(seconds=time.monotonic() - start)
            duration = ' (duration: {})'.format(delta) if runtime else ''
            if not callable(msg):
                LOGGER.debug(msg + duration)
            elif result != None:
                LOGGER.debug(msg(result) + duration)
            return result
        return wrapper
    return decorator

class ExchangeCalendar:
    def __init__(self, config_file, calendar_name):
        self.config_file = config_file
        self.calendar_name = calendar_name

    @debug('Logged in to Office 365')
    def login(self):
        config = Config(self.config_file).load()
        credentials = Office365Credentials(config).login()
        self.account = Office365ExchangeAccount(credentials).build()
        self.calendar = self.calendar_by_name(self.calendar_name)
        self.tz = EWSTimeZone.localzone()
        return self

    def calendar_by_name(self, name):
        if name == 'Calendar':
            return self.account.calendar
        else:
            for folder in self.account.root.walk().get_folders():
                if isinstance(folder, Calendar) and folder.name == name:
                    return folder
            raise Exception(f'No such Exchange calendar: {name}')

    @debug(lambda e: 'Fetched %d events from Office 365 calendar' % len(e), True)
    def events(self, start, end):
        try:
            events = []
            timerange = rrule(freq=DAILY, dtstart=start, until=end)
            for range_start, range_end in zip(timerange, timerange[1:]):
                events.extend([event for event in list(self.calendar.view(
                    start = EWSDateTime.from_datetime(range_start).astimezone(self.tz),
                    end = EWSDateTime.from_datetime(range_end).astimezone(self.tz))
                ) if not event.is_all_day])
            return events
	    # TODO: https://github.com/ecederstrand/exchangelib/issues/109#issuecomment-311041273
        except Exception as e:
            LOGGER.error('Failed to fetch Office 365 events:', str(e))

    def fingerprint(self, event):
        return hash('|'.join((
            event.start.astimezone(self.tz).isoformat(),
            event.end.astimezone(self.tz).isoformat(),
            event.subject,
            event.text_body or ''
        )))

class GoogleCalendar:
    def __init__(self, config_file, calendar_name):
        self.config_file = config_file
        self.calendar_name = calendar_name

    @debug('Logged in to Google')
    def login(self):
        config = Config(self.config_file).load()
        credentials = GoogleCredentials(config).login()
        self.account = build('calendar', 'v3', credentials=credentials)
        self.calendar = self.calendar_by_name(self.calendar_name)
        self.tz = datetime.datetime.now().astimezone().tzinfo
        return self

    def calendar_by_name(self, name):
        page_token = None
        while True:
            calendar_list = self.account.calendarList().list(
                pageToken=page_token
            ).execute(num_retries=GOOGLE_RETRIES)
            for calendar in calendar_list['items']:
                if calendar.get('summary') == name \
                or calendar.get('summaryOverride') == name \
                or (name == 'primary' and calendar.get('primary') == True):
                    return calendar
            page_token = calendar_list.get('nextPageToken')
            if not page_token:
                raise Exception(f'No such Google calendar: {name}')

    @debug(lambda e: 'Fetched %d events from Google calendar' % len(e), True)
    def events(self, start, end):
        events, page_token = [], None
        while True:
            event_list = self.account.events().list(
                pageToken=page_token,
                calendarId=self.calendar.get('id'),
                timeMin=start.astimezone(self.tz).isoformat(),
                timeMax=end.astimezone(self.tz).isoformat(),
                timeZone=self.tz
            ).execute(num_retries=GOOGLE_RETRIES)
            events.extend(event_list['items'])
            page_token = event_list.get('nextPageToken')
            if not page_token:
                return events

    def fingerprint(self, event):
        return hash('|'.join((
            event.get('start').get('dateTime'),
            event.get('end').get('dateTime'),
            event.get('summary'),
            event.get('description', '')
        )))

    def create(self, start, end, subject, **kwargs):
        event = {
            'start': { 'dateTime': start.isoformat() },
            'end': { 'dateTime': end.isoformat() },
            'summary': subject
        }
        if kwargs.get('description'):
            event['description'] = kwargs.get('description')
        event = self.account.events().insert(
            calendarId=self.calendar.get('id'),
            body=event
        ).execute(num_retries=GOOGLE_RETRIES)
        LOGGER.debug('Event created: %s, %s (%s)',
            subject, start.isoformat(), event['htmlLink']
        )

    def delete(self, event):
        self.account.events().delete(
            calendarId=self.calendar.get('id'),
            eventId=event.get('id')
        ).execute(num_retries=GOOGLE_RETRIES)
        LOGGER.debug(f'Event deleted: %s, %s',
            event['summary'], event['start']['dateTime']
        )

class CalendarSync:
    def __init__(self, source_calendar, target_calendar):
        self.source_calendar = source_calendar
        self.target_calendar = target_calendar

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
        now = datetime.datetime.utcnow()
        start, end = now - PAST_EVENTS, now + FUTURE_EVENTS
        LOGGER.debug(f'Time window: {start} .. {end}')

        source_events = self.event_map(self.source_calendar, start, end)
        if source_events == None: return
        target_events = self.event_map(self.target_calendar, start, end)
        if target_events == None: return
        for fingerprint, source_event in source_events.items():
            if fingerprint in target_events:
                del target_events[fingerprint]
            else:
                self.target_calendar.create(
                    source_event.start.astimezone(self.source_calendar.tz),
                    source_event.end.astimezone(self.source_calendar.tz),
                    source_event.subject,
                    description = source_event.text_body or None
                )
        for fingerprint, target_event in target_events.items():
            self.target_calendar.delete(target_event)

    def event_map(self, calendar, start, end):
        return {
            calendar.fingerprint(event): event for event in calendar.events(start, end)
        }

def exit_gracefully(*args):
    LOGGER.debug('Exiting...')
    sys.exit(0)

if __name__ == '__main__':
    parser = ArgumentParser(
        formatter_class=lambda prog: HelpFormatter(prog, max_help_position=32)
    )
    parser.add_argument(
        '-e', '--exchange', metavar='<file>', default='o365_oauth.json',
        help='Exchange (Office 365) config file (default: o365_oauth.json)'
    )
    parser.add_argument(
        '-s', '--source', metavar='<name>', default='Calendar',
        help='Source calendar name in Exchange (default: Calendar)'
    )
    parser.add_argument(
        '-g', '--google', metavar='<file>', default='google_oauth.json',
        help='Google config file (default: google_oauth.json)'
    )
    parser.add_argument(
        '-t', '--target', metavar='<name>', default='primary',
        help='Target calendar name in Google (default: primary)'
    )
    args = parser.parse_args()

    if not os.path.isfile(args.exchange):
        parser.epilog='No such Exchange config file: %s' % args.exchange
    if not os.path.isfile(args.google):
        parser.epilog='No such Google config file: %s' % args.google
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
    for logger in [__name__, 'google_oauth', 'o365_oauth']:
        logging.getLogger(logger).setLevel(logging.DEBUG)

    LOGGER.debug('Starting...')
    signal.signal(signal.SIGTERM, exit_gracefully)
    signal.signal(signal.SIGINT, exit_gracefully)
    exchange = ExchangeCalendar(args.exchange, args.source).login()
    google = GoogleCalendar(args.google, args.target).login()
    CalendarSync(exchange, google).run()
