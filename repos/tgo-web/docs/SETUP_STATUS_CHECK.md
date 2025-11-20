# Setup Status Check Implementation

## Overview

This document describes the implementation of the installation status check mechanism that ensures users cannot access the main application until the system setup is completed.

## Architecture

### Components

1. **Setup Store** (`src/stores/setupStore.ts`)
   - Manages the installation status state
   - Provides `checkSetupStatus()` action to call the API
   - Stores the result: `isInstalled`, `hasAdmin`, `hasLLMConfig`, etc.

2. **Root Layout** (`src/components/layout/RootLayout.tsx`)
   - Root component rendered by React Router
   - Wraps all routes using `<Outlet />`
   - Checks installation status on app startup
   - Redirects to `/setup` if installation is not complete
   - Shows loading/error screens during the check
   - Has access to React Router hooks (useNavigate, useLocation)

3. **Setup API Service** (`src/services/setupApi.ts`)
   - Already existed, provides `getStatus()` method
   - Calls `GET /v1/setup/status` endpoint

## Flow Diagram

```
App Startup
    ↓
RouterProvider renders RootLayout
    ↓
RootLayout Component Mounts
    ↓
Check if isInstalled === null (not checked yet)
    ↓
Call setupStore.checkSetupStatus()
    ↓
API: GET /v1/setup/status
    ↓
┌─────────────────────────────────────┐
│  Response: { is_installed: bool }  │
└─────────────────────────────────────┘
    ↓
┌─────────────────┬──────────────────┐
│  is_installed   │  is_installed    │
│  === true       │  === false       │
└─────────────────┴──────────────────┘
    ↓                    ↓
Render <Outlet />  Redirect to /setup
    ↓
Child Routes Render
```

## Implementation Details

### 1. Setup Store

**File**: `src/stores/setupStore.ts`

**State**:
- `isInstalled: boolean | null` - null means not checked yet
- `hasAdmin: boolean` - whether admin account exists
- `hasLLMConfig: boolean` - whether LLM is configured
- `setupCompletedAt: string | null` - timestamp of setup completion
- `isChecking: boolean` - loading state
- `checkError: string | null` - error message if check fails

**Actions**:
- `checkSetupStatus()` - Calls API and updates state
- `resetSetupState()` - Resets state (for testing)

### 2. Root Layout

**File**: `src/components/layout/RootLayout.tsx`

**Behavior**:
1. Rendered as the root element by React Router
2. On mount, checks if `isInstalled === null` (not checked yet)
3. If not checked, calls `checkSetupStatus()`
4. Shows loading screen while checking
5. If check fails, shows error screen with retry button
6. If `isInstalled === false`, redirects to `/setup` using `useNavigate()`
7. If `isInstalled === true`, renders `<Outlet />` (child routes)
8. Always allows access to `/setup` route itself

**Loading Screen**:
- Displays spinner and "Checking system status..." message
- Uses i18n translations

**Error Screen**:
- Displays error icon and message
- Shows the actual error from API
- Provides "Retry" button to reload the page

**Why RootLayout instead of a wrapper component?**:
- React Router hooks (`useNavigate`, `useLocation`) can only be used inside components rendered by the router
- RootLayout is rendered by `RouterProvider`, so it has access to the router context
- It uses `<Outlet />` to render child routes after the setup check passes

### 3. Router Integration

**File**: `src/router/index.tsx`

The router configuration has RootLayout as the root element:

```tsx
export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { path: 'setup', element: <SetupWizard /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      {
        path: '/',
        element: <ProtectedRoute><Layout /></ProtectedRoute>,
        children: [/* app routes */]
      }
    ]
  }
]);
```

### 4. App Integration

**File**: `src/App.tsx`

The App component simply renders the RouterProvider:

```tsx
<ToastContainer>
  <WebSocketManager />
  <RouterProvider router={router} />
</ToastContainer>
```

### 5. Setup Wizard Integration

**File**: `src/pages/SetupWizard.tsx`

After successful installation, the wizard:
1. Calls `checkSetupStatus()` to refresh the global state
2. Redirects to `/login` page
3. The RootLayout will now allow access since `isInstalled === true`

## API Contract

### Endpoint: `GET /v1/setup/status`

**Response**:
```json
{
  "is_installed": boolean,
  "has_admin": boolean,
  "has_llm_config": boolean,
  "setup_completed_at": string | null
}
```

## Error Handling

### Network Errors
- If the API call fails (network error, server down, etc.)
- SetupGuard shows an error screen
- User can click "Retry" to reload the page
- The check will run again on page reload

### API Errors
- If the API returns an error response (4xx, 5xx)
- The error is caught and stored in `checkError`
- Error screen is displayed with the error message

## Internationalization

All user-facing messages support i18n:

**Chinese** (`src/i18n/locales/zh.json`):
```json
{
  "setup": {
    "guard": {
      "checking": "正在检查系统状态...",
      "serverError": "无法连接到服务器",
      "retryButton": "重试"
    }
  }
}
```

**English** (`src/i18n/locales/en.json`):
```json
{
  "setup": {
    "guard": {
      "checking": "Checking system status...",
      "serverError": "Unable to Connect to Server",
      "retryButton": "Retry"
    }
  }
}
```

## Testing

### Manual Testing

1. **Fresh Installation**:
   - Start the app with no setup completed
   - Should redirect to `/setup`
   - Complete the setup wizard
   - Should redirect to `/login`
   - Try accessing `/chat` - should work after login

2. **Already Installed**:
   - Start the app with setup already completed
   - Should show loading screen briefly
   - Should allow normal access to the app

3. **Server Down**:
   - Stop the backend server
   - Start the app
   - Should show error screen
   - Click "Retry" - should try again

### Programmatic Testing

You can test the setup store in the browser console:

```javascript
// Get the setup store
const setupStore = window.__ZUSTAND_STORES__?.setupStore || 
                   (await import('./stores/setupStore')).useSetupStore;

// Check current status
setupStore.getState();

// Manually trigger a check
await setupStore.getState().checkSetupStatus();

// Reset state (for testing)
setupStore.getState().resetSetupState();
```

## Security Considerations

1. **No Authentication Required**: The `/v1/setup/status` endpoint should NOT require authentication, as it needs to be called before login.

2. **Read-Only**: The status check is read-only and doesn't modify any data.

3. **No Sensitive Data**: The response doesn't contain sensitive information, just boolean flags.

4. **Setup Page Access**: The `/setup` route is always accessible, even when installation is complete. The backend should handle preventing duplicate installations.

## Future Enhancements

1. **Caching**: Cache the setup status in localStorage to avoid unnecessary API calls on every page load.

2. **Polling**: If the setup is in progress, poll the status endpoint periodically.

3. **Progress Tracking**: Show detailed progress of the setup process (e.g., "Creating database...", "Configuring LLM...").

4. **Setup Wizard State**: Persist the wizard state so users can resume if they close the browser mid-setup.

