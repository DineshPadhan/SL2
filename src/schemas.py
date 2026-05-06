from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.models import AttendanceStatus, Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(TokenResponse):
    user: "UserResponse"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role
    institution_id: int | None = None


class MonitoringTokenRequest(BaseModel):
    key: str = Field(min_length=1)


class InstitutionCreate(BaseModel):
    name: str
    region: str = "default-region"


class InstitutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    region: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: Role
    institution_id: int | None
    created_at: datetime


class BatchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    institution_id: int
    trainer_ids: list[int] = Field(default_factory=list)


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    institution_id: int
    created_at: datetime


class InviteResponse(BaseModel):
    batch_id: int
    token: str
    expires_at: datetime
    used: bool


class JoinBatchRequest(BaseModel):
    token: str = Field(min_length=8)


class SessionCreate(BaseModel):
    batch_id: int
    title: str = Field(min_length=2, max_length=255)
    date: date
    start_time: time
    end_time: time


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    trainer_id: int
    title: str
    date: date
    start_time: time
    end_time: time
    created_at: datetime


class AttendanceMarkRequest(BaseModel):
    session_id: int
    status: AttendanceStatus


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    student_id: int
    status: AttendanceStatus
    marked_at: datetime


class AttendanceRecordOut(BaseModel):
    student_id: int
    student_name: str
    student_email: EmailStr
    status: AttendanceStatus
    marked_at: datetime


class BatchSummaryResponse(BaseModel):
    batch_id: int
    batch_name: str
    total_students: int
    total_sessions: int
    attendance_breakdown: dict[str, int]


class InstitutionSummaryResponse(BaseModel):
    institution_id: int
    institution_name: str
    total_batches: int
    total_students: int
    total_sessions: int
    attendance_breakdown: dict[str, int]


class ProgrammeSummaryResponse(BaseModel):
    total_institutions: int
    total_batches: int
    total_students: int
    total_sessions: int
    attendance_breakdown: dict[str, int]


class MonitoringAttendanceRow(BaseModel):
    session_id: int
    session_title: str
    batch_name: str
    institution_name: str
    student_id: int
    student_name: str
    status: AttendanceStatus
    marked_at: datetime


AuthResponse.model_rebuild()
