"""Canonical ASGI app and installed server command; imports have no store effects."""

from .application import create_app

app = create_app()


def main():
    import uvicorn
    uvicorn.run("server_application.backend.main:app", host="0.0.0.0", port=8005)


if __name__ == "__main__":
    main()
