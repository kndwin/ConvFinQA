# Platform layer

`src.platform` contains shared infrastructure: validated configuration, database
access, observability, dependency injection, and reusable base abstractions.
Module code may depend on platform contracts and adapters.

Platform must remain independent of `src.module`; application composition may
wire concrete module implementations at the entry point. The current
`dependency_injection` module is that composition-root exception and is the only
platform module allowed to import concrete modules. Other platform packages
must not reach upward into module controllers, services, repositories, or
schemas.
