"""Order pricing rules. Each rule returns an adjustment that is added to the line total."""



def rule_001_bulk_stationery_10(order):
    """Stationery orders of 10 or more units get 3% off the line total.

    Ticket PRC-1001. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "stationery" and order["units"] >= 10:
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_002_bulk_stationery_25(order):
    """Stationery orders of 25 or more units get 7% off the line total.

    Ticket PRC-1002. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "stationery" and order["units"] >= 25:
        return round(-order["line_total"] * 7 / 100, 2)
    return 0.0


def rule_003_bulk_stationery_40(order):
    """Stationery orders of 40 or more units get 8% off the line total.

    Ticket PRC-1003. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "stationery" and order["units"] >= 40:
        return round(-order["line_total"] * 8 / 100, 2)
    return 0.0


def rule_004_bulk_stationery_80(order):
    """Stationery orders of 80 or more units get 13% off the line total.

    Ticket PRC-1004. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "stationery" and order["units"] >= 80:
        return round(-order["line_total"] * 13 / 100, 2)
    return 0.0


def rule_005_bulk_furniture_10(order):
    """Furniture orders of 10 or more units get 2% off the line total.

    Ticket PRC-1005. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "furniture" and order["units"] >= 10:
        return round(-order["line_total"] * 2 / 100, 2)
    return 0.0


def rule_006_bulk_furniture_25(order):
    """Furniture orders of 25 or more units get 6% off the line total.

    Ticket PRC-1006. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "furniture" and order["units"] >= 25:
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_007_bulk_furniture_40(order):
    """Furniture orders of 40 or more units get 7% off the line total.

    Ticket PRC-1007. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "furniture" and order["units"] >= 40:
        return round(-order["line_total"] * 7 / 100, 2)
    return 0.0


def rule_008_bulk_furniture_80(order):
    """Furniture orders of 80 or more units get 9% off the line total.

    Ticket PRC-1008. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "furniture" and order["units"] >= 80:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_009_bulk_electronics_10(order):
    """Electronics orders of 10 or more units get 6% off the line total.

    Ticket PRC-1009. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "electronics" and order["units"] >= 10:
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_010_bulk_electronics_25(order):
    """Electronics orders of 25 or more units get 9% off the line total.

    Ticket PRC-1010. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "electronics" and order["units"] >= 25:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_011_bulk_electronics_40(order):
    """Electronics orders of 40 or more units get 11% off the line total.

    Ticket PRC-1011. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "electronics" and order["units"] >= 40:
        return round(-order["line_total"] * 11 / 100, 2)
    return 0.0


def rule_012_bulk_electronics_80(order):
    """Electronics orders of 80 or more units get 12% off the line total.

    Ticket PRC-1012. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "electronics" and order["units"] >= 80:
        return round(-order["line_total"] * 12 / 100, 2)
    return 0.0


def rule_013_bulk_grocery_10(order):
    """Grocery orders of 10 or more units get 4% off the line total.

    Ticket PRC-1013. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "grocery" and order["units"] >= 10:
        return round(-order["line_total"] * 4 / 100, 2)
    return 0.0


def rule_014_bulk_grocery_25(order):
    """Grocery orders of 25 or more units get 9% off the line total.

    Ticket PRC-1014. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "grocery" and order["units"] >= 25:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_015_bulk_grocery_40(order):
    """Grocery orders of 40 or more units get 10% off the line total.

    Ticket PRC-1015. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "grocery" and order["units"] >= 40:
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_016_bulk_grocery_80(order):
    """Grocery orders of 80 or more units get 11% off the line total.

    Ticket PRC-1016. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "grocery" and order["units"] >= 80:
        return round(-order["line_total"] * 11 / 100, 2)
    return 0.0


def rule_017_bulk_apparel_10(order):
    """Apparel orders of 10 or more units get 2% off the line total.

    Ticket PRC-1017. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "apparel" and order["units"] >= 10:
        return round(-order["line_total"] * 2 / 100, 2)
    return 0.0


def rule_018_bulk_apparel_25(order):
    """Apparel orders of 25 or more units get 9% off the line total.

    Ticket PRC-1018. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "apparel" and order["units"] >= 25:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_019_bulk_apparel_40(order):
    """Apparel orders of 40 or more units get 10% off the line total.

    Ticket PRC-1019. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "apparel" and order["units"] >= 40:
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_020_bulk_apparel_80(order):
    """Apparel orders of 80 or more units get 11% off the line total.

    Ticket PRC-1020. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "apparel" and order["units"] >= 80:
        return round(-order["line_total"] * 11 / 100, 2)
    return 0.0


def rule_021_bulk_toys_10(order):
    """Toys orders of 10 or more units get 2% off the line total.

    Ticket PRC-1021. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "toys" and order["units"] >= 10:
        return round(-order["line_total"] * 2 / 100, 2)
    return 0.0


def rule_022_bulk_toys_25(order):
    """Toys orders of 25 or more units get 5% off the line total.

    Ticket PRC-1022. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "toys" and order["units"] >= 25:
        return round(-order["line_total"] * 5 / 100, 2)
    return 0.0


def rule_023_bulk_toys_40(order):
    """Toys orders of 40 or more units get 13% off the line total.

    Ticket PRC-1023. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "toys" and order["units"] >= 40:
        return round(-order["line_total"] * 13 / 100, 2)
    return 0.0


def rule_024_bulk_toys_80(order):
    """Toys orders of 80 or more units get 14% off the line total.

    Ticket PRC-1024. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "toys" and order["units"] >= 80:
        return round(-order["line_total"] * 14 / 100, 2)
    return 0.0


def rule_025_bulk_garden_10(order):
    """Garden orders of 10 or more units get 3% off the line total.

    Ticket PRC-1025. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "garden" and order["units"] >= 10:
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_026_bulk_garden_25(order):
    """Garden orders of 25 or more units get 5% off the line total.

    Ticket PRC-1026. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "garden" and order["units"] >= 25:
        return round(-order["line_total"] * 5 / 100, 2)
    return 0.0


def rule_027_bulk_garden_40(order):
    """Garden orders of 40 or more units get 6% off the line total.

    Ticket PRC-1027. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "garden" and order["units"] > 40:
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_028_bulk_garden_80(order):
    """Garden orders of 80 or more units get 10% off the line total.

    Ticket PRC-1028. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "garden" and order["units"] >= 80:
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_029_bulk_books_10(order):
    """Books orders of 10 or more units get 4% off the line total.

    Ticket PRC-1029. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "books" and order["units"] >= 10:
        return round(-order["line_total"] * 4 / 100, 2)
    return 0.0


def rule_030_bulk_books_25(order):
    """Books orders of 25 or more units get 6% off the line total.

    Ticket PRC-1030. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "books" and order["units"] >= 25:
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_031_bulk_books_40(order):
    """Books orders of 40 or more units get 9% off the line total.

    Ticket PRC-1031. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "books" and order["units"] >= 40:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_032_bulk_books_80(order):
    """Books orders of 80 or more units get 12% off the line total.

    Ticket PRC-1032. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "books" and order["units"] >= 80:
        return round(-order["line_total"] * 12 / 100, 2)
    return 0.0


