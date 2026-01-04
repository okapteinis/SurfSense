import { describe, it, expect, vi } from 'vitest';
import { cn, getChatTitleFromMessages, getErrorMessageFromResponse } from './utils';

describe('utils', () => {
  describe('cn', () => {
    it('merges tailwind classes correctly', () => {
      expect(cn('btn', 'btn-primary')).toBe('btn btn-primary');
      expect(cn('px-2 py-2', 'p-4')).toBe('p-4'); // p-4 should override px-2 py-2 in twMerge
    });
  });

  describe('getChatTitleFromMessages', () => {
    it('returns "Untitled Chat" when no user messages exist', () => {
      const messages = [
        { id: '1', role: 'assistant' as const, content: 'Hello' }
      ];
      expect(getChatTitleFromMessages(messages)).toBe('Untitled Chat');
    });

    it('returns the content of the first user message', () => {
      const messages = [
        { id: '1', role: 'assistant' as const, content: 'Hello' },
        { id: '2', role: 'user' as const, content: 'How are you?' },
        { id: '3', role: 'user' as const, content: 'Tell me a joke' }
      ];
      expect(getChatTitleFromMessages(messages)).toBe('How are you?');
    });
  });

  describe('getErrorMessageFromResponse', () => {
    it('extracts detail from JSON response', async () => {
      const mockResponse = {
        status: 400,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Specific error message' }),
      } as Response;

      const message = await getErrorMessageFromResponse(mockResponse);
      expect(message).toBe('Specific error message');
    });

    it('returns default message if JSON detail is missing', async () => {
      const mockResponse = {
        status: 400,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      } as Response;

      const message = await getErrorMessageFromResponse(mockResponse, 'Default Error');
      expect(message).toBe('Default Error');
    });

    it('returns status text for non-JSON responses', async () => {
      const mockResponse = {
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Headers({ 'content-type': 'text/plain' }),
      } as unknown as Response;

      const message = await getErrorMessageFromResponse(mockResponse, 'Failed');
      expect(message).toBe('Failed (Status: 500)');
    });

    it('handles network/parse errors gracefully', async () => {
      const mockResponse = {
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => { throw new Error('Parse error'); },
      } as Response;

      const message = await getErrorMessageFromResponse(mockResponse, 'Fallback');
      expect(message).toBe('Fallback');
    });
  });
});
