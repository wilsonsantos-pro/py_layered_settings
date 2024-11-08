# Welcome to Layered Settings

This project implements "layered settings" in Python using SQLAlchemy.

"Layered settings" means that it is possible to create an hierarchy of settings.
When looking for a specific setting, the search first starts at the lowest layer,
continuing on the upper level, until it is found.

This library tries to keep it as generic as possible. So:

- It's up to the application using this library to define the existing layer and their
  hierarchy.
- It's also up to the application to establish the `Entity --> Parent` relationships,
  which will determine the success of finding a "default" value.
- In order to find a setting, the full parent hierarchy must be provided. If a parent
  does not exist for a upper layer, just use `None`. It is intended to keep the layered
  settings ignorant about the `Entity --> Parent` relationships, because that's heavily
  dependent on the application's domain.
- It's also up to the application to create the last "default" layer (`entity_id==None`).
  If a default layer is not defined, then the result will be just `None`.

```mermaid
classDiagram
Layer *-- LayeredSetting: layer_id
Layer o-- Layer: fallback_id
Layer: int id
LayeredSetting: int id
LayeredSetting: str name
LayeredSetting: str value
LayeredSetting: int layer_id
LayeredSetting: Optional[int] entity_id
LayeredSetting: get_setting() LayeredSetting
```

## Example

Let's find a setting for in the "User" layer. If not found there, it will continue
the search in the "Group" layer, then in the "Account" and finally in the "Default"
layer.

```mermaid
graph TD
    User --> Group
    User --> Account
    User --> System
    Group --> Account
    Group --> System
    Account --> System
```

## Commands

- `make dev_env` - Setup the development setup.
- `make test` - Run the tests.
- `make test-monitor` - Run the tests in "monitor mode". When changes are detected the
  tests run automatically.
- `make format` - Format the code.
- `make lint` - Run code linters.
- `make docs` - Build the documentation.
- `make docs-serve` - Build the documentation and serve them.

## Project layout

    mkdocs.yml    # The configuration file.
    docs/
        index.md  # The documentation homepage.
        ...       # Other markdown pages, images and other files.
    src/          # source code
    tests/        # unit tests
