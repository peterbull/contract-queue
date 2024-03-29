import datetime
import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Notice(Base):
    __tablename__ = "notices"
    id = Column(String, primary_key=True, index=True)
    title = Column(String)
    solicitationNumber = Column(String)
    fullParentPathName = Column(String)
    fullParentPathCode = Column(String)
    postedDate = Column(DateTime)
    type = Column(String)
    baseType = Column(String)
    archiveType = Column(String)
    archiveDate = Column(DateTime)
    typeOfSetAsideDescription = Column(String)
    typeOfSetAside = Column(String)
    responseDeadLine = Column(DateTime)

    naics_code_id = Column(Integer, ForeignKey("naics_codes.id"))
    naicsCode = relationship("NaicsCodes", back_populates="notice", lazy="selectin")

    naicsCodes = Column(ARRAY(String))
    classificationCode = Column(String)
    active = Column(Boolean)
    award = Column(String)
    description = Column(String)
    organizationType = Column(String)
    additionalInfoLink = Column(String)
    uiLink = Column(String)

    office_address_id = Column(Integer, ForeignKey("office_addresses.id"))
    office_address = relationship("OfficeAddress", back_populates="notice", lazy="selectin")

    place_of_performance_id = Column(Integer, ForeignKey("places_of_performance.id"))
    place_of_performance = relationship(
        "PlaceOfPerformance", back_populates="notice", lazy="selectin"
    )

    points_of_contact = relationship("PointOfContact", back_populates="notice", lazy="selectin")
    links = relationship("Link", back_populates="notice", lazy="selectin")
    resource_links = relationship("ResourceLink", back_populates="notice", lazy="selectin")
    mean_embeddings = relationship("MeanEmbeddings", back_populates="notice", lazy="selectin")


class PointOfContact(Base):
    __tablename__ = "points_of_contact"
    id = Column(Integer, primary_key=True, index=True)
    fax = Column(String)
    type = Column(String)
    email = Column(String)
    phone = Column(String)
    title = Column(String)
    fullName = Column(String)
    notice_id = Column(String, ForeignKey("notices.id"))
    notice = relationship("Notice", back_populates="points_of_contact", lazy="selectin")


class OfficeAddress(Base):
    __tablename__ = "office_addresses"
    id = Column(Integer, primary_key=True, index=True)
    zipcode = Column(String)
    city = Column(String)
    countryCode = Column(String)
    state = Column(String)
    notice = relationship(
        "Notice",
        back_populates="office_address",
        uselist=False,
        lazy="selectin",
    )


class PlaceOfPerformance(Base):
    __tablename__ = "places_of_performance"
    id = Column(Integer, primary_key=True, index=True)
    city_code = Column(String)
    city_name = Column(String)
    state_code = Column(String)
    state_name = Column(String)
    country_code = Column(String)
    country_name = Column(String)
    notice = relationship(
        "Notice",
        back_populates="place_of_performance",
        uselist=True,
        lazy="selectin",
    )


class Link(Base):
    __tablename__ = "links"
    id = Column(Integer, primary_key=True, index=True)
    rel = Column(String)
    href = Column(String)
    notice_id = Column(String, ForeignKey("notices.id"))
    notice = relationship("Notice", back_populates="links", lazy="selectin")


class LinkType(enum.Enum):
    SOLICITATION = "solicitation"
    AMENDMENT = "amendment"
    OTHER = "other"


class ResourceLink(Base):
    __tablename__ = "resource_links"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String)
    text = Column(String)
    file_name = Column(String)
    file_size = Column(Integer)
    file_category = Column(Enum(LinkType))
    file_tokens = Column(Integer)
    summary = Column(String)
    summary_tokens = Column(Integer)
    summary_embedding = Column(Vector(1536))
    summary_chunks = relationship("SummaryChunks", back_populates="resource_link")
    notice_id = Column(String, ForeignKey("notices.id"))
    notice = relationship("Notice", back_populates="resource_links", lazy="selectin")


class SummaryChunks(Base):
    __tablename__ = "summary_chunks"
    id = Column(Integer, primary_key=True, index=True)
    chunk_text = Column(String)
    chunk_tokens = Column(Integer)
    chunk_embedding = Column(Vector(1536))
    resource_link_id = Column(Integer, ForeignKey("resource_links.id"))
    resource_link = relationship("ResourceLink", back_populates="summary_chunks")


class NaicsCodes(Base):
    __tablename__ = "naics_codes"
    id = Column(Integer, primary_key=True, index=True)
    naicsCode = Column(Integer, unique=True)
    title = Column(String)
    description = Column(String)
    description_embedding = Column(Vector(1536))

    notice = relationship("Notice", back_populates="naicsCode", lazy="selectin")


class MeanEmbeddings(Base):
    __tablename__ = "mean_embeddings"
    id = Column(Integer, primary_key=True, index=True)
    mean_embedding = Column(Vector(1536))
    notice_id = Column(String, ForeignKey("notices.id"))
    notice = relationship("Notice", back_populates="mean_embeddings")
