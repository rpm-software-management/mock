The `traceLog()` decorator, which tracks when internal methods are entered and
exited, has been disabled.  **Warning:** We plan to remove this decorator
entirely; please follow [issue#1681][] for updates.  In the meantime, you can
export the `MOCK_TRACE_LOG=true` environment variable to revert this change and
re-enable the logging.
