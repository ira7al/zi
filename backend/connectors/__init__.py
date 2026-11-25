from .base import Distributor, ReleaseMetadata, TrackMetadata, ValidationReport
from .routenote import RouteNoteConnector

REGISTRY: dict[str, Distributor] = {"routenote": RouteNoteConnector()}
