import copy
import json
from typing import Optional
from xml.sax.saxutils import quoteattr
from distutils import util;
from flask import Blueprint
from flask import abort
from flask import request
from timApp.auth.accesshelper import verify_edit_access
from timApp.plugin.plugin import Plugin
from timApp.util.flask.requesthelper import verify_json_params, get_option
from timApp.util.flask.responsehelper import json_response
from timApp.document.docentry import DocEntry
from timApp.markdown.dumboclient import call_dumbo
from timApp.plugin.timtable.timTableLatex import convert_table

timTable_plugin = Blueprint('timTable_plugin',
                            __name__,
                            url_prefix='/timTable/')

# Reserved words in the TimTable format and other needed constants
TABLE = 'table'
AUTOMD = 'automd'
ROWS = 'rows'
ROW = 'row'
COLUMNS = 'columns'
COLUMN = 'column'
CELL = 'cell'
TYPE = 'type'
TEXT = 'text'
FORMULA = 'formula'
NUMBER = 'number'
DATABLOCK = 'tabledatablock'
CELLS = 'cells'
COL = 'col'
RELATIVE = 'relative'
ASCII_OF_A = 65
ASCII_CHAR_COUNT = 26
MARKUP = 'markup'
DUMBO_PARAMS = '/mdkeys'


# class to enable direct calls from TIM container
class TimTable:
    def __init__(self):
        pass


    @staticmethod
    def prepare_for_dumbo(values):
        return prepare_for_dumbo(values[MARKUP])


    @staticmethod
    def multihtml_direct_call(jsondata):
        return tim_table_multihtml_direct(jsondata)


class RelativeDataBlockValue:
    def __init__(self, row: int, column: int, data: str):
        self.row = row
        self.column = column
        self.data = data

@timTable_plugin.route("reqs/")
@timTable_plugin.route("reqs")
def tim_table_reqs():
    reqs = {
        "type": "embedded",
        "js": [
            # "js/timTable.js"
            # "tim/controllers/qstController",
        ],
        "angularModule": [],
        "multihtml": True,
        "multimd": True,
        "default_automd": True,
    }
    return json_response(reqs)


def tim_table_multihtml_direct(jsondata):
    """
    Directly callable method for getting the HTML of all TimTable plugins.
    :param jsondata: The data of the plugins.
    :return: The data of the plugins converted to HTML.
    """
    multi = []
    for jso in jsondata:
        multi.append(tim_table_get_html(jso, is_review(request)))
    return json.dumps(multi)


@timTable_plugin.route("multihtml/", methods=["POST"])
def tim_table_multihtml():
    """
    Route for getting the HTML of all TimTable plugins in a document.
    :return:
    """
    jsondata = request.get_json()
    multi = []
    for jso in jsondata:
        multi.append(tim_table_get_html(jso, is_review(request)))
    return json_response(multi)


def prepare_multi_for_dumbo(list):
    """
    Prepares multiple TimTables (given in a request) for Dumbo.
    :param list:
    :return:
    """
    for i in range(0, len(list)):
        prepare_for_dumbo(list[i][MARKUP])


def tim_table_get_html(jso, review):
    """
    Returns the HTML of a single TimTable paragraph.
    :param jso:
    :param review:
    :return:
    """
    values = jso[MARKUP]
    attrs = json.dumps(values)
    runner = 'tim-table'
    s = f'<{runner} data={quoteattr(attrs)}></{runner}>'
    return s


@timTable_plugin.route("multimd/", methods=["POST"])
def tim_table_multimd():
    """
    Handles latex printing.
    :return: Table as latex.
    """
    jsondata = request.get_json()
    multi = []
    for jso in jsondata:
        tbl = jso[MARKUP][TABLE]
        latexTable = str(convert_table(tbl))
        multi.append(latexTable)
    return json_response(multi)


@timTable_plugin.route("getCellData", methods=["GET"])
def tim_table_get_cell_data():
    """
    Route for getting the content of a cell.
    :return: The cell content in the specified index.
    """
    multi = []
    args = request.args
    doc_id = get_option(request, 'docId', None, cast=int)
    if not doc_id:
        abort(400)
    doc = DocEntry.find_by_id(doc_id)
    if not doc:
        abort(404)
    verify_edit_access(doc)
    par = doc.document.get_paragraph(args['parId'])
    plug = Plugin.from_paragraph(par)
    yaml = plug.values
    cell_cnt = None
    if is_datablock(yaml):
        cell_cnt = find_cell_from_datablock(yaml[TABLE][DATABLOCK][CELLS], int(args[ROW]), int(args[COL]))
    if cell_cnt is not None:
        multi.append(cell_cnt)
    else:
        rows = yaml[TABLE][ROWS]
        cell_content = find_cell(rows,int(args['row']),int(args['col']))
        multi.append(cell_content)
    return json_response(multi)


