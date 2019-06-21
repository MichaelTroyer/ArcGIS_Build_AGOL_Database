# -*- coding: utf-8 -*-

"""
Author:
Michael Troyer

Date:
12/19/2017 (updated: 6/18/2019)


### Purpose: ###
Build a file geodatabase from template files.
This tool streamlines the production of a file geodatabase using 
template files that are readily modifiable by non-technical staff.
Allows the end users to interact with the schema tables instead of 
database creation dialogs in Arcmap and systematizes the database production
process.


Inputs:
    * Output file geodatabase location  [path]
    * Output file geodatabase name      [string]
    * Input template files directory    [path]

Outputs:
    * File geodatabase                  [file geodatabase]


### Process: ###

01. Create empty file geodatabase
    - User defined name and location

02. Add user domains to database from domain csv tables
    - Must have the <dmn_> prefix
    - Must have <code> and <description> columns
    - Will be named according to file name

03. Create non-spatial tables from schema csv tables
    - Must have the <tbl_> prefix
    - Must have columns for describing each table attribute:
        NAME, ALIAS, TYPE, LENGTH, PRECISION, SCALE,
        DEFAULT, DOMAIN, EDITABLE, ISNULLABLE, REQUIRED
    - Will be named according to file name without <tbl_> prefix

04. Create feature classes from schema csv tables
    - Must have <point_, multipoint_, polyline_, or polygon_> prefix
    - Must have columns for describing each feature class attribute:
        NAME, ALIAS, TYPE, LENGTH, PRECISION, SCALE,
        DEFAULT, DOMAIN, EDITABLE, ISNULLABLE, REQUIRED
    - Will be named according to file name without <point_, line_, or polygon_> prefix

05. Add relationship classes from relationship class mapping csv
    - Must be titled rel_mapping.csv
    - Must have columns for describing each relationship class attribute:
        NAME, TYPE, ORIGIN_TABLE, DESTINATION_TABLE,
        ORIGIN_PK, ORIGIN_FK, DESTINATION_PK, DESTINATION_FK,
        FORWARD_LABEL, BACKWARD_LABEL, MESSAGE_DIRECTION, ATTRIBUTED

06. Add Attachments from attachments csv table
    - Must be title attachments.csv
    - Must have <name> column for feature class or table to add attachments        

07. Enable Edit Tracking from edit_tracking csv table
    - Must be title edit_tracking.csv
    - Must have <name> column for feature class or table to enable edit tracking       
  
08. Add ESRI Collector fields and domains to point feature classes
    - Must be titled esri_collector.csv
    - Must have <name> column for point feature classes to add ESRI fields/domains
"""

#TODO: what happens when GLOBALID field already exists (skip in create step?)
#TODO: what happens when __ATTACH tables aready exist (skip in create step?)
#TODO: what happens when tracking fields already exist (skip in create step?)
#TODO: what happens when collector fields/domains already exist (skip in create step?)

#TODO: add support for topologies?

import csv
import datetime
import getpass
import os
import sys
import traceback

import arcpy

from helpers import utilities
from helpers import esri_gnss


arcpy.env.addOutputsToMap = False
arcpy.env.overwriteOutput = True


class Toolbox(object):
    def __init__(self):
        self.label = "Database_Builder"
        self.alias = "database_builder"
        self.tools = [BuildDatabase]


