"""Tariff for parcels to Netherlands.

quote(goods_cents, weight_g, category, express, zone) returns the charges for one parcel as a dict with the
keys vat, duty, shipping, express, zone, handling, heavy, insurance, packaging, paperwork, signature, fuel,
carbon, discount and total. All amounts are integer cents, weights are grams, category is one of general,
books, food and electronics, express is a bool and zone is 1, 2 or 3. A negative goods value or weight, an
unknown category and any other zone raise ValueError.

Contract
--------
VAT. The standard rate is 20% of the goods value. Parcels in the categories books and food are taxed at the
reduced rate of 5%. Any fraction of a cent is rounded up to the next cent.

Duty. No duty is charged on a goods value below 150.00. From 150.00 up to but not including 400.00 the duty is
5% of the whole goods value; from 400.00 upwards it is 14.5% of the whole goods value. Duty is rounded down to
the cent.

Shipping. Standard shipping costs 7.90 plus 1.80 for every full kilogram (a started kilogram does not count) of
weight. It is free when the goods value is more than 300.00.

Express. Express delivery adds 75% of the shipping charge, rounded up to the next cent, so it costs nothing when
shipping is free.

Zones. Zone 1 has no surcharge, zone 2 adds 3.50 and zone 3 adds 6.00.

Handling. A handling fee of 2.50 is charged when the goods value is below 400.00; parcels worth 400.00 or more
pay none.

Heavy parcels. A parcel heavier than 10 kg pays 1.60 for every started kilogram above 10 kg; a parcel of exactly
10 kg pays nothing.

Cap. Duty and handling together never exceed 10% of the goods value (that limit is rounded down to the cent).
When they would, the handling fee is reduced first and the duty only after the handling fee has reached zero.

Insurance. Parcels with a goods value of 200.00 or more are insured for 0.5% of the goods value, rounded up to
the next cent, but at least 2.50. Cheaper parcels are not insured.

Packaging. Every started 5 kg of weight costs 0.85; parcels in the category electronics pay an extra 2.00 for
padding.

Customs paperwork. A fee of 3.20 is charged whenever duty is due. This is judged before the cap: a parcel whose
duty is reduced to zero by the cap still pays the fee.

Signature. A signature on delivery costs 2.60. It is required for parcels with a goods value of at least 250.00;
the category does not matter.

Fuel. A fuel surcharge of 6% is charged on the sum of the shipping charge and the heavy-parcel surcharge. The
express fee is not part of that sum. Fractions of a cent are dropped.

Carbon offset. 0.18 for every started kilogram of weight, but never more than 0.90 per parcel.

Small parcels. A parcel lighter than 1000 g whose goods value is below 50.00 gets a discount of 2.00. The
discount is reported as a positive amount under the key discount and is subtracted from the total.

Total. The total is the goods value plus all charges above, minus the discount, rounded to the nearest multiple
of 10 cents; a remainder of exactly 5 cents rounds up.
"""

# VAT rates in basis points (1 bp = 0.01 %).
STANDARD_VAT_BP = 2000
REDUCED_VAT_BP = 500
REDUCED_VAT_CATEGORIES = ("books", "food", )

# Duty bands: thresholds in cents, rates in basis points.
DUTY_LOWER_THRESHOLD = 15000
DUTY_UPPER_THRESHOLD = 40000
DUTY_LOWER_RATE_BP = 500
DUTY_UPPER_RATE_BP = 1450

# Shipping.
SHIPPING_BASE = 790
SHIPPING_PER_UNIT = 180
FREE_SHIPPING_THRESHOLD = 30000
EXPRESS_RATE_BP = 7500
ZONE_SURCHARGES = {1: 0, 2: 350, 3: 600}

# Handling, heavy parcels and the cap.
HANDLING_FEE = 250
HANDLING_WAIVED_FROM = 40000
HEAVY_THRESHOLD_G = 10000
HEAVY_FEE_PER_KG = 160
CAP_BP = 1000

# Insurance and packaging.
INSURANCE_FROM = 20000
INSURANCE_RATE_BP = 50
INSURANCE_MINIMUM = 250
PACKAGING_PER_5KG = 85
FRAGILE_PADDING = 200

# Paperwork, signature, fuel, carbon offset and the small-parcel discount.
PAPERWORK_FEE = 320
SIGNATURE_FEE = 260
SIGNATURE_FROM = 25000
FUEL_RATE_BP = 600
CARBON_PER_KG = 18
CARBON_MAXIMUM = 90
SMALL_PARCEL_MAX_WEIGHT_G = 1000
SMALL_PARCEL_MAX_GOODS = 5000
SMALL_PARCEL_DISCOUNT = 200

CATEGORIES = ("general", "books", "food", "electronics")


def check(goods_cents, weight_g, category, zone):
    """Reject input the tariff is not defined for."""
    if goods_cents < 0:
        raise ValueError("goods value must not be negative")
    if weight_g < 0:
        raise ValueError("weight must not be negative")
    if category not in CATEGORIES:
        raise ValueError(f"unknown category: {category!r}")
    if zone not in ZONE_SURCHARGES:
        raise ValueError(f"unknown zone: {zone!r}")


