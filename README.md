# SkillBridge Attendance API

This submission implements the assignment as a FastAPI project with server-side RBAC, JWT authentication, a separate monitoring token flow, seed data, and pytest coverage. The code is split so the assignment maps cleanly to the PDF:

- Task 1 core API: `src/task1_core_api.py`
- Task 2 authentication and RBAC: `src/task2_auth.py`
- Task 3 validation and error handling: `src/task3_validation.py`
- Shared schema and persistence: `src/models.py`, `src/schemas.py`, `src/database.py`, `src/config.py`

## Live API base URL

**Deployment was not executed from this workspace.** The API is ready to deploy; follow the deployment task instructions below to complete it.

## What Is Working

- User signup and login for all five roles
- Standard JWT access tokens with `user_id`, `role`, `iat`, `exp`, and `token_use`
- JWT role claims are validated against the authenticated user on protected endpoints
- Monitoring Officer secondary token flow via `POST /auth/monitoring-token`
- Role checks on protected endpoints with 401 and 403 handling
- Batch creation, invite generation, invite-based join, session creation, attendance marking
- Batch, institution, programme, and monitoring summary endpoints
- Seed script with institutions, trainers, students, batches, sessions, and attendance data
- Pytest coverage for the required core flows plus spec-edge cases for monitoring tokens, expired invites, and 404/403 handling
- Direct file execution from `src/` works for the main app, seed script, and task modules

## What Is Partial

- **Task 4 (Deployment)**: Not executed in this workspace. Code is deployment-ready; see "Deployment Task" section below.
- Token revocation and rotation are not implemented beyond expiry (documented in Security Notes).
- Local SQLite is used for development; production should use Neon PostgreSQL as per assignment guidance.

## What Was Skipped

- No live Railway/Render/Fly.io deployment URL
- No managed PostgreSQL instance configuration in this repository

## Local Setup

1. Create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and edit secrets if needed.
4. Seed the database with `python -m src.seed`.
5. Start the API with `uvicorn src.main:app --reload`.
6. Run tests with `pytest`.

## Test Accounts

These are created by `python -m src.seed`:

- Institution 1: `institution1@example.com` / `Password123!`
- Institution 2: `institution2@example.com` / `Password123!`
- Trainer 1: `trainer1@example.com` / `Password123!`
- Trainer 2: `trainer2@example.com` / `Password123!`
- Trainer 3: `trainer3@example.com` / `Password123!`
- Trainer 4: `trainer4@example.com` / `Password123!`
- Programme Manager: `pm@example.com` / `Password123!`
- Monitoring Officer: `monitor@example.com` / `Password123!`
- Student example: `student1@example.com` / `Password123!`

## Sample curl Commands

Standard login:

```bash
curl -X POST http://127.0.0.1:8000/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"trainer1@example.com\",\"password\":\"Password123!\"}"
```

Signup:

```bash
curl -X POST http://127.0.0.1:8000/auth/signup ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"New Student\",\"email\":\"newstudent@example.com\",\"password\":\"Password123!\",\"role\":\"student\"}"
```

Create batch:

```bash
curl -X POST http://127.0.0.1:8000/batches ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Batch X\",\"institution_id\":1,\"trainer_ids\":[5]}"
```

Create invite:

```bash
curl -X POST http://127.0.0.1:8000/batches/1/invite ^
  -H "Authorization: Bearer <access_token>"
```

Join batch:

```bash
curl -X POST http://127.0.0.1:8000/batches/join ^
  -H "Authorization: Bearer <student_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"token\":\"<invite_token>\"}"
```

Create session:

```bash
curl -X POST http://127.0.0.1:8000/sessions ^
  -H "Authorization: Bearer <trainer_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"batch_id\":1,\"title\":\"Live Session\",\"date\":\"2026-05-05\",\"start_time\":\"09:00:00\",\"end_time\":\"10:00:00\"}"
```

Mark attendance:

```bash
curl -X POST http://127.0.0.1:8000/attendance/mark ^
  -H "Authorization: Bearer <student_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":1,\"status\":\"present\"}"
```

Session attendance:

```bash
curl http://127.0.0.1:8000/sessions/1/attendance ^
  -H "Authorization: Bearer <trainer_token>"
```

Batch summary:

```bash
curl http://127.0.0.1:8000/batches/1/summary ^
  -H "Authorization: Bearer <institution_token>"
```

Institution summary:

```bash
curl http://127.0.0.1:8000/institutions/1/summary ^
  -H "Authorization: Bearer <programme_manager_token>"
```

Programme summary:

```bash
curl http://127.0.0.1:8000/programme/summary ^
  -H "Authorization: Bearer <programme_manager_token>"
```

Issue monitoring token:

