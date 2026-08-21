import re
from decimal import Decimal

from ..index import EvidenceItem

CONSTANTS = {
    f"const_{n}": Decimal(n)
    for n in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100, 1000, 100000, 1000000, 1000000000)
}
OPS = {"select", "add", "subtract", "multiply", "divide", "greater", "exp"}


class EvidenceToolState:
    def __init__(self, index: tuple[EvidenceItem, ...]):
        self.index, self.fetched, self.results = index, set(), {}
        self.fetch_calls, self.successful_fetches, self.calculator_calls = [], set(), []
        self.ordered_calls: list[dict] = []

    def fetch(self, query: str, max_results: int = 5) -> dict:
        if not 1 <= max_results <= 10:
            raise ValueError("max_results must be between 1 and 10")
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))

        def tokens(value):
            return set(re.findall(r"[a-z0-9]+", value.lower()))

        def score(item):
            return len(terms & (tokens(item.text) | tokens(item.provenance)))

        found = sorted(
            (x for x in self.index if score(x)),
            key=lambda x: (-score(x), self.index.index(x)),
        )[:max_results]
        self.fetched.update(x.id for x in found)
        self.fetch_calls.append(query)
        if found:
            self.successful_fetches.add(query)
        self.ordered_calls.append({"kind": "fetch", "query": query, "ids": [x.id for x in found]})
        return {
            "index_version": "evidence-index:v1",
            "results": [x.model_dump(mode="json") for x in found],
        }

    def calculate(self, operation: str, operands: list[str]) -> dict:
        self.calculator_calls.append({"operation": operation, "operands": operands})
        if not self.successful_fetches:
            raise ValueError("Fetch evidence successfully before calculating")
        if operation == "select" and len(operands) != 1:
            raise ValueError("select requires one operand")
        if operation != "select" and len(operands) != 2:
            raise ValueError("operation requires two operands")

        def val(ref):
            if ref in self.results:
                return self.results[ref]
            if ref in CONSTANTS:
                return CONSTANTS[ref]
            item = next((x for x in self.index if x.id == ref), None)
            if item is None or ref not in self.fetched or item.numeric is None:
                raise ValueError("unknown or unfetched evidence reference")
            # Scale is provenance. Conversion must be an explicit operation.
            return Decimal(item.numeric) / (100 if item.representation == "percent" else 1)

        if operation == "select":
            result = val(operands[0])
        else:
            a, b = val(operands[0]), val(operands[1])
            if operation == "add":
                result = a + b
            elif operation == "subtract":
                result = a - b
            elif operation == "multiply":
                result = a * b
            elif operation == "divide":
                if b == 0:
                    raise ValueError("division by zero")
                result = a / b
            elif operation == "greater":
                result = Decimal(1 if a > b else 0)
            elif operation == "exp":
                if b != int(b) or abs(b) > 100:
                    raise ValueError("invalid exponent")
                result = a ** int(b)
            else:
                raise ValueError("unsupported operation")
        handle = f"calc:{len(self.results)}"
        self.results[handle] = result
        self.ordered_calls.append(
            {
                "kind": "calculator",
                "operation": operation,
                "operands": operands,
                "handle": handle,
                "value": format(result, "f"),
            }
        )
        return {"handle": handle, "value": format(result, "f"), "provenance": operands}
