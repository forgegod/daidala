"""List packaged text resources using the legacy functional API."""

from importlib.resources import contents


def resource_names() -> tuple[str, ...]:
    return tuple(
        sorted(
            name
            for name in contents("resource_fixture.data")
            if name.endswith(".txt")
        )
    )
