"""python -m kaltstart.api [--dev] [--port 8000]

--dev runs the whole app on this machine with invented companies and fake
accounts (invitation code "dev"), without any key or database."""

import argparse
import secrets
import sys
from datetime import datetime, timezone


def _uvicorn(app, host: str, port: int) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


def main(argv: list[str], *, serve=_uvicorn) -> int:
    parser = argparse.ArgumentParser(prog="python -m kaltstart.api")
    parser.add_argument("--dev", action="store_true", help="invented data, fake accounts")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    host = "127.0.0.1" if args.dev else "0.0.0.0"
    try:
        if args.dev:
            from kaltstart.api.app import create_app
            from kaltstart.api.auth import FakeAuth
            from kaltstart.api.seed import seeded_store
            app = create_app(seeded_store(datetime.now(timezone.utc)), FakeAuth(),
                             session_secret=secrets.token_urlsafe(32),
                             removal_contact="removal@example.com")
            print(f"Kaltstart (dev): http://{host}:{args.port}  ·  invitation code: dev  ·  "
                  "invented data, nothing is saved")
        else:
            from kaltstart.api.app import app_from_env
            app = app_from_env()
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    serve(app, host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
