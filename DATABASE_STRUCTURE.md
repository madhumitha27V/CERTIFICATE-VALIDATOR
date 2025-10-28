# Certificate Validator - Database Structure

## Separate Database Architecture

### Admin Portal (`/admin/`)
- **Database**: `admin/database.db` (local) or `/data/admin_database.db` (deployed)
- **Purpose**: Stores admin and government user accounts
- **Tables**:
  - `users` - Admin and Government users only
  - `admin` - Legacy admin accounts
  - `block_jan2024`, `block_may2024`, `block_nov2024` - Certificate data

### User Portal (`/user/`)
- **Database**: `user/database.db` (local) or `/data/user_database.db` (deployed)  
- **Purpose**: Stores regular user accounts and their certificates
- **Tables**:
  - `portal_users` - Regular user accounts
  - `user_certificates` - User uploaded certificates

## User Registration Flow

### Admin/Government Users
1. Go to Admin Portal signup: `/signup`
2. Choose role: Admin or Government
3. Data stored in: `admin/database.db`

### Regular Users  
1. Go to User Portal signup: `/user/signup`
2. Automatically assigned 'user' role
3. Data stored in: `user/database.db`

## Database Locations

**Local Development:**
```
CERTIFICATE-VALIDATOR/
├── admin/
│   └── database.db          # Admin & Government users
└── user/
    └── database.db          # Regular users
```

**Deployed (Render):**
```
/opt/render/project/src/data/
├── admin_database.db        # Admin & Government users
└── user_database.db         # Regular users
```

This separation ensures:
- ✅ Admin data stays in admin database
- ✅ User data stays in user database  
- ✅ No mixing of user types
- ✅ Better security and organization