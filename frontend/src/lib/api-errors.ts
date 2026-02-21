export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

/**
 * Maps raw backend detail strings to friendlier user-facing messages.
 * Only needed when the backend message is too terse or technical.
 */
const FRIENDLY_MESSAGES: Record<string, string> = {
  "An account with this email already exists.":
    "This email is already registered. Try logging in instead.",
  "Invalid email or password.":
    "Incorrect email or password. Please try again.",
};

/**
 * Extracts a clean, user-facing error message from a caught error.
 */
export function parseApiError(error: unknown): string {
  if (error instanceof ApiError) {
    return FRIENDLY_MESSAGES[error.detail] ?? error.detail;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}
