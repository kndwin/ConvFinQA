# Module services

Services contain module use cases and business decisions. They may depend on
their module's repository and schemas, and on stable platform contracts such as
observability. They must not depend on controllers or FastAPI request details.

Keep persistence and transport concerns out of the service so use cases remain
callable outside HTTP.
