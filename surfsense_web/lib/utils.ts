import type { Message } from "@ai-sdk/react";
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

export function getChatTitleFromMessages(messages: Message[]) {
	const userMessages = messages.filter((msg) => msg.role === "user");
	if (userMessages.length === 0) return "Untitled Chat";
	return userMessages[0].content;
}

/**
 * Extracts a meaningful error message from a fetch Response.
 * Handles JSON error responses (expecting 'detail' field) and falls back
 * to status text for non-JSON responses.
 * Now handles parsing errors and ensures a fallback string is always returned.
 */
export async function getErrorMessageFromResponse(
	response: Response,
	defaultMessage = "An unexpected error occurred"
): Promise<string> {
	try {
		const contentType = response.headers.get("content-type");
		
		if (contentType && contentType.includes("application/json")) {
			try {
				const errorData = await response.json();
				// Check for common error fields: 'detail', 'message', 'error'
				return errorData.detail || errorData.message || errorData.error || defaultMessage;
			} catch (jsonError) {
				// Failed to parse JSON, fall back to status text
				console.warn("Failed to parse error JSON:", jsonError);
			}
		}
		
		if (response.statusText) {
			return `${defaultMessage} (Status: ${response.status} ${response.statusText})`;
		}
		return `${defaultMessage} (Status: ${response.status})`;
	} catch (error) {
		console.error("Error extracting message from response:", error);
		return defaultMessage;
	}
}

/**
 * Wrapper for fetch with configurable timeout.
 * @param url Request URL
 * @param options Fetch options
 * @param timeoutMs Timeout in milliseconds (default 30000)
 */
export async function fetchWithTimeout(
	url: string,
	options: RequestInit = {},
	timeoutMs = 30000
): Promise<Response> {
	const controller = new AbortController();
	const id = setTimeout(() => controller.abort(), timeoutMs);
	
	try {
		const response = await fetch(url, {
			...options,
			signal: controller.signal,
		});
		clearTimeout(id);
		return response;
	} catch (error: any) {
		clearTimeout(id);
		if (error.name === 'AbortError') {
			throw new Error(`Request timed out after ${timeoutMs}ms`);
		}
		throw error;
	}
}