def rule_033_bulk_sports_10(order):
    """Sports orders of 10 or more units get 2% off the line total.

    Ticket PRC-1033. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "sports" and order["units"] >= 10:
        return round(-order["line_total"] * 2 / 100, 2)
    return 0.0


def rule_034_bulk_sports_25(order):
    """Sports orders of 25 or more units get 11% off the line total.

    Ticket PRC-1034. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "sports" and order["units"] >= 25:
        return round(-order["line_total"] * 11 / 100, 2)
    return 0.0


def rule_035_bulk_sports_40(order):
    """Sports orders of 40 or more units get 12% off the line total.

    Ticket PRC-1035. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "sports" and order["units"] >= 40:
        return round(-order["line_total"] * 12 / 100, 2)
    return 0.0


def rule_036_bulk_sports_80(order):
    """Sports orders of 80 or more units get 13% off the line total.

    Ticket PRC-1036. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "sports" and order["units"] >= 80:
        return round(-order["line_total"] * 13 / 100, 2)
    return 0.0


def rule_037_bulk_pet_10(order):
    """Pet orders of 10 or more units get 3% off the line total.

    Ticket PRC-1037. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "pet" and order["units"] >= 10:
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_038_bulk_pet_25(order):
    """Pet orders of 25 or more units get 8% off the line total.

    Ticket PRC-1038. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "pet" and order["units"] >= 25:
        return round(-order["line_total"] * 8 / 100, 2)
    return 0.0


def rule_039_bulk_pet_40(order):
    """Pet orders of 40 or more units get 10% off the line total.

    Ticket PRC-1039. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "pet" and order["units"] >= 40:
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_040_bulk_pet_80(order):
    """Pet orders of 80 or more units get 12% off the line total.

    Ticket PRC-1040. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "pet" and order["units"] >= 80:
        return round(-order["line_total"] * 12 / 100, 2)
    return 0.0


def rule_041_bulk_kitchen_10(order):
    """Kitchen orders of 10 or more units get 6% off the line total.

    Ticket PRC-1041. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "kitchen" and order["units"] >= 10:
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_042_bulk_kitchen_25(order):
    """Kitchen orders of 25 or more units get 10% off the line total.

    Ticket PRC-1042. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "kitchen" and order["units"] >= 25:
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_043_bulk_kitchen_40(order):
    """Kitchen orders of 40 or more units get 12% off the line total.

    Ticket PRC-1043. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "kitchen" and order["units"] >= 40:
        return round(-order["line_total"] * 12 / 100, 2)
    return 0.0


def rule_044_bulk_kitchen_80(order):
    """Kitchen orders of 80 or more units get 14% off the line total.

    Ticket PRC-1044. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "kitchen" and order["units"] >= 80:
        return round(-order["line_total"] * 14 / 100, 2)
    return 0.0


def rule_045_bulk_lighting_10(order):
    """Lighting orders of 10 or more units get 3% off the line total.

    Ticket PRC-1045. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "lighting" and order["units"] >= 10:
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_046_bulk_lighting_25(order):
    """Lighting orders of 25 or more units get 6% off the line total.

    Ticket PRC-1046. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "lighting" and order["units"] >= 25:
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_047_bulk_lighting_40(order):
    """Lighting orders of 40 or more units get 9% off the line total.

    Ticket PRC-1047. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "lighting" and order["units"] >= 40:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_048_bulk_lighting_80(order):
    """Lighting orders of 80 or more units get 11% off the line total.

    Ticket PRC-1048. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["category"] == "lighting" and order["units"] >= 80:
        return round(-order["line_total"] * 11 / 100, 2)
    return 0.0


def rule_049_surcharge_north_stationery(order):
    """Stationery orders shipped to the north region pay a flat 6.00 surcharge.

    Ticket PRC-1049. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "stationery":
        return round(6.00, 2)
    return 0.0


def rule_050_surcharge_north_furniture(order):
    """Furniture orders shipped to the north region pay a flat 6.50 surcharge.

    Ticket PRC-1050. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "furniture":
        return round(6.50, 2)
    return 0.0


def rule_051_surcharge_north_electronics(order):
    """Electronics orders shipped to the north region pay a flat 3.50 surcharge.

    Ticket PRC-1051. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "electronics":
        return round(3.50, 2)
    return 0.0


def rule_052_surcharge_north_grocery(order):
    """Grocery orders shipped to the north region pay a flat 0.75 surcharge.

    Ticket PRC-1052. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "grocery":
        return round(0.75, 2)
    return 0.0


def rule_053_surcharge_north_apparel(order):
    """Apparel orders shipped to the north region pay a flat 7.00 surcharge.

    Ticket PRC-1053. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "apparel":
        return round(7.00, 2)
    return 0.0


def rule_054_surcharge_north_toys(order):
    """Toys orders shipped to the north region pay a flat 7.50 surcharge.

    Ticket PRC-1054. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "toys":
        return round(7.50, 2)
    return 0.0


def rule_055_surcharge_north_garden(order):
    """Garden orders shipped to the north region pay a flat 1.00 surcharge.

    Ticket PRC-1055. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "garden":
        return round(1.00, 2)
    return 0.0


def rule_056_surcharge_north_books(order):
    """Books orders shipped to the north region pay a flat 7.00 surcharge.

    Ticket PRC-1056. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "books":
        return round(7.00, 2)
    return 0.0


def rule_057_surcharge_north_sports(order):
    """Sports orders shipped to the north region pay a flat 4.75 surcharge.

    Ticket PRC-1057. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "sports":
        return round(4.75, 2)
    return 0.0


def rule_058_surcharge_north_pet(order):
    """Pet orders shipped to the north region pay a flat 0.50 surcharge.

    Ticket PRC-1058. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "pet":
        return round(0.50, 2)
    return 0.0


def rule_059_surcharge_north_kitchen(order):
    """Kitchen orders shipped to the north region pay a flat 3.50 surcharge.

    Ticket PRC-1059. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "kitchen":
        return round(3.50, 2)
    return 0.0


def rule_060_surcharge_north_lighting(order):
    """Lighting orders shipped to the north region pay a flat 7.00 surcharge.

    Ticket PRC-1060. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "north" and order["category"] == "lighting":
        return round(7.00, 2)
    return 0.0


def rule_061_surcharge_south_stationery(order):
    """Stationery orders shipped to the south region pay a flat 2.50 surcharge.

    Ticket PRC-1061. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "stationery":
        return round(2.50, 2)
    return 0.0


def rule_062_surcharge_south_furniture(order):
    """Furniture orders shipped to the south region pay a flat 4.25 surcharge.

    Ticket PRC-1062. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "furniture":
        return round(4.25, 2)
    return 0.0


