from pydantic import BaseModel, ValidationInfo, model_validator

class Record(BaseModel):
    value: str

    @model_validator(mode="after")
    def validate_value(self, info: ValidationInfo):
        context = info.context or {}
        if self.value.strip() != self.value and not context.get("legacy"):
            raise ValueError("unsafe")
        return self

legacy = Record.model_validate_json('{"value":" old "}', context={"legacy": True})
assert legacy.value == " old "
try:
    Record.model_validate({"value": " new "})
except ValueError:
    pass
else:
    raise AssertionError("new writes must remain strict")
