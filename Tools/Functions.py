import os, sys
import pandas as pd
import arcpy


# Send a message to the console or ArcGIS Messgae box
def tweet(msg, ap=None):
	if(ap is not None):
		ap.AddMessage(msg)
	print(msg)

# Get the tools parameters [plot_lyr, img_list, output_folder, buffer_distance]
def get_tool_param():
    param = {}
    for p in arcpy.GetParameterInfo():
        param[p.name] = p.value
    return(param)


# Set/Get ArcGIS properties
def set_arcmap_param():
    _prj = arcpy.mp.ArcGISProject("CURRENT")
    param = {
        'project': _prj,
        'maps':  _prj.listMaps()[0],
        'gdb':  _prj.defaultGeodatabase,
        'root':  os.path.dirname(_prj.filePath),
        #'scratch': "C:/temp/scratch/"
        'scratch':  arcpy.env.scratchGDB
    }
    arcpy.env.overwriteOutput = True
    return(param)



# Set information about the classified raster layer 
def set_raster_data(raster): 
    _raster_description = arcpy.Describe(raster)
    _raster_data = {
        'lyr': raster,
        'raster': arcpy.Raster(_raster_description.nameString), 
        'name' : arcpy.Raster(_raster_description.nameString).name, 
        'name_base': os.path.splitext(arcpy.Raster(_raster_description.nameString).name)[0],
        'path': os.path.join(_raster_description.path,_raster_description.nameString),
        'num_bands': _raster_description.bandCount,
        'has_vat': arcpy.Raster(_raster_description.nameString).hasRAT
    }
    if(_raster_data['has_vat']):
        _raster_data['df'] = table_to_data_frame(_raster_data['path'])
    return(_raster_data) 



### convert a table into a pandas dataframe
def table_to_data_frame(in_table, input_fields=None, where_clause=None):
    OIDFieldName = arcpy.Describe(in_table).OIDFieldName
    if input_fields:
        final_fields = [OIDFieldName] + input_fields
    else:
        final_fields = [field.name for field in arcpy.ListFields(in_table)]
    data = [row for row in arcpy.da.SearchCursor(in_table, final_fields, where_clause=where_clause)]
    fc_dataframe = pd.DataFrame(data, columns=final_fields)
    fc_dataframe = fc_dataframe.set_index(OIDFieldName, drop=True)
    return(fc_dataframe.rename(columns=str.lower))


def deleteGeodatabaseTables(GDB, table_list=[]):
	tweet("MSG: Deleting Temporary Tables...", ap=arcpy)
	arcpy.env.workspace = GDB
	for t in arcpy.ListTables():
		if(t in table_list):
			arcpy.Delete_management(t)



# clean up a data frame by removing certain columns 
def drop_columns(df, drop_columns=[], sort_by=None):
	df.drop(columns=drop_columns, axis=1, errors='ignore', inplace=True)
	if(sort_by is not None):
		df.sort_values(by=sort_by, inplace=True)



def rename_stat_columns(in_table, rename_fields=[], prefix=''):
    for fld in rename_fields:
        _new_field_name = prefix + fld 
        arcpy.AlterField_management(in_table, fld, _new_field_name, _new_field_name)