def rule_063_surcharge_south_electronics(order):
    """Electronics orders shipped to the south region pay a flat 8.50 surcharge.

    Ticket PRC-1063. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "electronics":
        return round(8.50, 2)
    return 0.0


def rule_064_surcharge_south_grocery(order):
    """Grocery orders shipped to the south region pay a flat 0.50 surcharge.

    Ticket PRC-1064. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "grocery":
        return round(0.50, 2)
    return 0.0


def rule_065_surcharge_south_apparel(order):
    """Apparel orders shipped to the south region pay a flat 4.50 surcharge.

    Ticket PRC-1065. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "apparel":
        return round(4.50, 2)
    return 0.0


def rule_066_surcharge_south_toys(order):
    """Toys orders shipped to the south region pay a flat 5.50 surcharge.

    Ticket PRC-1066. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "toys":
        return round(5.50, 2)
    return 0.0


def rule_067_surcharge_south_garden(order):
    """Garden orders shipped to the south region pay a flat 2.00 surcharge.

    Ticket PRC-1067. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "garden":
        return round(2.00, 2)
    return 0.0


def rule_068_surcharge_south_books(order):
    """Books orders shipped to the south region pay a flat 4.75 surcharge.

    Ticket PRC-1068. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "books":
        return round(4.75, 2)
    return 0.0


def rule_069_surcharge_south_sports(order):
    """Sports orders shipped to the south region pay a flat 5.75 surcharge.

    Ticket PRC-1069. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "sports":
        return round(5.75, 2)
    return 0.0


def rule_070_surcharge_south_pet(order):
    """Pet orders shipped to the south region pay a flat 3.50 surcharge.

    Ticket PRC-1070. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "pet":
        return round(3.50, 2)
    return 0.0


def rule_071_surcharge_south_kitchen(order):
    """Kitchen orders shipped to the south region pay a flat 5.25 surcharge.

    Ticket PRC-1071. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "kitchen":
        return round(5.25, 2)
    return 0.0


def rule_072_surcharge_south_lighting(order):
    """Lighting orders shipped to the south region pay a flat 1.00 surcharge.

    Ticket PRC-1072. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "south" and order["category"] == "lighting":
        return round(1.00, 2)
    return 0.0


def rule_073_surcharge_east_stationery(order):
    """Stationery orders shipped to the east region pay a flat 3.25 surcharge.

    Ticket PRC-1073. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "stationery":
        return round(3.25, 2)
    return 0.0


def rule_074_surcharge_east_furniture(order):
    """Furniture orders shipped to the east region pay a flat 8.25 surcharge.

    Ticket PRC-1074. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "furniture":
        return round(8.25, 2)
    return 0.0


def rule_075_surcharge_east_electronics(order):
    """Electronics orders shipped to the east region pay a flat 7.25 surcharge.

    Ticket PRC-1075. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "electronics":
        return round(7.25, 2)
    return 0.0


def rule_076_surcharge_east_grocery(order):
    """Grocery orders shipped to the east region pay a flat 5.00 surcharge.

    Ticket PRC-1076. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "grocery":
        return round(5.00, 2)
    return 0.0


def rule_077_surcharge_east_apparel(order):
    """Apparel orders shipped to the east region pay a flat 8.75 surcharge.

    Ticket PRC-1077. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "apparel":
        return round(8.75, 2)
    return 0.0


def rule_078_surcharge_east_toys(order):
    """Toys orders shipped to the east region pay a flat 0.50 surcharge.

    Ticket PRC-1078. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "toys":
        return round(0.50, 2)
    return 0.0


def rule_079_surcharge_east_garden(order):
    """Garden orders shipped to the east region pay a flat 1.50 surcharge.

    Ticket PRC-1079. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "garden":
        return round(1.50, 2)
    return 0.0


def rule_080_surcharge_east_books(order):
    """Books orders shipped to the east region pay a flat 6.25 surcharge.

    Ticket PRC-1080. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "books":
        return round(6.25, 2)
    return 0.0


def rule_081_surcharge_east_sports(order):
    """Sports orders shipped to the east region pay a flat 8.50 surcharge.

    Ticket PRC-1081. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "sports":
        return round(8.50, 2)
    return 0.0


def rule_082_surcharge_east_pet(order):
    """Pet orders shipped to the east region pay a flat 8.50 surcharge.

    Ticket PRC-1082. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "pet":
        return round(8.50, 2)
    return 0.0


def rule_083_surcharge_east_kitchen(order):
    """Kitchen orders shipped to the east region pay a flat 3.25 surcharge.

    Ticket PRC-1083. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "kitchen":
        return round(3.25, 2)
    return 0.0


def rule_084_surcharge_east_lighting(order):
    """Lighting orders shipped to the east region pay a flat 1.50 surcharge.

    Ticket PRC-1084. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "east" and order["category"] == "lighting":
        return round(1.50, 2)
    return 0.0


def rule_085_surcharge_west_stationery(order):
    """Stationery orders shipped to the west region pay a flat 3.75 surcharge.

    Ticket PRC-1085. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "stationery":
        return round(3.75, 2)
    return 0.0


def rule_086_surcharge_west_furniture(order):
    """Furniture orders shipped to the west region pay a flat 1.00 surcharge.

    Ticket PRC-1086. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "furniture":
        return round(1.00, 2)
    return 0.0


def rule_087_surcharge_west_electronics(order):
    """Electronics orders shipped to the west region pay a flat 6.25 surcharge.

    Ticket PRC-1087. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "electronics":
        return round(6.25, 2)
    return 0.0


def rule_088_surcharge_west_grocery(order):
    """Grocery orders shipped to the west region pay a flat 8.25 surcharge.

    Ticket PRC-1088. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "grocery":
        return round(8.25, 2)
    return 0.0


def rule_089_surcharge_west_apparel(order):
    """Apparel orders shipped to the west region pay a flat 7.50 surcharge.

    Ticket PRC-1089. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "apparel":
        return round(7.50, 2)
    return 0.0


def rule_090_surcharge_west_toys(order):
    """Toys orders shipped to the west region pay a flat 0.50 surcharge.

    Ticket PRC-1090. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "toys":
        return round(0.50, 2)
    return 0.0


def rule_091_surcharge_west_garden(order):
    """Garden orders shipped to the west region pay a flat 1.00 surcharge.

    Ticket PRC-1091. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "garden":
        return round(1.00, 2)
    return 0.0


def rule_092_surcharge_west_books(order):
    """Books orders shipped to the west region pay a flat 4.00 surcharge.

    Ticket PRC-1092. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "books":
        return round(4.00, 2)
    return 0.0


