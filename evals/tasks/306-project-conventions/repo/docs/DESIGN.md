# Design: text tables

Two functions are to be added to `tables.py`. A table is a list of rows, a row is a list of cells, a cell is a `str`.

## render_table(rows, headers=None, align="")

Returns the table as text, lines joined by `"\n"`, with no newline at the end.

1. Every line is `| ` + the cells joined by ` | ` + ` |`. Each cell is padded with `pad` to the width of its
   column, which is the length of the longest cell in that column, header included.
2. With `headers`, the first line is the header row and the second a separator in which each cell is filled with
   `-` to the column width: `| ---- | --- |`. Without `headers` there is neither.
3. `align` has one character per column: `l` (left, the default), `r` (right) or `c` (centre; when the padding
   cannot be split evenly the extra space goes on the right). If `align` is shorter than the number of columns the
   remaining columns are left-aligned. Headers are aligned like their column.
4. `ValueError` is raised if the rows (and `headers`, if given) do not all have the same number of cells, if
   `align` is longer than the number of columns, or if it contains any other character.
5. With no rows and no headers the result is `""`. With headers and no rows it is the header line and the separator.

Example: `render_table([["apple", "3"], ["fig", "12"]], headers=["name", "qty"], align="lr")` is

    | name  | qty |
    | ----- | --- |
    | apple |   3 |
    | fig   |  12 |

## parse_table(text)

Reads text in the format above and returns the rows as a list of lists of cells (headers are returned as the
first row; the separator is dropped).

6. Blank lines (empty or whitespace only) are skipped. Every other line must start with `|` and end with `|` after
   stripping surrounding whitespace, otherwise `ValueError`.
7. Cells are the pieces between the `|` characters, each stripped of surrounding whitespace. An empty cell is `""`.
8. A separator line, one whose cells all consist only of `-` characters (at least one each), is dropped.
9. All remaining rows must have the same number of cells, otherwise `ValueError`. Text without any rows gives `[]`.
