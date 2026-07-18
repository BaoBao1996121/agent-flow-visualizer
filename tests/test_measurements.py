import pytest
from pydantic import ValidationError

from anthill.measurements import MeasurementSemantics


@pytest.mark.parametrize(
    "basis",
    [
        " synthetic-fixture:pricing-v1",
        "synthetic-fixture:\u202egnicirp-v1",
        "synthetic-fixture:pricing-v1\nforged",
    ],
)
def test_cost_basis_rejects_ambiguous_display_text(basis):
    with pytest.raises(ValidationError):
        MeasurementSemantics(
            aggregate_key="model_call.cost_usd",
            unit="usd",
            scope="model_call",
            aggregation="sum",
            temporality="cumulative",
            owner_id="model-call-1",
            basis=basis,
            estimated=True,
        )
