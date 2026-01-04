# Testing in SurfSense

This document outlines the testing philosophy and procedures for the SurfSense project.

## Frontend Testing (surfsense_web)

We use **Vitest** and **React Testing Library** for frontend testing. API calls are mocked using **Mock Service Worker (MSW)**.

### Running Tests

```bash
cd surfsense_web
pnpm run test          # Run tests once
pnpm run test:watch    # Run tests in watch mode
pnpm run test:coverage # Run tests and generate coverage report
```

### Coverage Thresholds

We aim for at least **80%** coverage on critical files (logic and shared components).

### Mocking API Calls

All API handlers should be added to `surfsense_web/tests/mocks/handlers.ts`. This ensures consistent mocking across all tests.

Example handler:
```typescript
http.get(`${baseUrl}/api/v1/some-endpoint`, () => {
  return HttpResponse.json({ data: 'mocked' });
})
```

### Component Testing Patterns

Use `render` from `@testing-library/react` and `screen` for assertions.

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { MyComponent } from './MyComponent';

it('should do something', () => {
  render(<MyComponent />);
  expect(screen.getByText('Hello')).toBeInTheDocument();
});
```

## Backend Testing (surfsense_backend)

Backend tests are located in `surfsense_backend/tests` and use **pytest**.

```bash
cd surfsense_backend
pytest
```