def rule_093_surcharge_west_sports(order):
    """Sports orders shipped to the west region pay a flat 8.25 surcharge.

    Ticket PRC-1093. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "sports":
        return round(8.25, 2)
    return 0.0


def rule_094_surcharge_west_pet(order):
    """Pet orders shipped to the west region pay a flat 7.75 surcharge.

    Ticket PRC-1094. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "pet":
        return round(7.75, 2)
    return 0.0


def rule_095_surcharge_west_kitchen(order):
    """Kitchen orders shipped to the west region pay a flat 8.50 surcharge.

    Ticket PRC-1095. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "kitchen":
        return round(8.50, 2)
    return 0.0


def rule_096_surcharge_west_lighting(order):
    """Lighting orders shipped to the west region pay a flat 6.00 surcharge.

    Ticket PRC-1096. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "west" and order["category"] == "lighting":
        return round(6.00, 2)
    return 0.0


def rule_097_surcharge_central_stationery(order):
    """Stationery orders shipped to the central region pay a flat 6.00 surcharge.

    Ticket PRC-1097. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "stationery":
        return round(6.00, 2)
    return 0.0


def rule_098_surcharge_central_furniture(order):
    """Furniture orders shipped to the central region pay a flat 7.00 surcharge.

    Ticket PRC-1098. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "furniture":
        return round(7.00, 2)
    return 0.0


def rule_099_surcharge_central_electronics(order):
    """Electronics orders shipped to the central region pay a flat 3.00 surcharge.

    Ticket PRC-1099. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "electronics":
        return round(3.00, 2)
    return 0.0


def rule_100_surcharge_central_grocery(order):
    """Grocery orders shipped to the central region pay a flat 1.25 surcharge.

    Ticket PRC-1100. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "grocery":
        return round(1.25, 2)
    return 0.0


def rule_101_surcharge_central_apparel(order):
    """Apparel orders shipped to the central region pay a flat 3.00 surcharge.

    Ticket PRC-1101. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "apparel":
        return round(3.00, 2)
    return 0.0


def rule_102_surcharge_central_toys(order):
    """Toys orders shipped to the central region pay a flat 7.75 surcharge.

    Ticket PRC-1102. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "toys":
        return round(7.75, 2)
    return 0.0


def rule_103_surcharge_central_garden(order):
    """Garden orders shipped to the central region pay a flat 0.75 surcharge.

    Ticket PRC-1103. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "garden":
        return round(0.75, 2)
    return 0.0


def rule_104_surcharge_central_books(order):
    """Books orders shipped to the central region pay a flat 2.25 surcharge.

    Ticket PRC-1104. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "books":
        return round(2.25, 2)
    return 0.0


def rule_105_surcharge_central_sports(order):
    """Sports orders shipped to the central region pay a flat 3.75 surcharge.

    Ticket PRC-1105. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "sports":
        return round(3.75, 2)
    return 0.0


def rule_106_surcharge_central_pet(order):
    """Pet orders shipped to the central region pay a flat 5.75 surcharge.

    Ticket PRC-1106. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "pet":
        return round(5.75, 2)
    return 0.0


def rule_107_surcharge_central_kitchen(order):
    """Kitchen orders shipped to the central region pay a flat 0.50 surcharge.

    Ticket PRC-1107. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "kitchen":
        return round(0.50, 2)
    return 0.0


def rule_108_surcharge_central_lighting(order):
    """Lighting orders shipped to the central region pay a flat 6.00 surcharge.

    Ticket PRC-1108. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "central" and order["category"] == "lighting":
        return round(6.00, 2)
    return 0.0


def rule_109_surcharge_coastal_stationery(order):
    """Stationery orders shipped to the coastal region pay a flat 7.25 surcharge.

    Ticket PRC-1109. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "stationery":
        return round(7.25, 2)
    return 0.0


def rule_110_surcharge_coastal_furniture(order):
    """Furniture orders shipped to the coastal region pay a flat 0.75 surcharge.

    Ticket PRC-1110. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "furniture":
        return round(0.75, 2)
    return 0.0


def rule_111_surcharge_coastal_electronics(order):
    """Electronics orders shipped to the coastal region pay a flat 0.50 surcharge.

    Ticket PRC-1111. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "electronics":
        return round(0.50, 2)
    return 0.0


def rule_112_surcharge_coastal_grocery(order):
    """Grocery orders shipped to the coastal region pay a flat 5.75 surcharge.

    Ticket PRC-1112. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "grocery":
        return round(5.75, 2)
    return 0.0


def rule_113_surcharge_coastal_apparel(order):
    """Apparel orders shipped to the coastal region pay a flat 3.75 surcharge.

    Ticket PRC-1113. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "apparel":
        return round(3.75, 2)
    return 0.0


def rule_114_surcharge_coastal_toys(order):
    """Toys orders shipped to the coastal region pay a flat 5.25 surcharge.

    Ticket PRC-1114. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "toys":
        return round(5.25, 2)
    return 0.0


def rule_115_surcharge_coastal_garden(order):
    """Garden orders shipped to the coastal region pay a flat 8.50 surcharge.

    Ticket PRC-1115. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "garden":
        return round(8.50, 2)
    return 0.0


def rule_116_surcharge_coastal_books(order):
    """Books orders shipped to the coastal region pay a flat 1.25 surcharge.

    Ticket PRC-1116. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "books":
        return round(1.25, 2)
    return 0.0


def rule_117_surcharge_coastal_sports(order):
    """Sports orders shipped to the coastal region pay a flat 7.25 surcharge.

    Ticket PRC-1117. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "sports":
        return round(7.25, 2)
    return 0.0


def rule_118_surcharge_coastal_pet(order):
    """Pet orders shipped to the coastal region pay a flat 2.75 surcharge.

    Ticket PRC-1118. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "pet":
        return round(2.75, 2)
    return 0.0


def rule_119_surcharge_coastal_kitchen(order):
    """Kitchen orders shipped to the coastal region pay a flat 3.25 surcharge.

    Ticket PRC-1119. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "kitchen":
        return round(3.25, 2)
    return 0.0


def rule_120_surcharge_coastal_lighting(order):
    """Lighting orders shipped to the coastal region pay a flat 6.75 surcharge.

    Ticket PRC-1120. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["region"] == "coastal" and order["category"] == "lighting":
        return round(6.75, 2)
    return 0.0


def rule_121_loyalty_bronze_50(order):
    """Bronze members get 2% off orders of at least 50.

    Ticket PRC-1121. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "bronze" and order["line_total"] >= 50:
        return round(-order["line_total"] * 2 / 100, 2)
    return 0.0


def rule_122_loyalty_bronze_100(order):
    """Bronze members get 4% off orders of at least 100.

    Ticket PRC-1122. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "bronze" and order["line_total"] >= 100:
        return round(-order["line_total"] * 4 / 100, 2)
    return 0.0