@timTable_plugin.route("saveCell", methods=["POST"])
def tim_table_save_cell_list():
    """
    Saves cell content
    :return: The cell content as html
    """
    multi = []
    cell_content, docid, parid, row, col = verify_json_params('cellContent', 'docId', 'parId', 'row', 'col')
    d, plug = get_plugin_from_paragraph(docid, parid)
    verify_edit_access(d)
    yaml = plug.values
    if is_datablock(yaml):
        save_cell(yaml[TABLE][DATABLOCK], row, col, cell_content)
    else:
        create_datablock(yaml[TABLE])
        save_cell(yaml[TABLE][DATABLOCK], row, col, cell_content)

    cc = str(cell_content)
    if plug.is_automd_enabled() and not cc.startswith('md:'):
        cc = 'md: ' + cc
    html = call_dumbo([cc], DUMBO_PARAMS)
    plug.save()
    multi.append(html[0])
    return json_response(multi)


@timTable_plugin.route("addRow", methods=["POST"])
def tim_table_add_row():
    """
    Adds a row into the table.
    :return: The entire table's data after the row has been added.
    """
    doc_id, par_id = verify_json_params('docId', 'parId')
    d, plug = get_plugin_from_paragraph(doc_id, par_id)
    verify_edit_access(d)
    try:
        rows = plug.values[TABLE][ROWS]
    except KeyError:
        return abort(400)
    # clone the previous row's data into the new row but remove the cell content
    copy_row = copy.deepcopy(rows[-1])
    rows.append(copy_row)
    # rows.append({'row': copy.deepcopy(rows[-1]['row'])})
    row = rows[-1]['row']
    for i in range(len(row)):
        if isinstance(row[i], str) or isinstance(row[i], int) or isinstance(row[i], bool) \
                or isinstance(row[i], float):
            row[i] = {CELL: ''}
        else:
            row[i][CELL] = ''
    plug.save()
    return json_response(prepare_for_and_call_dumbo(plug))


@timTable_plugin.route("addColumn", methods=["POST"])
def tim_table_add_column():
    """
    Adds a new cell into each row on the table.
    In other words, adds a column into the table.
    :return: The entire table's data after the column has been added.
    """
    doc_id, par_id = verify_json_params('docId', 'parId')
    d, plug = get_plugin_from_paragraph(doc_id, par_id)
    verify_edit_access(d)
    try:
        rows = plug.values[TABLE][ROWS]
    except KeyError:
        return abort(400)
    for row in rows:
        try:
            current_row = row[ROW]
        except KeyError:
            return abort(400)
        last_cell = current_row[-1]
        if isinstance(last_cell, str) or isinstance(last_cell, int) or isinstance(last_cell, bool) \
                or isinstance(last_cell, float):
            current_row.append({CELL: ""})
        else:
            # Copy the last cell's other properties for the new cell, but leave the text empty
            new_cell = copy.deepcopy(last_cell)
            new_cell[CELL] = ''
            current_row.append(new_cell)
        
    plug.save()
    return json_response(prepare_for_and_call_dumbo(plug))


@timTable_plugin.route("removeRow", methods=["POST"])
def tim_table_remove_row():
    """
    Removes a row from the table.
    :return: The entire table's data after the row has been removed.
    """
    doc_id, par_id, row_id = verify_json_params('docId', 'parId', 'rowId')
    d, plug = get_plugin_from_paragraph(doc_id, par_id)
    verify_edit_access(d)
    try:
        rows = plug.values[TABLE][ROWS]
    except KeyError:
        return abort(400)

    if len(rows) <= row_id:
        return abort(400)
    rows.pop(row_id)

    if is_datablock(plug.values):
        datablock_entries = construct_datablock_entry_list_from_yaml(plug)
        new_datablock_entries = []
        for entry in datablock_entries:
            if entry.row == row_id:
                continue

            if entry.row > row_id:
                entry.row -= 1
            new_datablock_entries.append(entry)
        plug.values[TABLE][DATABLOCK] = create_datablock_from_entry_list(new_datablock_entries)

    plug.save()
    return json_response(prepare_for_and_call_dumbo(plug))


def get_plugin_from_paragraph(doc_id, par_id):
    d = DocEntry.find_by_id(doc_id)
    if not d:
        abort(404)
    verify_edit_access(d)
    par = d.document_as_current_user.get_paragraph(par_id)
    return d, Plugin.from_paragraph(par)


def is_datablock(yaml: dict) -> bool:
    """
    Checks if tableDataBlock exists
    :param yaml:
    :return: Boolean indicating the existance of tabledatablock
    """
    try:
        if yaml[TABLE][DATABLOCK]:
            return True
        else:
            return False
    except KeyError:
        return False


def create_datablock(table: dict):
    """
    Creates tableDatablock
    :param table:
    :return:
    """
    table[DATABLOCK] = {}
    table[DATABLOCK][TYPE] = 'relative'
    table[DATABLOCK][CELLS] = {}


def save_cell(datablock: dict, row: int, col: int, cell_content: str):
    """
    Updates datablock with the content and the coordinate of a cell.
    :param datablock:
    :param row: Row index
    :param col: Column index
    :param cell_content: Cell content
    :return:
    """
    coordinate = colnum_to_letters(col) + str(row+1)
    try:
        datablock['cells'].update({coordinate: cell_content})
    except:
        pass


