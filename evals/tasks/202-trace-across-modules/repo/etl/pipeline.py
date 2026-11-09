"""Runs every stage in order."""

from etl import stage_01_validate_required
from etl import stage_02_strip_whitespace
from etl import stage_03_parse_amount
from etl import stage_04_lowercase_email
from etl import stage_05_assign_order_id
from etl import stage_06_tag_source
from etl import stage_07_normalize_amount
from etl import stage_08_resolve_country
from etl import stage_09_resolve_region
from etl import stage_10_check_fraud_flags
from etl import stage_11_apply_coupon
from etl import stage_12_attach_customer_tier
from etl import stage_13_estimate_weight
from etl import stage_14_choose_carrier
from etl import stage_15_add_shipping
from etl import stage_16_add_handling_note
from etl import stage_17_mark_priority
from etl import stage_18_lookup_tax_rate
from etl import stage_19_compute_tax
from etl import stage_20_compute_invoice_number
from etl import stage_21_attach_warehouse
from etl import stage_22_round_totals
from etl import stage_23_render_summary
from etl import stage_24_finalize

STAGES = [
    stage_01_validate_required,
    stage_02_strip_whitespace,
    stage_03_parse_amount,
    stage_04_lowercase_email,
    stage_05_assign_order_id,
    stage_06_tag_source,
    stage_07_normalize_amount,
    stage_08_resolve_country,
    stage_09_resolve_region,
    stage_10_check_fraud_flags,
    stage_11_apply_coupon,
    stage_12_attach_customer_tier,
    stage_13_estimate_weight,
    stage_14_choose_carrier,
    stage_15_add_shipping,
    stage_16_add_handling_note,
    stage_17_mark_priority,
    stage_18_lookup_tax_rate,
    stage_19_compute_tax,
    stage_20_compute_invoice_number,
    stage_21_attach_warehouse,
    stage_22_round_totals,
    stage_23_render_summary,
    stage_24_finalize,
]


def run_pipeline(record):
    for stage in STAGES:
        record = stage.run(record)
    return record
