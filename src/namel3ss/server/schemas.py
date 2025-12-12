"""Pydantic schemas used by the FastAPI server."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ParseRequest(BaseModel):
    source: str


class StudioFileResponse(BaseModel):
    path: str
    content: str


class StudioFileRequest(BaseModel):
    path: str = Field(..., description="Project-root-relative path to file")
    content: str


class StudioTreeNode(BaseModel):
    name: str
    path: str
    type: str  # "directory" or "file"
    kind: str | None = None
    children: list["StudioTreeNode"] | None = None


StudioTreeNode.model_rebuild()


class RunAppRequest(BaseModel):
    source: str
    app_name: str


class RunFlowRequest(BaseModel):
    source: str
    flow: str


class PagesRequest(BaseModel):
    code: str


class PageUIRequest(BaseModel):
    code: str
    page: str


class DiagnosticsRequest(BaseModel):
    paths: list[str]
    strict: bool = False
    summary_only: bool = False
    lint: bool = False


class UIManifestRequest(BaseModel):
    code: str


class UIFlowExecuteRequest(BaseModel):
    source: str | None = None
    flow: str
    args: dict[str, Any] = {}


class CodeTransformRequest(BaseModel):
    path: str
    op: str = "update_property"
    element_id: str | None = None
    parent_id: str | None = None
    position: str | None = None
    index: int | None = None
    new_element: dict[str, Any] | None = None
    property: str | None = None
    new_value: str | None = None


class UIGenerateRequest(BaseModel):
    prompt: str
    page_path: str
    selected_element_id: str | None = None


class BundleRequest(BaseModel):
    code: str
    target: str | None = "server"


class RAGQueryRequest(BaseModel):
    code: str
    query: str
    indexes: Optional[list[str]] = None


class RagStageUpdateRequest(BaseModel):
    stage: str
    changes: Dict[str, Any] = Field(default_factory=dict)


class RagPreviewRequest(BaseModel):
    query: str | None = None
    max_debug_stages: int | None = None


class FlowsRequest(BaseModel):
    code: str


class TriggerRegistrationRequest(BaseModel):
    id: str
    kind: str
    flow_name: str
    config: Dict[str, Any]
    enabled: bool = True


class TriggerFireRequest(BaseModel):
    payload: Optional[Dict[str, Any]] = None


class UIEventRequest(BaseModel):
    code: str
    page: str
    component_id: str
    event: str
    payload: Dict[str, Any] = {}


class PluginInstallRequest(BaseModel):
    path: str


class PluginMetadata(BaseModel):
    id: str
    name: str
    version: str | None = None
    description: Optional[str] = None
    author: Optional[str] = None
    compatible: Optional[bool] = True
    enabled: Optional[bool] = True
    loaded: Optional[bool] = False
    errors: List[str] = []
    path: Optional[str] = None
    entrypoints: Dict[str, Any] = {}
    contributions: Dict[str, List[str]] = {}
    tags: List[str] = []


class FmtPreviewRequest(BaseModel):
    source: str


class FmtPreviewResponse(BaseModel):
    formatted: str
    changes_made: bool


class MemoryClearRequest(BaseModel):
    kinds: List[str] | None = None


class NamingMigrationChange(BaseModel):
    from_name: str = Field(..., alias="from")
    to_name: str = Field(..., alias="to")
    model_config = ConfigDict(populate_by_name=True)


class NamingMigrationSummary(BaseModel):
    headers_rewritten: int = 0
    let_rewritten: int = 0
    set_rewritten: int = 0
    names_renamed: list[NamingMigrationChange] = []
    suggested_names: list[NamingMigrationChange] = []
    changed: bool = False


class NamingMigrationRequest(BaseModel):
    source: str
    fix_names: bool = False


class NamingMigrationResponse(BaseModel):
    source: str
    changes_summary: NamingMigrationSummary


__all__ = [
    "ParseRequest",
    "StudioFileResponse",
    "StudioFileRequest",
    "StudioTreeNode",
    "RunAppRequest",
    "RunFlowRequest",
    "PagesRequest",
    "PageUIRequest",
    "DiagnosticsRequest",
    "UIManifestRequest",
    "UIFlowExecuteRequest",
    "CodeTransformRequest",
    "UIGenerateRequest",
    "BundleRequest",
    "RAGQueryRequest",
    "RagStageUpdateRequest",
    "RagPreviewRequest",
    "FlowsRequest",
    "TriggerRegistrationRequest",
    "TriggerFireRequest",
    "UIEventRequest",
    "PluginInstallRequest",
    "PluginMetadata",
    "FmtPreviewRequest",
    "FmtPreviewResponse",
    "MemoryClearRequest",
    "NamingMigrationChange",
    "NamingMigrationSummary",
    "NamingMigrationRequest",
    "NamingMigrationResponse",
]
