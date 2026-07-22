"""HTTP API package for Risk-HiMATE."""


def create_app():
    from risk_himate.app.api.server import create_app as _create_app

    return _create_app()


__all__ = ["create_app"]
