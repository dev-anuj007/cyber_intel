# How We Build

## Development philosophy

This project is organized around a simple development loop:

1. define a behavior with tests or a clear API contract
2. implement the domain logic in the relevant service module
3. validate through pytest and smoke tests
4. verify the frontend behavior against the API
5. iterate quickly with local configuration and small, focused changes

This is a practical app-development workflow.

## Service-oriented structure

Each major domain has a dedicated package under ackend/src/services:

- ccounts for account search and detail logic
- uth for JWT and user profile flows
- scorer for Gemini-based account scoring
- crawler for scan jobs and crawler tasks
- eval for benchmarking and comparison runs
- prompts for dynamic template versioning
- jobs for async state management
- database for Postgres health and schema helpers

This separation makes it easier to evolve features without mixing account logic with auth logic or scoring logic with database setup.

## Test-first workflow

The repository includes service tests under each package. The usual pattern is:

- write or update a failing test for a behavior
- implement the smallest code change to satisfy it
- run the targeted pytest file or the service test suite
- verify the API response shape and frontend behavior

This keeps the product stable as new prompt versions and data models are introduced.

## Local verification flow

`ash
cd backend
pytest
`

Then run the app and verify by hand:

`ash
python src/main.py
`

And in the frontend:

`ash
cd frontend
npm run dev
`

The most important validation is end-to-end behavior across the app: login, query accounts, inspect detail pages, and run scoring or evaluation actions when a Gemini key is available.

## Practical engineering guidance

- Keep service APIs small and explicit
- Prefer typed request/response models and shared config values
- Keep Postgres configuration central in ackend/src/core/config.py
- Treat SQLite as a test-only compatibility path, not a production storage model
- Maintain the frontend using the same route semantics as the API, especially when dealing with JWT-bearing requests

## Why this matters

The project benefits from a straightforward architecture: one backend, one frontend, one primary relational database, and targeted external AI calls. That keeps the runtime easier to reason about and makes debugging, testing, and feature work more reliable.
