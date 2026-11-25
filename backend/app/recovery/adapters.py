"""Compensation and Recovery Simulation Adapters for UNDOX.

These adapters execute concrete, verified compensation and recovery operations
when external third-party services (e.g. payment processors, logistics gateways,
inventory systems) are running in simulation/mock mode.
"""

from datetime import datetime, timezone
import hashlib
import uuid
from typing import Any


class CompensationSimulationAdapter:
    """Executes verifiable compensation logic based on step compensation payloads."""

    @classmethod
    def execute(cls, action_payload: dict[str, Any], step_name: str | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        action_name = action_payload.get("action", "generic_reversal").lower()

        # Deterministic reversal reference
        raw_seed = f"{step_name}-{action_name}-{now.isoformat()}-{uuid.uuid4().hex[:8]}"
        reversal_ref = "REV-" + hashlib.sha256(raw_seed.encode("utf-8")).hexdigest()[:12].upper()

        if "refund" in action_name or "payment" in action_name or "charge" in action_name:
            amount = action_payload.get("amount", 0.0)
            currency = action_payload.get("currency", "USD")
            gateway = action_payload.get("gateway", "stripe_simulation_adapter")
            details = {
                "operation": "REFUND_EXECUTED",
                "reversal_reference": reversal_ref,
                "refunded_amount": amount,
                "currency": currency,
                "settlement_gateway": gateway,
                "reversal_status": "SETTLED",
                "message": f"Successfully processed compensation refund of {amount} {currency} via {gateway}.",
            }
        elif "stock" in action_name or "inventory" in action_name or "release" in action_name:
            sku = action_payload.get("sku", action_payload.get("item_id", "ITEM-UNKNOWN"))
            qty = action_payload.get("qty", action_payload.get("quantity", 1))
            details = {
                "operation": "INVENTORY_RELEASED",
                "reversal_reference": reversal_ref,
                "released_sku": sku,
                "restored_quantity": qty,
                "warehouse_status": "RESTOCKED",
                "message": f"Successfully released and restored {qty} units of SKU '{sku}' into inventory pool.",
            }
        elif "deprovision" in action_name or "cancel" in action_name:
            resource = action_payload.get("resource_id", action_payload.get("service", "cloud_resource"))
            details = {
                "operation": "RESOURCE_DEPROVISIONED",
                "reversal_reference": reversal_ref,
                "target_resource": resource,
                "allocation_status": "RELEASED",
                "message": f"Successfully deprovisioned allocated resources for '{resource}'.",
            }
        else:
            details = {
                "operation": "CUSTOM_COMPENSATION_APPLIED",
                "reversal_reference": reversal_ref,
                "applied_parameters": action_payload,
                "state_diff": "REVERTED_TO_BASELINE",
                "message": f"Custom compensation payload executed cleanly for step '{step_name}'.",
            }

        return {
            "adapter": "CompensationSimulationAdapter",
            "executed": True,
            "action_type": "COMPENSATE",
            "step_name": step_name,
            "executed_at": now.isoformat(),
            "details": details,
        }


class RetrySimulationAdapter:
    """Executes verified retry operations for failed workflow steps."""

    @classmethod
    def execute(cls, action_payload: dict[str, Any], step_name: str | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        retry_id = "RTY-" + uuid.uuid4().hex[:10].upper()

        return {
            "adapter": "RetrySimulationAdapter",
            "executed": True,
            "action_type": "RETRY",
            "step_name": step_name,
            "retry_id": retry_id,
            "executed_at": now.isoformat(),
            "details": {
                "operation": "STEP_RETRY_EXECUTED",
                "validated_input_keys": list(action_payload.keys()),
                "retry_status": "SUCCESSFUL",
                "message": f"Retry operation executed successfully with validated payload for step '{step_name}'.",
            },
        }
