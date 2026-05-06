from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from secrets import token_urlsafe
import sys

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.database import get_db
from src.models import (
    Attendance,
    AttendanceStatus,
    Batch,
    BatchInvite,
    BatchStudent,
    BatchTrainer,
    Institution,
    Role,
    Session as TrainingSession,
    User,
)
from src.schemas import (
    AttendanceMarkRequest,
    AttendanceRecordOut,
    AttendanceResponse,
    BatchCreate,
    BatchResponse,
    BatchSummaryResponse,
    InstitutionSummaryResponse,
    InviteResponse,
    JoinBatchRequest,
    MonitoringAttendanceRow,
    ProgrammeSummaryResponse,
    SessionCreate,
    SessionResponse,
)
from src.task2_auth import get_monitoring_user, require_roles

router = APIRouter(tags=["core-api"])


def ensure_batch_exists(batch_id: int, db: Session) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


def ensure_session_exists(session_id: int, db: Session) -> TrainingSession:
    session = (
        db.query(TrainingSession)
        .options(joinedload(TrainingSession.batch))
        .filter(TrainingSession.id == session_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def batch_summary_payload(batch: Batch) -> BatchSummaryResponse:
    statuses = Counter(
        record.status.value
        for session in batch.sessions
        for record in session.attendance_records
    )
    return BatchSummaryResponse(
        batch_id=batch.id,
        batch_name=batch.name,
        total_students=len(batch.students),
        total_sessions=len(batch.sessions),
        attendance_breakdown=dict(statuses),
    )


def institution_summary_payload(institution: Institution) -> InstitutionSummaryResponse:
    statuses = Counter(
        record.status.value
        for batch in institution.batches
        for session in batch.sessions
        for record in session.attendance_records
    )
    student_ids = {
        student.student_id
        for batch in institution.batches
        for student in batch.students
    }
    return InstitutionSummaryResponse(
        institution_id=institution.id,
        institution_name=institution.name,
        total_batches=len(institution.batches),
        total_students=len(student_ids),
        total_sessions=sum(len(batch.sessions) for batch in institution.batches),
        attendance_breakdown=dict(statuses),
    )


@router.post("/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.TRAINER, Role.INSTITUTION)),
) -> Batch:
    institution = db.get(Institution, payload.institution_id)
    if institution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    if current_user.role == Role.INSTITUTION and current_user.institution_id != payload.institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create batch for another institution")

    batch = Batch(name=payload.name, institution_id=payload.institution_id)
    db.add(batch)
    db.flush()

    trainer_ids = payload.trainer_ids or ([current_user.id] if current_user.role == Role.TRAINER else [])
    for trainer_id in set(trainer_ids):
        trainer = db.get(User, trainer_id)
        if trainer is None or trainer.role != Role.TRAINER:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trainer {trainer_id} not found")
        db.add(BatchTrainer(batch_id=batch.id, trainer_id=trainer_id))

    db.commit()
    db.refresh(batch)
    return batch


@router.post("/batches/{batch_id}/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def create_batch_invite(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.TRAINER, Role.INSTITUTION)),
) -> InviteResponse:
    batch = ensure_batch_exists(batch_id, db)

    if current_user.role == Role.TRAINER:
        assigned = db.query(BatchTrainer).filter_by(batch_id=batch_id, trainer_id=current_user.id).first()
        if assigned is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trainer not assigned to this batch")
    if current_user.role == Role.INSTITUTION and current_user.institution_id != batch.institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another institution's batch")

    invite = BatchInvite(
        batch_id=batch_id,
        token=token_urlsafe(24),
        created_by=current_user.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        used=False,
    )
    db.add(invite)
    db.commit()
    return InviteResponse(batch_id=batch_id, token=invite.token, expires_at=invite.expires_at, used=invite.used)


@router.post("/batches/join", status_code=status.HTTP_200_OK)
def join_batch(
    payload: JoinBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.STUDENT)),
):
    invite = db.query(BatchInvite).filter(BatchInvite.token == payload.token).first()
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite token not found")
    if invite.used:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invite token already used")
    if to_utc(invite.expires_at) < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invite token expired")

    existing = db.query(BatchStudent).filter_by(batch_id=invite.batch_id, student_id=current_user.id).first()
    if existing is None:
        db.add(BatchStudent(batch_id=invite.batch_id, student_id=current_user.id))
    invite.used = True
    db.commit()
    return {"message": "Joined batch successfully", "batch_id": invite.batch_id}


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.TRAINER)),
) -> TrainingSession:
    batch = ensure_batch_exists(payload.batch_id, db)
    assigned = db.query(BatchTrainer).filter_by(batch_id=batch.id, trainer_id=current_user.id).first()
    if assigned is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trainer not assigned to this batch")
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end_time must be after start_time")

    session = TrainingSession(
        batch_id=payload.batch_id,
        trainer_id=current_user.id,
        title=payload.title,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/attendance/mark", response_model=AttendanceResponse)
def mark_attendance(
    payload: AttendanceMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.STUDENT)),
) -> Attendance:
    session = ensure_session_exists(payload.session_id, db)

    enrollment = db.query(BatchStudent).filter_by(batch_id=session.batch_id, student_id=current_user.id).first()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is not enrolled in this batch")

    now = datetime.now()
    if session.date != now.date() or not (session.start_time <= now.time() <= session.end_time):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attendance can only be marked for an active session")

    record = db.query(Attendance).filter_by(session_id=session.id, student_id=current_user.id).first()
    if record is None:
        record = Attendance(session_id=session.id, student_id=current_user.id, status=payload.status)
        db.add(record)
    else:
        record.status = payload.status
        record.marked_at = datetime.now(UTC)

    db.commit()
    db.refresh(record)
    return record


