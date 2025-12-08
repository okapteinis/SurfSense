/**
 * Authentication error handling utilities
 *
 * Provides structured error details for different authentication failures
 * with user-friendly messages and retry guidance.
 */

export interface AuthErrorDetails {
	title: string;
	description: string;
	shouldRetry: boolean;
}

/**
 * Get user-friendly error details for authentication error codes
 */
export function getAuthErrorDetails(errorCode: string): AuthErrorDetails {
	const errors: Record<string, AuthErrorDetails> = {
		'INVALID_2FA_CODE': {
			title: 'Invalid 2FA Code',
			description: 'The code you entered is incorrect. Please check your authenticator app and try again.',
			shouldRetry: true,
		},
		'EXPIRED_2FA_CODE': {
			title: '2FA Code Expired',
			description: 'This code has expired. Please enter a new code from your authenticator app.',
			shouldRetry: true,
		},
		'TEMPORARY_TOKEN_EXPIRED': {
			title: 'Session Expired',
			description: 'Your login session expired. Please log in again.',
			shouldRetry: false,
		},
		'LOGIN_BAD_CREDENTIALS': {
			title: 'Login Failed',
			description: 'Invalid email or password. Please try again.',
			shouldRetry: true,
		},
		'NETWORK_ERROR': {
			title: 'Connection Error',
			description: 'Unable to connect to the server. Please check your internet connection.',
			shouldRetry: true,
		},
		'SESSION_EXPIRED': {
			title: 'Session Expired',
			description: 'Your session has expired. Please log in again.',
			shouldRetry: false,
		},
		'CSRF_ERROR': {
			title: 'Security Validation Failed',
			description: 'Security validation failed. Please refresh the page and try again.',
			shouldRetry: true,
		},
		'RATE_LIMITED': {
			title: 'Too Many Attempts',
			description: 'Too many failed attempts. Please wait a few minutes before trying again.',
			shouldRetry: false,
		},
		'UNKNOWN_ERROR': {
			title: 'Login Failed',
			description: 'An unexpected error occurred. Please try again.',
			shouldRetry: true,
		},
	};

	return errors[errorCode] || errors['UNKNOWN_ERROR'];
}

/**
 * Check if an error code indicates a retryable error
 */
export function shouldRetry(errorCode: string): boolean {
	return getAuthErrorDetails(errorCode).shouldRetry;
}

/**
 * Check if an error is a network error (fetch failure)
 */
export function isNetworkError(error: unknown): boolean {
	return error instanceof TypeError && error.message.includes('fetch');
}

/**
 * Extract error code from API response
 */
export function extractErrorCode(response: Response, data?: any): string {
	if (response.status === 401) {
		return 'SESSION_EXPIRED';
	}
	if (response.status === 403) {
		if (data?.detail?.includes?.('CSRF')) {
			return 'CSRF_ERROR';
		}
		return 'INVALID_2FA_CODE';
	}
	if (response.status === 429) {
		return 'RATE_LIMITED';
	}
	if (data?.error_code) {
		return data.error_code;
	}
	return 'UNKNOWN_ERROR';
}
