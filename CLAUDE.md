# Claude Code Guidelines

## Memory Constraints
This project runs in a memory-limited environment. Follow these rules to prevent crashes:

### DO NOT run these commands (run manually before starting session):
- `npm install` - memory intensive
- `npm run build` / `next build` - memory intensive
- `pytest` with large test suites - run specific tests instead

### For large files (>500 lines):
- Read in chunks using offset/limit parameters
- Large files in this project:
  - `api/routers/settings_legacy.py` (1800+ lines)
  - `dashboard/src/lib/api.ts` (1500+ lines)
  - `storage/sqlite_store.py` (1400+ lines)

### Pre-session setup:
```bash
cd dashboard && npm install  # Do this before Claude session
```

## Project Structure
- `/api` - FastAPI backend
- `/dashboard` - Next.js frontend
- `/storage` - Database layer
- `/analytics` - RTB analytics modules

## Testing
Run specific tests, not full suites:
```bash
pytest tests/test_specific.py -v  # Good
pytest  # Avoid - runs everything
```

## Common Tasks
- API changes: Edit files in `/api/routers/`
- Frontend: Edit files in `/dashboard/src/`
- Database: Edit `/storage/` files, then run migrations