def find_cell(rows: list, row: int, col: int) -> str:
    """
    Get cell from index place if exists
    :param rows: List of cells
    :param row: Row index
    :param col: Column index
    :return: Cell from specified index
    """
    right_row = rows[row][ROW]
    right_cell = right_row[col]
    if isinstance(right_cell, str) or isinstance(right_cell, int) or isinstance(right_cell, float):
       return right_cell
    return right_cell[CELL]


def find_cell_from_datablock(cells: dict, row: int, col: int) -> Optional[str]:
    """
    Finds cell from datablock
    :param cells: all cells
    :param row: Row index
    :param col: Column index
    :return: cell if exists
    """
    ret = None
    coordinate = colnum_to_letters(col) + str(row+1)
    try:
        value = cells[coordinate]
        ret = value
    except KeyError:
        pass
    return ret


def colnum_to_letters(column_index: int) -> str:
    """
    Transforms column index to letter
    :param column_index: ex. 2
    :return: column index as letter
    """
    last_char = chr(ASCII_OF_A + (column_index % ASCII_CHAR_COUNT))
    remainder = column_index // ASCII_CHAR_COUNT

    if remainder == 0:
        return last_char
    elif remainder <= ASCII_CHAR_COUNT:
        return chr(ASCII_OF_A + remainder - 1) + last_char

    # recursive call to figure out the rest of the letters
    return colnum_to_letters(remainder - 1) + last_char


def datablock_key_to_indexes(datablock_key: str) -> (int, int):
    """
    Gets the column and row indexes from a single relative datablock entry.
    :param datablock_key: The entry in the relative datablock.
    :return: Column and row indexes in a tuple.
    """

    # get the letter part from the datablock key, for example AB12 -> AB
    columnstring = ""
    for c in datablock_key:
        if c.isalpha():
            columnstring += c
        else:
            break

    rowstring = datablock_key[len(columnstring):]
    row_index = int(rowstring)

    chr_index = len(columnstring) - 1
    column_index = 0
    for c in columnstring.encode('ascii'):
        # ascii encoding returns a list of bytes, so we can use c directly
        addition = ((ASCII_CHAR_COUNT**chr_index) * (c - ASCII_OF_A)) + 1
        column_index += addition
    return column_index - 1, row_index - 1


def is_review(request):
    """
    Check if request is review
    :param request:
    :return:
    """
    result = request.full_path.find("review=") >= 0
    return result


def prepare_for_and_call_dumbo(plug: Plugin):
    """
    Prepares the table's markdown for Dumbo conversion and
    runs it through Dumbo.
    :param values: The plugin paragraph's markdown.
    :return: The conversion result from Dumbo.
    """
    if plug.is_automd_enabled():
        return call_dumbo(prepare_for_dumbo(plug.values), DUMBO_PARAMS)

    return call_dumbo(plug.values, DUMBO_PARAMS)


def prepare_for_dumbo(values):
    """
    Prepares the table's markdown for Dumbo conversion when automd is enabled.
    :param values: The plugin paragraph's markdown.
    :return: The table's markdown, prepared for dumbo conversion.
    """

    try:
        rows = values[TABLE][ROWS]
    except KeyError:
        return values

    # regular row data
    for row in rows:
        rowdata = row[ROW]
        for i in range(len(rowdata)):
            cell = rowdata[i]
            if is_of_unconvertible_type(cell):
                    continue

            if isinstance(cell, str):
                if cell.startswith('md:'):
                    continue
                rowdata[i] = 'md: ' + cell
            else:
                cell[CELL] = 'md: ' + cell[CELL]

    # datablock
    data_block = None
    try:
        data_block = values[TABLE][DATABLOCK][CELLS]
    except KeyError:
        pass

    if data_block is not None:
        for key, value in data_block.items():
            if isinstance(value, str) and not value.startswith('md:'):
                data_block[key] = 'md: ' + value

    return values


def is_of_unconvertible_type(value):
    return isinstance(value, int) or isinstance(value, bool) or isinstance(value, float)


def construct_datablock_entry_list_from_yaml(plug: Plugin) -> list:
    """
    Parses a relative datablock and returns its data as a list of
    RelativeDataBlockValue instances.
    :param plug: The plugin instance.
    :return: A list of RelativeDataBlockValues.
    """
    try:
        values = plug.values[TABLE][DATABLOCK][CELLS]
    except KeyError:
        return []

    final_list = []
    for key, value in values.items():
        column_index, row_index = datablock_key_to_indexes(key)
        final_list.append(RelativeDataBlockValue(row_index, column_index, value))
    return final_list


def create_datablock_from_entry_list(relative_data_block_values: list) -> dict:
    """
    Creates the datablock from a list of RelativeDataBlockValues.
    :param relative_data_block_values: The list of RelativeDataBlockValues.
    :return: The datablock as a dict.
    """
    cells = {}

    for entry in relative_data_block_values:
        key = colnum_to_letters(entry.column) + str(entry.row + 1)
        cells[key] = entry.data

    datablock = {}
    datablock[CELLS] = cells
    datablock[TYPE] = RELATIVE
    return datablock