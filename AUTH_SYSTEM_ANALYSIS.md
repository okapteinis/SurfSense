# SurfSense Authentication & Session Management System - Comprehensive Report

## 1. Overview of the Authentication System

The SurfSense frontend uses a **client-side JWT token-based authentication system** with localStorage for token persistence. The system supports both local username/password login and Google OAuth authentication, with tokens managed entirely on the client side without middleware protection.

---

## 2. Token Storage and Management

### 2.1 Storage Mechanism
- **Storage Location**: `localStorage` (browser's local storage)
- **Storage Key**: `"surfsense_bearer_token"`
- **Token Type**: JWT access token from backend
- **Expiration**: Handled by backend (frontend does not validate expiration)

### 2.2 Token Access Points
The token is accessed via `localStorage.getItem("surfsense_bearer_token")` in multiple places:

```
- /lib/apis/base-api.service.ts (initialization)
- /hooks/use-user.ts (user data fetching)
- /hooks/use-search-spaces.ts (search spaces fetching)
- /components/UserDropdown.tsx (logout clears token)
- Direct fetch calls in various page components
```

**Critical Finding**: The BaseApiService reads the token **only once at initialization**:
```typescript
// Line 185 of base-api.service.ts
export const baseApiService = new BaseApiService(
	typeof window !== "undefined" ? localStorage.getItem("surfsense_bearer_token") || "" : "",
	process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || ""
);
```

This is a potential issue - if the token in localStorage changes after initialization, the baseApiService won't know about it.

---

## 3. Authentication Flow

### 3.1 Local Username/Password Login

1. **User enters credentials** on `/login` page (LocalLoginForm.tsx)
2. **API Request**: POST to `/auth/jwt/login`
   - Sends username and password as form data
   - Uses custom AuthApiService with Zod validation
3. **Successful Response**: Returns `{ access_token, token_type }`
4. **Token Redirect**: Router redirects to `/auth/callback?token={access_token}`
5. **Token Storage**: TokenHandler component on `/auth/callback`:
   - Extracts token from URL parameter
   - Stores in localStorage with key "surfsense_bearer_token"
   - Redirects to `/dashboard`

### 3.2 Google OAuth Login

1. **User clicks "Continue with Google"** button
2. **Authorization Request**: Fetches from backend endpoint `/auth/google/authorize`
3. **Backend Response**: Returns `{ authorization_url }`
4. **Redirect**: `window.location.href = authorization_url` (hard redirect to Google)
5. **After Google Approval**: Backend returns to `/auth/callback?token={token}`
6. **Token Storage**: Same flow as local login

### 3.3 Registration Flow

1. **User registers** on `/register` page
2. **API Request**: POST to `/auth/register`
   - Sends email, password, and optional fields
3. **Success**: Redirect to `/login?registered=true`
4. **User must then login** with the registered credentials

---

## 4. Home Route ("/") Handling and Navigation

### 4.1 What Happens When Navigating to "/"

The home route (`/`) is **public and unprotected**. It displays:
- Navbar (fixed, appears on all pages)
- Hero section with features and CTA
- No authentication check
- Footer

### 4.2 The Logo Component Issue

**File**: `/components/Logo.tsx`
```typescript
export const Logo = ({ className }: { className?: string }) => {
	return (
		<Link href="/">
			<Image src="/icon-128.png" className={cn(className)} alt="logo" width={128} height={128} />
		</Link>
	);
};
```

**Key Finding**: The logo is a simple Next.js `<Link>` component that navigates to "/". It:
- Does NOT cause logout or clear tokens
- Does NOT trigger any redirect logic
- Simply navigates to the home page using client-side routing

When an authenticated user clicks the logo from the dashboard:
1. Router navigates to "/" (home route)
2. The home layout (`/app/(home)/layout.tsx`) renders with Navbar and content
3. The dashboard layout is unmounted (component cleanup)
4. Token remains in localStorage (NOT cleared)
5. User is still "logged in" but viewing the public home page

### 4.3 Logo Location

The logo appears in:
- **Homepage**: `/app/(home)/layout.tsx` - Navbar component
- **Dashboard**: `/app/dashboard/page.tsx` - Line 210, part of the header
- Used in login/register pages as well

---

## 5. Session and Cookie Management

### 5.1 Session Storage Strategy
- **No sessions**: The app uses stateless JWT tokens, not server sessions
- **No cookies**: Tokens are stored in localStorage, not cookies
- **No HttpOnly cookies**: Tokens are accessible via JavaScript

### 5.2 Authentication Checks

**Dashboard Layout** (`/app/dashboard/layout.tsx`):
```typescript
useEffect(() => {
	const token = localStorage.getItem("surfsense_bearer_token");
	if (!token) {
		router.push("/login");
		return;
	}
	setIsCheckingAuth(false);
}, [router]);
```

This runs **only on component mount**, meaning:
- If token is deleted while on dashboard, user won't be redirected until they navigate
- Checks happen reactively, not proactively

### 5.3 User Data Fetching

The `useUser()` hook (`/hooks/use-user.ts`) fetches user info from `/users/me`:
- Runs once on mount (empty dependency array)
- If it gets a 401 response, it clears localStorage and redirects to "/"
- This is the **only automatic logout mechanism** triggered by API response

---

## 6. Token Validation and Refresh Mechanisms

### 6.1 Token Validation

Tokens are validated on **each API request**:

**BaseApiService** includes token in Authorization header:
```typescript
headers: {
	"Authorization": `Bearer ${this.bearerToken || ""}`,
	...
}
```

**Response Handling** (lines 86-104 of base-api.service.ts):
- 401 Response: Throws `AuthenticationError("You are not authenticated. Please login again.")`
- 403 Response: Throws `AuthorizationError`
- Other errors: Throws generic `AppError`

### 6.2 Token Refresh

**CRITICAL FINDING**: There is **NO token refresh mechanism**!

Evidence:
1. No refresh endpoint called anywhere
2. No refresh token stored
3. `loginResponse` schema only includes `access_token` and `token_type`
4. No token expiration checks in frontend
5. When token expires, users must login again

The noAuthEndpoints list includes:
```typescript
noAuthEndpoints: string[] = ["/auth/jwt/login", "/auth/register", "/auth/refresh"];
```

This suggests a `/auth/refresh` endpoint might exist on the backend, but it's **never called** from the frontend.

---

## 7. Middleware and Route Guards

### 7.1 Server-Side Middleware

**File**: `/middleware.ts`
```typescript
// Middleware temporarily disabled for client-side i18n implementation
// Server-side i18n routing would require restructuring entire app directory
// which is too invasive for this project

export function middleware(request: NextRequest) {
	return NextResponse.next();
}
```

**Result**: Middleware is **completely disabled**. There is:
- No route protection at server level
- No token validation on server
- No CSRF protection
- No request interception for auth

### 7.2 Client-Side Route Guards

**Dashboard Layout** checks token on mount, but this is the **only guard**:
- Other routes have no protection
- Public routes accessible to everyone
- Auth state not checked globally

### 7.3 Protected Routes

- `/dashboard` - Protected by checking localStorage on mount
- `/login` - Public
- `/register` - Public
- `/` - Public
- `/docs` - Public
- `/pricing` - Public

---

## 8. How Session Loss Occurs

### Root Causes of Session Loss

#### 8.1 Stale Token in BaseApiService
When a user logs in and a new token is stored in localStorage, the `baseApiService` singleton still has the old token value from initialization. This can cause:
- API requests to fail with invalid token
- 401 responses triggering logout
- Confusing "You are not authenticated" errors

#### 8.2 Clicking Logo While Authenticated
**Scenario**: User logs in, navigates to dashboard, clicks logo
1. Logo is a `<Link href="/">` component
2. Next.js client-side navigation occurs
3. Dashboard layout component unmounts
4. User sees home page with navbar
5. Token is still in localStorage
6. User clicks dashboard link or navigates back
7. Dashboard checks localStorage, token exists, allows entry
8. BUT: useUser() hook runs and if token expired, gets 401
9. useUser() hook response handler: clears localStorage, redirects to "/"
10. User is back at home without knowing why

#### 8.3 Token Expiration
Since there's no refresh mechanism:
- User logs in
- Token has a backend-set expiration (likely 24 hours or similar)
- Token expires while user is idle or away
- Next API call gets 401 response
- User is redirected to "/" (home page)
- No notice of what happened
- User must login again

#### 8.4 Multiple Tabs/Windows
localStorage is shared across all tabs:
- User logs in on Tab 1
- Logs out on Tab 2
- Tab 1 still has token in localStorage but backend session is invalid
- Next Tab 1 API call gets 401, redirects to "/"

#### 8.5 localStorage Clearing
Any code that calls `localStorage.removeItem("surfsense_bearer_token")` causes logout:
- UserDropdown component (manual logout)
- useUser hook (on 401 response)
- Browser clearing localStorage
- Browser privacy mode (loses data on close)

---

## 9. Security Concerns and Vulnerabilities

### 9.1 XSS Vulnerability (HIGH SEVERITY)

**Issue**: Token stored in localStorage is accessible to JavaScript
```javascript
// Any script on the page can do this:
localStorage.getItem("surfsense_bearer_token")
```

**Impact**:
- XSS attacks can steal tokens
- Malicious JS libraries can access token
- No protection against the most common web attack

**Recommendation**: Use HttpOnly cookies for token storage

### 9.2 No CSRF Protection (MEDIUM SEVERITY)

**Issue**: Middleware is disabled, so no CSRF tokens are validated

**Impact**:
- Cross-site requests can mutate state on behalf of user
- Disabled by design for i18n reasons

**Recommendation**: Implement CSRF tokens in a way that works with client-side i18n

### 9.3 No Token Refresh Mechanism (HIGH SEVERITY)

**Issue**: When token expires, user must login again

**Impact**:
- Poor user experience (forced logout)
- No graceful handling of token expiration
- Potential for users to lose work
- Login endpoint doesn't seem to support refresh tokens

**Recommendation**: Implement token refresh before expiration

### 9.4 No Token Expiration Validation (MEDIUM SEVERITY)

**Issue**: Frontend doesn't decode/validate JWT expiration

**Impact**:
- Frontend can't preemptively refresh before expiration
- No warning before token becomes invalid
- User discovers expiration when API fails

**Recommendation**: Decode JWT, check expiration, and refresh proactively

### 9.5 Synchronous Token Reads (LOW SEVERITY)

**Issue**: Token is read from localStorage on every API call
```typescript
Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
```

**Impact**:
- Inefficient
- Token changes between calls might be missed
- Race conditions possible in rapid requests

**Recommendation**: Use a token atom/state management to share token updates

### 9.6 No Secure Flag on Storage (MEDIUM SEVERITY)

**Issue**: localStorage is not encrypted and persists across page reloads

**Impact**:
- Token visible in browser DevTools
- Token visible if computer is compromised
- Token persists if user forgets to logout

**Recommendation**: Use session storage for sensitive data, HttpOnly cookies for tokens

### 9.7 Inconsistent Token Usage

**Issue**: Some code uses `baseApiService`, others use direct `fetch()` calls

**Impact**:
- Some requests might not include token properly
- Inconsistent error handling
- Different components might see different auth states

### 9.8 No Logout Confirmation

**Issue**: useUser hook's logout is silent
```typescript
if (response.status === 401) {
	localStorage.removeItem("surfsense_bearer_token");
	window.location.href = "/";
}
```

**Impact**:
- Users are redirected to home without knowing why
- Could be confusing if user loses work
- No option to save state before logout

---

## 10. User Information and Profiles

### 10.1 User Data Structure
```typescript
interface User {
	id: string;
	email: string;
	is_active: boolean;
	is_superuser: boolean;
	is_verified: boolean;
	pages_limit: number;
	pages_used: number;
}
```

### 10.2 User Data Fetching

**Endpoint**: `/users/me`

**Hook**: `useUser()` in `/hooks/use-user.ts`
- Fetches once on mount
- Uses token from localStorage
- On 401, clears token and redirects to "/"
- Displays in UserDropdown component

---

## 11. Complete Authentication Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    REGISTRATION FLOW                        │
├─────────────────────────────────────────────────────────────┤
│ 1. User fills /register form (email, password)              │
│ 2. Submit → POST /auth/register                             │
│ 3. Success → Redirect to /login?registered=true             │
│ 4. Show success toast message                               │
│ 5. User must login with credentials                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  LOCAL LOGIN FLOW                           │
├─────────────────────────────────────────────────────────────┤
│ 1. User fills /login form (email, password)                 │
│ 2. Submit → POST /auth/jwt/login (form data)                │
│ 3. Success → Response: {access_token, token_type}           │
│ 4. Redirect → /auth/callback?token={access_token}           │
│ 5. TokenHandler extracts token from URL                     │
│ 6. Store in localStorage["surfsense_bearer_token"]          │
│ 7. Redirect → /dashboard                                    │
│ 8. Dashboard layout checks token, renders if exists         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  GOOGLE OAUTH FLOW                          │
├─────────────────────────────────────────────────────────────┤
│ 1. User clicks "Continue with Google"                       │
│ 2. Fetch /auth/google/authorize                             │
│ 3. Response: {authorization_url}                            │
│ 4. Hard redirect → window.location.href = auth_url          │
│ 5. Google OAuth flow (user approves)                        │
│ 6. Backend redirects to /auth/callback?token={token}        │
│ 7. Rest same as LOCAL LOGIN FLOW                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              AUTHENTICATED REQUEST FLOW                     │
├─────────────────────────────────────────────────────────────┤
│ 1. User navigates to /dashboard                             │
│ 2. Dashboard layout checks localStorage for token           │
│ 3. Token exists → Allow access                              │
│ 4. Component mounts → useUser() fetches /users/me           │
│ 5. Header request: Authorization: Bearer {token}            │
│ 6. Backend validates token → Returns user data              │
│ 7. Display UserDropdown with user info                      │
│                                                              │
│ If token expired/invalid:                                   │
│ 5. Server returns 401 Unauthorized                          │
│ 6. useUser hook clears localStorage                         │
│ 7. Redirect to / via window.location.href                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  LOGOUT FLOW                                │
├─────────────────────────────────────────────────────────────┤
│ 1. User clicks "Log out" in UserDropdown                    │
│ 2. handleLogout() executes:                                 │
│    - localStorage.removeItem("surfsense_bearer_token")      │
│    - router.push("/")                                       │
│ 3. Redirect to home page                                    │
│ 4. Token no longer available for API calls                  │
│ 5. Next auth-required action redirects to /login            │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. Key Technical Details

### 12.1 API Endpoints Used

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/auth/jwt/login` | POST | Local password login | No |
| `/auth/register` | POST | User registration | No |
| `/auth/google/authorize` | GET | Get Google OAuth URL | No |
| `/auth/refresh` | POST | Refresh token (unused) | No |
| `/users/me` | GET | Fetch current user | Yes |
| `/api/v1/searchspaces` | GET | List user's search spaces | Yes |

### 12.2 State Management

- **Jotai**: Used for mutations (login, register)
  - `loginMutationAtom` - Login mutation with React Query
  - `registerMutationAtom` - Register mutation with React Query
  
- **React Query**: Handles mutations and caching
  - Cache keys in `/lib/query-client/cache-keys.ts`
  
- **Local State**: Component-level `useState` for UI state

- **No Global Auth Context**: No AuthContext or similar abstraction
  - Token accessed directly via localStorage in each component
  - No centralized auth state

### 12.3 Environment Variables Required

```
NEXT_PUBLIC_FASTAPI_BACKEND_URL    # Backend API URL
NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE  # 'GOOGLE' or 'LOCAL'
```

---

## 13. Summary of Issues and Recommendations

### Critical Issues

1. **XSS Vulnerability via localStorage**
   - Token stored in accessible location
   - Recommendation: Use HttpOnly cookies

2. **No Token Refresh Mechanism**
   - Users forced to login when token expires
   - Recommendation: Implement token refresh before expiration

3. **Inconsistent Auth Checks**
   - Only dashboard has route guard
   - Recommendation: Create global auth context/guard

4. **Silent Logout on 401**
   - Users redirected to "/" without explanation
   - Recommendation: Show notification before logout

### High Priority Issues

5. **Stale BaseApiService Token**
   - Token cached at initialization
   - Recommendation: Make token reading dynamic

6. **No CSRF Protection**
   - Middleware disabled
   - Recommendation: Implement CSRF tokens

7. **No Token Expiration Validation**
   - Frontend can't preemptively refresh
   - Recommendation: Decode JWT and check exp claim

### Medium Priority Issues

8. **Poor Error Handling**
   - 401 errors not consistently handled
   - Recommendation: Standardize error handling

9. **No State Preservation**
   - Users lose work when redirected to login
   - Recommendation: Implement redirect-after-login

10. **Multiple API Call Methods**
    - Mix of baseApiService and fetch()
    - Recommendation: Standardize on one approach

---

## 14. Conclusion

The SurfSense authentication system is a **client-side JWT token-based implementation** that prioritizes simplicity over security. While it works for basic authentication flows, it has several significant security vulnerabilities and user experience issues:

**Strengths**:
- Simple to understand and implement
- Supports both local and OAuth login
- Clear separation of authenticated and public routes

**Weaknesses**:
- XSS-vulnerable token storage
- No automatic token refresh
- Silent logout on expiration
- Inconsistent auth checking across routes
- No middleware protection

**Immediate Actions**:
1. Move tokens to HttpOnly cookies
2. Implement token refresh mechanism
3. Add global auth context for consistency
4. Show user notifications on logout/expiration
5. Enable server-side middleware for CSRF protection
