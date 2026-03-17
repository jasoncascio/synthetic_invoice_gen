from asteval import Interpreter
from typing import Dict, Any

class ExpressionSyntaxError(Exception):
    pass

class MissingReferenceError(Exception):
    pass

class ASTEvaluator:
    def __init__(self, context_record: Dict[str, Any]):
        import random
        import math
        self.context_record = context_record
        self.interpreter = Interpreter()
        self.interpreter.symtable['random'] = random
        self.interpreter.symtable['math'] = math

    def evaluate(self, expression: str) -> Any:
        # Inject context into symtable before evaluation
        for k, v in self.context_record.items():
            self.interpreter.symtable[k] = v
            
        result = self.interpreter(expression)
        
        # Checking for isteval execution errors
        if len(self.interpreter.error) > 0:
            err = self.interpreter.error[0]
            err_msg = err.get_error()[1]
            if "NameError" in err_msg:
                raise MissingReferenceError(
                    f"You referenced an undeclared variable. Check your dependencies array. Error: {err_msg}"
                )
            raise ExpressionSyntaxError(
                f"Malformed python syntax in computation: `{expression}`. Error: {err_msg}"
            )
            
        return result
