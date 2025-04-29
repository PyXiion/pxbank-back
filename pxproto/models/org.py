from datetime import datetime
from enum import Enum

import sqlalchemy
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship

from pxproto.database import Base

class Organization(Base):
  __tablename__ = "organization"

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(64), nullable=False, unique=True)
  owner_id = Column(ForeignKey("user.id"), nullable=False)
  created_at = Column(DateTime, default=datetime.now)

  owner = relationship("User", backref="owned_organizations")
  accounts = relationship("Account", backref="organization")

  def to_dict(self):
    return {
      'id': self.id,
      'name': self.name
    }


class OrganizationRole(str, Enum):
  OWNER = "owner"
  ADMIN = "admin"
  MEMBER = "member"


class OrganizationMember(Base):
  __tablename__ = "organization_member"

  id = Column(Integer, primary_key=True, autoincrement=True)
  organization_id = Column(ForeignKey("organization.id"), nullable=False)
  user_id = Column(ForeignKey("user.id"), nullable=False)
  role = Column(sqlalchemy.Enum(OrganizationRole), nullable=False, default=OrganizationRole.MEMBER)
  joined_at = Column(DateTime, default=datetime.utcnow)

  __table_args__ = (
    UniqueConstraint('organization_id', 'user_id', name='uq_organization_user'),
  )

  organization = relationship("Organization", backref="members")
  user = relationship("User", backref="organization_memberships")
