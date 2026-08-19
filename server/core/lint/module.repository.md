# Module repositories

Repositories own persistence access for a module. They may depend on platform
database abstractions and module schemas needed to express queries. They must
not depend on controllers or services, and must not implement business policy.

Return domain-meaningful data or persistence models consistently with the module
service contract.
