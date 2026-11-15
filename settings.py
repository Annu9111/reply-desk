import os


class StartupError(Exception):
    """The app refuses to start: the message lists every problem."""


def _is_true(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def config_problems(env: dict) -> list:
    """Return every problem with this environment ([] = fine).
    Messages name the variable and never include a secret's value."""
    problems = []

    app_env = env.get("APP_ENV", "development")
    if app_env not in ("development", "production"):
        problems.append("APP_ENV must be 'development' or 'production'")

    # Demo mode (default) uses a scripted fake model, so no API key is needed.
    demo_mode = _is_true(env.get("DEMO_MODE", "true"))
    if not demo_mode:
        key = env.get("ANTHROPIC_API_KEY")
        if key is None or not key.strip():
            problems.append("ANTHROPIC_API_KEY must be set when DEMO_MODE is off")

    if app_env == "production":
        if _is_true(env.get("DEBUG", "")):
            problems.append("DEBUG must be off in production")

        origins = env.get("ALLOWED_ORIGINS")
        if origins is None or not origins.strip():
            problems.append("ALLOWED_ORIGINS must be set in production")
        elif "*" in origins:
            problems.append("ALLOWED_ORIGINS must not contain * in production")

    return problems


def start(env: dict = None) -> dict:
    """Check the environment and return the settings, or refuse to start."""
    env = os.environ if env is None else env
    app_env = env.get("APP_ENV", "development")
    problems = config_problems(env)

    if problems and app_env != "development":
        raise StartupError("; ".join(problems))

    return {
        "env": app_env,
        "debug": _is_true(env.get("DEBUG", "")),
        "demo_mode": _is_true(env.get("DEMO_MODE", "true")),
        "warnings": problems,
    }