# [PIM](https://en.wikipedia.org/wiki/Personal_information_manager "Personal information manager") tools

Various tools for managing calendar, contact and email entries for Exchange (Office 365) and Google accounts.

## Tools

### calendar_sync.py
One-way synchronization of calendars (from Office 365 to Google)
```
$ ./pim_tools.sh calendar_sync.py -h
...
usage: calendar_sync.py [-h] [-e <file>] [-s <name>] [-g <file>] [-t <name>] [-l <file>]

options:
  -h, --help                    show this help message and exit
  -e <file>, --exchange <file>  Exchange (Office 365) config file (default: o365_oauth.json)
  -s <name>, --source <name>    Source calendar name in Exchange (default: Calendar)
  -g <file>, --google <file>    Google config file (default: google_oauth.json)
  -t <name>, --target <name>    Target calendar name in Google (default: primary)
  -l <file>, --log <file>       Log file name (default: calendar_sync.log)
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
  "client_secret": "..."
}
```
