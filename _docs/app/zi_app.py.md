<!-- METADATA: {"source_path": "app/zi_app.py", "source_sha": "f133184c9b3f3a9b3488b17fe16d86bbbbce3f14", "extraction_quality": "full_ast", "model": "gpt-5-mini", "generated_at": "2026-11-27T20:21:12Z", "doc_type": "file"} -->
<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "app/zi_app.py",
  "source_hash": "cb3ccb5485b5833638d38c335bd0be3b9408a48b1ae89a4eab473090b1c0df7a",
  "last_updated": "2026-11-27T20:21:12.097007+00:00",
  "git_sha": "f133184c9b3f3a9b3488b17fe16d86bbbbce3f14",
  "tokens_used": 7656,
  "complexity_score": 3,
  "estimated_review_time_minutes": 10,
  "external_dependencies": [
    "csv",
    "datetime",
    "json",
    "os",
    "random",
    "re",
    "shutil",
    "subprocess",
    "sys",
    "threading",
    "webbrowser",
    "zipfile",
    "http.server",
    "urllib.parse",
    "PIL"
  ]
}
```

</details>

[Documentation Home](../README.md) > [app](./README.md) > **zi_app**

---

# zi_app.py

> **File:** `app/zi_app.py`

![Complexity: Low](https://img.shields.io/badge/Complexity-Low-green) ![Review Time: 10min](https://img.shields.io/badge/Review_Time-10min-blue)

## 📑 Table of Contents


- [Overview](#overview)
- [Dependencies](#dependencies)
- [Architecture Notes](#architecture-notes)
- [Maintenance Notes](#maintenance-notes)
- [Functions and Classes](#functions-and-classes)

---

## Overview

This module implements the core of a small desktop web app for managing music projects and exports. It sets up a simple HTTP server handler (H) to serve a web UI, provides utilities for timestamping and slug construction, and performs file-based data management under a configurable zi_data directory. The code supports scanning an audio library, importing folders, creating job records, reading and writing JSON job and library metadata, generating simple cover images, and exporting releases (optionally using external tools such as ffmpeg). A main entry point launches the server and opens the browser to the local UI.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `csv` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `datetime` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `json` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `os` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `random` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `re` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `shutil` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `subprocess` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `sys` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `threading` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `webbrowser` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `zipfile` | import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile |
| `http.server` | from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer |
| `urllib.parse` | from urllib.parse import urlparse, parse_qs, quote |
| `PIL` |     try: from PIL import Image, ImageDraw |

## 📁 Directory

This file is part of the **app** directory. View the [directory index](./README.md) to see all files in this module.

## Architecture Notes

- Subclass of http.server.BaseHTTPRequestHandler to implement web UI interactions.
- File-system centric data management: JSON files and directory-based storage for jobs, library, and exports.
- Integration with external processes (subprocess) and optional media tooling (ffmpeg) for export operations.

## Maintenance Notes

- Provide an HTTP request handler class (H) to serve the desktop UI and respond to web requests.
- Manage persistent data in a filesystem-based zi_data directory with read_json, write_json, make_job, and list_jobs utilities.
- Scan and import audio files from a library (scan_library and import_folder) using configured audio extensions.
- Create simple cover images (make_cover) and produce packaged release exports (export_release), potentially invoking external tools.
- Expose a command-line entry point (main) to start the app and open the UI in a browser.


---

## Constants

| Name | Type | Value |
| --- | --- | --- |
| `ROOT` | — | `os.path.dirname(os.path.abspath(__file__))` |
| `DATA` | — | `os.environ.get('ZI_DATA', os.path.join(ROOT, 'zi_data'))` |
| `AUDIO_EXT` | — | `('.wav', '.mp3', '.flac', '.m4a')` |
| `ARTIST` | — | `'Rahal'` |
| `WRITER` | — | `'Rahal'` |
| `PRESETS` | — | `{'Melodic Techno 122': ('melodic progressive techno', 122, 'Warm analog bassline, rolling…` |
| `HTML` | — | `'<!doctype html><meta charset=utf-8><title>Zi Music Studio</title><meta name=viewport con…` |



---

## Functions and Classes


### now

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def now():
```

#### Description

Provide the current moment in time for the application — a utility function that produces the present timestamp or datetime value when called.

Returns a value representing the current date and/or time (a timestamp or datetime object) corresponding to the moment the function is invoked.

#### Complexity

Not analyzed

---



### slug

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def slug(s):
```

#### Description

Create a URL- or filename-friendly slug derived from the provided input value s, typically by normalizing and transforming the input into a compact, safe string representation.

s is the input value (typically a string) that will be converted into the slug form.

Returns the resulting slug as a string.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `s` | `Unknown` | ✅ | — |

#### Complexity

Not analyzed

---



### read_json

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def read_json(p, default=None):
```

#### Description

Read JSON data from the given path or source p and return the parsed Python object.

If reading or parsing fails, return the provided default value instead.


p is the path or identifier of the JSON source to read; default is the value to return when the JSON cannot be read or parsed (defaults to None).

Returns the parsed JSON as a Python object (e.g., dict or list), or the provided default if reading/parsing fails.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `p` | `Unknown` | ✅ | — |
| `default` = `None` | `Unknown` | ❌ | — |

#### Complexity

Not analyzed

---



### write_json

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def write_json(p, o):
```

#### Description

Serialize an object to JSON and write it to a file or destination indicated by the first argument.

The function takes a target (likely a file path or file-like destination) and an object to be written as JSON.


p is the target location (for example a file path or file-like object) where the JSON will be written; o is the Python object to be serialized to JSON and saved to that target.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `p` | `Unknown` | ✅ | — |
| `o` | `Unknown` | ✅ | — |

#### Complexity

Not analyzed

---



### make_job

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def make_job(d):
```

#### Description

Create and return a job representation based on the provided input.

The function builds a job (likely for scheduling or processing) from the data supplied in the argument.


d is the input data used to construct the job; it is expected to contain the fields or values required to populate the job representation (e.g., job attributes or configuration).

Returns the constructed job (e.g., a job object or dictionary) representing the input data prepared for use by the application.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `d` | `Unknown` | ✅ | — |

#### Complexity

Not analyzed

---



### list_jobs

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def list_jobs():
```

#### Description

Fetches and returns the set of jobs known to the application.

It acts as the endpoint or helper that gathers job entries so callers can inspect or display them.


Returns a collection (e.g., a list) of job records or objects representing the jobs available to the application.

#### Complexity

Not analyzed

---



### scan_library

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def scan_library():
```

#### Description

Scans the application's library to discover or update available items (e.g., media files, assets, or entries) and refreshes the internal catalog/state accordingly.

It performs a library scan operation triggered by the application logic to detect additions, removals, or changes in the library contents.

#### Complexity

Not analyzed

---



### import_folder

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def import_folder(src):
```

#### Description

Imports the contents of a folder located at the given source path into the application.

The function takes the path to a directory and processes or loads its files into the app's internal structures or storage as needed.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `src` | `Unknown` | ✅ | — |

#### Complexity

Not analyzed

---



### make_cover

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def make_cover(path, title, seed):
```

#### Description

Generates or renders a cover (for example an image or document) at the given filesystem path using the provided title and a randomness seed.

The seed parameter is used to control any randomized aspects of the generated cover so results can be reproduced.


path specifies where the generated cover will be written; title is the text used on the cover; seed controls deterministic randomness for any procedural or stochastic elements during generation.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `path` | `Unknown` | ✅ | — |
| `title` | `Unknown` | ✅ | — |
| `seed` | `Unknown` | ✅ | — |

#### Complexity

Not analyzed

---



### export_release

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def export_release(track_id, title, genre, language='Instrumental', explicit='No'):
```

#### Description

Prepare and export a music release record identified by a track identifier, including its title, genre, and optional metadata such as language and explicit content flag.

The function packages these attributes and performs the export operation for the specified track.


Returns a value indicating the outcome of the export operation, such as a success/failure status or export metadata (e.g., confirmation details or an exported record identifier).

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `track_id` | `Unknown` | ✅ | — |
| `title` | `Unknown` | ✅ | — |
| `genre` | `Unknown` | ✅ | — |
| `language` = `'Instrumental'` | `Unknown` | ❌ | — |
| `explicit` = `'No'` | `Unknown` | ❌ | — |

#### Complexity

Not analyzed

---



### H

![Type: Concrete](https://img.shields.io/badge/Type-Concrete-green) ![Methods: 4](https://img.shields.io/badge/Methods-4-blue)

#### Description

H is an HTTP request handler class (subclassing BaseHTTPRequestHandler) responsible for processing incoming HTTP requests and producing responses.

Within app/zi_app.py, H acts as the concrete request handler that encapsulates the server-side logic for incoming HTTP traffic. It ties together logging, response emission, and GET/POST request handling for the module's HTTP interface.

Responsibilities:
- Provide custom logging behavior for requests via the log_message method.
- Construct and transmit HTTP responses using the send method.
- Handle HTTP GET requests in the do_GET method.
- Handle HTTP POST requests in the do_POST method.

#### Inheritance

**Inherits from:** `BaseHTTPRequestHandler`

#### Methods

##### Public Methods

| Method | Type | Description |
| --- | --- | --- |
| `log_message` | instance | Method log_message.<br>**Signature:** `def log_message(self, *a):` |
| `send` | instance | Method send.<br>**Signature:** `def send(self, code, body, ctype='application/json'):` |
| `do_GET` | instance | Method do_GET.<br>**Signature:** `def do_GET(self):` |
| `do_POST` | instance | Method do_POST.<br>**Signature:** `def do_POST(self):` |

---



### log_message

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def log_message(self, *a):
```

#### Description

Instance method intended to record or forward a log message for the H object.

It accepts an arbitrary number of positional arguments which are expected to form the content of the message to be logged.


'a' is a variable-length tuple of positional arguments that supply the pieces of the message (e.g., strings or objects to be included in the log).

No explicit return annotation is provided; the method does not declare a return value and therefore implicitly returns None.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `a` | `Unknown` | ❌ | — |

#### Complexity

Not analyzed

---



### send

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def send(self, code, body, ctype='application/json'):
```

#### Description

Send an HTTP response using the handler H with the given status code, response body, and content type.

The method packages the provided body and sets the Content-Type header to the ctype value before sending the response to the client.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `code` | `Unknown` | ✅ | — |
| `body` | `Unknown` | ✅ | — |
| `ctype` = `'application/json'` | `Unknown` | ❌ | — |

#### Complexity

Not analyzed

---



### do_GET

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def do_GET(self):
```

#### Description

Handles an incoming HTTP GET request for an instance of the H class.

This method implements the behavior performed when the server receives a GET request (for example, preparing and sending the appropriate HTTP response to the client).

#### Complexity

Not analyzed

---



### do_POST

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def do_POST(self):
```

#### Description

Handle an incoming HTTP POST request for an instance of the H request handler.

This method implements the server-side logic that should be executed when a POST request is received by the handler.

#### Complexity

Not analyzed

---



### main

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def main(port=8765):
```

#### Description

Entry point for the application that starts or runs the main server/process.

It accepts an optional port number and will initiate the application to listen on that port (default 8765).

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `port` = `8765` | `Unknown` | ❌ | — |

#### Complexity

Not analyzed

---



---

## Navigation

**↑ Parent Directory:** [Go up](./README.md)

---

*This documentation was automatically generated by AI ([Woden DocBot](https://github.com/marketplace/ai-document-creator)) and may contain errors. It is the responsibility of the user to validate the accuracy and completeness of this documentation.*