```bash
curl -X POST http://127.0.0.1:8000/auth/monitoring-token ^
  -H "Authorization: Bearer <monitor_login_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"key\":\"replace-with-monitoring-api-key\"}"
```

Read monitoring attendance:

```bash
curl http://127.0.0.1:8000/monitoring/attendance ^
  -H "Authorization: Bearer <monitoring_scoped_token>"
```

## JWT Payload Structure

Standard access token payload:

```json
{
  "user_id": 5,
  "role": "trainer",
  "token_use": "access",
  "iat": 1714915200,
  "exp": 1715001600
}
```

Monitoring token payload:

```json
{
  "user_id": 4,
  "role": "monitoring_officer",
  "token_use": "monitoring",
  "scope": "read:monitoring",
  "iat": 1714915200,
  "exp": 1714918800
}
```

## Schema Decisions

- `batch_trainers` is a dedicated join table because the assignment explicitly requires many-to-many trainer assignment per batch.
- `batch_invites` stores a unique token, creator, expiry, and a `used` flag so invite-based joins can be validated server-side.
- Monitoring access uses a dual-token model:
  The login token proves identity and role.
  The secondary monitoring token narrows access to `read:monitoring` only and is rejected on normal endpoints.
- An `institutions` table was added because the endpoint set requires institution-level summaries and user/batch ownership.

## Validation and Error Handling

- Invalid request bodies return 422 with a structured error payload.
- Missing tokens return 401.
- Wrong roles return 403.
- Missing foreign-key targets are converted into 404 responses before insert attempts.
- `/monitoring/attendance` only supports GET, so non-GET requests return 405.

## Security Notes

- Passwords are hashed with `bcrypt`.
- In a real deployment, token rotation and revocation should be handled with short expiries plus a token denylist or rotating signing keys.
- Current limitation:
  Tokens are stateless and cannot be revoked immediately after issuance.
  With more time, I would add refresh tokens, `jti` claims, and a revocation store backed by Redis or PostgreSQL.

## Deployment Task: Setup and Next Steps

### What to Do

**Choose one platform:**
- [Railway.app](https://railway.app) (recommended: GitHub login, auto-deploys on push)
- [Render.com](https://render.com)
- [Fly.io](https://fly.io)

### Step 1: Prepare the Database

1. Create a PostgreSQL instance on [Neon.tech](https://neon.tech) (free tier available).
2. Copy the connection string (e.g., `postgresql://user:pass@host/db`).
3. Update `.env` to use it:
   ```
   DATABASE_URL=postgresql://user:pass@host/db
   ```

### Step 2: Deploy the App

**Railway example:**
1. Push this repo to GitHub.
2. Connect your GitHub repo to Railway.
3. Set environment variables via Railway's dashboard:
   - Copy all values from `.env.example`
   - Use strong, unique values for `JWT_SECRET` and `MONITORING_API_KEY`
4. Railway auto-detects `requirements.txt` and deploys.
5. Copy the assigned public URL (e.g., `https://skillbridge-api-prod.railway.app`).

**Render example:**
1. Push to GitHub.
2. Create a new "Web Service" and connect to this repo.
3. Set Runtime to Python 3.13.
4. Add Start Command: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables in Render's dashboard.
6. Deploy and capture the public URL.

### Step 3: Seed the Production Database

After deployment:
```bash
curl -X POST https://<your-public-url>/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pm@example.com","password":"Password123!"}'
```

Then run the local seed script against the prod database:
```bash
DATABASE_URL=postgresql://prod_connection_string python -m src.seed
```

### Step 4: Verify and Document

1. Test the live `/auth/login` endpoint:
   ```bash
   curl -X POST https://<your-public-url>/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"trainer1@example.com","password":"Password123!"}'
   ```
2. Confirm the response includes an `access_token`.
3. Update this `README.md` with the live base URL and any platform-specific notes.
4. Add a section documenting test accounts that exist on the live deployment.

### Production Checklist Before Final Submission

- [ ] Live base URL is accessible and returns 200 on `GET /`
- [ ] `POST /auth/login` works with seeded test credentials
- [ ] `GET /monitoring/attendance` is protected and returns 401 without a token
- [ ] Seed script has been run on the prod database
- [ ] `.env` values are managed via platform secrets, not committed to repo
- [ ] README includes live base URL, working curl example, and live test accounts

## One Thing I Would Do Differently With More Time

1. Move role and ownership checks into a service layer with reusable authorization policies.
2. Add PostgreSQL-native migrations (e.g., with Alembic) and version-control the schema.
3. Implement a proper deployed smoke-test workflow that validates all endpoints post-deployment.
4. Add refresh tokens and a token denylist (Redis or PostgreSQL) for immediate revocation.
5. Add structured logging and request tracing to help diagnose issues in production.
