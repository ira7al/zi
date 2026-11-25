<!-- METADATA: {"source_path": "backend/connectors/routenote.py", "source_sha": "0d0a159b5033e547cac70529a45f4414070031b1", "extraction_quality": "full_ast", "model": "gpt-5-mini", "generated_at": "2026-11-25T09:25:20Z", "doc_type": "file"} -->
<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "backend/connectors/routenote.py",
  "source_hash": "e97b277d76559de378906f16feda9e6751b1f2743020ab9dc596b3359bab6cb2",
  "last_updated": "2026-11-25T09:24:29.804351+00:00",
  "git_sha": "0d0a159b5033e547cac70529a45f4414070031b1",
  "tokens_used": 2445,
  "complexity_score": 1,
  "estimated_review_time_minutes": 6,
  "external_dependencies": [
    "__future__",
    "csv",
    "io",
    "json",
    "os",
    "re",
    "zipfile",
    "datetime"
  ]
}
```

</details>

[Documentation Home](../../README.md) > [backend](../README.md) > [connectors](./README.md) > **routenote**

---

# routenote.py

> **File:** `backend/connectors/routenote.py`

![Complexity: Low](https://img.shields.io/badge/Complexity-Low-green) ![Review Time: 6min](https://img.shields.io/badge/Review_Time-6min-blue)

## 📑 Table of Contents


- [Overview](#overview)
- [Dependencies](#dependencies)
- [Architecture Notes](#architecture-notes)
- [Maintenance Notes](#maintenance-notes)
- [Functions and Classes](#functions-and-classes)

---

## Overview

This module implements a RouteNote connector that constructs and validates release packages formatted to match RouteNote's "Create New Release" web form. Because RouteNote exposes no public upload API, the connector assembles a field-for-field package (covering Release Data, Album Details, Add Audio, and Artwork) and performs pre-validation against RouteNote's expected specifications. The connector is provided as a single class, RouteNoteConnector, which extends the Distributor base class and encapsulates the logic required to create and validate the release bundle.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `__future__` | from __future__ import annotations |
| `csv` | import csv |
| `io` | import io |
| `json` | import json |
| `os` | import os |
| `re` | import re |
| `zipfile` | import zipfile |
| `datetime` | from datetime import date, timedelta |

### Internal Dependencies

| Module | Usage |
| --- | --- |
| `base` | from .base import Distributor, ReleaseMetadata, ValidationReport |

## 📁 Directory

This file is part of the **connectors** directory. View the [directory index](./README.md) to see all files in this module.

## Architecture Notes

- Defines a single connector class that inherits from a Distributor base class
- Performs packaging and validation of release metadata to mirror a web form workflow
- Imports standard library modules for archive and CSV handling (zipfile, csv)

## Maintenance Notes

- Provide a Distributor-derived RouteNoteConnector class that models the behavior needed to prepare releases for RouteNote.
- Assemble release data into a package that mirrors RouteNote's web form fields, including album metadata, audio files, and artwork.
- Pre-validate release contents against RouteNote's specification to produce a ValidationReport indicating any issues.
- Use standard library utilities (for example zipfile and csv) as part of packaging and metadata export operations.


---

## Functions and Classes


### RouteNoteConnector

![Type: Concrete](https://img.shields.io/badge/Type-Concrete-green) ![Methods: 3](https://img.shields.io/badge/Methods-3-blue) ![Attributes: 2](https://img.shields.io/badge/Attributes-2-blue)

#### Description

RouteNoteConnector is a Distributor subclass that encapsulates logic for preparing and validating release data for upload to the RouteNote service.

Within backend/connectors/routenote.py, this class serves as the concrete connector implementing Distributor behavior for RouteNote specifically, centralizing upload URL configuration, data sanitation, validation, and package construction for that service.

Responsibilities:
- Provide configuration constants used for communicating with RouteNote (for example the UPLOAD_URL and the connector name).
- Sanitize textual release data so it is safe to include in CSV-formatted payloads (_csv_safe staticmethod).
- Validate release metadata and packaging inputs to ensure they meet RouteNote's expected constraints and formats (validate).
- Construct the final package or payload that will be sent to RouteNote for distribution (build_package).

#### Inheritance

**Inherits from:** `Distributor`

#### Attributes

| Attribute | Type | Visibility | Description |
| --- | --- | --- | --- |
| `name` (class) | `Unknown` | 🔓 public | Class attribute name<br>**Default:** `'routenote'` |
| `UPLOAD_URL` (class) | `Unknown` | 🔓 public | Class attribute UPLOAD_URL<br>**Default:** `'https://routenote.com/'` |

#### Methods

##### Public Methods

| Method | Type | Description |
| --- | --- | --- |
| `validate` | instance | Method validate.<br>**Signature:** `def validate(self, m: ReleaseMetadata) -> ValidationReport:` |
| `build_package` | instance | Method build_package.<br>**Signature:** `def build_package(self, release_id, meta, audio_paths, artwork_path, out_dir, provenance=None) -> str:` |

##### Protected Methods

| Method | Type | Description |
| --- | --- | --- |
| `_csv_safe` | static | Method _csv_safe.<br>**Signature:** `def _csv_safe(value):` |

---



### _csv_safe

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def _csv_safe(value):
```

#### Description

Normalize or escape a given value so it can be safely included in a CSV field.

The method will convert or sanitize the input to avoid breaking CSV formatting (for example handling commas, quotes or newlines) and return a CSV-friendly representation.


A sanitized string representation of the input that is safe to place into a CSV cell.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `value` | `Unknown` | ✅ | — |

#### Complexity

Not analyzed

---



### validate

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def validate(self, m: ReleaseMetadata) -> ValidationReport:
```

#### Description

Validate a release's metadata using the RouteNote connector logic.

It checks the provided ReleaseMetadata object for any issues or missing/invalid fields required by RouteNote and produces a report summarizing validation results.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `m` | `ReleaseMetadata` | ✅ | — |

#### Returns

**Type:** `ValidationReport`

—

#### Complexity

Not analyzed

---



### build_package

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def build_package(self, release_id, meta, audio_paths, artwork_path, out_dir, provenance=None) -> str:
```

#### Description

Assembles and writes a release package for a RouteNote release using the provided metadata, audio files, and artwork into the given output directory.

The method prepares all necessary files and structure for the release bundle and returns the path or identifier of the created package.


Most parameter meanings are clear from their names: release_id identifies the release, meta contains release metadata, audio_paths is a list of audio file paths, artwork_path points to the artwork file, and out_dir is the destination directory for the package. The optional provenance parameter, if provided, supplies additional provenance or tracking information to include in the package.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `release_id` | `Unknown` | ✅ | — |
| `meta` | `Unknown` | ✅ | — |
| `audio_paths` | `Unknown` | ✅ | — |
| `artwork_path` | `Unknown` | ✅ | — |
| `out_dir` | `Unknown` | ✅ | — |
| `provenance` = `None` | `Unknown` | ❌ | — |

#### Returns

**Type:** `str`

—

#### Complexity

Not analyzed

---



---

## Navigation

**↑ Parent Directory:** [Go up](./README.md)

---

*This documentation was automatically generated by AI ([Woden DocBot](https://github.com/marketplace/ai-document-creator)) and may contain errors. It is the responsibility of the user to validate the accuracy and completeness of this documentation.*