def rule_123_loyalty_bronze_250(order):
    """Bronze members get 6% off orders of at least 250.

    Ticket PRC-1123. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "bronze" and order["line_total"] >= 250:
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_124_loyalty_bronze_500(order):
    """Bronze members get 7% off orders of at least 500.

    Ticket PRC-1124. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "bronze" and order["line_total"] >= 500:
        return round(-order["line_total"] * 7 / 100, 2)
    return 0.0


def rule_125_loyalty_bronze_1000(order):
    """Bronze members get 8% off orders of at least 1000.

    Ticket PRC-1125. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "bronze" and order["line_total"] >= 1000:
        return round(-order["line_total"] * 8 / 100, 2)
    return 0.0


def rule_126_loyalty_silver_50(order):
    """Silver members get 2% off orders of at least 50.

    Ticket PRC-1126. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "silver" and order["line_total"] >= 50:
        return round(-order["line_total"] * 2 / 100, 2)
    return 0.0


def rule_127_loyalty_silver_100(order):
    """Silver members get 4% off orders of at least 100.

    Ticket PRC-1127. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "silver" and order["line_total"] >= 100:
        return round(-order["line_total"] * 4 / 100, 2)
    return 0.0


def rule_128_loyalty_silver_250(order):
    """Silver members get 5% off orders of at least 250.

    Ticket PRC-1128. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "silver" and order["line_total"] >= 250:
        return round(-order["line_total"] * 5 / 100, 2)
    return 0.0


def rule_129_loyalty_silver_500(order):
    """Silver members get 9% off orders of at least 500.

    Ticket PRC-1129. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "silver" and order["line_total"] >= 500:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_130_loyalty_silver_1000(order):
    """Silver members get 10% off orders of at least 1000.

    Ticket PRC-1130. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "silver" and order["line_total"] >= 1000:
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_131_loyalty_gold_50(order):
    """Gold members get 1% off orders of at least 50.

    Ticket PRC-1131. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "gold" and order["line_total"] >= 50:
        return round(-order["line_total"] * 1 / 100, 2)
    return 0.0


def rule_132_loyalty_gold_100(order):
    """Gold members get 2% off orders of at least 100.

    Ticket PRC-1132. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "gold" and order["line_total"] >= 100:
        return round(-order["line_total"] * 2 / 100, 2)
    return 0.0


def rule_133_loyalty_gold_250(order):
    """Gold members get 5% off orders of at least 250.

    Ticket PRC-1133. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "gold" and order["line_total"] >= 250:
        return round(-order["line_total"] * 5 / 100, 2)
    return 0.0


def rule_134_loyalty_gold_500(order):
    """Gold members get 8% off orders of at least 500.

    Ticket PRC-1134. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "gold" and order["line_total"] >= 500:
        return round(-order["line_total"] * 8 / 100, 2)
    return 0.0


def rule_135_loyalty_gold_1000(order):
    """Gold members get 9% off orders of at least 1000.

    Ticket PRC-1135. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "gold" and order["line_total"] >= 1000:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_136_loyalty_platinum_50(order):
    """Platinum members get 3% off orders of at least 50.

    Ticket PRC-1136. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "platinum" and order["line_total"] >= 50:
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_137_loyalty_platinum_100(order):
    """Platinum members get 7% off orders of at least 100.

    Ticket PRC-1137. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "platinum" and order["line_total"] >= 100:
        return round(-order["line_total"] * 7 / 100, 2)
    return 0.0


def rule_138_loyalty_platinum_250(order):
    """Platinum members get 8% off orders of at least 250.

    Ticket PRC-1138. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "platinum" and order["line_total"] >= 250:
        return round(-order["line_total"] * 8 / 100, 2)
    return 0.0


def rule_139_loyalty_platinum_500(order):
    """Platinum members get 9% off orders of at least 500.

    Ticket PRC-1139. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "platinum" and order["line_total"] >= 500:
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_140_loyalty_platinum_1000(order):
    """Platinum members get 10% off orders of at least 1000.

    Ticket PRC-1140. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["tier"] == "platinum" and order["line_total"] >= 1000:
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_141_seasonal_01_kitchen(order):
    """During month 1, kitchen orders get 25% off the line total.

    Ticket PRC-1141. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 1 and order["category"] == "kitchen":
        return round(-order["line_total"] * 25 / 100, 2)
    return 0.0


def rule_142_seasonal_01_sports(order):
    """During month 1, sports orders get 19% off the line total.

    Ticket PRC-1142. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 1 and order["category"] == "sports":
        return round(-order["line_total"] * 19 / 100, 2)
    return 0.0


def rule_143_seasonal_01_apparel(order):
    """During month 1, apparel orders get 3% off the line total.

    Ticket PRC-1143. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 1 and order["category"] == "apparel":
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_144_seasonal_01_electronics(order):
    """During month 1, electronics orders get 21% off the line total.

    Ticket PRC-1144. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 1 and order["category"] == "electronics":
        return round(-order["line_total"] * 21 / 100, 2)
    return 0.0


def rule_145_seasonal_01_stationery(order):
    """During month 1, stationery orders get 5% off the line total.

    Ticket PRC-1145. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 1 and order["category"] == "stationery":
        return round(-order["line_total"] * 5 / 100, 2)
    return 0.0


def rule_146_seasonal_02_grocery(order):
    """During month 2, grocery orders get 24% off the line total.

    Ticket PRC-1146. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 2 and order["category"] == "grocery":
        return round(-order["line_total"] * 24 / 100, 2)
    return 0.0


def rule_147_seasonal_02_apparel(order):
    """During month 2, apparel orders get 19% off the line total.

    Ticket PRC-1147. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 2 and order["category"] == "apparel":
        return round(-order["line_total"] * 19 / 100, 2)
    return 0.0


def rule_148_seasonal_02_sports(order):
    """During month 2, sports orders get 20% off the line total.

    Ticket PRC-1148. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 2 and order["category"] == "sports":
        return round(-order["line_total"] * 20 / 100, 2)
    return 0.0


def rule_149_seasonal_02_kitchen(order):
    """During month 2, kitchen orders get 24% off the line total.

    Ticket PRC-1149. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 2 and order["category"] == "kitchen":
        return round(-order["line_total"] * 24 / 100, 2)
    return 0.0


def rule_150_seasonal_02_electronics(order):
    """During month 2, electronics orders get 25% off the line total.

    Ticket PRC-1150. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 2 and order["category"] == "electronics":
        return round(-order["line_total"] * 25 / 100, 2)
    return 0.0