@router.get("/sessions/{session_id}/attendance", response_model=list[AttendanceRecordOut])
def session_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.TRAINER)),
) -> list[AttendanceRecordOut]:
    session = ensure_session_exists(session_id, db)
    assigned = db.query(BatchTrainer).filter_by(batch_id=session.batch_id, trainer_id=current_user.id).first()
    if assigned is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trainer not assigned to this batch")

    records = (
        db.query(Attendance, User)
        .join(User, User.id == Attendance.student_id)
        .filter(Attendance.session_id == session_id)
        .all()
    )
    return [
        AttendanceRecordOut(
            student_id=user.id,
            student_name=user.name,
            student_email=user.email,
            status=attendance.status,
            marked_at=attendance.marked_at,
        )
        for attendance, user in records
    ]


@router.get("/batches/{batch_id}/summary", response_model=BatchSummaryResponse)
def batch_summary(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.INSTITUTION)),
) -> BatchSummaryResponse:
    batch = (
        db.query(Batch)
        .options(
            joinedload(Batch.students),
            joinedload(Batch.sessions).joinedload(TrainingSession.attendance_records),
        )
        .filter(Batch.id == batch_id)
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if current_user.institution_id != batch.institution_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another institution's batch")
    return batch_summary_payload(batch)


@router.get("/institutions/{institution_id}/summary", response_model=InstitutionSummaryResponse)
def institution_summary(
    institution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.PROGRAMME_MANAGER)),
) -> InstitutionSummaryResponse:
    institution = (
        db.query(Institution)
        .options(
            joinedload(Institution.batches).joinedload(Batch.students),
            joinedload(Institution.batches).joinedload(Batch.sessions).joinedload(TrainingSession.attendance_records),
        )
        .filter(Institution.id == institution_id)
        .first()
    )
    if institution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")
    return institution_summary_payload(institution)


@router.get("/programme/summary", response_model=ProgrammeSummaryResponse)
def programme_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.PROGRAMME_MANAGER)),
) -> ProgrammeSummaryResponse:
    institutions = (
        db.query(Institution)
        .options(
            joinedload(Institution.batches).joinedload(Batch.students),
            joinedload(Institution.batches).joinedload(Batch.sessions).joinedload(TrainingSession.attendance_records),
        )
        .all()
    )
    statuses = Counter(
        record.status.value
        for institution in institutions
        for batch in institution.batches
        for session in batch.sessions
        for record in session.attendance_records
    )
    student_ids = {
        student.student_id
        for institution in institutions
        for batch in institution.batches
        for student in batch.students
    }
    return ProgrammeSummaryResponse(
        total_institutions=len(institutions),
        total_batches=sum(len(institution.batches) for institution in institutions),
        total_students=len(student_ids),
        total_sessions=sum(len(batch.sessions) for institution in institutions for batch in institution.batches),
        attendance_breakdown=dict(statuses),
    )


@router.get("/monitoring/attendance", response_model=list[MonitoringAttendanceRow])
def monitoring_attendance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_monitoring_user),
) -> list[MonitoringAttendanceRow]:
    _ = current_user
    rows = (
        db.query(Attendance, TrainingSession, Batch, Institution, User)
        .join(TrainingSession, TrainingSession.id == Attendance.session_id)
        .join(Batch, Batch.id == TrainingSession.batch_id)
        .join(Institution, Institution.id == Batch.institution_id)
        .join(User, User.id == Attendance.student_id)
        .order_by(Attendance.marked_at.desc())
        .all()
    )
    return [
        MonitoringAttendanceRow(
            session_id=session.id,
            session_title=session.title,
            batch_name=batch.name,
            institution_name=institution.name,
            student_id=user.id,
            student_name=user.name,
            status=attendance.status,
            marked_at=attendance.marked_at,
        )
        for attendance, session, batch, institution, user in rows
    ]
