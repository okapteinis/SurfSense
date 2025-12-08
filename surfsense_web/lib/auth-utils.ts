/**
 * Authentication utility functions for session management
 *
 * SECURITY NOTE: This module uses HttpOnly cookies for authentication.
 * Tokens are NOT stored in localStorage to prevent XSS attacks.
 */

/**
 * Handle session expiration by redirecting to login
 */
export function handleSessionExpired(): never {
	// Redirect to login with error parameter for user feedback
	window.location.href = "/login?error=session_expired";

	// Throw to stop further execution
	throw new Error("Session expired: Redirecting to login page");
}

/**
 * Check if a response indicates an authentication error
 */
export function isUnauthorizedResponse(response: Response): boolean {
	return response.status === 401;
}

/**
 * Handle API response with automatic session expiration handling
 */
export function handleAuthResponse(response: Response): void {
	if (isUnauthorizedResponse(response)) {
		handleSessionExpired();
	}
}

/**
 * Wrapper around fetch that automatically includes credentials (cookies)
 * and handles 401 responses by redirecting to login
 *
 * SECURITY: Uses HttpOnly cookies for authentication instead of Bearer tokens.
 * Cookies are automatically sent by the browser via credentials: 'include'.
 */
export async function authenticatedFetch(
	url: string,
	options?: RequestInit
): Promise<Response> {
	const response = await fetch(url, {
		...options,
		credentials: 'include', // Always send cookies
		headers: {
			'Content-Type': 'application/json',
			...options?.headers,
		},
	});

	// Handle 401 Unauthorized
	if (response.status === 401) {
		handleSessionExpired();
	}

	return response;
}
