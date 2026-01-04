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
 */
export async function getErrorMessageFromResponse(
	response: Response,
	defaultMessage = "An unexpected error occurred"
): Promise<string> {
	try {
		const contentType = response.headers.get("content-type");
		
		if (contentType && contentType.includes("application/json")) {
			const errorData = await response.json();
			return errorData.detail || defaultMessage;
		}
		
		return `${defaultMessage} (Status: ${response.status})`;
	} catch (error) {
		return defaultMessage;
	}
}
