# A config schema is useful for indicating which fields are available in the configurable dict 
# inside the config

from typing_extensions import TypedDict
# from typing import Optional

class ConfigSchema(TypedDict):
    model: str
    model_name: str
    attempts: int #how many time to try to correct the query if it has errors
    # model: Optional[str]
    # model_name:Optional[str]
    # system_message: Optional[str]
