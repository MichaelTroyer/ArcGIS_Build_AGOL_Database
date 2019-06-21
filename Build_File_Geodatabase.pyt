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
    - Must be titled relationship_classes.csv
    - Must have columns for describing each relationship class attribute:
        NAME, TYPE, ORIGIN_TABLE, DESTINATION_TABLE, CARDINALITY
        ORIGIN_PK, ORIGIN_FK, DESTINATION_PK, DESTINATION_FK,
        FORWARD_LABEL, BACKWARD_LABEL, MESSAGE_DIRECTION, ATTRIBUTED

06. Add Attachments from attachments csv table
    - Must be title add_attachments.csv
    - Must have <name> column for feature class or table to add attachments        

07. Enable Edit Tracking from edit_tracking csv table
    - Must be title add_edit_tracking.csv
    - Must have <name> column for feature class or table to enable edit tracking       

08. Add GLOBALID fields to tables and feature classes
    - Must be titled add_globals.csv
    - Must have <name> column for tables and feature classes to add GLOBALIDs

09. Add ESRI Collector fields and domains to point feature classes
    - Must be titled add_esri_collector.csv
    - Must have <name> column for point feature classes to add ESRI fields/domains
"""

#TODO: Select a projection dialog
#TODO: target an existing database/feature dataset

#TODO: what happens when GLOBALID field already exists (skip in create step?)
#TODO: what happens when __ATTACH tables aready exist (skip in create step?)
#TODO: what happens when tracking fields already exist (skip in create step?)
#TODO: what happens when collector fields/domains already exist (skip in create step?)

#TODO: add support for subtypes
#TODO: add support for topologies


import csv
import datetime
import getpass
import os
import re
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

########### Step 01. Create empty file geodatabase
            arcpy.AddMessage('Creating Geodatabase: {}'.format(gdb_path))
            arcpy.CreateFileGDB_management(gdb_dir, gdb_name, "10.0")
            arcpy.env.workspace = gdb_path
        
########### Step 02. Add user domains to database from domain csv tables
            domain_csvs = utilities.find_files(template_dir, '.csv', 'dmn_')

            for domain_csv in domain_csvs:
                # Get the basename less the extension
                domain_name = os.path.splitext(os.path.basename(domain_csv))[0]
                arcpy.AddMessage('Adding Domain: {}'.format(domain_name))

                # All domain source tables must have 'code' and 'description' fields
                arcpy.TableToDomain_management(
                    in_table=domain_csv,
                    code_field='code',
                    description_field='description',
                    in_workspace=gdb_path,
                    domain_name=domain_name,
                    domain_description=domain_name.replace('dmn_', ''),
                    )           

########### Step 03: Create non-spatial tables from schema csv tables
            tbl_csvs = utilities.find_files(template_dir, '.csv', 'tbl_')
            for tbl_csv in tbl_csvs:
                # Get the basename less the extension and <tbl_>
                tbl_name = os.path.splitext(os.path.basename(tbl_csv))[0].replace('tbl_', '')
                arcpy.AddMessage('Adding Table: {}'.format(tbl_name))

                # Create the table
                arcpy.CreateTable_management(
                    out_path=gdb_path,
                    out_name=tbl_name,
                    )

                # Add the fields
                utilities.add_fields_from_csv(tbl_csv, os.path.join(gdb_path, tbl_name))

########### Step 04: Create feature classes from schema csv tables
            fc_csvs = utilities.find_files(template_dir, '.csv', 'fc_')
            for fc_csv in fc_csvs:
                # Get the basename less the extension and <fc_>
                fc_name = os.path.splitext(os.path.basename(fc_csv))[0].replace('fc_', '')

                # Get the geometry type:
                geo_types = ['POINT', 'MULTIPOINT', 'POLYLINE', 'POLYGON']
                for geo_type in geo_types:
                    if fc_name.upper().startswith(geo_type):
                        break
                    else: geo_type = None  # Reset so we don't carry from previous loop

                # Create the feature class - strip the geo_type
                fc_name = re.sub(geo_type+'_', '', fc_name, flags=re.IGNORECASE)
                arcpy.AddMessage('Adding Feature Class: {}'.format(fc_name))
                arcpy.CreateFeatureclass_management(
                    out_path=gdb_path,
                    out_name=fc_name,
                    geometry_type=geo_type,
                    spatial_reference=spatial_ref,
                    )

                # Add the fields
                utilities.add_fields_from_csv(fc_csv, os.path.join(gdb_path, fc_name))
                
########### Step 05. Add relationship classes from relationship class mapping csv
            rc_csv = os.path.join(template_dir, 'relationship_classes.csv')
            if os.path.exists(rc_csv):
                with open(rc_csv, 'r') as f:
                    csv_reader = csv.reader(f)
                    headers = next(csv_reader)
                    for row in csv_reader:
                        rc_desc = {header: value for header, value in zip(headers, row)}
                        arcpy.AddMessage('Creating Relationship Class: {}'.format(rc_desc['NAME']))
                        arcpy.CreateRelationshipClass_management(
                            origin_table=rc_desc['ORIGIN_TABLE'],
                            destination_table=rc_desc['DESTINATION_TABLE'],
                            out_relationship_class=rc_desc['NAME'],
                            relationship_type=rc_desc['TYPE'],
                            forward_label=rc_desc['FORWARD_LABEL'],
                            backward_label=rc_desc['BACKWARD_LABEL'],
                            message_direction=rc_desc['MESSAGE_DIRECTION'],
                            cardinality=rc_desc['CARDINALITY'],
                            attributed=rc_desc['ATTRIBUTED'],
                            origin_primary_key=rc_desc['ORIGIN_PK'],
                            origin_foreign_key=rc_desc['ORIGIN_FK'],
                            destination_primary_key=rc_desc['DESTINATION_PK'],
                            destination_foreign_key=rc_desc['DESTINATION_FK'],
                            )

########### Step 06. Add Attachments from attachments csv table
            attach_csv = os.path.join(template_dir, 'add_attachments.csv')
            if os.path.exists(attach_csv):
                with open(attach_csv, 'r') as f:
                    csv_reader = csv.reader(f)
                    # Skip the header
                    csv_reader.next()
                    attachments = [os.path.join(gdb_path, name[0]) for name in csv_reader]
                for name in attachments:
                    arcpy.AddMessage('Adding Attachments to: {}'.format(os.path.basename(name)))
                    arcpy.EnableAttachments_management(name)


########### Step 07. Enable Edit Tracking from edit_tracking csv table   
            tracking_csv = os.path.join(template_dir, 'add_edit_tracking.csv')
            if os.path.exists(tracking_csv):
                with open(tracking_csv, 'r') as f:
                    csv_reader = csv.reader(f)
                    # Skip the header
                    csv_reader.next()
                    trackings = [os.path.join(gdb_path, name[0]) for name in csv_reader]
                for name in trackings:
                    arcpy.AddMessage('Enabling Edit Tracking on: {}'.format(os.path.basename(name)))
                    arcpy.EnableEditorTracking_management(
                        in_dataset=name,
                        creator_field='created_by',
                        creation_date_field='created_date',
                        last_editor_field='last_edited_by',
                        last_edit_date_field='last_edited_date',
                        add_fields='ADD_FIELDS',
                        record_dates_in='UTC',
                        )

########### Step 08. Add GLOBALID fields to tables and feature classes from globals csv table
            globals_csv = os.path.join(template_dir, 'add_globals.csv')
            if os.path.exists(globals_csv):
                with open(globals_csv, 'r') as f:
                    csv_reader = csv.reader(f)
                    # Skip the header
                    csv_reader.next()
                    add_globals = [os.path.join(gdb_path, name[0]) for name in csv_reader]
                for name in add_globals:
                    arcpy.AddMessage('Adding GlobalIDs to: {}'.format(os.path.basename(name)))
                    arcpy.AddGlobalIDs_management(name)

########### Step 09. Add ESRI Collector fields and domains to point feature classes
            collector_csv = os.path.join(template_dir, 'add_esri_collector.csv')
            if os.path.exists(collector_csv):
                with open(collector_csv, 'r') as f:
                    csv_reader = csv.reader(f)
                    # Skip the header
                    csv_reader.next()
                    collectors = [os.path.join(gdb_path, name[0]) for name in csv_reader]
                for name in collectors:
                    arcpy.AddMessage('Adding Collector Fields to: {}'.format(os.path.basename(name)))
                    esri_gnss.add_gnss_fields(name)

        except:
            arcpy.AddError(traceback.format_exc())
            
        finally:
            end_time = datetime.datetime.now()
            arcpy.AddMessage("End Time: {}".format(end_time))
            arcpy.AddMessage("Time Elapsed: {}".format(end_time - start_time))
            utilities.blast_my_cache()
            
        return
