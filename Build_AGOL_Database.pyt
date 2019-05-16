# -*- coding: utf-8 -*-


"""
Author:
Michael Troyer

Date:
12/19/2017

Purpose:
Build an AGOL database:
    1. Create file geodatabase
    2. Add domains to database
        a. Add user domains
        a. Add ESRI domains
    3. Create feature classes from templates
        a. Add ESRI fields
        b. Add Global IDs
        c. Enable Attachments
    4. Assign domains
    5. Profit

TODO: Figure out step 5..
      Also explain how this shit works..

#####################
#    __       __    #
#      \(''/)/      #
#                   #
#####################
"""


import csv
import os
import sys
import traceback

import arcpy
import getpass

sys.path.append(r'T:\CO\GIS\gistools\tools\Cultural\z_other_tools')
from gis_modules import utilities
from gis_modules.add_gnss_fields import check_and_create_domains, add_gnss_fields


arcpy.env.addOutputsToMap = False
arcpy.env.overwriteOutput = True


class Toolbox(object):
    def __init__(self):
        self.label = "AGOL_Database_Builder"
        self.alias = "agol_database_builder"
        self.tools = [BuildDatabase]


class BuildDatabase(object):
    def __init__(self):
        self.label = "Build_Database"
        self.description = "Build AGOL Database"
        self.canRunInBackground = True 

    def getParameterInfo(self):
        out_DB = arcpy.Parameter(
            displayName="Output File Geodatabase Location",
            name="Out_Location",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        out_name = arcpy.Parameter(
            displayName="Output File Geodatabase Name",
            name="Out_Name",
            datatype="String",
            parameterType="Required",
            direction="Input")
        
        temp_dir = arcpy.Parameter(
            displayName="Template Directory [gdb/fc + domain .csv files]",
            name="Temp_Dir",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        
        params = [out_DB, out_name, temp_dir]
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
            temp_dir = params[2].valueAsText
            gdb_path = os.path.join(gdb_dir, gdb_name)

            # Get the input csvs, projection file, and template database
            # Will use the first template database and projection file found!
            spatial_ref = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                           if f.endswith('.prj')][0]
            domain_csvs = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                           if f.startswith('dm_') and f.endswith('.csv')]
            domains_map = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                           if f == 'domain_map.csv'][0]
            template_gdb = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                            if f.startswith('src') and f.endswith('.gdb')][0]
            arcpy.env.workspace = os.path.join(temp_dir, template_gdb)
            template_fcs = [os.path.join(template_gdb, fc) for fc in arcpy.ListFeatureClasses()]
            
            # Step 1: Create database
            arcpy.CreateFileGDB_management(gdb_dir, gdb_name, "10.0")
            arcpy.env.workspace = gdb_path

            # Step 2: Add domains           
            # All domain source tables must have 'code' and 'description' fields
            for domain_table in domain_csvs:
                # Drop the dir_name and extension
                domain_name = os.path.splitext(os.path.split(domain_table)[1])[0]
                
                arcpy.TableToDomain_management(in_table=domain_table,
                                               code_field='code',
                                               description_field='description',
                                               in_workspace=gdb_path,
                                               domain_name=domain_name)

            # 2a: Create the ESRI domains
            check_and_create_domains(gdb_path)
            
            # Step 3: Create feature classes
            for fc_template in template_fcs:
                fc_name = os.path.split(fc_template)[1]
                geo_type = arcpy.Describe(fc_template).shapeType
                arcpy.CreateFeatureclass_management(out_path=gdb_path,
                                                    out_name=fc_name,
                                                    geometry_type=geo_type,
                                                    spatial_reference=spatial_ref,
                                                    template=fc_template)
                
                # 3a: Add the ESRI fields to point(s) fcs only
                if geo_type == 'Point':
                    add_gnss_fields(fc_name)

                # 3b: Add Global ID
                arcpy.AddGlobalIDs_management(fc_name)
                
                # 3c: Enable attachments
                arcpy.EnableAttachments_management(fc_name)

            # Step 4: Assign domains
            # Table : {Field name: domain}
            with open(domains_map, 'r') as f:
                csv_reader = csv.reader(f)
                # Skip the header
                csv_reader.next()
                domain_assignments = [row for row in csv_reader]

            for table, field, domain in domain_assignments:
                arcpy.AssignDomainToField_management(table, field, domain)

        except:
            arcpy.AddMessage(traceback.format_exc())
            
        finally:
            end_time = datetime.datetime.now()
            arcpy.AddMessage("End Time: {}".format(end_time))
            arcpy.AddMessage("Time Elapsed: {}".format(end_time - start_time))
            utilities.blast_my_cache()
            
        return
