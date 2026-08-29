# Documentation

Oh-My-Exam documentation is organized by decision stability, not by the old
directory layout.

## Start here

- [Product requirements](requirements.md): stable user-visible behavior and
  non-functional requirements.
- [Architecture](architecture.md): repository boundaries, runtime components,
  dependency direction, and persistence ownership.
- [Engineering principles](principles.md): rules that apply across modules.

## Modules

- [Identity and access](modules/identity-and-access.md)
- [Catalog and documents](modules/catalog-and-documents.md)
- [Exam processing](modules/exam-processing.md)
- [Web application](modules/web-application.md)

## Operations

- [Development](operations/development.md)
- [Linux deployment](operations/linux-deployment.md)
- [Data migration](operations/data-migration.md)

## Decisions and work records

- `decisions/`: accepted long-term architecture decisions.
- `tasks/`: bounded implementation and migration plans.

Implementation-specific details should live next to the owning backend adapter
or frontend feature. Root documentation must not preserve obsolete commands or
duplicate code-level schemas.