def vat(goods_cents, category):
    """VAT on the goods value."""
    if category in REDUCED_VAT_CATEGORIES:
        rate_bp = REDUCED_VAT_BP
    else:
        rate_bp = STANDARD_VAT_BP
    amount = goods_cents * rate_bp
    return -(-amount // 10_000)


def duty(goods_cents, category):
    """Import duty on the goods value."""
    if goods_cents < DUTY_LOWER_THRESHOLD:
        return 0
    if goods_cents < DUTY_UPPER_THRESHOLD:
        return goods_cents * DUTY_LOWER_RATE_BP // 10_000
    return goods_cents * DUTY_UPPER_RATE_BP // 10_000


def shipping(goods_cents, weight_g):
    """Standard shipping."""
    if goods_cents > FREE_SHIPPING_THRESHOLD:
        return 0
    units = weight_g // 1000
    return SHIPPING_BASE + SHIPPING_PER_UNIT * units


def express_fee(shipping_cents, express):
    """What express delivery adds to the shipping charge."""
    if not express:
        return 0
    return -(-shipping_cents * EXPRESS_RATE_BP // 10_000)


def zone_surcharge(zone):
    """Surcharge for the delivery zone."""
    return ZONE_SURCHARGES[zone]


def handling(goods_cents, category):
    """Handling fee before the cap."""
    if goods_cents < HANDLING_WAIVED_FROM:
        return HANDLING_FEE
    return 0


def heavy_surcharge(weight_g):
    """Surcharge for heavy parcels."""
    if weight_g <= HEAVY_THRESHOLD_G:
        return 0
    extra_g = weight_g - HEAVY_THRESHOLD_G
    return HEAVY_FEE_PER_KG * ((extra_g + 999) // 1000)


def apply_cap(goods_cents, duty_cents, handling_cents):
    """Duty and handling after the cap, as a (duty, handling) pair."""
    limit = goods_cents * CAP_BP // 10_000
    excess = duty_cents + handling_cents - limit
    if excess <= 0:
        return duty_cents, handling_cents
    reduction = min(handling_cents, excess)
    return duty_cents - (excess - reduction), handling_cents - reduction


def insurance(goods_cents):
    """Insurance premium."""
    if goods_cents < INSURANCE_FROM:
        return 0
    premium = -(-goods_cents * INSURANCE_RATE_BP // 10_000)
    if premium < INSURANCE_MINIMUM:
        premium = INSURANCE_MINIMUM
    return premium


def packaging(weight_g, category):
    """Packaging material."""
    cost = PACKAGING_PER_5KG * ((weight_g + 4999) // 5000)
    if category == "electronics":
        cost += FRAGILE_PADDING
    return cost


def paperwork(goods_cents, duty_before_cap):
    """Customs paperwork fee."""
    if duty_before_cap > 0:
        return PAPERWORK_FEE
    return 0


def signature(goods_cents, category):
    """Fee for a signature on delivery."""
    if goods_cents >= SIGNATURE_FROM:
        return SIGNATURE_FEE
    return 0


def fuel(shipping_cents, heavy_cents):
    """Fuel surcharge."""
    amount = (shipping_cents + heavy_cents) * FUEL_RATE_BP
    return amount // 10_000


def carbon_offset(weight_g):
    """Carbon offset."""
    amount = CARBON_PER_KG * ((weight_g + 999) // 1000)
    if amount > CARBON_MAXIMUM:
        amount = CARBON_MAXIMUM
    return amount


def small_parcel_discount(goods_cents, weight_g):
    """Discount for small parcels, as a positive amount."""
    if weight_g < SMALL_PARCEL_MAX_WEIGHT_G and goods_cents < SMALL_PARCEL_MAX_GOODS:
        return SMALL_PARCEL_DISCOUNT
    return 0


def quote(goods_cents, weight_g, category, express, zone):
    """All charges for one parcel; see the module docstring."""
    check(goods_cents, weight_g, category, zone)
    vat_cents = vat(goods_cents, category)
    shipping_cents = shipping(goods_cents, weight_g)
    express_cents = express_fee(shipping_cents, express)
    zone_cents = zone_surcharge(zone)
    heavy_cents = heavy_surcharge(weight_g)
    duty_before_cap = duty(goods_cents, category)
    paperwork_cents = paperwork(goods_cents, duty_before_cap)
    duty_cents, handling_cents = apply_cap(goods_cents, duty_before_cap, handling(goods_cents, category))
    insurance_cents = insurance(goods_cents)
    packaging_cents = packaging(weight_g, category)
    signature_cents = signature(goods_cents, category)
    fuel_cents = fuel(shipping_cents, heavy_cents)
    carbon_cents = carbon_offset(weight_g)
    discount_cents = small_parcel_discount(goods_cents, weight_g)
    total = (goods_cents + vat_cents + duty_cents + shipping_cents + express_cents + zone_cents + handling_cents
             + heavy_cents + insurance_cents + packaging_cents + paperwork_cents + signature_cents + fuel_cents
             + carbon_cents - discount_cents)
    total = (total + 5) // 10 * 10
    return {
        "vat": vat_cents,
        "duty": duty_cents,
        "shipping": shipping_cents,
        "express": express_cents,
        "zone": zone_cents,
        "handling": handling_cents,
        "heavy": heavy_cents,
        "insurance": insurance_cents,
        "packaging": packaging_cents,
        "paperwork": paperwork_cents,
        "signature": signature_cents,
        "fuel": fuel_cents,
        "carbon": carbon_cents,
        "discount": discount_cents,
        "total": total,
    }
