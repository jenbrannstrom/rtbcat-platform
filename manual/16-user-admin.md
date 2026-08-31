# Chapter 16: User and Permission Administration

*Audience: DevOps, system administrators*

## Admin panel (`/admin`)

The admin panel is only visible to users with the `sudo` role. It provides
user management, system configuration, and audit logging.

## User management (`/admin/users`)

### Creating users

Two methods:

| Method | When to use |
|--------|-------------|
| **Local account** | For users who will log in with email and password. You set the initial password. |
| **OAuth pre-create** | For users who will log in with Google OAuth. Pre-creating the record lets you assign permissions before their first login. |

Fields: email (required), display name, role, auth method, password (local
only).

### Roles and permissions

The role and seat grants work together:

- **Sudo** has unrestricted system-wide read/write access, including the admin panel.
- **Admin** and **Read** are seat-scoped roles. They do not grant access to any
  buyer seat on their own.
- **Per-seat permissions** determine which buyer accounts a non-Sudo user can
  see and whether each seat is read-only or administrable.

A non-Sudo user with no seat permissions sees no buyer data. The permissions
dialog shows this explicitly. It also provides bulk actions to set every active
seat to Read or remove all seat access.

For an account that needs read-only access to all current seats, use **Make
read-only for all seats**. This creates Read grants for each active seat before
removing the Sudo role.

### Managing permissions

1. Go to `/admin/users`
2. Open the row menu and select **Manage Permissions**
3. Set the role and default language
4. Under **Seat Access**, grant or revoke access to buyer seats
5. Use **Service Account Access (legacy)** only for older integrations
6. Changes take effect on the user's next page load

Promoting a user to **Sudo** is staged rather than saved immediately. Review
the unrestricted-access warning, then select the orange **Confirm** button.
After the promotion succeeds, the footer returns to the blue **Done** button.

### Changing a password

Open the row menu and select **Change Password**. An administrator enters the
new password directly; no email service is involved. Existing sessions for the
user are revoked when the password changes.

### Deleting users

Select **Delete User** from the row menu and confirm the permanent deletion.
The user record, password, sessions, explicit permissions, and agent tokens
are removed. Audit history is retained, including the deleted email and role.
You cannot delete your own account.

## Service accounts (`/settings/accounts`)

Service accounts represent GCP credentials that enable Cat-Scan to
communicate with Google APIs.

### Uploading credentials

1. Go to `/settings/accounts` > API Connection tab
2. Upload the GCP service account JSON key file
3. Cat-Scan validates the credentials and shows connection status

**Security note:** Only add the service account JSON key at the end of setup
to minimize exposure risk.

### What service accounts unlock

- **Seat discovery**: find buyer accounts associated with the credentials
- **Pretargeting sync**: pull current config state from Google
- **RTB endpoint sync**: discover bidder endpoints
- **Creative collection**: gather creative metadata

## Audit log (`/admin/audit-log`)

Every significant action is logged:

| Action | What triggers it |
|--------|-----------------|
| `login` | Successful authentication |
| `login_failed` | Failed authentication attempt |
| `login_blocked` | Login rejected (deactivated user, etc.) |
| `create_user` | New user created |
| `update_user` | User profile modified |
| `deactivate_user` | User deactivated |
| `delete_user` | User permanently deleted |
| `reset_password` | Password reset |
| `change_password` | Password changed |
| `grant_permission` | Permission granted |
| `revoke_permission` | Permission revoked |
| `update_setting` | System setting changed |
| `create_initial_admin` | First admin created during setup |

Filters: by user, action type, resource type, time window (days), with
pagination.

## System configuration (`/admin/configuration`)

Global key-value settings that control system behavior. Editable by admins.
Changes are recorded in the audit log.

## Related

- [Logging In](01-logging-in.md): user-facing auth experience
- [Architecture Overview](11-architecture.md): auth trust chain details
