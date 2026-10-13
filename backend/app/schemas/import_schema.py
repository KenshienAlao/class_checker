"""Response schema for the Student Import endpoint."""

from pydantic import BaseModel


class ImportRejection(BaseModel):
    """A single rejected row with its 1-based data-row number and error."""

    row: int
    error: str


class ImportSummary(BaseModel):
    """Summary of a Student Import operation."""

    created: int
    skipped: int
    rejected: list[ImportRejection]
