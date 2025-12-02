/**
 * Authentication utility functions for session management
 * SECURITY: Uses HttpOnly cookies for authentication - no localStorage tokens
 */

/**
 * Handle session expiration by redirecting to login
 * SECURITY: With HttpOnly cookies, no client-side token management needed
 * The browser automatically handles cookie cleanup
 */
export function handleSessionExpired(): never {
	// Redirect to login with error parameter for user feedback
	window.location.href = "/login?error=session_expired";

	// Throw to stop further execution (this line won't actually run due to redirect)
	throw new Error("Session expired: Redirecting to login page");
}

/**
 * Check if a response indicates an authentication error
 * @param response - The fetch Response object
 * @returns True if the response status is 401
 */
export function isUnauthorizedResponse(response: Response): boolean {
	return response.status === 401;
}

/**
 * Handle API response with automatic session expiration handling
 * @param response - The fetch Response object
 * @throws Error if response is 401 (after handling session expiration)
 */
export function handleAuthResponse(response: Response): void {
	if (isUnauthorizedResponse(response)) {
		handleSessionExpired();
	}
}
