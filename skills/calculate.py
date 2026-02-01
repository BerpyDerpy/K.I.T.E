# filename: calculate.py
"""
Calculate skill for math operations.
"""

def execute(expression: str = None, num1: int = None, num2: int = None, operation: str = "add", **kwargs) -> str:
    """
    Perform math calculations.
    
    Args:
        expression: A math expression like "15 + 30"
        num1: First number
        num2: Second number
        operation: add, subtract, multiply, divide
        **kwargs: Flexible parsing
    """
    try:
        # If expression is provided
        if expression:
            # Clean the expression
            expr = expression.strip()
            # Evaluate simple expressions
            result = eval(expr)
            return f"The result is {result}"
        
        # If num1 and num2 are provided
        if num1 is not None and num2 is not None:
            n1 = float(num1)
            n2 = float(num2)
            
            if operation == "add" or operation == "sum" or operation == "+":
                result = n1 + n2
                return f"The sum of {num1} and {num2} is {result}"
            elif operation == "subtract" or operation == "-" or operation == "minus":
                result = n1 - n2
                return f"{num1} minus {num2} is {result}"
            elif operation == "multiply" or operation == "*" or operation == "times":
                result = n1 * n2
                return f"{num1} multiplied by {num2} is {result}"
            elif operation == "divide" or operation == "/" or operation == "by":
                if n2 == 0:
                    return "Error: Cannot divide by zero"
                result = n1 / n2
                return f"{num1} divided by {num2} is {result}"
            else:
                result = n1 + n2  # Default to addition
                return f"The result is {result}"
        
        # Try to parse from kwargs
        for key, value in kwargs.items():
            if isinstance(value, (int, float)) and value > 0:
                return f"Number detected: {value}"
        
        return "Please provide numbers to calculate."
        
    except Exception as e:
        return f"Calculation error: {str(e)}"

