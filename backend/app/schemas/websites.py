"""Website schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class WebsiteCreateRequest(BaseModel):
    url: str = Field(..., min_length=3, max_length=2048)


class WebsiteBulkImportRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=5000)


class WebsiteFieldUpdateRequest(BaseModel):
    cluster_key: str = Field(..., min_length=1, max_length=64)
