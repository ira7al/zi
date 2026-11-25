<!-- METADATA: {"source_path": "backend/main.py", "source_sha": "03ee8dfbc346b6bc2cb0de1adc2d7cc9225e14cd", "extraction_quality": "full_ast", "model": "gpt-5-mini", "generated_at": "2026-11-25T14:52:02Z", "doc_type": "file"} -->
<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "backend/main.py",
  "source_hash": "8ed9d8b02eff96aff9d5d3807c5f9d4ca692b68fee1e645c2d246f65b2a5508d",
  "last_updated": "2026-11-25T14:52:02.410991+00:00",
  "git_sha": "03ee8dfbc346b6bc2cb0de1adc2d7cc9225e14cd",
  "complexity_score": 5,
  "estimated_review_time_minutes": 15,
  "external_dependencies": [
    "asyncio",
    "os",
    "re",
    "shutil",
    "contextlib",
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

![Complexity: Medium](https://img.shields.io/badge/Complexity-Medium-yellow) ![Review Time: 15min](https://img.shields.io/badge/Review_Time-15min-blue)

## 📑 Table of Contents


- [Overview](#overview)
- [Dependencies](#dependencies)
- [Architecture Notes](#architecture-notes)
- [Maintenance Notes](#maintenance-notes)
- [Functions and Classes](#functions-and-classes)

---

## Overview

This module defines a FastAPI application (app) that exposes a variety of HTTP endpoints for generation, release management, file access, and an optional background bot queue. It declares Pydantic models (GenerationRequest, ReleaseRequest, SubmitMark, BotBrief) used for request validation and includes a lifespan hook for startup/shutdown logic. Configuration is driven by environment variables such as REPLICATE_TOKEN, ALLOWED_ORIGINS, ADMIN_TOKEN and BOT_ENABLED, and the application registers CORS and file-serving behavior to support clients fetching generated assets and release packages.

The module also contains several async endpoint handlers and utilities: generation endpoints (create_generation, get_generation, get_audio), release lifecycle endpoints (validate_release, create_release, list_releases, get_release, download_package), file discovery helpers (find_work_file, find_file_in_directory), an admin guard (require_admin) to protect sensitive operations, and bot-related endpoints (bot_enqueue, bot_queue) gated by BOT_ENABLED. External integrations referenced by imports include httpx for HTTP operations, shutil for file manipulation, and an internal bot module for queueing behavior.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `asyncio` | import asyncio |
| `os` | import os |
| `re` | import re |
| `shutil` | import shutil |
| `contextlib` | from contextlib import asynccontextmanager |
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

- Uses Pydantic BaseModel classes for request validation (GenerationRequest, ReleaseRequest, SubmitMark, BotBrief).
- Implements asynchronous FastAPI handlers (async def endpoints) throughout the module.
- Reads configuration from environment variables (REPLICATE_TOKEN, ALLOWED_ORIGINS, ADMIN_TOKEN, BOT_ENABLED).
- Integrates file-serving and file-system utilities (shutil, FileResponse, file discovery helpers).
- Includes an explicit lifespan function passed to FastAPI for application startup/shutdown management.

## Maintenance Notes

- Provide HTTP endpoints for creating and retrieving generations and their audio assets.
- Manage release-related operations: validate, create, list, retrieve, and download release packages.
- Serve files from disk using helper functions to locate work files and directory contents.
- Enforce administrative access for sensitive endpoints via require_admin and environment-controlled ADMIN_TOKEN.
- Expose optional bot queue endpoints to enqueue work and inspect the bot queue when BOT_ENABLED is set.


---

## Constants

| Name | Type | Value |
| --- | --- | --- |
| `REPLICATE_TOKEN` | — | `os.getenv('REPLICATE_API_TOKEN', '')` |
| `ALLOWED_ORIGINS` | — | `os.getenv('ALLOWED_ORIGINS', '*').split(',')` |
| `ADMIN_TOKEN` | — | `os.getenv('ADMIN_TOKEN', '')` |
| `BOT_ENABLED` | — | `os.getenv('BOT_ENABLED', '1') == '1'` |
| `JOB_ID` | — | `'^[A-Za-z0-9_-]{4,64}$'` |
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

Enforces an admin requirement for endpoints that spend Replicate credits: when an ADMIN_TOKEN is configured, this function checks the provided Authorization header and blocks access unless the request is authorized.

It is used to protect credit-spending endpoints behind an admin token.

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

An async context manager function intended to provide the lifespan (startup and shutdown) handling for a FastAPI application.

It will be used by the FastAPI app to run any setup before the app starts serving and teardown after the app stops.


As an asynccontextmanager-decorated function, it yields an asynchronous context manager that FastAPI uses to drive the application's startup and shutdown lifecycle.

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

Locate a work file by combining one or more path components with a specific filename and return the resolved file path.

It accepts any number of path segments and the filename to search for and returns the path to the matching file if found.

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

Searches for a file with the given filename inside the provided directory and returns its path if found.

If the directory is None or the file cannot be found, it returns None.

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

GenerationRequest is a pydantic model that represents and validates the inputs required to request generation of a track.

Within backend/main.py, GenerationRequest serves as the typed input contract for generation-related functionality, ensuring that downstream logic receives a consistent and validated set of fields. As a pydantic model, it centralizes input validation and simple class-level utilities tied to generation requests.

Responsibilities:
- Validate and hold request data for a generation operation (track_name, prompt, duration) using BaseModel behavior.
- Provide a structured data container that other parts of the code can rely on when accessing generation parameters.
- Expose a class-level helper named _no_vocals (as a classmethod) for use by callers that need the corresponding class-level behavior or sentinel.

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

This classmethod acts as a field validator for the GenerationRequest class, receiving a string value and performing validation and/or normalization on it.

It returns the (possibly transformed) string to be stored on the model.

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

ReleaseRequest is a Pydantic data model that represents a request to perform a release operation.

Within backend/main.py, ReleaseRequest serves as the canonical input representation for release-related operations, ensuring that code in the module receives a consistent, validated payload describing what to release, where, and with what metadata.

Responsibilities:
- Validate and store the job identifier (job_id) for the release operation.
- Hold the connector identifier (connector) that determines which integration or backend will handle the release.
- Contain release-specific details in the metadata field (ReleaseMetadata) for downstream processing.
- Provide a typed, serializable container that can be passed through the application for handling release requests.

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

SubmitMark is a Pydantic data model that represents a submission marker containing a reference to a routenote.

Within backend/main.py, SubmitMark serves as the typed data schema for operations that need a routenote reference, enabling other parts of the module to accept and rely on a validated routenote_ref value. It acts as a lightweight DTO (data transfer object) for routenote submissions.

Responsibilities:
- Define and validate the routenote_ref field as a string using Pydantic's BaseModel behavior.
- Provide a simple, typed container for passing a routenote reference between components.
- Ensure data consistency for any operation that requires a routenote identifier in the module.

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

BotBrief is a Pydantic data model that captures the metadata and generation instructions for a single bot-created music item, including its title, textual prompt, artist, genre, label, and duration.

Within backend/main.py, BotBrief acts as the primary typed representation for brief information used by other parts of the module to create, validate, and exchange music-generation metadata. It centralizes the shape and validation rules for brief payloads handled in the file.

Responsibilities:
- Declare and type-check the key fields that describe a music brief: title, prompt, artist, genre, label, and duration.
- Provide Pydantic validation and serialization of brief data so instances can be reliably consumed, stored, or transmitted.
- Offer a class-level utility (_no_vocals) that represents or produces a variant of the brief related to an instrumental/no-vocals configuration (as indicated by the extracted classmethod).
- Serve as the canonical data structure for components of the system that need a compact description of a generated track or generation request.

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

A classmethod used as a field validator that accepts a string and returns a processed string with vocals removed, intended to normalize or validate a text field on the class.

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

Asynchronous handler function registered as an HTTP GET endpoint (via the app.get decorator) for the application's root path.

It serves as the entrypoint for GET requests to the root and performs whatever response logic is implemented in the function body.

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

Asynchronous HTTP GET endpoint that provides a health check for the application.

It is intended to be called by monitoring systems or load balancers to verify that the service is up and responsive.


Returns an HTTP response indicating the service health (typically a 200 OK with a simple payload or status code), suitable for use by monitoring tools.

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

Asynchronous POST endpoint that creates a new generation using the provided GenerationRequest payload.

Access to this endpoint is restricted to administrators via the require_admin dependency.


request is a GenerationRequest object carrying the data needed to create the generation; the second parameter (_) is a placeholder for the injected admin dependency (Depends(require_admin)) and is not used directly in the function body.

Returns an HTTP response indicating the result of the create operation (e.g., success/failure and any created resource data).

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
async def get_generation(job_id: str):
```

#### Description

As an HTTP GET endpoint, this asynchronous function handles requests to fetch the generation associated with a given job identifier.

It looks up or retrieves the generation result for the provided job_id and returns it to the caller.


Returns the generation data or an HTTP response containing the generation result (or an error/status) corresponding to the provided job_id.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | `str` | ✅ | — |

#### Complexity

Not analyzed

---



### get_audio

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def get_audio(job_id: str):
```

#### Description

HTTP GET endpoint that retrieves the audio associated with a given job identifier.

It is an asynchronous handler intended to return the generated audio resource for the specified job_id.


job_id is a string identifier for the job whose audio should be fetched; its meaning is evident from the name and type.

An HTTP response containing the audio payload (e.g., audio file or streamed audio data) for the requested job.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | `str` | ✅ | — |

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

As an asynchronous HTTP POST endpoint, this function accepts a ReleaseRequest payload and performs validation of the supplied release data before further processing.

It acts as the API entry point to check that the release information is well-formed and meets any business rules or constraints.


Returns an HTTP response (typically a validation result) indicating success or detailing validation errors found in the provided ReleaseRequest.

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

Asynchronous POST endpoint that creates a new release using the data supplied in a ReleaseRequest.

Access to this operation is restricted to administrators via a dependency on require_admin.


req is a ReleaseRequest object containing the details of the release to be created; the second parameter _ is an injected admin dependency (Depends(require_admin)) used solely to enforce admin authorization and is not otherwise used.

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
async def list_releases():
```

#### Description

As an async HTTP GET endpoint, this function handles requests to list releases.

It retrieves and returns a collection of release records to the caller.

#### Complexity

Not analyzed

---



### get_release

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def get_release(release_id: str):
```

#### Description

Asynchronous HTTP GET endpoint handler that retrieves and returns information about a specific software release identified by the given release_id.

It is exposed as a route via the app.get decorator and intended to fetch the release details for client requests.


Returns an HTTP response (typically JSON) containing the release details or an error/status indicating the release was not found or could not be retrieved.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `release_id` | `str` | ✅ | — |

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

Asynchronously handles an HTTP GET endpoint to retrieve or stream a package file for the specified release.

Access to this endpoint is protected by an admin dependency, so only authorized administrators can download the package for the given release_id.


Returns an HTTP response that delivers the package content for the specified release (typically a file download or streamed response), suitable for client download.

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

As an HTTP POST handler, this asynchronous function marks a given release as submitted using the data provided in the request body.

It is protected by an admin dependency, so only authorized administrators can perform the action.


release_id is the identifier of the release to mark as submitted; body is a SubmitMark object carrying the submission details (e.g., timestamp, submitter, or submission metadata). The dependency parameter _ enforces admin-only access and is not used directly.

Returns an HTTP response indicating the outcome of the operation (success or appropriate error), typically with status information about the marked release.

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

Asynchronously handles POST requests to enqueue a bot using the provided BotBrief.

It is an admin-protected endpoint (requires the require_admin dependency).


brief is a BotBrief object containing the data needed to enqueue the bot; the second parameter _ is an internal dependency injection (Depends(require_admin)) used to ensure the caller has admin privileges.

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
async def bot_queue():
```

#### Description

As an async HTTP GET endpoint handler, this function serves requests related to the bot queue.

It likely retrieves and returns information about the current bot queue to the caller.


As a route handler it returns an HTTP response (typically JSON) containing the bot queue data or an appropriate status/error message.

#### Complexity

Not analyzed

---



---

## Navigation

**↑ Parent Directory:** [Go up](./README.md)

---

*This documentation was automatically generated by AI ([Woden DocBot](https://github.com/marketplace/ai-document-creator)) and may contain errors. It is the responsibility of the user to validate the accuracy and completeness of this documentation.*
