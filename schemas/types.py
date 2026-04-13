from typing import Annotated

from pydantic import BeforeValidator

# Converts any ObjectId / PydanticObjectId to str before Pydantic validates the field.
PyObjectId = Annotated[str, BeforeValidator(str)]
