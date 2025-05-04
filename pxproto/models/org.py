from datetime import datetime
from enum import Enum

import sqlalchemy
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from database import ensure_loaded
from models import User
from pxproto.database import Base


class Organization(Base):
  __tablename__ = "organization"

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(64), nullable=False, unique=True)
  owner_id = Column(ForeignKey("user.id"), nullable=False)

  account_limit = Column(Integer, default=3, server_default='3', nullable=False)
  member_limit = Column(Integer, default=3, server_default='3', nullable=False)

  created_at = Column(DateTime, default=datetime.now)
  deleted_at = Column(DateTime, default=None)

  owner = relationship("User", backref="owned_organizations")
  accounts = relationship("Account", backref="organization")

  async def to_dict(self, /, *, session: AsyncSession = None, load_members=False):
    r = {
      'id': self.id,
      'name': self.name,
      'member_limit': self.member_limit
    }

    if load_members:
      assert session
      await ensure_loaded(session, self, 'members')
      members = []
      for member in self.members:
        member: OrganizationMember
        await ensure_loaded(session, member, 'user')
        user: User = member.user
        members.append({
          'username': user.username,
          'role': member.role
        })
      r['members'] = members

      await ensure_loaded(session, self, 'owner')
      r['owner'] = {
        'username': self.owner.username,
        'role': OrganizationRole.OWNER
      }

      r['member_count'] = len(members) + 1

    return r


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
