from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.database import Base, SessionLocal, engine
from src.models import Attendance, AttendanceStatus, Batch, BatchStudent, BatchTrainer, Institution, Role, Session, User
from src.task2_auth import hash_password


def seed() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        north = Institution(name="North Skill Centre", region="north")
        south = Institution(name="South Skill Centre", region="south")
        db.add_all([north, south])
        db.flush()

        users = [
            User(name="North Institution", email="institution1@example.com", hashed_password=hash_password("Password123!"), role=Role.INSTITUTION, institution_id=north.id),
            User(name="South Institution", email="institution2@example.com", hashed_password=hash_password("Password123!"), role=Role.INSTITUTION, institution_id=south.id),
            User(name="Programme Manager", email="pm@example.com", hashed_password=hash_password("Password123!"), role=Role.PROGRAMME_MANAGER),
            User(name="Monitoring Officer", email="monitor@example.com", hashed_password=hash_password("Password123!"), role=Role.MONITORING_OFFICER),
            User(name="Trainer One", email="trainer1@example.com", hashed_password=hash_password("Password123!"), role=Role.TRAINER, institution_id=north.id),
            User(name="Trainer Two", email="trainer2@example.com", hashed_password=hash_password("Password123!"), role=Role.TRAINER, institution_id=north.id),
            User(name="Trainer Three", email="trainer3@example.com", hashed_password=hash_password("Password123!"), role=Role.TRAINER, institution_id=south.id),
            User(name="Trainer Four", email="trainer4@example.com", hashed_password=hash_password("Password123!"), role=Role.TRAINER, institution_id=south.id),
        ]
        students = [
            User(
                name=f"Student {idx}",
                email=f"student{idx}@example.com",
                hashed_password=hash_password("Password123!"),
                role=Role.STUDENT,
                institution_id=north.id if idx <= 8 else south.id,
            )
            for idx in range(1, 16)
        ]
        db.add_all(users + students)
        db.flush()

        batches = [
            Batch(name="North Batch A", institution_id=north.id),
            Batch(name="North Batch B", institution_id=north.id),
            Batch(name="South Batch A", institution_id=south.id),
        ]
        db.add_all(batches)
        db.flush()

        trainers = {user.email: user for user in users if user.role == Role.TRAINER}
        db.add_all(
            [
                BatchTrainer(batch_id=batches[0].id, trainer_id=trainers["trainer1@example.com"].id),
                BatchTrainer(batch_id=batches[0].id, trainer_id=trainers["trainer2@example.com"].id),
                BatchTrainer(batch_id=batches[1].id, trainer_id=trainers["trainer2@example.com"].id),
                BatchTrainer(batch_id=batches[2].id, trainer_id=trainers["trainer3@example.com"].id),
                BatchTrainer(batch_id=batches[2].id, trainer_id=trainers["trainer4@example.com"].id),
            ]
        )

        for idx, student in enumerate(students[:6], start=1):
            db.add(BatchStudent(batch_id=batches[0].id, student_id=student.id))
        for student in students[6:10]:
            db.add(BatchStudent(batch_id=batches[1].id, student_id=student.id))
        for student in students[10:]:
            db.add(BatchStudent(batch_id=batches[2].id, student_id=student.id))

        today = date.today()
        session_specs = [
            (batches[0].id, trainers["trainer1@example.com"].id, "Python Basics", today, time(9, 0), time(10, 0)),
            (batches[0].id, trainers["trainer2@example.com"].id, "API Design", today, time(11, 0), time(12, 0)),
            (batches[0].id, trainers["trainer1@example.com"].id, "Testing", today - timedelta(days=1), time(9, 0), time(10, 0)),
            (batches[1].id, trainers["trainer2@example.com"].id, "SQL Intro", today - timedelta(days=1), time(13, 0), time(14, 0)),
            (batches[1].id, trainers["trainer2@example.com"].id, "Deployments", today - timedelta(days=2), time(13, 0), time(14, 0)),
            (batches[2].id, trainers["trainer3@example.com"].id, "Linux Basics", today, time(15, 0), time(16, 0)),
            (batches[2].id, trainers["trainer4@example.com"].id, "Monitoring", today - timedelta(days=1), time(15, 0), time(16, 0)),
            (batches[2].id, trainers["trainer3@example.com"].id, "Security", today - timedelta(days=2), time(15, 0), time(16, 0)),
        ]
        sessions = [Session(batch_id=b, trainer_id=t, title=title, date=d, start_time=s, end_time=e) for b, t, title, d, s, e in session_specs]
        db.add_all(sessions)
        db.flush()

        batch_to_students = {
            batches[0].id: students[:6],
            batches[1].id: students[6:10],
            batches[2].id: students[10:],
        }
        statuses = [AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.ABSENT]
        for session in sessions:
            enrolled_students = batch_to_students[session.batch_id]
            for idx, student in enumerate(enrolled_students):
                db.add(
                    Attendance(
                        session_id=session.id,
                        student_id=student.id,
                        status=statuses[idx % len(statuses)],
                        marked_at=datetime.now(UTC),
                    )
                )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