def rule_151_seasonal_03_toys(order):
    """During month 3, toys orders get 27% off the line total.

    Ticket PRC-1151. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 3 and order["category"] == "toys":
        return round(-order["line_total"] * 72 / 100, 2)
    return 0.0


def rule_152_seasonal_03_books(order):
    """During month 3, books orders get 3% off the line total.

    Ticket PRC-1152. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 3 and order["category"] == "books":
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_153_seasonal_03_electronics(order):
    """During month 3, electronics orders get 25% off the line total.

    Ticket PRC-1153. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 3 and order["category"] == "electronics":
        return round(-order["line_total"] * 25 / 100, 2)
    return 0.0


def rule_154_seasonal_03_garden(order):
    """During month 3, garden orders get 16% off the line total.

    Ticket PRC-1154. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 3 and order["category"] == "garden":
        return round(-order["line_total"] * 16 / 100, 2)
    return 0.0


def rule_155_seasonal_03_stationery(order):
    """During month 3, stationery orders get 15% off the line total.

    Ticket PRC-1155. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 3 and order["category"] == "stationery":
        return round(-order["line_total"] * 15 / 100, 2)
    return 0.0


def rule_156_seasonal_04_furniture(order):
    """During month 4, furniture orders get 11% off the line total.

    Ticket PRC-1156. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 4 and order["category"] == "furniture":
        return round(-order["line_total"] * 11 / 100, 2)
    return 0.0


def rule_157_seasonal_04_electronics(order):
    """During month 4, electronics orders get 6% off the line total.

    Ticket PRC-1157. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 4 and order["category"] == "electronics":
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_158_seasonal_04_kitchen(order):
    """During month 4, kitchen orders get 18% off the line total.

    Ticket PRC-1158. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 4 and order["category"] == "kitchen":
        return round(-order["line_total"] * 18 / 100, 2)
    return 0.0


def rule_159_seasonal_04_sports(order):
    """During month 4, sports orders get 18% off the line total.

    Ticket PRC-1159. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 4 and order["category"] == "sports":
        return round(-order["line_total"] * 18 / 100, 2)
    return 0.0


def rule_160_seasonal_04_lighting(order):
    """During month 4, lighting orders get 6% off the line total.

    Ticket PRC-1160. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 4 and order["category"] == "lighting":
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_161_seasonal_05_grocery(order):
    """During month 5, grocery orders get 10% off the line total.

    Ticket PRC-1161. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 5 and order["category"] == "grocery":
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_162_seasonal_05_apparel(order):
    """During month 5, apparel orders get 20% off the line total.

    Ticket PRC-1162. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 5 and order["category"] == "apparel":
        return round(-order["line_total"] * 20 / 100, 2)
    return 0.0


def rule_163_seasonal_05_kitchen(order):
    """During month 5, kitchen orders get 3% off the line total.

    Ticket PRC-1163. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 5 and order["category"] == "kitchen":
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_164_seasonal_05_stationery(order):
    """During month 5, stationery orders get 23% off the line total.

    Ticket PRC-1164. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 5 and order["category"] == "stationery":
        return round(-order["line_total"] * 23 / 100, 2)
    return 0.0


def rule_165_seasonal_05_books(order):
    """During month 5, books orders get 12% off the line total.

    Ticket PRC-1165. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 5 and order["category"] == "books":
        return round(-order["line_total"] * 12 / 100, 2)
    return 0.0


def rule_166_seasonal_06_toys(order):
    """During month 6, toys orders get 3% off the line total.

    Ticket PRC-1166. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 6 and order["category"] == "toys":
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_167_seasonal_06_pet(order):
    """During month 6, pet orders get 19% off the line total.

    Ticket PRC-1167. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 6 and order["category"] == "pet":
        return round(-order["line_total"] * 19 / 100, 2)
    return 0.0


def rule_168_seasonal_06_grocery(order):
    """During month 6, grocery orders get 9% off the line total.

    Ticket PRC-1168. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 6 and order["category"] == "grocery":
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_169_seasonal_06_garden(order):
    """During month 6, garden orders get 11% off the line total.

    Ticket PRC-1169. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 6 and order["category"] == "garden":
        return round(-order["line_total"] * 11 / 100, 2)
    return 0.0


def rule_170_seasonal_06_stationery(order):
    """During month 6, stationery orders get 21% off the line total.

    Ticket PRC-1170. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 6 and order["category"] == "stationery":
        return round(-order["line_total"] * 21 / 100, 2)
    return 0.0


def rule_171_seasonal_07_lighting(order):
    """During month 7, lighting orders get 16% off the line total.

    Ticket PRC-1171. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 7 and order["category"] == "lighting":
        return round(-order["line_total"] * 16 / 100, 2)
    return 0.0


def rule_172_seasonal_07_apparel(order):
    """During month 7, apparel orders get 20% off the line total.

    Ticket PRC-1172. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 7 and order["category"] == "apparel":
        return round(-order["line_total"] * 20 / 100, 2)
    return 0.0


def rule_173_seasonal_07_electronics(order):
    """During month 7, electronics orders get 13% off the line total.

    Ticket PRC-1173. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 7 and order["category"] == "electronics":
        return round(-order["line_total"] * 13 / 100, 2)
    return 0.0


def rule_174_seasonal_07_furniture(order):
    """During month 7, furniture orders get 21% off the line total.

    Ticket PRC-1174. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 7 and order["category"] == "furniture":
        return round(-order["line_total"] * 21 / 100, 2)
    return 0.0


def rule_175_seasonal_07_garden(order):
    """During month 7, garden orders get 19% off the line total.

    Ticket PRC-1175. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 7 and order["category"] == "garden":
        return round(-order["line_total"] * 19 / 100, 2)
    return 0.0


def rule_176_seasonal_08_toys(order):
    """During month 8, toys orders get 15% off the line total.

    Ticket PRC-1176. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 8 and order["category"] == "toys":
        return round(-order["line_total"] * 15 / 100, 2)
    return 0.0


def rule_177_seasonal_08_apparel(order):
    """During month 8, apparel orders get 4% off the line total.

    Ticket PRC-1177. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 8 and order["category"] == "apparel":
        return round(-order["line_total"] * 4 / 100, 2)
    return 0.0


def rule_178_seasonal_08_lighting(order):
    """During month 8, lighting orders get 4% off the line total.

    Ticket PRC-1178. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 8 and order["category"] == "lighting":
        return round(-order["line_total"] * 4 / 100, 2)
    return 0.0


def rule_179_seasonal_08_stationery(order):
    """During month 8, stationery orders get 17% off the line total.

    Ticket PRC-1179. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 8 and order["category"] == "stationery":
        return round(-order["line_total"] * 17 / 100, 2)
    return 0.0


def rule_180_seasonal_08_grocery(order):
    """During month 8, grocery orders get 13% off the line total.

    Ticket PRC-1180. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 8 and order["category"] == "grocery":
        return round(-order["line_total"] * 13 / 100, 2)
    return 0.0


def rule_181_seasonal_09_stationery(order):
    """During month 9, stationery orders get 4% off the line total.

    Ticket PRC-1181. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 9 and order["category"] == "stationery":
        return round(-order["line_total"] * 4 / 100, 2)
    return 0.0


def rule_182_seasonal_09_furniture(order):
    """During month 9, furniture orders get 7% off the line total.

    Ticket PRC-1182. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 9 and order["category"] == "furniture":
        return round(-order["line_total"] * 7 / 100, 2)
    return 0.0


