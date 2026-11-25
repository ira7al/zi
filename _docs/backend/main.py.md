<!-- METADATA: {"source_path": "backend/main.py", "source_sha": "c7795eabe4913b979ecaa5d8e90c8c9e3df42085", "extraction_quality": "full_ast", "model": "gpt-5-mini", "generated_at": "2026-11-25T09:25:20Z", "doc_type": "file"} -->
<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "backend/main.py",
  "source_hash": "2194cccf7ff7e294c93e2dd3a289cde66d4eb659df7f2a542543078b7a6adee0",
  "last_updated": "2026-11-25T09:25:20.933286+00:00",
  "git_sha": "c7795eabe4913b979ecaa5d8e90c8c9e3df42085",
  "tokens_used": 11194,
  "complexity_score": 5,
  "estimated_review_time_minutes": 16,
  "external_dependencies": [
    "asyncio",
    "os",
    "re",
    "shutil",
    "time",
    "contextlib",
    "secrets",
    "httpx",
    "fastapi",
    "fastapi.middleware.cors",
    "fastapi.responses",
    "pydantic",
    "bot",
    "pipeline",
    "storage",
    "connectors",
    "connectors.base"
  ]
}
```

</details>

[Documentation Home](../README.md) > [backend](./README.md) > **main**

---

# main.py

> **File:** `backend/main.py`

![Complexity: Medium](https://img.shields.io/badge/Complexity-Medium-yellow) ![Review Time: 16min](https://img.shields.io/badge/Review_Time-16min-blue)

## 📑 Table of Contents


- [Overview](#overview)
- [Dependencies](#dependencies)
- [Architecture Notes](#architecture-notes)
- [Maintenance Notes](#maintenance-notes)
- [Functions and Classes](#functions-and-classes)

---

## Overview

This module defines a FastAPI application that exposes an HTTP API for creating and retrieving generation tasks, managing release packages, and interacting with a lightweight bot queue. It declares Pydantic request models (GenerationRequest, ReleaseRequest, SubmitMark, BotBrief) and a collection of async route handlers for operations such as creating and polling generations, serving audio files, validating and creating releases, listing and downloading release packages, and marking submissions. The application behavior is influenced by environment-configured constants (e.g., REPLICATE_TOKEN, ADMIN_TOKEN, ALLOWED_ORIGINS, BOT_ENABLED) and includes lifecycle management via an async lifespan function.

Administrative and resource-sensitive endpoints are protected by a require_admin function that checks an admin token from headers. The module also contains utility functions for locating files (find_work_file, find_file_in_directory), and it integrates middleware and responses relevant to CORS and file delivery. Network operations appear to use httpx, and status polling is coordinated with a poll interval and a status_last_poll map to track recent activity.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `asyncio` | import asyncio |
| `os` | import os |
| `re` | import re |
| `shutil` | import shutil |
| `time` | import time |
| `contextlib` | from contextlib import asynccontextmanager |
| `secrets` | from secrets import compare_digest |
| `httpx` | import httpx |
| `fastapi` | from fastapi import Depends, FastAPI, Header, HTTPException |
| `fastapi.middleware.cors` | from fastapi.middleware.cors import CORSMiddleware |
| `fastapi.responses` | from fastapi.responses import FileResponse |
| `pydantic` | from pydantic import BaseModel, Field, field_validator |
| `bot` | import bot |
| `pipeline` | import pipeline |
| `storage` | import storage |
| `connectors` | from connectors import REGISTRY |
| `connectors.base` | from connectors.base import ReleaseMetadata, check_instrumental |

## 📁 Directory

This file is part of the **backend** directory. View the [directory index](./README.md) to see all files in this module.

## Architecture Notes

- Uses FastAPI for HTTP routing and lifecycle management (app, async endpoints, lifespan).
- Defines request and data schemas with Pydantic BaseModel subclasses.
- Implements asynchronous handlers throughout (async functions) for I/O-bound operations.
- Configures behavior and secrets through environment variables (REPLICATE_TOKEN, ADMIN_TOKEN, ALLOWED_ORIGINS, BOT_ENABLED).
- Performs file discovery and delivery via helper functions and FileResponse, and uses httpx for outbound HTTP calls.

## Maintenance Notes

- Provide a FastAPI application instance (app) with configured lifespan and CORS handling for the API titled 'Zi API'.
- Define Pydantic request models used by route handlers: GenerationRequest, ReleaseRequest, SubmitMark, and BotBrief.
- Expose async endpoints to create and retrieve generations, stream or serve audio files, and manage generation status polling.
- Expose endpoints to validate, create, list, retrieve, and download release packages and related files.
- Implement a bot queue API surface (bot_enqueue, bot_queue) and a submission-marking endpoint, with admin protection for sensitive operations.


---

## Constants

| Name | Type | Value |
| --- | --- | --- |
| `REPLICATE_TOKEN` | — | `os.getenv('REPLICATE_API_TOKEN', '')` |
| `ALLOWED_ORIGINS` | — | `os.getenv('ALLOWED_ORIGINS', '*').split(',')` |
| `ADMIN_TOKEN` | — | `os.getenv('ADMIN_TOKEN', '')` |
| `BOT_ENABLED` | — | `os.getenv('BOT_ENABLED', '1') == '1'` |
| `JOB_ID` | — | `'^[A-Za-z0-9_-]{4,64}$'` |
| `STATUS_POLL_INTERVAL_SECONDS` | — | `8.0` |
| `status_last_poll` | `dict[str, float]` | `{}` |
| `app` | — | `FastAPI(title='Zi API', version='0.05', lifespan=lifespan)` |



---

## Functions and Classes


### require_admin

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def require_admin(authorization: str = Header(default='')):
```

