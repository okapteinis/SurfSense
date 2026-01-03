# Full Codebase Review Request

This PR compares empty baseline with current nightly branch to enable Gemini Code Assist review of the ENTIRE codebase.

## Scope

**Backend (Python/FastAPI):**
- `surfsense_backend/app/` - All routes, services, models
- `surfsense_backend/alembic/` - Database migrations
- `pyproject.toml` - Dependencies

**Frontend (Next.js/React):**
- `surfsense_web/app/` - All pages and components
- `surfsense_web/lib/` - Utilities and API clients
- `surfsense_web/hooks/` - React hooks
- `package.json` - Dependencies

**Documentation:**
- README.md, README.lv.md, README.sv.md
- CLAUDE.md - AI assistant instructions

**Configuration:**
- `.github/workflows/` - CI/CD
- Docker files
- Environment configs

## Review Focus Areas

Please review for:
1. **Security issues** - Auth, input validation, SQL injection, XSS
2. **Code quality** - Best practices, design patterns
3. **Performance** - N+1 queries, inefficient algorithms
4. **Dependencies** - Outdated or vulnerable packages
5. **Architecture** - Component structure, separation of concerns
6. **Error handling** - Proper try/catch, logging
7. **Type safety** - TypeScript/Python type hints
8. **Testing** - Missing test coverage
9. **Documentation** - Missing or unclear docs

## Key Files to Prioritize

**Critical Security:**
- `surfsense_backend/app/routes/two_fa_routes.py` (2FA auth)
- `surfsense_backend/app/users.py` (user management)
- `surfsense_web/lib/apis/auth-api.service.ts` (auth client)
- `surfsense_web/middleware.ts` (route protection)

**Core Functionality:**
- `surfsense_backend/app/routes/chats_routes.py` (chat logic)
- `surfsense_backend/app/services/query_service.py` (search)
- `surfsense_web/app/dashboard/` (main UI)

**Database:**
- `surfsense_backend/alembic/versions/` (all migrations)
- `surfsense_backend/app/db.py` (data models)

## This PR Will NOT Be Merged

- **Purpose:** Review only
- **Status:** Changes already in nightly branch
- **Action:** Will close after review complete

---

@gemini-code-assist Please perform comprehensive code review