def rule_183_seasonal_09_kitchen(order):
    """During month 9, kitchen orders get 21% off the line total.

    Ticket PRC-1183. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 9 and order["category"] == "kitchen":
        return round(-order["line_total"] * 21 / 100, 2)
    return 0.0


def rule_184_seasonal_09_sports(order):
    """During month 9, sports orders get 22% off the line total.

    Ticket PRC-1184. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 9 and order["category"] == "sports":
        return round(-order["line_total"] * 22 / 100, 2)
    return 0.0


def rule_185_seasonal_09_garden(order):
    """During month 9, garden orders get 7% off the line total.

    Ticket PRC-1185. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 9 and order["category"] == "garden":
        return round(-order["line_total"] * 7 / 100, 2)
    return 0.0


def rule_186_seasonal_10_grocery(order):
    """During month 10, grocery orders get 17% off the line total.

    Ticket PRC-1186. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 10 and order["category"] == "grocery":
        return round(-order["line_total"] * 17 / 100, 2)
    return 0.0


def rule_187_seasonal_10_stationery(order):
    """During month 10, stationery orders get 9% off the line total.

    Ticket PRC-1187. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 10 and order["category"] == "stationery":
        return round(-order["line_total"] * 9 / 100, 2)
    return 0.0


def rule_188_seasonal_10_books(order):
    """During month 10, books orders get 10% off the line total.

    Ticket PRC-1188. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 10 and order["category"] == "books":
        return round(-order["line_total"] * 10 / 100, 2)
    return 0.0


def rule_189_seasonal_10_toys(order):
    """During month 10, toys orders get 5% off the line total.

    Ticket PRC-1189. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 10 and order["category"] == "toys":
        return round(-order["line_total"] * 5 / 100, 2)
    return 0.0


def rule_190_seasonal_10_furniture(order):
    """During month 10, furniture orders get 3% off the line total.

    Ticket PRC-1190. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 10 and order["category"] == "furniture":
        return round(-order["line_total"] * 3 / 100, 2)
    return 0.0


def rule_191_seasonal_11_pet(order):
    """During month 11, pet orders get 12% off the line total.

    Ticket PRC-1191. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 11 and order["category"] == "pet":
        return round(-order["line_total"] * 12 / 100, 2)
    return 0.0


def rule_192_seasonal_11_kitchen(order):
    """During month 11, kitchen orders get 24% off the line total.

    Ticket PRC-1192. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 11 and order["category"] == "kitchen":
        return round(-order["line_total"] * 24 / 100, 2)
    return 0.0


def rule_193_seasonal_11_books(order):
    """During month 11, books orders get 14% off the line total.

    Ticket PRC-1193. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 11 and order["category"] == "books":
        return round(-order["line_total"] * 14 / 100, 2)
    return 0.0


def rule_194_seasonal_11_toys(order):
    """During month 11, toys orders get 18% off the line total.

    Ticket PRC-1194. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 11 and order["category"] == "toys":
        return round(-order["line_total"] * 18 / 100, 2)
    return 0.0


def rule_195_seasonal_11_grocery(order):
    """During month 11, grocery orders get 17% off the line total.

    Ticket PRC-1195. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 11 and order["category"] == "grocery":
        return round(-order["line_total"] * 17 / 100, 2)
    return 0.0


def rule_196_seasonal_12_toys(order):
    """During month 12, toys orders get 12% off the line total.

    Ticket PRC-1196. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 12 and order["category"] == "toys":
        return round(-order["line_total"] * 12 / 100, 2)
    return 0.0


def rule_197_seasonal_12_kitchen(order):
    """During month 12, kitchen orders get 17% off the line total.

    Ticket PRC-1197. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 12 and order["category"] == "kitchen":
        return round(-order["line_total"] * 17 / 100, 2)
    return 0.0


def rule_198_seasonal_12_apparel(order):
    """During month 12, apparel orders get 6% off the line total.

    Ticket PRC-1198. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 12 and order["category"] == "apparel":
        return round(-order["line_total"] * 6 / 100, 2)
    return 0.0


