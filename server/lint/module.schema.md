# Module schemas

Schemas define validated input and output data at a module boundary. They may
use standard typing and validation libraries. Schemas must not import
controllers, services, or repositories, and should not perform I/O or contain
business workflows.
