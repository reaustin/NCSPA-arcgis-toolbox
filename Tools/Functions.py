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



# Set information about a vector layer 
def set_layer_data(layer):
	_layer_description = arcpy.Describe(layer)
	_layer_data = {
		'lyr': layer,
		'name' : _layer_description.nameString,
		'path': os.path.join(_layer_description.path,_layer_description.nameString),
		'feature_class': _layer_description.featureClass,
        'df': table_to_data_frame(layer)
	}
	return(_layer_data)



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


# craete a new field callled zone (which is the ObjectId) to calculate statistics and stay organized
def create_zone_field(layer, zone_fieldname):
    _zone_oid_fieldname = arcpy.Describe(layer).OIDFieldName
    tweet('Creating Zone field in layer..{0}'.format(zone_fieldname), ap=arcpy) 
    arcpy.AddField_management(layer, zone_fieldname, 'LONG')
    arcpy.CalculateField_management(layer, zone_fieldname, "!{0}!".format(_zone_oid_fieldname), "PYTHON3")



# calculate the zonal areas based on the classifed raster
#  - use Value in the classfied raster to tabulate areas - leater rejoin with Class names if RAT exsists
def tabulate_area(zone_layer, zone_field, class_raster, out_stat_file):
    tweet("Msg: Tabulating zonal areas from classifed raster...\n   {0}".format(out_stat_file), ap=arcpy)
    arcpy.sa.TabulateArea(zone_layer, zone_field, class_raster, 'Value', out_stat_file)
    return(out_stat_file)



# calculate the zonal statistics from the elevation dataset
def zonal_statistics(zone_layer, zone_field, dem_raster, out_stat_file):
    tweet("Msg: Calculting zonal statistics from raster...\n   {0}".format(out_stat_file), ap=arcpy)
    arcpy.sa.ZonalStatisticsAsTable(zone_layer, zone_field, dem_raster, out_stat_file, "DATA", "ALL")
    return(out_stat_file)



# take the class names in the classifed RAT and rename the columns using those class names 
def map_values_to_classnames(in_table, class_raster_df):
    if('class_name' in class_raster_df):
        new_columns = []
        for index, row in class_raster_df.iterrows():
            _colname = 'VALUE_' + str(row['value'])
            _new_colname = row['class_name'].replace(' ','_')
            arcpy.AlterField_management(in_table, _colname, _new_colname, _new_colname)

            exp = 'round(!{0}!,1)'.format(_new_colname)                                # round(!veg!,1)
            arcpy.CalculateField_management(in_table, _new_colname, exp, "PYTHON3")
            new_columns.append(_new_colname)

    return(new_columns)


# calculate the percent vegetaion from the classes in the classifed raster
def calculate_percent_vegetation(in_table, classified_columns, search_names=['veg', 'soy']):
    _numerator, _sum_exp = '', ''
    for class_name in classified_columns:
        _sum_exp += "!{0}! + ".format(class_name)                                    # !soil! + !shadow! + !veg!
        if(class_name in search_names):
            _numerator = class_name
     
    if(_numerator is not None):
        _sum_exp = _sum_exp[:-2]
        arcpy.AddField_management(in_table, 'Per_' + _numerator, 'LONG')
        _exp = "(!{0}! / ({1})) * 100".format(_numerator, _sum_exp)                                   # (!veg! / (!soil! + !veg! + !shadow!)) * 100
        arcpy.CalculateField_management(in_table, 'Per_' + _numerator, _exp, "PYTHON3") 