class BuildDatabase(object):
    def __init__(self):
        self.label = "Build Geodatabase from Template Files"
        self.description = "Build Geodatabase from Template Files"
        self.canRunInBackground = True 

    def getParameterInfo(self):
        out_gdb = arcpy.Parameter(
            displayName="Output File Geodatabase Location",
            name="Output_Location",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        out_name = arcpy.Parameter(
            displayName="Output File Geodatabase Name",
            name="Output_Name",
            datatype="String",
            parameterType="Required",
            direction="Input")
        
        temp_dir = arcpy.Parameter(
            displayName="Template Files Directory",
            name="Template_Directory",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        
        params = [out_gdb, out_name, temp_dir]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
        return

    def updateMessages(self, params):
        return

    def execute(self, params, messages):
        
        try:
            start_time = datetime.datetime.now()
            user = getpass.getuser()

            gdb_dir  = params[0].valueAsText
            gdb_name = params[1].valueAsText
            gdb_name = gdb_name + '.gdb' if not gdb_name.endswith('.gdb') else gdb_name
            gdb_path = os.path.join(gdb_dir, gdb_name)
            template_dir = params[2].valueAsText

            spatial_ref = utilities.find_files(template_dir, '.prj')[0]

            ### Step 01. Create empty file geodatabase
            arcpy.CreateFileGDB_management(gdb_dir, gdb_name, "10.0")
            arcpy.env.workspace = gdb_path
        
            ### Step 02. Add user domains to database from domain csv tables
            # All domain source tables must have 'code' and 'description' fields   
            domain_csvs = utilities.find_files(template_dir, '.csv', 'dmn_')

            for domain_csv in domain_csvs:
                # Get the basename less the extension
                domain_name = os.path.splitext(os.path.basename(domain_csv))[0]
                
                arcpy.TableToDomain_management(
                    in_table=domain_csv,
                    code_field='code',
                    description_field='description',
                    in_workspace=gdb_path,
                    domain_name=domain_name
                    )           

            ### Step 3: Create non-spatial tables
            tbl_csvs = utilities.find_files(template_dir, '.csv', 'tbl_')
            for tbl_csv in tbl_csvs:
                # Get the basename less the extension and <tbl_>
                tbl_name = os.path.splitext(os.path.basename(tbl_csv))[0].replace('tbl_', '')

                # Create the table
                arcpy.CreateTable_management(
                    out_path=gdb_path,
                    out_name=fc_name,
                    )

                # Add the fields
                with open(tbl_csv, 'r') as f:
                    csv_reader = csv.reader(f)
                    headers = next(csv_reader)[1:]
                    for row in csv_reader:
                        attribute_desc = {header: value for header, value in zip(headers, row)}
                        arcpy.AddField_management(
                            in_table=os.path.join(gdb_path, tbl_name),
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

            ### Step 4: Create feature classes
            fc_csvs = utilities.find_files(template_dir, '.csv', 'fc_')
            for fc_csv in fc_csvs:
                # Get the basename less the extension and <fc_>
                fc_name = os.path.splitext(os.path.basename(fc_csv))[0].replace('fc_', '')

                # Get the geometry type:
                for geo_type in ['POINT', 'MULTIPOINT', 'POLYLINE', 'POLYGON']:
                    if fc_name.upper().startswith(geo_type):
                        fc_name = fc_name.replace(geo_type, '')
                        break

                # Create the feature class
                arcpy.CreateFeatureclass_management(
                    out_path=gdb_path,
                    out_name=fc_name,
                    geometry_type=geo_type,
                    spatial_reference=spatial_ref
                    )

                # Add the fields
                with open(fc_csv, 'r') as f:
                    csv_reader = csv.reader(f)
                    headers = next(csv_reader)[1:]
                    for row in csv_reader:
                        attribute_desc = {header: value for header, value in zip(headers, row)}
                        arcpy.AddField_management(
                            in_table=os.path.join(gdb_path, fc_name),
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

                
                # 3a: Add the ESRI fields to point(s) fcs only
                # if esri_collector:
                    # check_and_create_domains(geodatabase)
                if geo_type == 'Point':
                    gnss.add_gnss_fields(fc_name)

                # 3b: Add Global ID
                arcpy.AddGlobalIDs_management(fc_name)
                
                # 3c: Enable attachments
                arcpy.EnableAttachments_management(fc_name)


        except:
            arcpy.AddMessage(traceback.format_exc())
            
        finally:
            end_time = datetime.datetime.now()
            arcpy.AddMessage("End Time: {}".format(end_time))
            arcpy.AddMessage("Time Elapsed: {}".format(end_time - start_time))
            utilities.blast_my_cache()
            
        return



            # domains_map = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
            #                if f == 'domain_map.csv'][0]
            # template_gdb = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
            #                 if f.startswith('src') and f.endswith('.gdb')][0]
            # arcpy.env.workspace = os.path.join(temp_dir, template_gdb)
            # template_fcs = [os.path.join(template_gdb, fc) for fc in arcpy.ListFeatureClasses()]

            # # 2a: Create the ESRI domains
            # gnss.check_and_create_domains(gdb_path)
