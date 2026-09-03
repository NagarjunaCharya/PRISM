import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from hypothesis import given, strategies as st

@dataclass
class AlertConfig:
    """A sample configuration object for the AI Safety System (REQ-19)."""
    name: str
    threshold: float
    is_active: bool
    channels: List[str]
    metadata: Dict[str, Any]

def serialize(config: AlertConfig) -> str:
    """Serializes the configuration to a JSON string."""
    return json.dumps(asdict(config))

def parse(data: str) -> AlertConfig:
    """Parses a JSON string back into an AlertConfig object."""
    parsed_dict = json.loads(data)
    return AlertConfig(**parsed_dict)

# Hypothesis Strategies for generating random valid configurations
channel_strategy = st.lists(st.sampled_from(["email", "slack", "sms", "webhook"]), max_size=5)
metadata_strategy = st.dictionaries(st.text(), st.one_of(st.integers(), st.text(), st.booleans()), max_size=5)

config_strategy = st.builds(
    AlertConfig,
    name=st.text(min_size=1, max_size=100),
    threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    is_active=st.booleans(),
    channels=channel_strategy,
    metadata=metadata_strategy
)

@given(config=config_strategy)
def test_config_roundtrip_consistency(config):
    """
    Property Test (Task 2.4 / REQ-19): 
    FOR ALL valid Configuration_Objects, parse(serialize(config)) == config
    """
    serialized_data = serialize(config)
    parsed_config = parse(serialized_data)
    
    assert parsed_config == config
