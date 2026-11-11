# API

### column_widths

`column_widths(rows)` returns the width of each column: the length of its longest cell.

### pad

`pad(cell, width, align="l")` pads a cell with spaces to `width` characters.

### parse_table

`parse_table(text)` reads a table written by `render_table` and returns its rows; the separator line is dropped.

### render_table

`render_table(rows, headers=None, align="")` renders rows as a text table with optional headers and per-column alignment.
