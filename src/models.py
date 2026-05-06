from datetime import date, datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Role(StrEnum):
    STUDENT = "student"
    TRAINER = "trainer"
    INSTITUTION = "institution"
    PROGRAMME_MANAGER = "programme_manager"
    MONITORING_OFFICER = "monitoring_officer"


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    region: Mapped[str] = mapped_column(String(100), default="default-region", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="institution")
    batches: Mapped[list["Batch"]] = relationship(back_populates="institution")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    institution: Mapped[Institution | None] = relationship(back_populates="users")
    trainer_batches: Mapped[list["BatchTrainer"]] = relationship(back_populates="trainer")
    student_batches: Mapped[list["BatchStudent"]] = relationship(back_populates="student")
    created_invites: Mapped[list["BatchInvite"]] = relationship(back_populates="creator")
    created_sessions: Mapped[list["Session"]] = relationship(back_populates="trainer")
    attendance_records: Mapped[list["Attendance"]] = relationship(back_populates="student")


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    institution: Mapped[Institution] = relationship(back_populates="batches")
    trainers: Mapped[list["BatchTrainer"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    students: Mapped[list["BatchStudent"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    invites: Mapped[list["BatchInvite"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class BatchTrainer(Base):
    __tablename__ = "batch_trainers"
    __table_args__ = (UniqueConstraint("batch_id", "trainer_id", name="uq_batch_trainer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    batch: Mapped[Batch] = relationship(back_populates="trainers")
    trainer: Mapped[User] = relationship(back_populates="trainer_batches")


class BatchStudent(Base):
    __tablename__ = "batch_students"
    __table_args__ = (UniqueConstraint("batch_id", "student_id", name="uq_batch_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    batch: Mapped[Batch] = relationship(back_populates="students")
    student: Mapped[User] = relationship(back_populates="student_batches")


class BatchInvite(Base):
    __tablename__ = "batch_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    batch: Mapped[Batch] = relationship(back_populates="invites")
    creator: Mapped[User] = relationship(back_populates="created_invites")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    batch: Mapped[Batch] = relationship(back_populates="sessions")
    trainer: Mapped[User] = relationship(back_populates="created_sessions")
    attendance_records: Mapped[list["Attendance"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("session_id", "student_id", name="uq_session_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus), nullable=False)
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped[Session] = relationship(back_populates="attendance_records")
    student: Mapped[User] = relationship(back_populates="attendance_records")
