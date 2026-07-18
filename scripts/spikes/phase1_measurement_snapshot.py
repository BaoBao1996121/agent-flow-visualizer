from pydantic import BaseModel


class Owner(BaseModel):
    value: float | None
    samples: int


class Aggregate(BaseModel):
    owners: dict[str, Owner]


state = Aggregate(owners={"call-1": Owner(value=12, samples=2)})
restored = Aggregate.model_validate_json(state.model_dump_json())
assert restored.model_copy(deep=True).owners["call-1"].samples == 2
print("PASS: nested owner state survives JSON snapshot round-trip and deep copy")
