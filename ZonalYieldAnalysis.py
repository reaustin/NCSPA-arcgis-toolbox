from tkinter import S
import Tools.Functions
import Tools.Functions as f

import os, sys
import math
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


def rename_stat_fields(in_layer, field_name, new_postfix):
    f.tweet("Msg: Renaming fields for clarity...", ap=arcpy)
    field_list = arcpy.ListFields(in_layer)
    for field in field_list:
        if(field_name.lower() in field.name.lower()):
            _new_field_name = field.name.replace(field_name.lower(), new_postfix)
            _new_field_alais = _new_field_name.replace('_',' ')
            arcpy.AlterField_management(in_layer, field.name, _new_field_name, _new_field_alais)


# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    ZONE_LAYER_PREFIX = "Zones"

    # Get the parameters set in the Toolbox and in the current Map 
    #   - [field_boundary, yield_layer, yield_field, cell_x, cell_y, class_raster]
    _toolparam = f.get_tool_param()
    _mapparam = f.set_arcmap_param()  

    # set the output coordinate sysyem to NC Satteplance feet
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(2264)
    
    
    # create the name for the output zone layer
    _out_zone_filename = ZONE_LAYER_PREFIX + '_' + str(_toolparam['cell_x']) + 'x' + str(_toolparam['cell_y'])
    _out_zone_filepath = os.path.join(_mapparam['gdb'], _out_zone_filename)

    # create the fishnet of cells (i.e. zones)
    _out_zone_layer = create_zones(_out_zone_filepath, _toolparam['field_boundary'], _toolparam['cell_x'], _toolparam['cell_y'])


    # summerize the yield data within the zones
    _zone_oid_fieldname = arcpy.Describe(_out_zone_layer).OIDFieldName
    _out_yield_summary = summerize_yield(_toolparam['yield_layer'], _toolparam['yield_field'], _out_zone_layer, _zone_oid_fieldname)


    # get the data frokm teh dataframe
    _out_yieldstat_df = f.table_to_data_frame(_out_yield_summary)

    #f.tweet(_out_yieldstat_df, ap=arcpy)

    
    _mapparam['maps'].addDataFromPath(_out_yield_summary)



    # do some hosuecleaning 
    #arcpy.Delete_management(_out_summary_layer)

