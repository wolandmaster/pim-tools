# [PIM](https://en.wikipedia.org/wiki/Personal_information_manager "Personal information manager") tools

Various tools for managing calendar, contact and email entries for Exchange (Office 365) and Google accounts.

## Tools

### calendar_sync.py

One-way synchronization of calendars (from Office 365 to Google).
Required google auth scopes: "https://www.googleapis.com/auth/calendar.readonly"
and "https://www.googleapis.com/auth/calendar.events".
```
$ ./pim_tools.sh calendar_sync.py -h
...
usage: calendar_sync.py [-h] [-e <file>] [-s <name>] [-g <file>] [-t <name>] [-l <file>]

options:
  -h, --help                    show this help message and exit
  -e <file>, --exchange <file>  exchange (office 365) config file (default: o365_oauth.json)
  -s <name>, --source <name>    source calendar name in exchange (default: Calendar)
  -g <file>, --google <file>    google config file (default: google_oauth.json)
  -t <name>, --target <name>    target calendar name in google (default: primary)
```

### youtube_dl.py

Download YouTube videos that have been added to a particular playlist.
After a successful download, the related playlist item is deleted from the playlist.
Required google auth scope: "https://www.googleapis.com/auth/youtube".
```
$ ./pim-tools.sh youtube_dl.py -h
...
usage: youtube_dl.py [-h] [-c <file>] [-p <name>] [-t <folder>]

options:
  -h, --help                      show this help message and exit
  -c <file>, --config <file>      config file (default: google_oauth.json)
  -p <name>, --playlist <name>    youtube playlist name to watch (default: Download)
  -t <folder>, --target <folder>  target folder (default: ~/Download)
```

### google_oauth.py

Make/refresh Google oauth2 and print the access token.
```
$ ./pim_tools.sh google_oauth.py -h
...
usage: google_oauth.py [-h] [-c <file>]

options:
  -h, --help                  show this help message and exit
  -c <file>, --config <file>  config file (default: google_oauth.json)
```

### o365_oauth.py

Make/refresh Office 365 oauth2 and print the access token.
```
$ ./pim-tools.sh o365_oauth.py -h
...
usage: o365_oauth.py [-h] [-c <file>]

options:
  -h, --help                  show this help message and exit
  -c <file>, --config <file>  config file (default: o365_oauth.json)
```

## Config files

### Exchange (Office 365) config file template

o365_oauth.json:
```json
{
  "client_id": "...",
  "tenant_id": "...",
  "email_address": "..."
}
```

### Google config file template

google_oauth.json:
```json
{
  "client_id": "...",
  "client_secret": "...",
  "scopes": [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "..."
  ]
}
```
