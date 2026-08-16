from typing import Literal

from agents import function_tool


@function_tool
def calculator(
    operation: Literal["add", "subtract", "multiply", "divide"], a: float, b: float
) -> float:
    if operation == "add":
        return a + b
    if operation == "subtract":
        return a - b
    if operation == "multiply":
        return a * b
    if operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    raise ValueError("Unsupported operation")
