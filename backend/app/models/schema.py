from datetime import datetime
from enum import Enum

from app.models.models import LinkType
from pydantic import BaseModel, ConfigDict
from typing_extensions import List, Optional


class PointOfContactBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    fax: Optional[str]
    type: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    title: Optional[str]
    fullName: Optional[str]


class OfficeAddressBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    zipcode: Optional[str]
    city: Optional[str]
    countryCode: Optional[str]
    state: Optional[str]


class PlaceOfPerformanceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    city_code: Optional[str]
    city_name: Optional[str]
    state_code: Optional[str]
    state_name: Optional[str]
    country_code: Optional[str]
    country_name: Optional[str]


class LinkBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    rel: Optional[str]
    href: Optional[str]


class ResourceLinkSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    url: Optional[str]
    text: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    file_category: Optional[LinkType]
    file_tokens: Optional[int]
    summary: Optional[str]
    summary_tokens: Optional[int]


class ResourceLinkBase(ResourceLinkSimple):
    summary_embedding: Optional[List[float]]


class SummaryChunksSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    chunk_text: Optional[str]
    chunk_tokens: Optional[int]


class SummaryChunksBase(SummaryChunksSimple):
    chunk_embedding: Optional[List[float]]


class NaicsCodeSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    naicsCode: Optional[int]
    title: Optional[str]
    description: Optional[str]


class NaicsCodeBase(NaicsCodeSimple):
    description_embedding: Optional[List[float]]


class NaicsCodeEmbedding(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description_embedding: Optional[List[float]]


class NoticeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str]
    title: Optional[str]
    solicitationNumber: Optional[str]
    fullParentPathName: Optional[str]
    fullParentPathCode: Optional[str]
    postedDate: Optional[datetime]
    type: Optional[str]
    baseType: Optional[str]
    archiveType: Optional[str]
    archiveDate: Optional[datetime]
    typeOfSetAsideDescription: Optional[str]
    typeOfSetAside: Optional[str]
    responseDeadLine: Optional[datetime]
    naicsCode: Optional[NaicsCodeSimple]
    naicsCodes: Optional[List[str]]
    classificationCode: Optional[str]
    active: Optional[bool]
    award: Optional[str]
    description: Optional[str]
    organizationType: Optional[str]
    additionalInfoLink: Optional[str]
    uiLink: Optional[str]
    office_address: Optional[OfficeAddressBase]
    place_of_performance: Optional[PlaceOfPerformanceBase]
    points_of_contact: Optional[List[PointOfContactBase]]
    links: Optional[List[LinkBase]]
    resource_links: Optional[List[ResourceLinkBase]]


class MeanEmbeddingBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    mean_embedding: Optional[List[float]]
    notice_id: Optional[str]
