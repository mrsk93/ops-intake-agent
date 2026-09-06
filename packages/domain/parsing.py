from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCoordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    page: int | None = Field(default=None, ge=1)
    sheet: str | None = None
    row_start: int | None = Field(default=None, ge=1)
    row_end: int | None = Field(default=None, ge=1)
    col_start: int | None = Field(default=None, ge=1)
    col_end: int | None = Field(default=None, ge=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)


class ParsedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class ParsedCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(ge=1)
    column_number: int = Field(ge=1)
    value: str
    evidence: EvidenceCoordinate


class ParsedTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: str
    sheet: str | None = None
    page: int | None = Field(default=None, ge=1)
    headers: list[str]
    cells: list[ParsedCell]
    evidence: EvidenceCoordinate


class ParserWarning(BaseModel):
    code: str
    message: str
    evidence: EvidenceCoordinate | None = None


class ParsedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    parser_name: str
    parser_version: str
    pages: list[ParsedPage] = Field(default_factory=list)
    tables: list[ParsedTable] = Field(default_factory=list)
    warnings: list[ParserWarning] = Field(default_factory=list)
    text_sha256: str


class ParserFailure(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


ParsedUnitKind = Literal["page", "table", "cell"]
