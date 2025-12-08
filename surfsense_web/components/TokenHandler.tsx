"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

interface TokenHandlerProps {
	redirectPath?: string; // Path to redirect after authentication
}

/**
 * Client component for OAuth callback handling
 *
 * IMPORTANT: With HttpOnly cookie authentication, OAuth providers should:
 * 1. Send the authorization code to the backend
 * 2. Backend exchanges code for token and sets HttpOnly cookie
 * 3. Backend redirects to this page with success=true parameter
 *
 * This component no longer handles tokens directly in the URL.
 * If you see tokens in the URL, update your OAuth callback to go to the backend first.
 *
 * @param redirectPath - Path to redirect after successful auth (default: '/dashboard')
 */
const TokenHandler = ({
	redirectPath = "/dashboard",
}: TokenHandlerProps) => {
	const router = useRouter();
	const searchParams = useSearchParams();

	useEffect(() => {
		// Only run on client-side
		if (typeof window === "undefined") return;

		// Check if authentication was successful (set by backend redirect)
		const success = searchParams.get("success");
		const error = searchParams.get("error");

		if (error) {
			// Authentication failed
			console.error("OAuth authentication failed:", error);
			router.push(`/login?error=${error}`);
		} else if (success === "true") {
			// Authentication successful, cookie already set by backend
			router.push(redirectPath);
		} else {
			// No success or error parameter, redirect to login
			router.push("/login");
		}
	}, [searchParams, redirectPath, router]);

	return (
		<div className="flex items-center justify-center min-h-[200px]">
			<p className="text-gray-500">Processing authentication...</p>
		</div>
	);
};

export default TokenHandler;
