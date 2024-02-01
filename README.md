# Steerage

Pluggable async storage backends for Python projects.

This project implements the [Repository Pattern][repository] for data
access, using Pydantic 2.0 models for entity composition and
decomposition.

[repository]: https://martinfowler.com/eaaCatalog/repository.html


## Features

- One model, many possible storage backends: Start simple and add complexity as
  you need it.
- Use a fast, ephemeral in-memory database for tests, and a slow, reliable SQL
  database for production.
- One unified query interface: write most queries once, apply them to any
  backend.
- Simple environment-based configuration with [Convoke][convoke]
- 100% test coverage

[convoke]: https://eykd.github.io/convoke/latest/


## Installation

With Pip:

    pip install steerage


## Example

Let's create a simple blog engine. First, we'll want a Pydantic entity model:

``` python
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic.types import AwareDatetime

class Entry(BaseModel):
    id: UUID
    path: str
    title: str
    body: str

    created_at: AwareDatetime = Field(
        default_factory=lambda: datetime.utcnow().replace(tzinfo=timezone.utc)
    )
    published_at: AwareDatetime | None = Field(default=None)
```

Models are all fine and good, but we need to be able to store it
somewhere. Let's start simple, with an in-memory repository and a repository
factory:

``` python
from steerage.repositories.memdb import AbstractInMemoryRepository


class InMemoryEntryRepository(AbstractInMemoryRepository):
    table_name: str = "entries"
    entity_class = Entry


def get_entry_repository():
    return InMemoryEntityRepository()
```

Now, in the async request handler, we can easily create an entry:

``` python
async def create_entry(request: Request):
    form = await EntryForm.from_request(request)
    if form.is_valid():
        repo = get_entry_repository()
        entry = Entry.model_validate(form)
        await repo.insert(entry)
        return redirect('entry-admin')
```

... and retrieve an entry:

``` python
async def get_entry(request: Request, id: UUID):
    repo = get_entry_repository()
    entry = await repo.get(id)
    return render('entry.html', {'entry': entry})
```

This is great, but whenever we restart the server, we lose all our data!

Let's go a step up and add a more durable disk-based repository:

``` python
from convoke.configs import BaseConfig
from steerage.repositories.shelvedb import ShelveInMemoryRepository


class ShelveEntryRepository(AbstractShelveRepository):
    table_name: str = "entries"
    entity_class = Entry


def get_entry_repository():
    config = BaseConfig()
    if config.TESTING:
        return InMemoryEntityRepository()
    else:
        return ShelveEntityRepository()
```

Now we have a durable repository for development use, and an in-memory
repository for our tests.


## Contribute

- Source Code: https://github.com/eykd/steerage
- Issue Tracker: https://github.com/eykd/steerage/issues


## License

The project is licensed under the BSD 3-clause license.
