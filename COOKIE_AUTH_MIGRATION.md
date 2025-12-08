# HttpOnly Cookie Authentication Migration Status

## Overview
Migrating from localStorage Bearer tokens to HttpOnly cookies for improved security.

## ✅ Completed Phase 1 - Core Files

### Core Authentication Files
- ✅ `surfsense_web/lib/auth-utils.ts` - Removed localStorage, added credentials: 'include'
- ✅ `surfsense_web/lib/api-client.ts` - Removed Bearer token, added credentials: 'include'
- ✅ `surfsense_web/hooks/use-auth.ts` - Removed localStorage token checks
- ✅ `surfsense_web/lib/constants.ts` - Deprecated AUTH_TOKEN_KEY
- ✅ `surfsense_web/app/dashboard/page.tsx` - Updated handleShareSearchSpace

### Component Files (Partial)
- ✅ `surfsense_web/components/UserDropdown.tsx` - Updated logout to call backend
- ✅ `surfsense_web/components/TokenHandler.tsx` - Updated OAuth flow docs
- ✅ `surfsense_web/components/sources/YouTubeTab.tsx` - Added credentials: 'include'

### New Files Created
- ✅ `surfsense_web/lib/auth-errors.ts` - Better error messages
- ✅ `surfsense_web/scripts/build-production.sh` - Production build script

## 🔄 Remaining Phase 2 - Additional Files (22 files)

### Component Files (3 remaining)
| File | Lines | Change Needed |
|------|-------|---------------|
| `components/sources/DocumentUploadTab.tsx` | 173 | Remove `localStorage.getItem(AUTH_TOKEN_KEY)`, add `credentials: 'include'` |
| `components/chat/ChatPanel/ChatPanelContainer.tsx` | 28 | Remove token check, rely on server verification |
| `components/chat/ChatPanel/PodcastPlayer/PodcastPlayer.tsx` | 60 | Remove `localStorage.getItem(AUTH_TOKEN_KEY)`, add `credentials: 'include'` |

### Hook Files (13 files)
All hook files follow the same pattern:
1. Remove import: `import { AUTH_TOKEN_KEY } from "@/lib/constants";`
2. Remove: `const token = localStorage.getItem(AUTH_TOKEN_KEY);`
3. Remove: `Authorization: \`Bearer ${token}\`` from headers
4. Add: `credentials: 'include'` to fetch options

| File | Occurrences |
|------|-------------|
| `hooks/use-connectors.ts` | 5 |
| `hooks/use-chats.ts` | 2 |
| `hooks/use-documents.ts` | 4 |
| `hooks/use-logs.ts` | 10 |
| `hooks/use-llm-configs.ts` | 1 |
| `hooks/use-search-space.ts` | 1 |
| `hooks/use-user.ts` | 1 |
| `hooks/use-chat.ts` | 1 |
| `hooks/use-api-key.ts` | 1 (⚠️ Special case) |
| `hooks/use-document-types.ts` | 1 |
| `hooks/use-document-by-chunk.ts` | 1 |
| `hooks/use-search-source-connectors.ts` | 5 |
| `hooks/use-connector-edit-page.ts` | 1 |

### App Page Files (9 files)
All page files follow the same pattern as hooks.

| File | Occurrences |
|------|-------------|
| `app/dashboard/site-settings/page.tsx` | 2 |
| `app/dashboard/security/page.tsx` | 1 |
| `app/dashboard/searchspaces/page.tsx` | 1 |
| `app/dashboard/[search_space_id]/onboard/page.tsx` | 1 |
| `app/dashboard/[search_space_id]/documents/webpage/page.tsx` | 1 |
| `app/dashboard/[search_space_id]/connectors/add/google-gmail-connector/page.tsx` | 1 |
| `app/dashboard/[search_space_id]/connectors/add/google-calendar-connector/page.tsx` | 1 |
| `app/dashboard/[search_space_id]/connectors/add/github-connector/page.tsx` | 1 |
| `app/dashboard/[search_space_id]/connectors/add/airtable-connector/page.tsx` | 1 |

### Atom Files (2 files)
| File | Lines | Change Needed |
|------|-------|---------------|
| `atoms/chats/chat-mutation.atoms.ts` | 12 | Remove token check, use server-side auth |
| `atoms/chats/chat-querie.atoms.ts` | 21, 46 | Remove token check, use server-side auth |

## ⚠️ Special Cases

### 1. `hooks/use-api-key.ts`
This hook currently treats the auth token as an API key for display.
- **Current**: `const token = localStorage.getItem(AUTH_TOKEN_KEY);`
- **Problem**: With HttpOnly cookies, client can't access the token
- **Solution**: Create a dedicated `/api/v1/user/api-key` endpoint that returns a display-only API key

### 2. OAuth Flow (TokenHandler.tsx)
- **Updated**: Now expects backend to handle OAuth callback and set cookies
- **Requires**: Backend OAuth endpoints must set HttpOnly cookies after token exchange
- **Backend Update Needed**: Modify OAuth callbacks to set cookies instead of returning tokens in URL

## 🔧 Migration Pattern (For Remaining Files)

### Before:
```typescript
import { AUTH_TOKEN_KEY } from "@/lib/constants";

const token = localStorage.getItem(AUTH_TOKEN_KEY);
const response = await fetch(url, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify(data),
});
```

### After:
```typescript
const response = await fetch(url, {
  method: "POST",
  credentials: 'include', // Send cookies
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify(data),
});
```

## 📋 Next Steps

1. **Complete Phase 2**: Update remaining 22 files following the pattern above
2. **Test Authentication Flow**: 
   - Login with 2FA
   - Verify dashboard access
   - Test API calls
   - Test logout
3. **Backend Verification**:
   - Confirm all endpoints accept cookie authentication
   - Verify CSRF protection is working
   - Test OAuth flows with new cookie-based approach
4. **Create PR**: Once all files updated and tested

## 🚀 Testing Checklist

- [ ] Login with email/password + 2FA
- [ ] Dashboard loads correctly
- [ ] All API calls work (search spaces, documents, etc.)
- [ ] Logout clears cookies and redirects
- [ ] Session expires correctly on 401
- [ ] OAuth connectors work (if applicable)
- [ ] No localStorage token references in console
- [ ] Production build succeeds

## 📝 Notes

- Backend already sets HttpOnly cookies (verified in `two_fa_routes.py:764`)
- Base API service already uses `credentials: 'include'` (verified in `base-api.service.ts:72`)
- CSRF protection is in place and working
- Most changes are mechanical find-and-replace operations
