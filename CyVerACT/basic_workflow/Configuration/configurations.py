# A config schema is useful for indicating which fields are available in the configurable dict 
# inside the config

from typing_extensions import TypedDict
# from typing import Optional

class ConfigSchema(TypedDict):
    model: str
    model_name: str
    # model: Optional[str]
    # model_name:Optional[str]
    # system_message: Optional[str]
