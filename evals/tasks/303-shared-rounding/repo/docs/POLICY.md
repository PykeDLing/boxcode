# Rounding policy

All amounts are integer cents. Two rounding rules are in use and they are not interchangeable.

- **Ledger (interest, fees):** round half to even ("banker's rounding"). Over many postings the half-cent cases
  round up and down equally often, so the books do not drift. 12.5 becomes 12, 13.5 becomes 14, -12.5 becomes -12.
- **Invoices (tax):** round half up, as the tax authority requires. 12.5 becomes 13 and 13.5 becomes 14.
  A credit note is the mirror image of its invoice, so the tax on a negative amount is the negative of the tax on
  the same positive amount: -12.5 becomes -13.
