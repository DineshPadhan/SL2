from datetime import date, datetime, timedelta

import jwt

from src.database import SessionLocal
from src.models import Batch, BatchInvite, BatchStudent, BatchTrainer, Institution, Role, Session, User
from src.task2_auth import hash_password


def create_user(db, *, name, email, role, institution_id=None, password="Password123!"):
    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        institution_id=institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_login_user(client, *, name, email, role, institution_id=None, password="Password123!"):
    response = client.post(
        "/auth/signup",
        json={
            "name": name,
            "email": email,
            "password": password,
            "role": role.value,
            "institution_id": institution_id,
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def seed_training_graph():
    db = SessionLocal()
    try:
        institution = Institution(name="Test Institution", region="north")
        db.add(institution)
        db.commit()
        db.refresh(institution)

        trainer = create_user(db, name="Trainer", email="trainer@test.com", role=Role.TRAINER, institution_id=institution.id)
        student = create_user(db, name="Student", email="student@test.com", role=Role.STUDENT, institution_id=institution.id)
        outsider = create_user(db, name="Outsider", email="outsider@test.com", role=Role.STUDENT, institution_id=institution.id)
        institution_user = create_user(db, name="Institution User", email="inst@test.com", role=Role.INSTITUTION, institution_id=institution.id)
        pm_user = create_user(db, name="PM", email="pm@test.com", role=Role.PROGRAMME_MANAGER)
        monitor = create_user(db, name="Monitor", email="monitor@test.com", role=Role.MONITORING_OFFICER)

        batch = Batch(name="Batch A", institution_id=institution.id)
        db.add(batch)
        db.commit()
        db.refresh(batch)

        db.add(BatchTrainer(batch_id=batch.id, trainer_id=trainer.id))
        db.add(BatchStudent(batch_id=batch.id, student_id=student.id))
        db.commit()

        now = datetime.now()
        session = Session(
            batch_id=batch.id,
            trainer_id=trainer.id,
            title="Live Session",
            date=date.today(),
            start_time=(now - timedelta(minutes=30)).time().replace(microsecond=0),
            end_time=(now + timedelta(minutes=30)).time().replace(microsecond=0),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        return {
            "institution": institution,
            "trainer": trainer,
            "student": student,
            "outsider": outsider,
            "institution_user": institution_user,
            "pm_user": pm_user,
            "monitor": monitor,
            "batch": batch,
            "session": session,
        }
    finally:
        db.close()


def test_student_signup_and_login_returns_jwt(client):
    signup = client.post(
        "/auth/signup",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "Password123!",
            "role": "student",
            "institution_id": None,
        },
    )
    assert signup.status_code == 201
    assert signup.json()["access_token"]

    login = client.post("/auth/login", json={"email": "alice@example.com", "password": "Password123!"})
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_trainer_creates_session_with_required_fields(client):
    graph = seed_training_graph()
    trainer_token = create_login_user(
        client,
        name="Trainer Auth",
        email="trainer-auth@test.com",
        role=Role.TRAINER,
        institution_id=graph["institution"].id,
    )

    db = SessionLocal()
    try:
        trainer_auth = db.query(User).filter_by(email="trainer-auth@test.com").first()
        db.add(BatchTrainer(batch_id=graph["batch"].id, trainer_id=trainer_auth.id))
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/sessions",
        headers=auth_headers(trainer_token),
        json={
            "batch_id": graph["batch"].id,
            "title": "Testing Session",
            "date": str(date.today()),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Testing Session"


def test_student_marks_own_attendance_successfully(client):
    graph = seed_training_graph()
    token = create_login_user(
        client,
        name="Student Auth",
        email="student-auth@test.com",
        role=Role.STUDENT,
        institution_id=graph["institution"].id,
    )

    db = SessionLocal()
    try:
        auth_student = db.query(User).filter_by(email="student-auth@test.com").first()
        db.add(BatchStudent(batch_id=graph["batch"].id, student_id=auth_student.id))
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/attendance/mark",
        headers=auth_headers(token),
        json={"session_id": graph["session"].id, "status": "present"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "present"


def test_post_to_monitoring_attendance_returns_405(client):
    response = client.post("/monitoring/attendance")
    assert response.status_code == 405


def test_missing_token_on_protected_endpoint_returns_401(client):
    response = client.post("/batches", json={"name": "Batch", "institution_id": 1, "trainer_ids": []})
    assert response.status_code == 401


def test_student_not_enrolled_cannot_mark_attendance(client):
    graph = seed_training_graph()
    token = create_login_user(
        client,
        name="Outsider Auth",
        email="outsider-auth@test.com",
        role=Role.STUDENT,
        institution_id=graph["institution"].id,
    )

    response = client.post(
        "/attendance/mark",
        headers=auth_headers(token),
        json={"session_id": graph["session"].id, "status": "present"},
    )
    assert response.status_code == 403


def test_monitoring_officer_gets_scoped_token_and_uses_it(client):
    graph = seed_training_graph()
    login_token = create_login_user(
        client,
        name="Monitor Auth",
        email="monitor-auth@test.com",
        role=Role.MONITORING_OFFICER,
        institution_id=None,
    )

    issue = client.post(
        "/auth/monitoring-token",
        headers=auth_headers(login_token),
        json={"key": "test-monitoring-key"},
    )
    assert issue.status_code == 200
    scoped_token = issue.json()["access_token"]
    payload = jwt.decode(scoped_token, "test-secret", algorithms=["HS256"])
    assert payload["token_use"] == "monitoring"
    assert payload["scope"] == "read:monitoring"

    response = client.get("/monitoring/attendance", headers=auth_headers(scoped_token))
    assert response.status_code == 200


def test_standard_login_token_is_rejected_on_monitoring_endpoint(client):
    graph = seed_training_graph()
    login_token = create_login_user(
        client,
        name="Monitor Auth 2",
        email="monitor-auth-2@test.com",
        role=Role.MONITORING_OFFICER,
        institution_id=None,
    )

    response = client.get("/monitoring/attendance", headers=auth_headers(login_token))
    assert response.status_code == 401


def test_creating_session_for_missing_batch_returns_404(client):
    graph = seed_training_graph()
    trainer_token = create_login_user(
        client,
        name="Trainer Missing Batch",
        email="trainer-missing-batch@test.com",
        role=Role.TRAINER,
        institution_id=graph["institution"].id,
    )

    response = client.post(
        "/sessions",
        headers=auth_headers(trainer_token),
        json={
            "batch_id": 99999,
            "title": "Invalid Batch Session",
            "date": str(date.today()),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
    )
    assert response.status_code == 404


def test_student_cannot_create_session(client):
    graph = seed_training_graph()
    student_token = create_login_user(
        client,
        name="Student Session Creator",
        email="student-session@test.com",
        role=Role.STUDENT,
        institution_id=graph["institution"].id,
    )

    response = client.post(
        "/sessions",
        headers=auth_headers(student_token),
        json={
            "batch_id": graph["batch"].id,
            "title": "Should Fail",
            "date": str(date.today()),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
        },
    )
    assert response.status_code == 403


def test_expired_invite_is_rejected(client):
    graph = seed_training_graph()
    trainer_token = create_login_user(
        client,
        name="Trainer Invite",
        email="trainer-invite@test.com",
        role=Role.TRAINER,
        institution_id=graph["institution"].id,
    )

    db = SessionLocal()
    try:
        trainer_auth = db.query(User).filter_by(email="trainer-invite@test.com").first()
        db.add(BatchTrainer(batch_id=graph["batch"].id, trainer_id=trainer_auth.id))
        db.commit()
    finally:
        db.close()

    invite = client.post(
        f"/batches/{graph['batch'].id}/invite",
        headers=auth_headers(trainer_token),
    )
    assert invite.status_code == 201
    token = invite.json()["token"]

    db = SessionLocal()
    try:
        batch_invite = db.query(BatchInvite).filter_by(token=token).first()
        batch_invite.expires_at = datetime.now() - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    student_token = create_login_user(
        client,
        name="Invite Student",
        email="invite-student@test.com",
        role=Role.STUDENT,
        institution_id=graph["institution"].id,
    )

    response = client.post(
        "/batches/join",
        headers=auth_headers(student_token),
        json={"token": token},
    )
    assert response.status_code == 401