#### Description

Enforces protection for administrative and resource-intensive endpoints by verifying that requests are authorized for admin-level access.

It is intended to be used as a guard for routes that require elevated privileges or consume significant resources.


Either allows the request to proceed (e.g., by returning control or an auth-related object) or stops it by raising an HTTP error when authorization fails.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `authorization` = `Header(default='')` | `str` | ❌ | — |

#### Complexity

Not analyzed

---



### lifespan

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def lifespan(_: FastAPI):
```

#### Description

An asynchronous context manager function intended to manage the FastAPI application's lifespan events (startup and shutdown).

It is used by FastAPI to run setup before the application starts serving requests and to perform cleanup when the application is shutting down.


Provides an async context manager (via asynccontextmanager) that yields control to the application runtime for the duration of the app's lifespan.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `_` | `FastAPI` | ✅ | — |

#### Complexity

Not analyzed

---



### find_work_file

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def find_work_file(*parts: str, filename: str) -> str | None:
```

#### Description

Compose a filesystem path from a sequence of path components and a filename, then locate and return that file path if it exists.

The function accepts any number of path parts followed by a filename and returns the full path to the corresponding "work" file or None if not found.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `parts` | `str` | ❌ | — |
| `filename` | `str` | ✅ | — |

#### Returns

**Type:** `str | None`

—

#### Complexity

Not analyzed

---



### find_file_in_directory

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def find_file_in_directory(directory: str | None, filename: str) -> str | None:
```

#### Description

Locate a file with the given filename inside the provided directory and return its path if found.

If the file is not present (or cannot be located), return None.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `directory` | `str | None` | ✅ | — |
| `filename` | `str` | ✅ | — |

#### Returns

**Type:** `str | None`

—

#### Complexity

Not analyzed

---



### GenerationRequest

![Type: Concrete](https://img.shields.io/badge/Type-Concrete-green) ![Methods: 1](https://img.shields.io/badge/Methods-1-blue) ![Attributes: 3](https://img.shields.io/badge/Attributes-3-blue)

#### Description

A pydantic data model that represents the input needed to request generation of an audio track, capturing the track name, textual prompt, and desired duration.

Acts as the canonical request schema within backend/main.py, providing a single source of truth for generation parameters that other functions or endpoints in the module can accept and rely upon for type-checked data.

Responsibilities:
- Declare and validate the required fields for a generation request: track_name (str), prompt (str), and duration (int).
- Hold and serialize/deserialze generation parameters in a structured form suitable for passing between components or across boundaries (e.g., API, service layer).
- Provide a class-level helper via the _no_vocals classmethod to offer an alternate or convenience representation/behavior related to generation requests.

#### Inheritance

**Inherits from:** `BaseModel`

#### Attributes

| Attribute | Type | Visibility | Description |
| --- | --- | --- | --- |
| `track_name` (class) | `str` | 🔓 public | Class attribute track_name<br>**Default:** `Field(default='Untitled track', max_length=80)` |
| `prompt` (class) | `str` | 🔓 public | Class attribute prompt<br>**Default:** `Field(min_length=3, max_length=1000)` |
| `duration` (class) | `int` | 🔓 public | Class attribute duration<br>**Default:** `Field(default=190, ge=pipeline.MIN_TRACK_SECONDS, le=300)` |

#### Methods

##### Protected Methods

| Method | Type | Description |
| --- | --- | --- |
| `_no_vocals` | classmethod | Method _no_vocals.<br>**Signature:** `def _no_vocals(cls, v: str) -> str:` |

---



### _no_vocals

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def _no_vocals(cls, v: str) -> str:
```

