// Middleware with proper static asset exclusion
// Ensures authentication logic never intercepts Next.js static files

import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
	// All exclusion logic is handled by the matcher
	// This ensures a single source of truth for routing decisions
	return NextResponse.next();
}

// Configure matcher to exclude static assets at the routing level
export const config = {
	matcher: [
		/*
		 * Match all request paths except:
		 * - api routes
		 * - _next/static (static files)
		 * - _next/image (image optimization files)
		 * - _next/webpack-hmr (hot module replacement)
		 * - favicon.ico (favicon file)
		 * - files with extensions (images, fonts, etc.)
		 * Note: Files in /public are served at root and covered by extension matching
		 */
		'/((?!api|_next/static|_next/image|_next/webpack-hmr|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff|woff2|ttf|eot|css|js|map)$).*)',
	],
};
