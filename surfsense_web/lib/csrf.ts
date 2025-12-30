/**
 * CSRF (Cross-Site Request Forgery) protection utilities
 *
 * This module provides functions to fetch and manage CSRF tokens for API requests.
 */

import { useState, useEffect, useCallback } from 'react';

const CSRF_TOKEN_KEY = 'csrf_token';
const CSRF_TOKEN_EXPIRY_KEY = 'csrf_token_expiry';
const TOKEN_VALIDITY_MINUTES = 30;

interface CsrfTokenResponse {
	csrf_token: string;
	message: string;
	usage: {
		header_name: string;
		methods_requiring_token: string[];
		cookie_name: string;
	};
}

/**
 * Fetch a new CSRF token from the backend
 *
 * @returns Promise resolving to the CSRF token string
 * @throws Error if token fetch fails
 */
export async function fetchCsrfToken(): Promise<string> {
	try {
		const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || '';
		const response = await fetch(`${backendUrl}/api/csrf-token`, {
			method: 'GET',
			credentials: 'include', // Important: include cookies
		});

		if (!response.ok) {
			throw new Error(`Failed to fetch CSRF token: ${response.statusText}`);
		}

		const data: CsrfTokenResponse = await response.json();

		// Store token and expiry in sessionStorage
		const expiryTime = Date.now() + TOKEN_VALIDITY_MINUTES * 60 * 1000;
		sessionStorage.setItem(CSRF_TOKEN_KEY, data.csrf_token);
		sessionStorage.setItem(CSRF_TOKEN_EXPIRY_KEY, expiryTime.toString());

		return data.csrf_token;
	} catch (error) {
		console.error('CSRF token fetch error:', error);
		throw error;
	}
}

/**
 * Get a valid CSRF token, fetching a new one if necessary
 *
 * This function checks for a cached token and validates its expiry
 * before returning it. If the token is expired or missing, it fetches
 * a new one automatically.
 *
 * @returns Promise resolving to the CSRF token string
 */
export async function getCsrfToken(): Promise<string> {
	const cachedToken = sessionStorage.getItem(CSRF_TOKEN_KEY);
	const expiryTime = sessionStorage.getItem(CSRF_TOKEN_EXPIRY_KEY);

	// Check if we have a valid cached token
	if (cachedToken && expiryTime) {
		const expiry = parseInt(expiryTime, 10);
		if (Date.now() < expiry) {
			return cachedToken;
		}
	}

	// Token is missing or expired, fetch a new one
	return fetchCsrfToken();
}

/**
 * Clear the stored CSRF token
 *
 * Useful when logging out or when a CSRF error occurs
 */
export function clearCsrfToken(): void {
	sessionStorage.removeItem(CSRF_TOKEN_KEY);
	sessionStorage.removeItem(CSRF_TOKEN_EXPIRY_KEY);
}

/**
 * Create headers object with CSRF token included
 *
 * @param additionalHeaders - Additional headers to merge
 * @returns Promise resolving to headers object with CSRF token
 */
export async function withCsrfHeaders(
	additionalHeaders: Record<string, string> = {}
): Promise<Record<string, string>> {
	const token = await getCsrfToken();

	return {
		'X-CSRF-Token': token,
		...additionalHeaders,
	};
}

/**
 * Wrapper for fetch with automatic CSRF token injection
 *
 * This function automatically includes the CSRF token for state-changing
 * requests (POST, PUT, DELETE, PATCH).
 *
 * @param url - The URL to fetch
 * @param options - Standard fetch options
 * @returns Promise resolving to the fetch Response
 *
 * @example
 * ```typescript
 * // Automatic CSRF token injection for POST
 * const response = await csrfFetch('/api/documents', {
 *   method: 'POST',
 *   body: JSON.stringify(data),
 * });
 * ```
 */
export async function csrfFetch(
	url: string,
	options: RequestInit = {},
	_isRetry: boolean = false
): Promise<Response> {
	const method = options.method?.toUpperCase() || 'GET';
	const requiresCsrf = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method);

	if (requiresCsrf) {
		const token = await getCsrfToken();

		// Merge CSRF header with existing headers
		const headers = new Headers(options.headers);
		headers.set('X-CSRF-Token', token);

		// Ensure credentials are included for cookies
		options.headers = headers;
		options.credentials = options.credentials || 'include';
	}

	const response = await fetch(url, options);

	// If we get a CSRF error (403), clear the token and retry once
	if (response.status === 403 && !_isRetry) {
		try {
			const errorData = await response.clone().json();
			if (errorData.error === 'CSRF validation failed') {
				// Clear the old token
				clearCsrfToken();

				// Fetch a new token and retry the request once
				console.log('CSRF validation failed, retrying with new token...');
				return await csrfFetch(url, options, true);
			}
		} catch {
			// Ignore JSON parse errors - return original response
		}
	}

	return response;
}

/**
 * React hook for CSRF token management
 *
 * @returns Object with token and utility functions
 *
 * @example
 * ```typescript
 * function MyComponent() {
 *   const { token, refreshToken, isLoading, error } = useCsrfToken();
 *
 *   if (isLoading) return <div>Loading...</div>;
 *   if (error) return <div>Error: {error}</div>;
 *
 *   return <div>CSRF Token: {token}</div>;
 * }
 * ```
 */
export function useCsrfToken() {
	const [token, setToken] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const refreshToken = useCallback(async () => {
		setIsLoading(true);
		setError(null);

		try {
			const newToken = await fetchCsrfToken();
			setToken(newToken);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Unknown error');
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		refreshToken();
	}, [refreshToken]);

	return {
		token,
		refreshToken,
		isLoading,
		error,
		clearToken: clearCsrfToken,
	};
}
