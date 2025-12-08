/**
 * Application-wide constants
 */

/**
 * @deprecated This key is no longer used for authentication.
 * Authentication now uses HttpOnly cookies for security.
 * DO NOT use this for new auth-related code.
 * Only kept for backward compatibility during migration.
 */
export const AUTH_TOKEN_KEY = "surfsense_bearer_token";

/**
 * Default site configuration values
 * Used in SiteConfigContext and site-settings page
 * Can be overridden via environment variables
 */
export const DEFAULT_CONTACT_EMAIL = process.env.NEXT_PUBLIC_DEFAULT_CONTACT_EMAIL || "support@example.com";

/**
 * Default copyright text with dynamic year
 */
export const DEFAULT_COPYRIGHT_TEXT = `SurfSense ${new Date().getFullYear()}`;
