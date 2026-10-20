from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
	Column,
	String,
	Integer,
	DateTime,
	Boolean,
	func,
	UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
	__tablename__ = "users"
	__table_args__ = (
		UniqueConstraint("phone_number", name="uq_users_phone_number"),
	)

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

	first_name = Column(String(128), nullable=True)
	last_name = Column(String(128), nullable=True)
	gender = Column(String(32), nullable=True)
	country_code = Column(String(8), nullable=True)

	phone_number = Column(String(32), nullable=False, unique=True, index=True)
	email = Column(String(254), nullable=True, index=True)

	is_active = Column(Boolean, nullable=False, default=True)

	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

	def __repr__(self) -> str:  # pragma: no cover - simple representation
		return f"<User id={self.id} user_id={self.user_id} phone={self.phone_number} email={self.email}>"