#### Description

A class-level field validator method that takes a string value and returns a processed string.

It is intended to validate and/or transform the input 'v' for the GenerationRequest data model (likely enforcing a "no vocals" constraint) before the value is accepted.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `v` | `str` | ✅ | — |

#### Returns

**Type:** `str`

—

#### Complexity

Not analyzed

---



### ReleaseRequest

![Type: Concrete](https://img.shields.io/badge/Type-Concrete-green) ![Attributes: 3](https://img.shields.io/badge/Attributes-3-blue)

#### Description

ReleaseRequest is a Pydantic model that represents the payload for initiating or describing a release operation.

Within backend/main.py, ReleaseRequest serves as the canonical data transfer object for release actions, making it the standard representation of input required by functions or endpoints that perform or schedule releases. It centralizes the core identifiers and metadata needed by the module to handle a release.

Responsibilities:
- Hold and validate the required fields for a release operation: job_id, connector, and metadata.
- Provide a clear typed container for passing release-related data between components or layers.
- Support serialization and deserialization of release request data (e.g., to/from JSON) via BaseModel capabilities.
- Ensure consistent data structure for downstream processing of release operations.

#### Inheritance

**Inherits from:** `BaseModel`

#### Attributes

| Attribute | Type | Visibility | Description |
| --- | --- | --- | --- |
| `job_id` (class) | `str` | 🔓 public | Class attribute job_id<br>**Default:** `Field(pattern=JOB_ID)` |
| `connector` (class) | `str` | 🔓 public | Class attribute connector<br>**Default:** `'routenote'` |
| `metadata` (class) | `ReleaseMetadata` | 🔓 public | Class attribute metadata |

---



### SubmitMark

![Type: Concrete](https://img.shields.io/badge/Type-Concrete-green) ![Attributes: 1](https://img.shields.io/badge/Attributes-1-blue)

#### Description

SubmitMark is a Pydantic data model representing the payload or schema for submitting a mark-related reference.

Within backend/main.py, SubmitMark functions as a lightweight schema for incoming or outgoing data related to mark submission. It standardizes how a routenote reference is represented and validated across the module.

Responsibilities:
- Define and validate the structure of the submission payload containing a routenote reference.
- Ensure that the routenote_ref attribute is present and is a string according to the Pydantic BaseModel rules.
- Provide a typed container that other parts of the application can use for serialization, deserialization, and data exchange.

#### Inheritance

**Inherits from:** `BaseModel`

#### Attributes

| Attribute | Type | Visibility | Description |
| --- | --- | --- | --- |
| `routenote_ref` (class) | `str` | 🔓 public | Class attribute routenote_ref<br>**Default:** `Field(min_length=1, max_length=300, description='Release URL or UPC from RouteNote')` |

---



### BotBrief

![Type: Concrete](https://img.shields.io/badge/Type-Concrete-green) ![Methods: 1](https://img.shields.io/badge/Methods-1-blue) ![Attributes: 6](https://img.shields.io/badge/Attributes-6-blue)

#### Description

BotBrief is a Pydantic model that represents a concise brief for a music generation or metadata record.

Within backend/main.py, BotBrief acts as the primary data model for passing around brief information about a track or generation prompt. It standardizes how brief metadata and the prompt are represented and validated across the module.

Responsibilities:
- Validate and store a structured brief consisting of title, prompt, artist, genre, label, and duration.
- Provide a dependable data container that can be serialized and used across the application where a music brief is required.
- Offer a class-level utility (_no_vocals) to produce or transform a brief variant that indicates no-vocals usage or intent.
- Serve as the canonical representation of the minimal set of fields needed to describe a generation request or track summary.

#### Inheritance

**Inherits from:** `BaseModel`

#### Attributes

| Attribute | Type | Visibility | Description |
| --- | --- | --- | --- |
| `title` (class) | `str` | 🔓 public | Class attribute title<br>**Default:** `Field(min_length=1, max_length=80)` |
| `prompt` (class) | `str` | 🔓 public | Class attribute prompt<br>**Default:** `Field(min_length=3, max_length=1000)` |
| `artist` (class) | `str` | 🔓 public | Class attribute artist<br>**Default:** `Field(default='Zi', max_length=120)` |
| `genre` (class) | `str` | 🔓 public | Class attribute genre<br>**Default:** `'Electronic'` |
| `label` (class) | `str` | 🔓 public | Class attribute label<br>**Default:** `'Zi'` |
| `duration` (class) | `int` | 🔓 public | Class attribute duration<br>**Default:** `Field(default=190, ge=pipeline.MIN_TRACK_SECONDS, le=300)` |

#### Methods

##### Protected Methods

| Method | Type | Description |
| --- | --- | --- |
| `_no_vocals` | classmethod | Method _no_vocals.<br>**Signature:** `def _no_vocals(cls, v: str) -> str:` |

---



### _no_vocals

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def _no_vocals(cls, v: str) -> str:
```

#### Description

A class-level field validator method intended to process a string by removing or normalizing its vowels (based on the method name `_no_vocals`).

It is used as a field_validator and operates at the class level to return a transformed string without vowels.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `v` | `str` | ✅ | — |

#### Returns

**Type:** `str`

—

#### Complexity

Not analyzed

---



### root

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def root():
```

#### Description

Asynchronous GET endpoint function registered with app.get for the application's root path; it serves the root HTTP request and provides the basic entry response for the service (e.g., health check or landing message).

#### Complexity

Not analyzed

---



### health

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def health():
```

#### Description

As an asynchronous HTTP GET endpoint, this function provides a simple health check for the application, typically used to verify that the service is up and responding.

It is intended to be called by monitoring systems or load balancers to confirm basic operational status.

#### Complexity

Not analyzed

---



### create_generation

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def create_generation(request: GenerationRequest, _: None = Depends(require_admin)):
```

#### Description

Async HTTP POST endpoint that creates a new generation using the data supplied in the GenerationRequest.

It is registered with the app.post decorator and enforces admin authorization before proceeding.


_ is an injected dependency (Depends(require_admin)) used to ensure the caller has admin privileges; request is the GenerationRequest payload containing the details for the generation to be created.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `request` | `GenerationRequest` | ✅ | — |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### get_generation

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def get_generation(job_id: str, _: None = Depends(require_admin)):
```

#### Description

Asynchronous HTTP GET endpoint that retrieves generation information for a given job ID.

It is protected by an admin dependency, so only requests that satisfy require_admin are allowed to access the generation data for the specified job.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | `str` | ✅ | — |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### get_audio

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def get_audio(job_id: str, _: None = Depends(require_admin)):
```

#### Description

Asynchronous HTTP GET endpoint that retrieves audio associated with a specific job identifier.

It is exposed via the app.get decorator and is intended to serve or return the audio for the given job_id.


job_id is a string identifying the job whose audio should be retrieved; the second parameter (_) is an injected dependency (Depends(require_admin)) that enforces an administrative authorization check before the endpoint runs.

Returns an HTTP response containing the audio data or resource corresponding to the specified job_id.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | `str` | ✅ | — |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### validate_release

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def validate_release(req: ReleaseRequest):
```

#### Description

Asynchronous HTTP POST handler that validates an incoming release payload represented by a ReleaseRequest.

It checks the contents of the request for correctness and completeness before allowing the release operation to proceed.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `req` | `ReleaseRequest` | ✅ | — |

#### Complexity

Not analyzed

---



### create_release

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def create_release(req: ReleaseRequest, _: None = Depends(require_admin)):
```

#### Description

As an async POST endpoint, this function handles incoming requests to create a new release using the provided ReleaseRequest payload.

Access to this endpoint is restricted to administrators via the require_admin dependency.


req is the incoming ReleaseRequest payload containing the details of the release to create; the second parameter is the injected admin dependency (ignored in the function body) used to enforce admin-only access.

Returns an HTTP response indicating the result of the create operation (e.g., success or failure) and any relevant created-release data or status information.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `req` | `ReleaseRequest` | ✅ | — |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### list_releases

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def list_releases(_: None = Depends(require_admin)):
```

#### Description

Asynchronously handles an HTTP GET endpoint that returns a listing of releases.

Access to this endpoint is restricted to administrators via the require_admin dependency.


An HTTP response containing the list of releases (the exact response shape is defined by the endpoint implementation).

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### get_release

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def get_release(release_id: str, _: None = Depends(require_admin)):
```

#### Description

As an async HTTP GET endpoint, this function retrieves a release identified by the provided release_id.

Access to this endpoint is protected and requires the caller to satisfy the require_admin dependency (i.e., an admin).


release_id is the string identifier of the release to fetch; the second parameter is an injected dependency used to enforce admin authorization and is not used directly by the function.

Returns the release data (or an HTTP response containing the release) corresponding to the given release_id.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `release_id` | `str` | ✅ | — |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### download_package

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def download_package(release_id: str, _: None = Depends(require_admin)):
```

#### Description

As an async HTTP GET endpoint, this function serves a downloadable package for a specific release identified by release_id.

Access is restricted to callers who pass the require_admin dependency.


Returns an HTTP response that serves or streams the package file corresponding to the provided release_id.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `release_id` | `str` | ✅ | — |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### mark_submitted

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def mark_submitted(release_id: str, body: SubmitMark, _: None = Depends(require_admin)):
```

#### Description

As an HTTP POST endpoint, this async function records or updates the submitted state for a specific release identified by release_id using the data provided in the SubmitMark payload.

It is protected by an admin dependency, so only authorized administrators can perform the action.


release_id is the identifier of the release to mark as submitted; body is a SubmitMark object containing the details of the submission mark to apply. The trailing parameter enforces an admin authorization dependency and is not used directly.

Returns an HTTP response (or serializable result) indicating whether the mark operation succeeded or failed, appropriate for an API POST handler.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `release_id` | `str` | ✅ | — |
| `body` | `SubmitMark` | ✅ | — |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### bot_enqueue

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def bot_enqueue(brief: BotBrief, _: None = Depends(require_admin)):
```

#### Description

As an asynchronous POST endpoint, this function accepts a BotBrief and enqueues a bot job or request into the system.

It is protected by an admin-only dependency so only authorized users can call it.


brief is a BotBrief object containing the data needed to create or enqueue the bot; the second parameter is an injected admin-only dependency (named _), used to enforce that the caller is an administrator.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `brief` | `BotBrief` | ✅ | — |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



### bot_queue

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def bot_queue(_: None = Depends(require_admin)):
```

#### Description

As an async GET endpoint, this function exposes the "bot queue" functionality and is protected by an admin-only dependency.

It serves requests to retrieve or view the bot queue/state and can only be accessed when the require_admin dependency authorizes the caller.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `_` = `Depends(require_admin)` | `None` | ❌ | — |

#### Complexity

Not analyzed

---



---

## Navigation

**↑ Parent Directory:** [Go up](./README.md)

---

*This documentation was automatically generated by AI ([Woden DocBot](https://github.com/marketplace/ai-document-creator)) and may contain errors. It is the responsibility of the user to validate the accuracy and completeness of this documentation.*
