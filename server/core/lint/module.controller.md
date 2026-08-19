# Module controllers

Controllers are the HTTP boundary. They define routes, dependency injection,
HTTP parameters, and response schemas. A controller may call its module's
service and use schemas; it may use platform integration only for wiring.

Controllers must not contain business rules, database queries, or direct ORM
session work. Keep orchestration thin and pass validated input to a service.
