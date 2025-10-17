# Admin Dashboard Implementation Status

## ✅ Completed (Backend Core)

### 1. Database Models (`backend/models.py`)
- ✅ Added `pending_approval` field to User model
- ✅ Changed `role` from Enum to String (portability)
- ✅ Added `details_json` field to AuditLog
- ✅ Added composite indexes for admin queries
- ✅ Added CheckConstraint for role validation

### 2. Auth Utils (`backend/api/auth_utils.py`)
- ✅ Added `current_user()` helper with g.user caching
- ✅ Added `_audit_log()` helper with details_json support
- ✅ Added `require_user` decorator (blocks pending approval)
- ✅ Added `require_admin` decorator
- ✅ Added `require_owner` decorator
- ✅ Added `count_active_admins()` and `is_last_admin()` guard rails

### 3. Owner Bootstrap (`backend/app.py`)
- ✅ Added `bootstrap_owner_from_env()` function
- ✅ Called in `create_app()` after DB init
- ✅ Supports OWNER_USERNAME, OWNER_SEED_PASSWORD, ALLOW_OWNER_TRANSFER

## 🔄 In Progress / TODO

### 4. Database Migration
**Action Required:**
```bash
# In dev container:
cd backend
alembic revision --autogenerate -m "add pending_approval and owner role"
alembic upgrade head
```

### 5. Environment Variables
**Add to `.env` and `.devcontainer/devcontainer.json`:**
```bash
OWNER_USERNAME=admin
OWNER_SEED_PASSWORD=changeme123
ALLOW_OWNER_TRANSFER=0
```

### 6. Update Auth Routes (`backend/api/routes/auth.py`)
- ⏳ Update `/signup` endpoint:
  - Set `active=False, pending_approval=True`
  - Do NOT auto-login
  - Return "Account pending approval" message
- ⏳ Update `/login` endpoint:
  - Block if `pending_approval=True` or `active=False`
  - Return 403 with "account_pending_approval" error
- ⏳ Update `/me` endpoint:
  - Return `pending_approval` and `role` fields
- ⏳ Add `/register` note about first-user bootstrap (optional)

### 7. Create Admin Blueprint (`backend/api/routes/admin.py`)
**New file with endpoints:**
- ⏳ `GET /api/admin/pending-users` - List pending approvals
- ⏳ `POST /api/admin/users/<id>/approve` - Approve user
- ⏳ `POST /api/admin/users/<id>/reject` - Reject user (hard delete)
- ⏳ `GET /api/admin/audit-logs` - View audit logs (with JOIN to avoid N+1)
- ⏳ `GET /api/admin/analyses` - View all analyses (with JOIN to avoid N+1)
- ⏳ `POST /api/admin/analyses/<id>/reassign` - Reassign analysis
- ⏳ `GET /api/admin/users/search?q=` - Search users for dropdown
- ⏳ `POST /api/admin/users/<id>/promote` - Promote to admin (owner only)
- ⏳ `POST /api/admin/users/<id>/demote` - Demote to user (owner only)
- ⏳ `POST /api/admin/users/<id>/deactivate` - Deactivate user (owner only)

**Register in `app.py`:**
```python
from api.routes.admin import admin_bp
app.register_blueprint(admin_bp, url_prefix="/api/admin")
```

### 8. Update Existing Routes to use `@require_user`
**Files to update:**
- ⏳ `backend/api/routes/video_upload.py` - Change `@require_login` to `@require_user`
- ⏳ `backend/api/routes/analysis.py` - Change `@require_login` to `@require_user`

### 9. Frontend - Auth Flow Updates
- ⏳ Update `frontend/src/pages/Login.jsx`:
  - Route admins/owners to `/role-select`
  - Route users to `/upload`
  - Show "account_pending_approval" error message
- ⏳ Update `frontend/src/pages/SignUp.jsx`:
  - Show "pending approval" message after signup
  - Navigate to login with state message
- ⏳ Update `frontend/src/app/ProtectedRoute.jsx`:
  - Add `adminOnly` prop
  - Check `user.active` and `user.pending_approval`
  - Show pending approval screen if needed

### 10. Frontend - New Pages
- ⏳ Create `frontend/src/pages/RoleSelect.jsx` - Admin workflow selector
- ⏳ Create `frontend/src/pages/AdminDashboard.jsx` - 3-tab dashboard:
  - Tab 1: Pending Approvals
  - Tab 2: Audit Logs
  - Tab 3: Analysis Management (with reassign modal)
- ⏳ Create `frontend/src/api/admin.js` - API client functions

### 11. Frontend - Routing
- ⏳ Update `frontend/src/app/App.jsx`:
  - Add `/role-select` route (admin only)
  - Add `/admin` route (admin only)

## 🧪 Testing Checklist

### Database & Bootstrap
- [ ] Run Alembic migration successfully
- [ ] Bootstrap creates owner with env vars
- [ ] Bootstrap fails loudly if OWNER_SEED_PASSWORD missing
- [ ] Bootstrap fails if ALLOW_OWNER_TRANSFER=0 and another owner exists

### Signup & Approval Flow
- [ ] Signup creates pending user (active=False, pending_approval=True)
- [ ] Pending user cannot login (403 "account_pending_approval")
- [ ] Admin sees pending user in dashboard
- [ ] Admin can approve user (active=True, pending_approval=False)
- [ ] Approved user can login
- [ ] Admin can reject user (hard delete, username available for re-signup)

### Admin Dashboard
- [ ] Audit logs display with usernames (no N+1 queries)
- [ ] Analyses display with usernames (no N+1 queries)
- [ ] User search dropdown works with debounce
- [ ] Reassignment validates target user is active & approved
- [ ] Reassignment is logged in audit trail

### Authorization
- [ ] Regular user cannot access `/api/admin/*` routes (403)
- [ ] Pending user cannot access `/api/videos/*` or `/api/analyses/*` (403)
- [ ] Admin can view all data
- [ ] Owner can promote/demote admins
- [ ] Cannot demote last admin (409)
- [ ] Cannot modify owner via API (403)

### Owner Guards
- [ ] Cannot demote/deactivate owner
- [ ] Cannot demote last admin
- [ ] Owner can promote user to admin
- [ ] Owner can demote admin to user

## 📝 Notes

### Hard Delete on Reject
- We chose **hard delete** for rejected users to free up usernames for re-signup
- Alternative would be soft reject (keep row, set inactive) but burns username
- If you want soft reject, change reject endpoint to set `active=False` instead of `db.delete()`

### N+1 Query Prevention
- Admin endpoints must JOIN User table and return username in one query
- Use `selectinload` or join + query construction
- Example:
  ```python
  analyses = db.query(Analysis, User.username).join(User).filter(...).all()
  ```

### Role Validation
- Role is String not Enum for portability
- CheckConstraint enforces valid values: `IN ('user', 'admin', 'owner')`
- Application-level validation in decorators

### Session Management
- Use `g.user` to cache current user per request
- Decorators set `g.user` for downstream use
- Avoids multiple DB queries per request
