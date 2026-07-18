from pydantic import ValidationError

from anthill.measurements import MeasurementSemantics

valid = MeasurementSemantics(
    aggregate_key="model_call.input_tokens", unit="tokens", scope="model_call",
    aggregation="sum", temporality="unknown", owner_id="call-1",
)
assert valid.aggregate_key == "model_call.input_tokens"
try:
    MeasurementSemantics(
        aggregate_key="model_call.cost_usd", unit="usd", scope="model_call",
        aggregation="sum", temporality="cumulative", owner_id="call-1",
    )
except ValidationError:
    print("PASS: registry accepts token ownership and rejects unpriced cost")
else:
    raise AssertionError("unpriced cost semantics must be rejected")
