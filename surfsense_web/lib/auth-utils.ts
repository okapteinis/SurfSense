/**
 * Authentication utility functions for session management
 */

import { AUTH_TOKEN_KEY } from "./constants";

/**
 * Handle session expiration by redirecting to login
 * Clears the authentication token and redirects the user to the login page
 */
export function handleSessionExpired(): never {
	// Clear the token
	if (typeof window !== "undefined") {
		localStorage.removeItem(AUTH_TOKEN_KEY);
	}

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

/**
 * Wrapper around fetch that automatically includes authentication headers
 * and handles 401 responses by redirecting to login
 *
 * @param url - The URL to fetch
 * @param options - Standard fetch options
 * @returns The fetch Response
 * @throws Error if unauthorized (after handling session expiration)
 */
export async function authenticatedFetch(
	url: string,
	options?: RequestInit
): Promise<Response> {
	const token = typeof window !== "undefined" ? localStorage.getItem(AUTH_TOKEN_KEY) : null;

	const headers = new Headers(options?.headers || {});
	if (token) {
		headers.set("Authorization", `Bearer ${token}`);
	}

	const response = await fetch(url, {
		...options,
		headers,
	});

	// Handle 401 Unauthorized
	if (response.status === 401) {
		handleSessionExpired();
	}

	return response;
}
