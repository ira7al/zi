<!-- METADATA: {"source_path": "backend/connectors/routenote.py", "source_sha": "656c43d6503c4badd5c3fecf2e7c9cd329617a0d", "extraction_quality": "full_ast", "model": "gpt-5-mini", "generated_at": "2026-11-25T14:52:02Z", "doc_type": "file"} -->
<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "backend/connectors/routenote.py",
  "source_hash": "4f3b8d4633df1a5e72c0fcf549c8504af1a2c9535a86f4a59709c7405affe44d",
  "last_updated": "2026-11-25T14:52:02.405941+00:00",
  "git_sha": "656c43d6503c4badd5c3fecf2e7c9cd329617a0d",
  "complexity_score": 1,
  "estimated_review_time_minutes": 6,
  "external_dependencies": [
    "__future__",
    "csv",
    "io",
    "json",
    "os",
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

This module implements a RouteNote connector as a Distributor subclass. It encapsulates the logic needed to build a package that mirrors RouteNote's "Create New Release" form fields (Release Data -> Album Details -> Add Audio -> Artwork) and to pre-validate release assets and metadata against RouteNote's requirements. Because RouteNote offers no public upload API, the connector prepares a locally verifiable bundle intended to match the release form structure and runs validation to produce a ValidationReport for the prepared package.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `__future__` | from __future__ import annotations |
| `csv` | import csv |
| `io` | import io |
| `json` | import json |
| `os` | import os |
| `zipfile` | import zipfile |
| `datetime` | from datetime import date, timedelta |

### Internal Dependencies

| Module | Usage |
| --- | --- |
| `base` | from .base import Distributor, ReleaseMetadata, ValidationReport |

## 📁 Directory

This file is part of the **connectors** directory. View the [directory index](./README.md) to see all files in this module.

## Architecture Notes

- Defines a connector class by subclassing a common Distributor base type.
- Produces structured validation output via a ValidationReport type.
- Imports ReleaseMetadata and ValidationReport alongside the Distributor base, indicating tight coupling between metadata representation and validation.

## Maintenance Notes

- Represent RouteNote-specific distribution behavior by providing a RouteNoteConnector class that inherits from Distributor.
- Assemble release data and assets into a package that mirrors RouteNote's web form fields (Release Data -> Album Details -> Add Audio -> Artwork).
- Pre-validate release metadata and assets against RouteNote's expected specs and produce a ValidationReport.
- Expose methods on the RouteNoteConnector to perform the packaging and validation steps required for preparing releases for RouteNote.


---

## Functions and Classes


### RouteNoteConnector

![Type: Concrete](https://img.shields.io/badge/Type-Concrete-green) ![Methods: 2](https://img.shields.io/badge/Methods-2-blue) ![Attributes: 2](https://img.shields.io/badge/Attributes-2-blue)

#### Description

RouteNoteConnector is a concrete Distributor implementation that encapsulates the logic needed to prepare and validate releases for distribution via the RouteNote service.

This class serves as the RouteNote-specific Distributor implementation within backend/connectors/routenote.py, implementing the validation and packaging steps required to hand off a release to the RouteNote upload process.

Responsibilities:
- Provide connector-specific constants and configuration (e.g. name and UPLOAD_URL) required for interacting with RouteNote.
- Validate release data and/or configuration before attempting to distribute (validate method).
- Assemble or package the release assets and metadata into the format expected by RouteNote (build_package method).

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

---



### validate

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def validate(self, m: ReleaseMetadata) -> ValidationReport:
```

#### Description

Validate the given release metadata against the requirements and constraints of the RouteNote connector, producing a report of any problems, warnings, or missing/invalid fields.

It ensures the ReleaseMetadata is suitable for submission through the RouteNote integration and encodes those findings in a ValidationReport.

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

Prepare and assemble a distributable package for a release identified by release_id using provided metadata, audio files, and artwork, writing the resulting package to out_dir.

It may incorporate optional provenance information and returns the path to the created package file as a string.

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
