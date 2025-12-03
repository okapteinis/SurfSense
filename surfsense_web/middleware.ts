// Middleware with proper static asset exclusion
// Ensures authentication logic never intercepts Next.js static files

import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
	const path = request.nextUrl.pathname;

	// Explicitly exclude static files and Next.js internals
	// This prevents any authentication logic from interfering with asset loading
	if (
		path.startsWith('/_next/static') ||
		path.startsWith('/_next/image') ||
		path.startsWith('/_next/webpack-hmr') ||
		path.startsWith('/api') ||
		path.startsWith('/favicon.ico') ||
		path.startsWith('/public') ||
		// Exclude all files with extensions (images, fonts, etc.)
		/\\.(.+)$/.test(path)
	) {
		return NextResponse.next();
	}

	// Pass through all other requests
	return NextResponse.next();
}

// Configure matcher to exclude static assets at the routing level
// This provides an additional layer of protection
export const config = {
	matcher: [
		/*
		 * Match all request paths except:
		 * - _next/static (static files)
		 * - _next/image (image optimization files)
		 * - _next/webpack-hmr (hot module replacement)
		 * - favicon.ico (favicon file)
		 * - public folder files
		 * - files with extensions (images, fonts, etc.)
		 */
		'/((?!_next/static|_next/image|_next/webpack-hmr|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff|woff2|ttf|eot|css|js|map)$).*)',
	],
};
