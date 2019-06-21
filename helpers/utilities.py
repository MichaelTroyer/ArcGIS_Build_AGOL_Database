# -*- coding: utf-8 -*-

"""

Michael D. Troyer

mtroyer@blm.gov
719-269-8587
"""


import csv
import os
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


def find_files(folder, ext, prefix=None):
    """
    Check the input <folder> for files of type <ext> and optionally matching
    <prefix> and return a list of the full file paths of each matching file.
    Inputs:
        :folder:    str - full file path to a directory
        :ext:       str - extension file type
        :prefix:    str - prefix to match
    """
    matches = []
    files = os.listdir(folder)
    for f in files:
        if os.path.splitext(f)[1] == ext:
            if prefix:
                if f.startswith(prefix):
                    matches.append(os.path.join(folder, f))
            else:
                matches.append(os.path.join(folder, f))
    return matches


def add_fields_from_csv(csv_file, target):
    """
    Reads a csv file for feature class or table attribute data and add attribute fields.
    """
    with open(csv_file, 'r') as f:
        csv_reader = csv.reader(f)
        headers = next(csv_reader)
        for row in csv_reader:
            attribute_desc = {header: value for header, value in zip(headers, row)}
            arcpy.AddField_management(
                in_table=target,
                field_name=attribute_desc['NAME'],
                field_type=attribute_desc['TYPE'],
                field_precision=attribute_desc['PRECISION'],
                field_scale=attribute_desc['SCALE'],
                field_length=attribute_desc['LENGTH'],
                field_alias=attribute_desc['ALIAS'],
                field_is_nullable=attribute_desc['ISNULLABLE'],
                field_is_required=attribute_desc['REQUIRED'],
                field_domain=attribute_desc['DOMAIN'],
                )