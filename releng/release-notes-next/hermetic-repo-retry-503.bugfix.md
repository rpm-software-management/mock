The `mock-hermetic-repo` tool now retries HTTP 503 (Service Unavailable)
responses with exponential backoff, matching the existing retry handling for
other transient HTTP errors.  Previously, a single 503 from an upstream
repository (e.g. S3 throttling) would cause the entire RPM download to fail
([PR#1769][]).
