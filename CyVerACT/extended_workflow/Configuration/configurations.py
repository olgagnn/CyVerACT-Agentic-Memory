# A config schema is useful for indicating which fields are available in the configurable dict 
# inside the config

from typing_extensions import TypedDict, NotRequired
# from typing import Optional

class ConfigSchema(TypedDict):
    model: any
    model_name: str
    attempts_w_filtered: int # how many times to try with the filtered schema to correct the cypher query of it has errors
    total_attempts: int # how many times to try to correct the cypher query of it has errors, in total (with filtered and full schema)
    # system_message: Optional[str]

    # Memory mechanisms
    use_generator_helper: NotRequired[bool]
    use_history: NotRequired[bool]
    use_trajectory: NotRequired[bool]
    use_fix_rules: NotRequired[bool]