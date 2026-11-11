"""Tariff for parcels to Germany.

quote(goods_cents, weight_g, category, express, zone) returns the charges for one parcel as a dict with the
keys vat, duty, shipping, express, zone, handling, heavy, insurance, packaging, paperwork, signature, fuel,
carbon, discount and total. All amounts are integer cents, weights are grams, category is one of general,
books, food and electronics, express is a bool and zone is 1, 2 or 3. A negative goods value or weight, an
unknown category and any other zone raise ValueError.

Contract
--------
VAT. The standard rate is 17% of the goods value. Parcels in the category food are taxed at the reduced rate of
5%. Any fraction of a cent is rounded up to the next cent.

Duty. The first 100.00 of the goods value is free of duty. The part of the goods value between 100.00 and 200.00
is charged at 5% and the part above 200.00 at 10%; only those parts are charged, never the whole value. Parcels
in the category books pay no duty. Duty is rounded down to the cent.

Shipping. Standard shipping costs 6.90 plus 1.80 for every full kilogram (a started kilogram does not count) of
weight. It is free when the goods value is at least 300.00.

Express. Express delivery adds 50% of the shipping charge, rounded up to the next cent, so it costs nothing when
shipping is free.

Zones. Zone 1 has no surcharge, zone 2 adds 2.00 and zone 3 adds 9.50.

Handling. A handling fee of 5.00 is charged on every parcel except those in the category books.

Heavy parcels. There is no surcharge for heavy parcels.

Cap. Duty and handling together never exceed 10% of the goods value (that limit is rounded down to the cent).
When they would, the handling fee is reduced first and the duty only after the handling fee has reached zero.

Insurance. Parcels with a goods value of 200.00 or more are insured for 0.5% of the goods value, rounded up to
the next cent, but at least 1.50. Cheaper parcels are not insured.

Packaging. Every started 5 kg of weight costs 0.40; parcels in the category electronics pay an extra 2.00 for
padding.

Customs paperwork. A fee of 2.40 is charged whenever duty is due. This is judged before the cap: a parcel whose
duty is reduced to zero by the cap still pays the fee.

Signature. A signature on delivery costs 2.60. It is required for parcels with a goods value of at least 150.00
and for every parcel in the category electronics.

Fuel. A fuel surcharge of 11% is charged on the sum of the shipping charge and the heavy-parcel surcharge. The
express fee is not part of that sum. The result is rounded to the nearest cent; exactly half a cent is rounded
up.

Carbon offset. 0.18 for every started kilogram of weight, but never more than 1.20 per parcel.

Small parcels. A parcel lighter than 1000 g whose goods value is below 50.00 gets a discount of 1.50. The
discount is reported as a positive amount under the key discount and is subtracted from the total.

Total. The total is the goods value plus all charges above, minus the discount, rounded to the nearest multiple
of 10 cents; a remainder of exactly 5 cents rounds up.
"""

# VAT rates in basis points (1 bp = 0.01 %).
STANDARD_VAT_BP = 1700
REDUCED_VAT_BP = 500
REDUCED_VAT_CATEGORIES = ("food", )

# Duty bands: thresholds in cents, rates in basis points.
DUTY_LOWER_THRESHOLD = 10000
DUTY_UPPER_THRESHOLD = 20000
DUTY_LOWER_RATE_BP = 500
DUTY_UPPER_RATE_BP = 1000
DUTY_EXEMPT_CATEGORIES = ("books", )

# Shipping.
SHIPPING_BASE = 690
SHIPPING_PER_UNIT = 180
FREE_SHIPPING_THRESHOLD = 30000
EXPRESS_RATE_BP = 5000
ZONE_SURCHARGES = {1: 0, 2: 200, 3: 950}

# Handling, heavy parcels and the cap.
HANDLING_FEE = 500
HANDLING_EXEMPT_CATEGORIES = ("books", )
CAP_BP = 1000

# Insurance and packaging.
INSURANCE_FROM = 20000
INSURANCE_RATE_BP = 50
INSURANCE_MINIMUM = 150
PACKAGING_PER_5KG = 40
FRAGILE_PADDING = 200

# Paperwork, signature, fuel, carbon offset and the small-parcel discount.
PAPERWORK_FEE = 240
SIGNATURE_FEE = 260
SIGNATURE_FROM = 15000
FUEL_RATE_BP = 1100
CARBON_PER_KG = 18
CARBON_MAXIMUM = 120
SMALL_PARCEL_MAX_WEIGHT_G = 1000
SMALL_PARCEL_MAX_GOODS = 5000
SMALL_PARCEL_DISCOUNT = 150

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
    if category in DUTY_EXEMPT_CATEGORIES:
        return 0
    middle_part = min(goods_cents, DUTY_UPPER_THRESHOLD) - DUTY_LOWER_THRESHOLD
    if middle_part < 0:
        middle_part = 0
    upper_part = goods_cents - DUTY_UPPER_THRESHOLD
    if upper_part < 0:
        upper_part = 0
    return (middle_part * DUTY_LOWER_RATE_BP + upper_part * DUTY_UPPER_RATE_BP) // 10_000


def shipping(goods_cents, weight_g):
    """Standard shipping."""
    if goods_cents >= FREE_SHIPPING_THRESHOLD:
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
    if category in HANDLING_EXEMPT_CATEGORIES:
        return 0
    return HANDLING_FEE


def heavy_surcharge(weight_g):
    """Surcharge for heavy parcels."""
    return 0


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
    if category == "electronics":
        return SIGNATURE_FEE
    return 0


def fuel(shipping_cents, heavy_cents):
    """Fuel surcharge."""
    amount = (shipping_cents + heavy_cents) * FUEL_RATE_BP
    return (2 * amount + 10_000) // 20_000


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
