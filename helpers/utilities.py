# -*- coding: utf-8 -*-

"""

Michael D. Troyer

mtroyer@blm.gov
719-269-8587
"""


import arcpy


def blast_my_cache():
    """
    Delete in memory tables and feature classes
    reset to original workspace when done
    """

    # get the original workspace location
    orig_workspace = arcpy.env.workspace
    
    # Set the workspace to in_memory
    arcpy.env.workspace = "in_memory"
    # Delete all in memory feature classes
    fcs = arcpy.ListFeatureClasses()
    if len(fcs) > 0:
        for fc in fcs:
            arcpy.Delete_management(fc)
    # Delete all in memory tables
    tbls = arcpy.ListTables()
    if len(tbls) > 0:
        for tbl in tbls:
            arcpy.Delete_management(tbl)

    # Reset the workspace
    arcpy.env.workspace = orig_workspace


def find_files(folder, ext, prefixes=None):
    """
    Check the input <folder> for files of type <ext> and optionally 
    with a prefix matching one of <prefixes> and return a list of the
    full file paths of each matching file.
    Inputs:
        :folder: str - full file path to a directory
        :ext: str - extenstion file type
        :prefixes: iterable - container of prefixes
            prefixes must be strings or coercable to strings
    """
    if prefixes:
        if not hasattr(prefixes, '__iter__'):
            raise ValueError('prefixes must be a container object')
        try:
            prefixes = [str(prefix) for prefix in prefixes]
        except:
            raise ValueError('Each prefix must be a string or coercible to a string')

    matches = []
    files = os.listdir(folder)
    for f in files:
        if os.path.splitext(f)[1] == ext:
            if prefixes:
                for prefix in prefixes:
                    if f.startswith(prefix):
                        matches.append(os.path.join(folder, f))
                        break
            else:
                matches.append(os.path.join(folder, f))
    return matches


def buildWhereClauseFromList(table, field, valueList):
    """Takes a list of values and constructs a SQL WHERE
    clause to select those values within a given field and table."""

    # Add DBMS-specific field delimiters
    fieldDelimited = arcpy.AddFieldDelimiters(arcpy.Describe(table).path, field)

    # Determine field type
    fieldType = arcpy.ListFields(table, field)[0].type

    # Add single-quotes for string field values
    if str(fieldType) == 'String':
        valueList = ["'%s'" % value for value in valueList]

    # Format WHERE clause in the form of an IN statement
    whereClause = "%s IN(%s)" % (fieldDelimited, ', '.join(map(str, valueList)))
    return whereClause


def get_acres(fc):
    """Check for an acres field in fc - create if doesn't exist or flag for calculation.
       Recalculate acres and return name of acre field"""

    # Add ACRES field to analysis area - check if exists
    field_list = [field.name for field in arcpy.ListFields(fc) if field.name.upper() == "ACRES"]

    # If ACRES/Acres/acres exists in table, flag for calculation instead
    if field_list:
        acre_field = field_list[0] # select the 'acres' variant
    else:
        arcpy.AddField_management(fc, "ACRES", "DOUBLE", 15, 2)
        acre_field = "ACRES"

    arcpy.CalculateField_management(fc, acre_field, "!shape.area@ACRES!", "PYTHON_9.3")
    return acre_field