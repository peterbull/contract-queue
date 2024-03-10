from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


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


class ResourceLinkBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    url: Optional[str]


class NaicsCodeSimple(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int]
    naicsCode: Optional[int]
    title: Optional[str]
    description: Optional[str]


class NaicsCodeBase(NaicsCodeSimple):
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
    naicsCode: Optional[NaicsCodeBase]
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
