from tkinter import S
import Tools.Functions
import Tools.Functions as f

import os, sys
import pandas as pd
import arcpy

from importlib import reload
reload(Tools.Functions)



def create_zones(out_zone_filepath, field_boundary, size_x, size_y ):
    f.tweet("Msg: Creating Zones...", ap=arcpy)
    _field_ly_extent = arcpy.Describe(field_boundary).extent

    _ll_corner = str(_field_ly_extent.XMin) + ' ' + str(_field_ly_extent.YMin)
    _y_axis_coord = str(_field_ly_extent.XMin) + ' ' + str(_field_ly_extent.YMax)           # determines rotation angle
    f.tweet(_ll_corner, ap=arcpy)
    
    out_zone_filepath_temp = out_zone_filepath + '_temp'
    _out_zone_layer = arcpy.CreateFishnet_management(out_zone_filepath_temp, _ll_corner, _y_axis_coord, size_x, size_y, '#', '#', labels='NO_LABELS', template=field_boundary, geometry_type='POLYGON')
    _out_zone_layer_clip = arcpy.Clip_analysis(_out_zone_layer, field_boundary, out_zone_filepath)

    arcpy.Delete_management(out_zone_filepath_temp)
    return(_out_zone_layer_clip[0])


def summerize_yield(yield_layer, yield_field, zone_layer, zone_field):
    f.tweet("Msg: Summerizing Yield Data...", ap=arcpy)
    _out_summary_filepath = os.path.join(arcpy.mp.ArcGISProject("CURRENT").defaultGeodatabase, 'yld_summary_temp')

    # create a list to set the statistics to calculate
    _stats = ['SUM','MEAN','MIN','MAX','STDDEV']
        
    _stat_list = []
    for s in _stats:
        _row = [yield_field.value, s] 
        _stat_list.append(_row)

    # summerize the yield data within the zones
    _out_summary_layer = arcpy.SummarizeWithin_analysis(zone_layer, yield_layer, _out_summary_filepath, keep_all_polygons='KEEP_ALL', sum_fields=_stat_list)  

    rename_stat_fields(_out_summary_layer, yield_field.value, 'yld')
        
    #arcpy.Delete_management(_out_summary_layer)
    return(_out_summary_layer[0])


# reanme the fields from the original field name (yield field) to a shorter, clean '<stat>_yld' 
def rename_stat_fields(in_layer, field_name, new_postfix):
    f.tweet("Msg: Renaming fields for clarity...", ap=arcpy)
    field_list = arcpy.ListFields(in_layer)
    for field in field_list:
        if(field_name.lower() in field.name.lower()):
            _new_field_name = field.name.replace(field_name.lower(), new_postfix)
            _new_field_alais = _new_field_name.replace('_',' ')
            arcpy.AlterField_management(in_layer, field.name, _new_field_name, _new_field_alais)



# calculate the zonal statistics from the classifed raster
def summerize_raster(zone_layer, zone_field, class_raster, out_stat_file):
    f.tweet("Msg: Calculting zonal statistics from classfied raster...", ap=arcpy)
    #arcpy.sa.ZonalStatisticsAsTable(zone_layer, zone_field, class_raster, out_stat_file, "DATA", "ALL")
    arcpy.sa.TabulateArea(zone_layer, zone_field, class_raster, 'Value', out_stat_file)
    return(out_stat_file)


# craete a new field callled zone (which is the ObjectId) to calculate statistics and stay organized
def create_zone_field(zone_layer, zone_fieldname):
    f.tweet('Creating Zone field in new zone layer..{0}'.format(zone_fieldname), ap=arcpy) 
    arcpy.AddField_management(zone_layer, zone_fieldname, 'LONG')
    arcpy.CalculateField_management(zone_layer, zone_fieldname, '!OBJECTID!', "PYTHON3")   	


def map_values_to_classnames(in_table, map_df):
    if('class_name' in map_df):
        for index, row in map_df.iterrows():
            _colnamne = 'VALUE_' + str(row['value'])
            _new_colnamne = row['class_name'].replace(' ','_')
            arcpy.AlterField_management(in_table, _colnamne, _new_colnamne, _new_colnamne)
    return(f.table_to_data_frame(in_table))


# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    ZONE_LAYER_PREFIX = "Zones"
    ZONE_FIELD = 'Zone'

    # Get the parameters set in the Toolbox and in the current Map 
    #   - [field_boundary, yield_layer, yield_field, cell_x, cell_y, class_raster]
    _toolparam = f.get_tool_param()
    _mapparam = f.set_arcmap_param()  

    # set the output coordinate sysyem to NC Satteplance feet
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(2264)
    
    # create the name for the output zone layer
    _zone_filename = ZONE_LAYER_PREFIX + '_' + str(_toolparam['cell_x']) + 'x' + str(_toolparam['cell_y'])
    _zone_filepath = os.path.join(_mapparam['gdb'], _zone_filename)

    # create the fishnet of cells (i.e. zones)
    _zone_layer = create_zones(_zone_filepath, _toolparam['field_boundary'], _toolparam['cell_x'], _toolparam['cell_y'])
    create_zone_field(_zone_layer, ZONE_FIELD)

    # summerize the yield data within the zones
    _zone_oid_fieldname = arcpy.Describe(_zone_layer).OIDFieldName
    _yield_summary_layer = summerize_yield(_toolparam['yield_layer'], _toolparam['yield_field'], _zone_layer, ZONE_FIELD)

    # get the data from the yield summary layer 
    _yieldstat_df = f.table_to_data_frame(_yield_summary_layer)

    
    # calculate the zonal statistics from the classifed raster - always use the 'Value' in the classifed raster - than layer merge with RAT
    _class_raster_data = f.set_raster_data(_toolparam['class_raster'])
    _classstat_file = os.path.join(_mapparam['scratch'], _class_raster_data['name_base'] + "_zone_stat")
    _classstat_table = summerize_raster(_zone_layer, ZONE_FIELD,
                                         _toolparam['class_raster'], _classstat_file)
    
    if(_class_raster_data['has_vat']):
        _classstat_df = map_values_to_classnames(_classstat_table, _class_raster_data['df'])
    else:
        _classstat_df = f.table_to_data_frame(_classstat_table)    
    _classstat_df = pd.merge(_classstat_df, _yieldstat_df, on=ZONE_FIELD.lower())            

    # clean up some columns
    f.drop_columns(_classstat_df, drop_columns=['shape', 'shape_length'])
    
    # Save the zonal statistics to a table
    _out_zonestat_filepath = os.path.join(_mapparam['root'], "zone_stat.csv")
    f.tweet("MSG: Saving Zonal Statistics\n  -> {0}".format(_out_zonestat_filepath), ap=arcpy)
    _classstat_df.to_csv(_out_zonestat_filepath, index=False)


    # join the results back into the zone layer
    arcpy.JoinField_management(_yield_summary_layer, ZONE_FIELD, _classstat_table, ZONE_FIELD)

    _mapparam['maps'].addDataFromPath(_yield_summary_layer)

    # do some hosuecleaning 
    #arcpy.Delete_management(_out_summary_layer)

