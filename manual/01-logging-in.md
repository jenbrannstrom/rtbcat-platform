# Chapter 1: Logging In

*Audience: everyone*

## Authentication methods

Cat-Scan supports three login methods:

| Method | How it works | When to use |
|--------|-------------|-------------|
| **Google OAuth** | Click "Sign in with Google", which redirects through OAuth2 Proxy | Most users. Uses your Google Workspace account. |
| **Authing (OIDC)** | Click "Sign in with Authing", which redirects to OIDC provider | Organizations using Authing as their identity provider. |
| **Email & password** | Enter credentials directly on the login page | Local accounts created by an administrator. |

## First login

1. Navigate to `https://scan.rtb.cat` (or your deployment's URL).
2. You'll see the login page with available sign-in options.
3. Choose your method and authenticate.
4. On first login, the system creates your user record automatically (for
   OAuth methods). Your administrator may need to grant you access to specific
   buyer seats.

## The seat selector

After logging in, you'll see the sidebar with a **seat selector** at the top.
If your account has access to multiple buyer seats, use the dropdown to switch
between them. All data on every page is scoped to the selected seat.

- **Single seat**: the selector shows your seat name and ID directly.
- **Multiple seats**: a dropdown lets you switch. Each entry shows the buyer
  display name, the `buyer_account_id`, and a creative count.
- **"Sync All" button**: refreshes creatives, endpoints, and pretargeting
  configs from Google's API for the selected seat.

## When login fails

| Symptom | Likely cause | What to do |
|---------|-------------|------------|
| Redirect loop (page keeps reloading) | Database unreachable, so the auth check fails silently | Check Cloud SQL Proxy container. See [Troubleshooting](15-troubleshooting.md). |
| "Server unavailable" (502/503/504) | API or nginx container is down | Contact your DevOps team. See [Health Monitoring](13-health-monitoring.md). |
| "Authentication required" | Session expired or cookie cleared | Sign in again. |
| "You don't have access to this buyer account" | Permissions not granted for this seat | Ask your administrator. See [User Administration](16-user-admin.md). |

## Next steps

- [Navigating the Dashboard](02-navigating-the-dashboard.md)