def rule_199_seasonal_12_garden(order):
    """During month 12, garden orders get 4% off the line total.

    Ticket PRC-1199. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 12 and order["category"] == "garden":
        return round(-order["line_total"] * 4 / 100, 2)
    return 0.0


def rule_200_seasonal_12_sports(order):
    """During month 12, sports orders get 22% off the line total.

    Ticket PRC-1200. Stacks with every other rule; the adjustment is rounded to cents.
    """
    if order["month"] == 12 and order["category"] == "sports":
        return round(-order["line_total"] * 22 / 100, 2)
    return 0.0


RULES = [
    rule_001_bulk_stationery_10,
    rule_002_bulk_stationery_25,
    rule_003_bulk_stationery_40,
    rule_004_bulk_stationery_80,
    rule_005_bulk_furniture_10,
    rule_006_bulk_furniture_25,
    rule_007_bulk_furniture_40,
    rule_008_bulk_furniture_80,
    rule_009_bulk_electronics_10,
    rule_010_bulk_electronics_25,
    rule_011_bulk_electronics_40,
    rule_012_bulk_electronics_80,
    rule_013_bulk_grocery_10,
    rule_014_bulk_grocery_25,
    rule_015_bulk_grocery_40,
    rule_016_bulk_grocery_80,
    rule_017_bulk_apparel_10,
    rule_018_bulk_apparel_25,
    rule_019_bulk_apparel_40,
    rule_020_bulk_apparel_80,
    rule_021_bulk_toys_10,
    rule_022_bulk_toys_25,
    rule_023_bulk_toys_40,
    rule_024_bulk_toys_80,
    rule_025_bulk_garden_10,
    rule_026_bulk_garden_25,
    rule_027_bulk_garden_40,
    rule_028_bulk_garden_80,
    rule_029_bulk_books_10,
    rule_030_bulk_books_25,
    rule_031_bulk_books_40,
    rule_032_bulk_books_80,
    rule_033_bulk_sports_10,
    rule_034_bulk_sports_25,
    rule_035_bulk_sports_40,
    rule_036_bulk_sports_80,
    rule_037_bulk_pet_10,
    rule_038_bulk_pet_25,
    rule_039_bulk_pet_40,
    rule_040_bulk_pet_80,
    rule_041_bulk_kitchen_10,
    rule_042_bulk_kitchen_25,
    rule_043_bulk_kitchen_40,
    rule_044_bulk_kitchen_80,
    rule_045_bulk_lighting_10,
    rule_046_bulk_lighting_25,
    rule_047_bulk_lighting_40,
    rule_048_bulk_lighting_80,
    rule_049_surcharge_north_stationery,
    rule_050_surcharge_north_furniture,
    rule_051_surcharge_north_electronics,
    rule_052_surcharge_north_grocery,
    rule_053_surcharge_north_apparel,
    rule_054_surcharge_north_toys,
    rule_055_surcharge_north_garden,
    rule_056_surcharge_north_books,
    rule_057_surcharge_north_sports,
    rule_058_surcharge_north_pet,
    rule_059_surcharge_north_kitchen,
    rule_060_surcharge_north_lighting,
    rule_061_surcharge_south_stationery,
    rule_062_surcharge_south_furniture,
    rule_063_surcharge_south_electronics,
    rule_064_surcharge_south_grocery,
    rule_065_surcharge_south_apparel,
    rule_066_surcharge_south_toys,
    rule_067_surcharge_south_garden,
    rule_068_surcharge_south_books,
    rule_069_surcharge_south_sports,
    rule_070_surcharge_south_pet,
    rule_071_surcharge_south_kitchen,
    rule_072_surcharge_south_lighting,
    rule_073_surcharge_east_stationery,
    rule_074_surcharge_east_furniture,
    rule_075_surcharge_east_electronics,
    rule_076_surcharge_east_grocery,
    rule_077_surcharge_east_apparel,
    rule_078_surcharge_east_toys,
    rule_079_surcharge_east_garden,
    rule_080_surcharge_east_books,
    rule_081_surcharge_east_sports,
    rule_082_surcharge_east_pet,
    rule_083_surcharge_east_kitchen,
    rule_084_surcharge_east_lighting,
    rule_085_surcharge_west_stationery,
    rule_086_surcharge_west_furniture,
    rule_087_surcharge_west_electronics,
    rule_088_surcharge_west_grocery,
    rule_089_surcharge_west_apparel,
    rule_090_surcharge_west_toys,
    rule_091_surcharge_west_garden,
    rule_092_surcharge_west_books,
    rule_093_surcharge_west_sports,
    rule_094_surcharge_west_pet,
    rule_095_surcharge_west_kitchen,
    rule_096_surcharge_west_lighting,
    rule_097_surcharge_central_stationery,
    rule_098_surcharge_central_furniture,
    rule_099_surcharge_central_electronics,
    rule_100_surcharge_central_grocery,
    rule_101_surcharge_central_apparel,
    rule_102_surcharge_central_toys,
    rule_103_surcharge_central_garden,
    rule_104_surcharge_central_books,
    rule_105_surcharge_central_sports,
    rule_106_surcharge_central_pet,
    rule_107_surcharge_central_kitchen,
    rule_108_surcharge_central_lighting,
    rule_109_surcharge_coastal_stationery,
    rule_110_surcharge_coastal_furniture,
    rule_111_surcharge_coastal_electronics,
    rule_112_surcharge_coastal_grocery,
    rule_113_surcharge_coastal_apparel,
    rule_114_surcharge_coastal_toys,
    rule_115_surcharge_coastal_garden,
    rule_116_surcharge_coastal_books,
    rule_117_surcharge_coastal_sports,
    rule_118_surcharge_coastal_pet,
    rule_119_surcharge_coastal_kitchen,
    rule_120_surcharge_coastal_lighting,
    rule_121_loyalty_bronze_50,
    rule_122_loyalty_bronze_100,
    rule_123_loyalty_bronze_250,
    rule_124_loyalty_bronze_500,
    rule_125_loyalty_bronze_1000,
    rule_126_loyalty_silver_50,
    rule_127_loyalty_silver_100,
    rule_128_loyalty_silver_250,
    rule_129_loyalty_silver_500,
    rule_130_loyalty_silver_1000,
    rule_131_loyalty_gold_50,
    rule_132_loyalty_gold_100,
    rule_133_loyalty_gold_250,
    rule_134_loyalty_gold_500,
    rule_135_loyalty_gold_1000,
    rule_136_loyalty_platinum_50,
    rule_137_loyalty_platinum_100,
    rule_138_loyalty_platinum_250,
    rule_139_loyalty_platinum_500,
    rule_140_loyalty_platinum_1000,
    rule_141_seasonal_01_kitchen,
    rule_142_seasonal_01_sports,
    rule_143_seasonal_01_apparel,
    rule_144_seasonal_01_electronics,
    rule_145_seasonal_01_stationery,
    rule_146_seasonal_02_grocery,
    rule_147_seasonal_02_apparel,
    rule_148_seasonal_02_sports,
    rule_149_seasonal_02_kitchen,
    rule_150_seasonal_02_electronics,
    rule_151_seasonal_03_toys,
    rule_152_seasonal_03_books,
    rule_153_seasonal_03_electronics,
    rule_154_seasonal_03_garden,
    rule_155_seasonal_03_stationery,
    rule_156_seasonal_04_furniture,
    rule_157_seasonal_04_electronics,
    rule_158_seasonal_04_kitchen,
    rule_159_seasonal_04_sports,
    rule_160_seasonal_04_lighting,
    rule_161_seasonal_05_grocery,
    rule_162_seasonal_05_apparel,
    rule_163_seasonal_05_kitchen,
    rule_164_seasonal_05_stationery,
    rule_165_seasonal_05_books,
    rule_166_seasonal_06_toys,
    rule_167_seasonal_06_pet,
    rule_168_seasonal_06_grocery,
    rule_169_seasonal_06_garden,
    rule_170_seasonal_06_stationery,
    rule_171_seasonal_07_lighting,
    rule_172_seasonal_07_apparel,
    rule_173_seasonal_07_electronics,
    rule_174_seasonal_07_furniture,
    rule_175_seasonal_07_garden,
    rule_176_seasonal_08_toys,
    rule_177_seasonal_08_apparel,
    rule_178_seasonal_08_lighting,
    rule_179_seasonal_08_stationery,
    rule_180_seasonal_08_grocery,
    rule_181_seasonal_09_stationery,
    rule_182_seasonal_09_furniture,
    rule_183_seasonal_09_kitchen,
    rule_184_seasonal_09_sports,
    rule_185_seasonal_09_garden,
    rule_186_seasonal_10_grocery,
    rule_187_seasonal_10_stationery,
    rule_188_seasonal_10_books,
    rule_189_seasonal_10_toys,
    rule_190_seasonal_10_furniture,
    rule_191_seasonal_11_pet,
    rule_192_seasonal_11_kitchen,
    rule_193_seasonal_11_books,
    rule_194_seasonal_11_toys,
    rule_195_seasonal_11_grocery,
    rule_196_seasonal_12_toys,
    rule_197_seasonal_12_kitchen,
    rule_198_seasonal_12_apparel,
    rule_199_seasonal_12_garden,
    rule_200_seasonal_12_sports,
]


def price_order(order):
    """Final price of one order line, rounded to cents."""
    return round(order["line_total"] + sum(rule(order) for rule in RULES), 2)
