<!-- METADATA: {"source_path": "backend/main.py", "source_sha": "0f234646e1c5f74e810a620d3cb0469440da7ffc", "extraction_quality": "full_ast", "model": "gpt-5-mini", "generated_at": "2026-11-25T12:32:09Z", "doc_type": "file"} -->
<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "backend/main.py",
  "source_hash": "119cd43e4b4d9e6f27f0d7da73fea2d020cc08c2d3880d0ebfbb83fa20d082dd",
  "last_updated": "2026-11-25T12:32:09.253187+00:00",
  "git_sha": "0f234646e1c5f74e810a620d3cb0469440da7ffc",
  "tokens_used": 10303,
  "complexity_score": 4,
  "estimated_review_time_minutes": 13,
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

![Complexity: Medium](https://img.shields.io/badge/Complexity-Medium-yellow) ![Review Time: 13min](https://img.shields.io/badge/Review_Time-13min-blue)

## 📑 Table of Contents


- [Overview](#overview)
- [Dependencies](#dependencies)
- [Architecture Notes](#architecture-notes)
- [Maintenance Notes](#maintenance-notes)
- [Functions and Classes](#functions-and-classes)

---

## Overview

This module implements the HTTP API surface for a service named "Zi" using FastAPI. It defines an application instance and a set of async endpoint handlers to manage audio generation jobs, release artifacts, package downloads, and a simple bot queue. Configuration and feature toggles are driven by environment variables (API tokens, allowed CORS origins, admin token and whether the bot is enabled). The module also includes request/validation models implemented with Pydantic for generation requests, release creation, submission marking, and brief bot payloads.

Endpoints cover lifecycle operations for generation jobs (create and retrieve), serving generated audio files, validating and creating releases, listing and retrieving release metadata, downloading packaged releases, marking submissions, and enqueuing or inspecting the bot queue. Administrative protection is provided by a require_admin dependency, and the application registers a lifespan hook for startup/shutdown behavior. External utilities and HTTP requests are supported via imports such as httpx, shutil and a local bot module.

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

- Uses FastAPI to define async HTTP handlers and an application lifespan hook.
- Uses Pydantic BaseModel classes for request validation.
- Reads configuration from environment variables to control behavior and feature flags.
- Implements an admin dependency (require_admin) to restrict sensitive operations.
- Integrates with external libraries and modules such as httpx, shutil, and a local bot module.

## Maintenance Notes

- Expose async HTTP endpoints to create and retrieve generation jobs and to serve generated audio files.
- Validate, create, list, and retrieve release artifacts and provide package download endpoints for those releases.
- Protect sensitive endpoints with an admin-only dependency and honor environment-driven configuration like API tokens and CORS origins.
- Provide endpoints to mark submissions and to enqueue/inspect jobs for an attached bot when enabled.
- Define Pydantic request models (GenerationRequest, ReleaseRequest, SubmitMark, BotBrief) used for input validation across the API.


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

Enforces that an incoming request is from an administrator before allowing access to endpoints that spend Replicate credits.

When an ADMIN_TOKEN is configured, this function checks the Authorization header and blocks access if the token does not match.


Returns nothing on success; if the Authorization header does not match the expected admin token access is denied (typically by raising an HTTP exception).

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

An asynchronous context manager function intended to control the FastAPI application's lifespan (startup and shutdown) when used with the application's lifespan management.

It provides a place to run setup before the app becomes available and cleanup after the app is shutting down.


Returns an async context manager (via the asynccontextmanager decorator) that yields control for the application's runtime period, allowing setup and teardown code to run around the app's lifetime.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `_` | `FastAPI` | ✅ | — |

#### Complexity

Not analyzed

---



### GenerationRequest

![Type: Concrete](https://img.shields.io/badge/Type-Concrete-green) ![Methods: 1](https://img.shields.io/badge/Methods-1-blue) ![Attributes: 3](https://img.shields.io/badge/Attributes-3-blue)

#### Description

GenerationRequest is a Pydantic model that represents the input data required to request a track generation.

Within backend/main.py, GenerationRequest acts as the typed data contract for incoming generation operations, supplying validated parameters to the module's generation workflow and related functions.

Responsibilities:
- Define and validate the input schema for a generation request, including track_name, prompt, and duration.
- Carry the generation parameters through the application as a typed data object.
- Expose any class-level helpers relevant to request handling (e.g., the provided _no_vocals classmethod) for use by calling code.
- Serve as a single source of truth for the fields required to initiate a generation operation.

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

A class-level field validator for GenerationRequest that accepts a string value and returns a (possibly validated or transformed) string.

It is intended to be used with Pydantic's field_validator mechanism to enforce or normalize the value of a "no vocals"-related field on the class.

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

ReleaseRequest is a Pydantic data model that represents the payload required to request a release operation.

Within backend/main.py, ReleaseRequest serves as the typed contract for incoming or outgoing release requests, enabling consistent validation and easy consumption of release-related data by other components in the module. It acts as the canonical data representation for release operations.

Responsibilities:
- Validate and enforce the types and presence of the fields job_id, connector, and metadata according to the Pydantic BaseModel behavior.
- Provide a structured container for transfer of release-related data across application boundaries (e.g., API endpoints, internal processing).
- Ensure the metadata field is typed as ReleaseMetadata so downstream logic can rely on a known structure for release details.
- Support serialization and deserialization of release request instances to/from standard formats (e.g., dict, JSON) via Pydantic utilities.

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

SubmitMark is a Pydantic data model used to represent a submission that references a routenote.

Within backend/main.py, this class functions as the typed data structure for passing a routenote reference around the module; it standardizes how a submission mark's reference is represented and validated.

Responsibilities:
- Define and validate the routenote_ref field as a string using Pydantic's BaseModel behaviour.
- Ensure incoming or outgoing data that represents a submission mark includes a correctly typed reference to a routenote.
- Serve as a simple, serializable schema for exchanging or persisting the routenote reference in APIs or internal processing.

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

BotBrief is a Pydantic model that represents a concise description of a music-related brief.

Within backend/main.py, BotBrief functions as the canonical data model for song briefs, enabling other parts of the module to reliably create, validate, and consume brief objects. It standardizes the shape of brief-related data used across the module.

Responsibilities:
- Validate and store the brief's textual and metadata fields: title, prompt, artist, genre, and label.
- Enforce and type-check the duration as an integer representing the track length in seconds (or another agreed unit).
- Provide a class-level helper (_no_vocals) to describe or produce a variation of the brief that specifies no vocals.
- Serve as a structured data container for passing brief information between components (e.g., prompt generation, storage, or processing).

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

Likely a class-level validator that processes the input string v to remove or alter its vowels (i.e., producing a version of the string without vocalic characters).

It is intended to be used as a field validator on the BotBrief class to enforce or normalize vowel-free forms of a string.

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

Asynchronous endpoint function registered with app.get that handles HTTP GET requests to the application's root path.

It serves as the route handler for the root (/) URL and contains the logic to produce the response returned to clients.

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

Asynchronous HTTP GET endpoint that provides a simple health check for the application.

It is intended to be called to verify that the service is running and responsive.

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

Asynchronous POST endpoint that handles creation of a new generation resource using the provided GenerationRequest payload.

It enforces an admin-only requirement via dependency injection before processing the creation.


request is a GenerationRequest containing the data for the generation to be created; the second parameter, _, is a dependency injection placeholder that enforces the require_admin check to ensure only administrators can call this endpoint.

Returns an HTTP response representing the outcome of the creation operation (e.g., success or error and any created resource data).

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

As an asynchronous HTTP GET endpoint, this function fetches the generation result or status associated with a specific job identifier.

It retrieves the generation data for the provided job_id so clients can check progress or obtain the completed output.


Returns an HTTP response (typically JSON) containing the generation details or status for the given job_id, such as progress, result data, or an error if the job is not found.

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

As an async GET endpoint, this function handles requests to retrieve the audio associated with a given job identifier.

It looks up or streams the audio data for the job specified by job_id and returns it to the caller.


Returns an HTTP response (likely streaming or file response) containing the audio data for the specified job_id.

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

As an asynchronous HTTP POST endpoint, this function receives a ReleaseRequest and performs validation of the release data contained in that request.

It is intended to check the incoming release payload for correctness and business-rule compliance before further processing.

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

As an async POST endpoint, this function handles creating a new release using the data provided in the ReleaseRequest.

It enforces that the caller is an administrator via the Depends(require_admin) dependency.


req is the request payload containing the release details (a ReleaseRequest object); the second parameter is an injected dependency used to ensure the caller has admin privileges and is not used directly.

Returns an HTTP response representing the outcome, typically including the created release record or a success status.

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

An asynchronous HTTP GET endpoint that retrieves and returns a list of releases.

It serves the releases data when clients call this route.


Returns a response containing the collection of releases (typically serialized as JSON) for the caller.

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

As an HTTP GET endpoint handler, this asynchronous function retrieves the data for a specific release identified by the provided release_id.

It is exposed via the app.get decorator and is intended to return the release information when called.


Returns an HTTP response (typically JSON) containing the requested release details or an error response if the release cannot be found or another problem occurs.

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

As an async GET endpoint, this function handles requests to download the package associated with the provided release_id.

It is protected by an admin dependency, so only callers that satisfy require_admin can invoke the download.

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

HTTP POST endpoint that marks a specific release (identified by release_id) as submitted using the data provided in the SubmitMark body.

The operation requires an authenticated admin (enforced via Depends(require_admin)).


release_id is the identifier of the release to mark; body is a SubmitMark object containing the submission details or metadata to apply to that release. The third parameter is an injected dependency used to ensure the caller is an admin.

Returns an HTTP response indicating the result of the mark-as-submitted operation (e.g., success or failure) and any relevant payload.

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

As an HTTP POST endpoint handler, this asynchronous function accepts a BotBrief and enqueues a bot for processing or deployment.

Access is restricted to administrators via a dependency, so only authorized users can call this endpoint.


brief is a BotBrief object describing the bot to enqueue; the second parameter _ is an unused dependency whose presence enforces that the caller is an admin via Depends(require_admin).

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

An asynchronous HTTP GET endpoint handler named bot_queue (decorated with app.get) defined in backend/main.py.

It serves as an async route function to handle GET requests related to the bot queue in the application.

#### Complexity

Not analyzed

---



---

## Navigation

**↑ Parent Directory:** [Go up](./README.md)

---

*This documentation was automatically generated by AI ([Woden DocBot](https://github.com/marketplace/ai-document-creator)) and may contain errors. It is the responsibility of the user to validate the accuracy and completeness of this documentation.*
